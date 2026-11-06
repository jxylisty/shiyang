# -*- coding: utf-8 -*-
"""
补齐 10 味旧药材的 HERB 成分归属（v3 未覆盖、v1 归属错乱）

背景（2026-11-06 实测）：
- `rel_herb_compound_v3` 只覆盖旧 34 味里的 24 味；剩下 10 味（天冬/玉竹/百合/
  胖大海/薏苡仁/蜂蜜/酸枣仁/麦冬/麦芽/黄芪）没有任何成分归属。
- `rel_herb_compound`(v1) 对这 10 味有数据，但与自建 `herb_compound_content`
  （有含量的策展数据）重叠为 0/10 —— 与旧表整体错乱特征一致，判定不可采纳。
  数据真实铁律：宁可空链，不可污染。
- 这 10 味在扩容时已补标 HERB ID（herb.source），但没拉成分。

数据来源（全部真实，无一条编造）：
- 药材→成分：`detail_api(label=Herb)` 的 `herb_ingredient`
- 成分→靶点：`detail_api(label=Ingredient)` 的 `ingredient_target`（**只对 top N
  成分逐个拉**，不做「药材级靶点 × 全部成分」的交叉积——那是伪造关联）
- 药材级靶点统计（P/FDR）：`herb_target`，存入独立表 `rel_herb_target_herb`

落位（不碰 v1/v2/v3 历史表）：
- 新表 `rel_herb_compound_herb`：本轮补的药材→成分归属，source 记 HERB ID
- 新表 `rel_herb_target_herb`：药材级靶点富集统计（P/FDR 如实保留）
- `compound` / `target` / `rel_compound_target(source_db='herb.ac.cn')`：与扩容批同口径
- 新成分预测列一律 NULL

用法：
    python -X utf8 scripts/import_herbs_legacy10.py            # 只看计划
    python -X utf8 scripts/import_herbs_legacy10.py --apply    # 采集并写库
    python -X utf8 scripts/import_herbs_legacy10.py --apply --top-ingredients 30
"""
import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "shiyang.db"
CACHE = ROOT / "data" / "cache" / "herb_ingest_legacy10.json"
HERB_API = "http://herb.ac.cn/chedi/api/"
BATCH = 20261106

TARGET_HERBS = ["天冬", "玉竹", "百合", "胖大海", "薏苡仁",
                "蜂蜜", "酸枣仁", "麦冬", "麦芽", "黄芪"]


def _parse_link_cell(cell):
    if isinstance(cell, dict):
        return cell.get("title", ""), cell.get("link", "")
    return str(cell), ""


def _post(payload: dict) -> dict:
    r = requests.post(HERB_API, json=payload, timeout=40)
    r.raise_for_status()
    return r.json()


def fetch_detail(herb_id: str) -> dict:
    return _post({"func_name": "detail_api", "key_id": herb_id,
                  "label": "Herb", "v": herb_id})


