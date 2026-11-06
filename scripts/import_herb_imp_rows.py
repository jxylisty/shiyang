# -*- coding: utf-8 -*-
"""
补齐 2 味 herbc 映射行的空缺（橘红/花椒，2026-11-06）

背景：`herb` 表里 `imp:橘红`、`imp:花椒` 是扩容时按「与别名共用条目」惯例落的
镜像行，当时只写了 source/reference_url，**没采集成因、性味归经全空**。结果在
药材图鉴里点开是空白页（ux-tester 验收 P2「4 味药材详情几乎空白」的其中 2 味）。

实测（2026-11-06）：HERB 里这两条数据完整——橘红 90 成分/21 靶点、
花椒 152 成分/188 靶点；SymMap 也有中文性味归经（橘红 辛,苦,温→肺,脾；
花椒 辛,温→脾,胃,肾）。所以属于「能拿到但没采」，不是数据缺口。

做法：
- 成分归属写入 `rel_herb_compound`（v1 扩容口径，与 import_herbs_20261105 一致）
- 药材级靶点富集统计写入 `rel_herb_target_herb`（P/FDR 如实保留）
- 性味/归经用 SymMap 中文值（优先）→ HERB 英文翻译兜底
- 功效优先用 HERB summary 的 Function 原文，缺失则用 Indication
- 幂等：关联按唯一键 INSERT OR IGNORE，字段只补空值不覆盖已有

用法：
    python -X utf8 scripts/import_herb_imp_rows.py
    python -X utf8 scripts/import_herb_imp_rows.py --apply
"""
import json
import sqlite3
import sys
import time
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "shiyang.db"
CACHE = ROOT / "data" / "cache" / "herb_ingest_imp_rows.json"
HERB_API = "http://herb.ac.cn/chedi/api/"
BATCH = 20261106
APPLY = "--apply" in sys.argv

TARGETS = ["橘红", "花椒"]


def _cell(v):
    """summary 行的文本列可能是 {link,title} dict 或 str"""
    if isinstance(v, dict):
        t = v.get("title")
        return t if isinstance(t, str) else None
    return v if isinstance(v, str) else None


