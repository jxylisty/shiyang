# -*- coding: utf-8 -*-
"""
从修复后的大创库同步数据到 shiyang.db

背景：大创库 asthma_v2.db 于 2026-10-26 完成数据质量修复：
  - 药材-成分归属 100% 重建（1,504 条全部来自溯源 Excel）
  - mw/logP 由 RDKit 重算，smile_short 规范化
  - source_db / network_centrality 等编造字段已清空
  - 三维机制评分用真实 Enrichr GSEA 重算（radar_*_gsea）
  - 入血概率由重训模型（ROC-AUC 0.903）重算

shiyang 此前用的是修复前的旧数据，本脚本同步更新：
  1. compound: prob_cctcm / prob_herb / mw / logp / radar_*_gsea
  2. rel_herb_compound_v2: 用大创库重建后的归属（覆盖我此前从 Excel 重建的 63 条）
  3. rel_compound_target: 刷新 source_db 为 NULL（原为随机标签）
  4. target: 补充 target_type/species（供人类蛋白过滤）

用法：python -X utf8 scripts/sync_from_repaired_db.py [--apply]
"""
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "shiyang.db"
SRC = ROOT.parent / "my-asthma-system" / "asthma-core" / "data" / "asthma_v2.db"
APPLY = "--apply" in sys.argv


def main():
    if not SRC.exists():
        sys.exit(f"大创库不存在: {SRC}")
    if not DB.exists():
        sys.exit(f"shiyang 库不存在: {DB}")

    if APPLY:
        backup = DB.with_name(f"shiyang.db.bak-sync-{datetime.now():%Y%m%d%H%M%S}")
        shutil.copy2(DB, backup)
        print(f"已备份: {backup.name}\n")

    src = sqlite3.connect(f"file:{SRC.as_posix()}?mode=ro", uri=True)
    src.row_factory = sqlite3.Row
    dst = sqlite3.connect(DB)
    dst.row_factory = sqlite3.Row

    # ---- 1. compound 表同步 ----
    src_cols = {d[1] for d in src.execute("PRAGMA table_info(compound)")}
    dst_cols = {d[1] for d in dst.execute("PRAGMA table_info(compound)")}
    has_gsea = "radar_anti_inflammatory_gsea" in src_cols

    # shiyang 侧补齐 GSEA 列
    if has_gsea:
        for c in ("radar_anti_inflammatory_gsea", "radar_immune_regulation_gsea",
                  "radar_airway_repair_gsea"):
            if c not in dst_cols:
                dst.execute(f"ALTER TABLE compound ADD COLUMN {c} REAL")
                print(f"新增列 compound.{c}")

    s_comps = {r["id"]: dict(r) for r in src.execute(
        "SELECT id,name,prob_cctcm,prob_herb,mw,logp,"
        + ("radar_anti_inflammatory,radar_immune_regulation,radar_airway_repair,"
           "radar_anti_inflammatory_gsea,radar_immune_regulation_gsea,radar_airway_repair_gsea"
           if has_gsea else
           "radar_anti_inflammatory,radar_immune_regulation,radar_airway_repair")
        + " FROM compound")}

    updated = changed_prob = 0
    prob_deltas = []
    for cid, row in s_comps.items():
        old = dst.execute("SELECT prob_cctcm, mw, logp FROM compound WHERE id=?", (cid,)).fetchone()
        if not old:
            continue
        if old["prob_cctcm"] is not None and row["prob_cctcm"] is not None:
            prob_deltas.append(abs(old["prob_cctcm"] - row["prob_cctcm"]))
        fields = ["prob_cctcm", "prob_herb", "mw", "logp",
                  "radar_anti_inflammatory", "radar_immune_regulation", "radar_airway_repair"]
        vals = [row[f] for f in fields]
        if has_gsea:
            fields += ["radar_anti_inflammatory_gsea", "radar_immune_regulation_gsea",
                       "radar_airway_repair_gsea"]
            vals += [row["radar_anti_inflammatory_gsea"], row["radar_immune_regulation_gsea"],
                     row["radar_airway_repair_gsea"]]
        dst.execute(f"UPDATE compound SET {', '.join(f'{f}=?' for f in fields)} WHERE id=?",
                    (*vals, cid))
        updated += 1
        if old["prob_cctcm"] is not None and row["prob_cctcm"] is not None \
                and abs(old["prob_cctcm"] - row["prob_cctcm"]) > 0.2:
            changed_prob += 1

    if prob_deltas:
        import statistics
        print(f"compound 更新 {updated} 条；入血概率平均变化 "
              f"{statistics.mean(prob_deltas):.3f}，变化>0.2 的 {changed_prob} 个")

    # ---- 2. 归属关系：用大创库重建结果覆盖 ----
    dst.execute("DROP TABLE IF EXISTS rel_herb_compound_v3")
    dst.execute("""CREATE TABLE rel_herb_compound_v3 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        herb_id TEXT NOT NULL,
        compound_id TEXT NOT NULL,
        source TEXT DEFAULT 'asthma_v2.db 修复后归属',
        UNIQUE(herb_id, compound_id))""")
    links = src.execute("SELECT herb_id, compound_id FROM rel_herb_compound").fetchall()
    ins = 0
    for r in links:
        # 只保留 shiyang 库里存在的 herb/compound
        h = dst.execute("SELECT 1 FROM herb WHERE id=?", (r["herb_id"],)).fetchone()
        c = dst.execute("SELECT 1 FROM compound WHERE id=?", (r["compound_id"],)).fetchone()
        if h and c:
            dst.execute("INSERT OR IGNORE INTO rel_herb_compound_v3(herb_id,compound_id) VALUES (?,?)",
                        (r["herb_id"], r["compound_id"]))
            ins += 1
    print(f"归属关系 v3：{ins} 条（来自大创库修复后的 rel_herb_compound）")

    # ---- 3. 靶点关联：source_db 置 NULL（原为随机标签）----
    dst.execute("UPDATE rel_compound_target SET source_db=NULL WHERE source_db IS NOT NULL")
    print("rel_compound_target.source_db 已清空（原随机标签）")

    # ---- 4. target 表刷新 type/species ----
    tgt = {r["gene"]: dict(r) for r in src.execute("SELECT gene,target_type,species FROM target")}
    t_upd = 0
    for gene, row in tgt.items():
        cur = dst.execute("SELECT 1 FROM target WHERE gene=?", (gene,)).fetchone()
        if cur:
            dst.execute("UPDATE target SET target_type=?, species=? WHERE gene=?",
                        (row["target_type"], row["species"], gene))
            t_upd += 1
    print(f"target 表更新 {t_upd} 条 type/species")

    if APPLY:
        dst.commit()
        print("\n✅ 已提交")
    else:
        dst.rollback()
        print("\n（dry-run，未写入。加 --apply 执行）")

    # 校验摘要
    if APPLY:
        row = dst.execute("SELECT prob_cctcm FROM compound WHERE name='人参皂苷Rb1'").fetchone()
        if row:
            print(f"校验 人参皂苷Rb1 入血概率 = {row[0]:.4f}")
        n3 = dst.execute("SELECT COUNT(*) FROM rel_herb_compound_v3").fetchone()[0]
        n2 = dst.execute("SELECT COUNT(*) FROM rel_herb_compound_v2").fetchone()[0]
        print(f"归属条数：v2(Excel重建)={n2} → v3(大创修复后)={n3}")

    src.close()
    dst.close()


if __name__ == "__main__":
    main()