def fetch_ingredient(ing_id: str) -> dict:
    return _post({"func_name": "detail_api", "key_id": ing_id,
                  "label": "Ingredient", "v": ing_id})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="实际采集并写库")
    ap.add_argument("--top-ingredients", type=int, default=20,
                    help="每味药材取前 N 个成分逐个拉成分详情以取真实靶点（默认 20）")
    args = ap.parse_args()

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    plan = []
    for name in TARGET_HERBS:
        row = conn.execute("SELECT id, name, source FROM herb WHERE name=?", (name,)).fetchone()
        if not row:
            print(f"[skip] {name} 不在 herb 表")
            continue
        herb_id = next((t for t in (row["source"] or "").split() if t.startswith("HERB")), None)
        if not herb_id:
            print(f"[skip] {name} 无 HERB ID（source={row['source']}）")
            continue
        n_v3 = conn.execute("SELECT COUNT(*) FROM rel_herb_compound_v3 WHERE herb_id=?",
                            (row["id"],)).fetchone()[0]
        n_new = conn.execute("SELECT COUNT(*) FROM rel_herb_compound_herb WHERE herb_id=?",
                             (row["id"],)).fetchone()[0] \
            if _table_exists(conn, "rel_herb_compound_herb") else 0
        if n_v3 or n_new:
            print(f"[skip] {name} 已有归属（v3={n_v3} 本轮={n_new}）")
            continue
        plan.append((name, row["id"], herb_id))

    print(f"待补 {len(plan)} 味（每味取前 {args.top_ingredients} 个成分拉真实靶点）：")
    for name, hid_herb, herb_id in plan:
        print(f"  {name:<6} 库内 {hid_herb:<12} HERB {herb_id}")

    if not plan:
        conn.close()
        return 0
    if not args.apply:
        print("\n未加 --apply，未采集未写库。")
        conn.close()
        return 0

    # ---------- 采集（带缓存，重跑不打 API）----------
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    cache.setdefault("_herbs", {})
    cache.setdefault("_ingredients", {})
    for name, hid_herb, herb_id in plan:
        if herb_id in cache["_herbs"]:
            print(f"[cache] 药材 {name} ({herb_id})")
        else:
            print(f"[fetch] 药材 {name} ({herb_id}) ...", end=" ", flush=True)
            try:
                d = fetch_detail(herb_id)
                cache["_herbs"][herb_id] = d
                n_i = max(0, len(d.get("herb_ingredient") or []) - 1)
                n_t = max(0, len(d.get("herb_target") or []) - 1)
                print(f"成分 {n_i} / 药材级靶点 {n_t}")
            except Exception as e:
                print(f"失败：{e}")
            time.sleep(0.5)

        d = cache["_herbs"].get(herb_id)
        if not d:
            continue
        ing_rows = (d.get("herb_ingredient") or [])[1:][:args.top_ingredients]
        for row in ing_rows:
            ing_id, _ = _parse_link_cell(row[0])
            if not ing_id or ing_id in cache["_ingredients"]:
                continue
            try:
                cache["_ingredients"][ing_id] = fetch_ingredient(ing_id)
            except Exception as e:
                print(f"  [warn] 成分 {ing_id} 拉取失败：{e}")
            time.sleep(0.35)
        print(f"  成分详情缓存累计 {len(cache['_ingredients'])} 条")

    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    print(f"\n采集缓存 → {CACHE.relative_to(ROOT)}")

    # ---------- 建独立口径表（幂等）----------
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS rel_herb_compound_herb (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            herb_id TEXT NOT NULL,
            compound_id TEXT NOT NULL,
            source TEXT,
            added_batch INTEGER,
            UNIQUE(herb_id, compound_id)
        );
        CREATE INDEX IF NOT EXISTS idx_rhch_herb ON rel_herb_compound_herb(herb_id);
        CREATE INDEX IF NOT EXISTS idx_rhch_compound ON rel_herb_compound_herb(compound_id);
        CREATE TABLE IF NOT EXISTS rel_herb_target_herb (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            herb_id TEXT NOT NULL,
            target_gene TEXT NOT NULL,
            p_value REAL,
            fdr_bh REAL,
            source TEXT,
            added_batch INTEGER,
            UNIQUE(herb_id, target_gene)
        );
        CREATE INDEX IF NOT EXISTS idx_rht_herb ON rel_herb_target_herb(herb_id);
    """)
    conn.commit()

    # ---------- 写库 ----------
    n_rhc = n_comp = n_tgt = n_rct = 0
    for name, hid_herb, herb_id in plan:
        d = cache["_herbs"].get(herb_id)
        if not d:
            print(f"[miss] {name} 采集失败，跳过")
            continue
        ing_rows = (d.get("herb_ingredient") or [])[1:]
        tgt_rows = (d.get("herb_target") or [])[1:]
        src = f"herb.ac.cn {herb_id}"

        # 药材 → 成分（全部，真实）
        for row in ing_rows:
            comp_id, _ = _parse_link_cell(row[0])
            comp_name = row[1] if len(row) > 1 else None
            if not comp_id or not comp_name:
                continue
            n_comp += conn.execute(
                "INSERT OR IGNORE INTO compound(id,name) VALUES (?,?)",
                (comp_id, comp_name)).rowcount
            n_rhc += conn.execute(
                "INSERT OR IGNORE INTO rel_herb_compound_herb"
                "(herb_id,compound_id,source,added_batch) VALUES (?,?,?,?)",
                (hid_herb, comp_id, src, BATCH)).rowcount

        # 药材级靶点富集统计（P/FDR 如实保留）
        for row in tgt_rows:
            if len(row) < 2:
                continue
            gene = row[1]
            n_tgt += conn.execute(
                "INSERT OR IGNORE INTO target(gene,target_type,species) VALUES (?,?,?)",
                (gene, "未知(herb.ac.cn)", "未知(herb.ac.cn)")).rowcount
            try:
                p = float(row[2]) if len(row) > 2 and row[2] not in (None, "NA", "") else None
                fdr = float(row[3]) if len(row) > 3 and row[3] not in (None, "NA", "") else None
            except (TypeError, ValueError):
                p = fdr = None
            conn.execute(
                "INSERT OR IGNORE INTO rel_herb_target_herb"
                "(herb_id,target_gene,p_value,fdr_bh,source,added_batch) "
                "VALUES (?,?,?,?,?,?)", (hid_herb, gene, p, fdr, src, BATCH))

        # 成分 → 靶点（只取前 N 个成分的**真实** ingredient_target，不做交叉积）
        top_ids = [(_parse_link_cell(r[0])[0]) for r in ing_rows
                   if r and _parse_link_cell(r[0])[0]][:args.top_ingredients]
        ing_targets = 0
        for comp_id in top_ids:
            det = cache["_ingredients"].get(comp_id)
            if not det:
                continue
            irows = det.get("ingredient_target") or []
            if not irows:
                continue
            for trow in irows[1:]:
                if not isinstance(trow, (list, tuple)) or len(trow) < 2:
                    continue
                gene = trow[1]
                if not gene or not isinstance(gene, str):
                    continue
                conn.execute("INSERT OR IGNORE INTO target(gene,target_type,species) "
                             "VALUES (?,?,?)",
                             (gene, "未知(herb.ac.cn)", "未知(herb.ac.cn)"))
                # Database sources 列（如 'TCMSP:TAR00165'）如实记入 reference
                dbs = trow[2] if len(trow) > 2 and isinstance(trow[2], str) else "NA"
                n_rct += conn.execute(
                    "INSERT OR IGNORE INTO rel_compound_target"
                    "(compound_id,target_gene,activity_type,activity_value,"
                    "activity_unit,reference,source_db) VALUES (?,?,NULL,NULL,NULL,?,?)",
                    (comp_id, gene,
                     f"P=NA; FDR_BH=NA (ingredient-level association; {herb_id}; sources: {dbs})",
                     "herb.ac.cn")).rowcount
                ing_targets += 1
        print(f"[write] {name}: 成分 {len(ing_rows)} / 药材级靶点 {len(tgt_rows)} "
              f"/ 成分级靶点关联 {ing_targets}")

    # ---------- 校正计数 ----------
    _recount(conn)
    conn.commit()
    print(f"\n新增：compound {n_comp} / rel_herb_compound_herb {n_rhc} "
          f"/ target {n_tgt} / rel_compound_target {n_rct}")
    conn.close()
    print("完成。")
    return 0


def _table_exists(conn, name: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                        (name,)).fetchone() is not None


def _recount(conn):
    """按三口径重算 compound_count：v3（旧24味）+ v1（扩容71味）+ 本轮补的10味。"""
    has_rhch = _table_exists(conn, "rel_herb_compound_herb")
    extra = ("+ (SELECT COUNT(*) FROM rel_herb_compound_herb h2 WHERE h2.herb_id=herb.id)"
             if has_rhch else "")
    conn.execute(f"""UPDATE herb SET compound_count = (
        CASE WHEN herb.id LIKE 'ccTCM%'
             THEN (SELECT COUNT(*) FROM rel_herb_compound_v3 v WHERE v.herb_id=herb.id)
                  {extra}
             ELSE (SELECT COUNT(*) FROM rel_herb_compound v WHERE v.herb_id=herb.id)
        END)""")
    conn.execute("""UPDATE compound SET target_count =
        (SELECT COUNT(*) FROM rel_compound_target r WHERE r.compound_id=compound.id)""")


if __name__ == "__main__":
    sys.exit(main())