def _parse_link(cell):
    if isinstance(cell, dict):
        return cell.get("title", "")
    return str(cell)


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    plan = []
    for name in TARGETS:
        r = conn.execute("SELECT id,name,source,compound_count FROM herb WHERE name=?",
                         (name,)).fetchone()
        if not r:
            print(f"[skip] {name} 不在 herb 表")
            continue
        herb_id = next((t for t in (r["source"] or "").split() if t.startswith("HERB")), None)
        if not herb_id:
            print(f"[skip] {name} 无 HERB ID")
            continue
        have = conn.execute("SELECT COUNT(*) FROM rel_herb_compound WHERE herb_id=?",
                            (r["id"],)).fetchone()[0]
        if have:
            print(f"[skip] {name} 已有 {have} 条归属")
            continue
        plan.append((name, r["id"], herb_id))

    print(f"待补 {len(plan)} 味：")
    for n, hid, hb in plan:
        print(f"  {n:<6} 库内 {hid:<12} HERB {hb}")
    if not plan:
        conn.close()
        return 0
    if not APPLY:
        print("\n未加 --apply，未采集未写库。")
        conn.close()
        return 0

    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    for name, hid, herb_id in plan:
        if herb_id in cache:
            print(f"[cache] {name}")
            continue
        print(f"[fetch] {name} ({herb_id}) ...", end=" ", flush=True)
        try:
            r = requests.post(HERB_API, json={
                "func_name": "detail_api", "key_id": herb_id,
                "label": "Herb", "v": herb_id}, timeout=40)
            r.raise_for_status()
            cache[herb_id] = r.json()
            d = cache[herb_id]
            print(f"成分 {max(0, len(d.get('herb_ingredient') or []) - 1)} / "
                  f"靶点 {max(0, len(d.get('herb_target') or []) - 1)}")
        except Exception as e:
            print(f"失败：{e}")
        time.sleep(0.6)
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    # SymMap 中文性味归经（优先）
    sm = {}
    smpath = ROOT / "data" / "symmap_smhb_v2.json"
    if smpath.exists():
        sm = json.loads(smpath.read_text(encoding="utf-8"))

    n_rhc = n_comp = n_tgt = n_rht = 0
    for name, hid, herb_id in plan:
        d = cache.get(herb_id)
        if not d:
            print(f"[miss] {name} 采集失败")
            continue
        src = f"herb.ac.cn {herb_id}"
        ing = (d.get("herb_ingredient") or [])[1:]
        tgt = (d.get("herb_target") or [])[1:]

        # 1) 成分归属
        for row in ing:
            cid = _parse_link(row[0])
            cname = row[1] if len(row) > 1 else None
            if not cid or not cname:
                continue
            n_comp += conn.execute(
                "INSERT OR IGNORE INTO compound(id,name) VALUES (?,?)",
                (cid, cname)).rowcount
            n_rhc += conn.execute(
                "INSERT OR IGNORE INTO rel_herb_compound(herb_id,compound_id) VALUES (?,?)",
                (hid, cid)).rowcount

        # 2) 药材级靶点富集（P/FDR 如实保留）
        for row in tgt:
            if len(row) < 2:
                continue
            gene = row[1]
            conn.execute("INSERT OR IGNORE INTO target(gene,target_type,species) VALUES (?,?,?)",
                         (gene, "未知(herb.ac.cn)", "未知(herb.ac.cn)"))
            try:
                p = float(row[2]) if len(row) > 2 and row[2] not in (None, "NA", "") else None
                fdr = float(row[3]) if len(row) > 3 and row[3] not in (None, "NA", "") else None
            except (TypeError, ValueError):
                p = fdr = None
            n_rht += conn.execute(
                "INSERT OR IGNORE INTO rel_herb_target_herb"
                "(herb_id,target_gene,p_value,fdr_bh,source,added_batch) VALUES (?,?,?,?,?,?)",
                (hid, gene, p, fdr, src, BATCH)).rowcount
            n_tgt += 1

        # 3) 性味/归经/功效（只补空值，不覆盖已有）
        sym = sm.get(name) or {}
        props_cn = sym.get("properties_cn")
        merid_cn = sym.get("meridians_cn")

        # 按表头名取值——不要用固定下标！
        # HERB 对不同药材返回的 summary 列集合不同（金银花 17 列，代代花只有 10 列，
        # 没有 Properties/Meridians/Function 列），按 row[5]/row[6]/row[8] 取会把
        # 「Therapeutic class（理气药）」当成性味、「TCMID 数字 ID」当成功效。
        summary = (d.get("summary") or [])
        cells = {}
        if len(summary) >= 2 and isinstance(summary[0], list) and isinstance(summary[1], list):
            cells = {str(h): v for h, v in zip(summary[0], summary[1])}
        herb_props = _cell(cells.get("Properties"))
        herb_merid = _cell(cells.get("Meridians"))
        func = _cell(cells.get("Function"))
        indic = _cell(cells.get("Indication"))

        # 性味拆成 nature + flavor 两列：SymMap 形如「辛,苦,温」，最后一个温性
        nature = flavor = None
        if props_cn:
            parts = [p.strip() for p in props_cn.replace("，", ",").split(",") if p.strip()]
            natures = [p for p in parts if p in ("寒", "微寒", "大寒", "凉", "平", "温", "微温", "热")]
            flavors = [p for p in parts if p not in natures]
            nature = natures[-1] if natures else None
            flavor = ",".join(flavors) if flavors else None

        cur = conn.execute("""
            UPDATE herb SET
              nature = COALESCE(NULLIF(nature,''), ?),
              flavor = COALESCE(NULLIF(flavor,''), ?),
              meridians = COALESCE(NULLIF(meridians,''), ?),
              functions = COALESCE(NULLIF(functions,''), ?)
            WHERE id=?""",
            (nature, flavor, merid_cn or herb_merid,
             func or indic, hid))
        print(f"[write] {name}: 成分 {len(ing)} / 靶点 {len(tgt)} / "
              f"性味 {nature}/{flavor} 归经 {merid_cn or herb_merid} (更新 {cur.rowcount} 行)")

    # 计数归一
    conn.execute("""UPDATE herb SET compound_count =
        (SELECT COUNT(*) FROM rel_herb_compound v WHERE v.herb_id=herb.id)
        WHERE herb.id LIKE 'imp:%'""")
    conn.execute("""UPDATE compound SET target_count =
        (SELECT COUNT(*) FROM rel_compound_target r WHERE r.compound_id=compound.id)""")
    conn.commit()
    print(f"\n新增：compound {n_comp} / rel_herb_compound {n_rhc} / "
          f"rel_herb_target_herb {n_rht}")
    conn.close()
    print("完成。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
