# -*- coding: utf-8 -*-
"""
重建 herb → compound 归属关系（修复源库系统性错乱）

背景：my-asthma-system/asthma_v2.db 的 rel_herb_compound 表存在系统性错乱——
      薄荷里挂人参皂苷F2、菊花里挂胆酸、巴戟天里挂知母皂苷AIII，抽查 5/5 全错。
      原始数据 数据库溯源/主要展示数据均为cctcm2.0/药材-化合物-含量-赵玉男.xlsx
      中「中药材 → 单体成分中文名」归属正确（薄荷→薄荷醇/胡薄荷酮，菊花→芹菜素）。

做法：以原始 Excel 为唯一真源，重建 rel_herb_compound_v2，不改动旧表（保留对照）。
      名称匹配：精确 → 去括号别名 → 去空格/全半角归一。
输出：shiyang.db 新增 rel_herb_compound_v2 表 + 修复报告 docs/归属重建报告.md
用法：python -X utf8 scripts/rebuild_herb_compound.py
"""
import re
import sqlite3
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import openpyxl

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "shiyang.db"
XLSX = ROOT.parent / "数据库溯源" / "主要展示数据均为cctcm2.0" / "药材-化合物-含量-赵玉男.xlsx"


def norm(s: str) -> str:
    """名称归一：全角→半角、去所有空白、小写。"""
    s = unicodedata.normalize("NFKC", str(s))
    return re.sub(r"\s+", "", s).lower()


def strip_paren(s: str) -> str:
    """去掉中文/英文括号及其内容，用于「红车轴草苷（三叶豆紫檀苷）」这类别名匹配。"""
    s = re.sub(r"[（(].*?[)）]", "", s)
    return s.strip()


def main():
    if not XLSX.exists():
        sys.exit(f"原始数据不存在: {XLSX}")

    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    wb.close()

    # Excel: 药材名 → {成分名}
    excel_map = defaultdict(set)
    for r in rows:
        herb, comp = r[1], r[5]
        if herb and comp:
            excel_map[str(herb).strip()].add(str(comp).strip())
    print(f"Excel 读入 {len(rows)} 行，{len(excel_map)} 味药材")

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    db_herbs = {r["name"]: r["id"] for r in conn.execute("SELECT id,name FROM herb")}
    db_comps = {r["name"]: r["id"] for r in conn.execute("SELECT id,name FROM compound")}

    # 建归一化索引（含去括号别名），提高匹配率
    excel_norm = {}          # norm_name -> 原始名
    for herb, comps in excel_map.items():
        for c in comps:
            excel_norm[norm(c)] = c
            sp = strip_paren(c)
            if sp:
                excel_norm.setdefault(norm(sp), c)
    db_comp_norm = {norm(n): (n, i) for n, i in db_comps.items()}
    for n, i in db_comps.items():
        sp = strip_paren(n)
        if sp:
            db_comp_norm.setdefault(norm(sp), (n, i))

    conn.execute("DROP TABLE IF EXISTS rel_herb_compound_v2")
    conn.execute("""CREATE TABLE rel_herb_compound_v2 (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        herb_id TEXT NOT NULL REFERENCES herb(id),
        compound_id TEXT NOT NULL REFERENCES compound(id),
        source TEXT DEFAULT '药材-化合物-含量-赵玉男.xlsx',
        UNIQUE(herb_id, compound_id))""")

    stats = {"herb_hit": 0, "herb_miss": [], "links": 0, "comp_miss": defaultdict(set)}
    for herb_name, herb_id in db_herbs.items():
        comps = excel_map.get(herb_name)
        if not comps:
            # 尝试归一化匹配药材名
            hit = next((v for k, v in excel_map.items() if norm(k) == norm(herb_name)), None)
            comps = hit
        if not comps:
            stats["herb_miss"].append(herb_name)
            continue
        stats["herb_hit"] += 1
        for cname in comps:
            target = db_comp_norm.get(norm(cname)) or db_comp_norm.get(norm(strip_paren(cname)))
            if not target:
                stats["comp_miss"][herb_name].add(cname)
                continue
            conn.execute(
                "INSERT OR IGNORE INTO rel_herb_compound_v2(herb_id,compound_id) VALUES (?,?)",
                (herb_id, target[1]))
            stats["links"] += 1

    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM rel_herb_compound_v2").fetchone()[0]
    old_total = conn.execute("SELECT COUNT(*) FROM rel_herb_compound").fetchone()[0]

    print(f"\n重建完成：{total} 条关联（旧表 {old_total} 条）")
    print(f"药材命中 {stats['herb_hit']}/{len(db_herbs)}")
    if stats["herb_miss"]:
        print(f"未命中药材（Excel 无此药材）: {stats['herb_miss']}")
    miss_total = sum(len(v) for v in stats["comp_miss"].values())
    print(f"未匹配成分名 {miss_total} 个（Excel 有但 DB 无此化合物）")
    if miss_total:
        sample = list(stats["comp_miss"].items())[:5]
        for h, cs in sample:
            print(f"  {h}: {list(cs)[:3]}")

    # 抽查验证
    print("\n=== 重建后抽查 ===")
    for h in ["薄荷", "菊花", "金银花", "甘草", "枸杞子"]:
        rows2 = conn.execute(
            "SELECT c.name FROM rel_herb_compound_v2 r JOIN compound c ON c.id=r.compound_id "
            "JOIN herb h ON h.id=r.herb_id WHERE h.name=? LIMIT 6", (h,)).fetchall()
        print(f"  {h}: {[r['name'] for r in rows2]}")

    conn.close()


if __name__ == "__main__":
    main()
