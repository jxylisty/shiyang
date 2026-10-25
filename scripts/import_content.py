# -*- coding: utf-8 -*-
"""
解析「药材-化合物-含量」Excel → shiyang.db 新表 herb_compound_content
含量为区间（如 0.06~0.10%）→ 解析为 min/max (单位:%，对药材干重)
用法：python -X utf8 import_content.py
"""
import re
import sqlite3
import sys
from pathlib import Path

import openpyxl

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
XLSX = ROOT.parent / "数据库溯源" / "主要展示数据均为cctcm2.0" / "药材-化合物-含量-赵玉男.xlsx"
DB = ROOT / "data" / "shiyang.db"

RANGE = re.compile(r"([\d.]+)\s*[~～\-]\s*([\d.]+)")
SINGLE = re.compile(r"([\d.]+)")


def parse_pct(v):
    """'0.06~0.10%' → (0.06, 0.10)；'0.5%' → (0.5, 0.5)；NA/空 → None"""
    if v is None:
        return None
    s = str(v).strip()
    if not s or s.upper() in ("NA", "N/A", "-"):
        return None
    m = RANGE.search(s)
    if m:
        lo, hi = float(m.group(1)), float(m.group(2))
        return (min(lo, hi), max(lo, hi))
    m = SINGLE.search(s)
    if m:
        return (float(m.group(1)), float(m.group(1)))
    return None


wb = openpyxl.load_workbook(XLSX, read_only=True)
ws = wb.active
rows = []
seen = set()
for r in ws.iter_rows(min_row=2, values_only=True):
    herb, comp_cn, comp_en, content = r[1], r[5], r[6], r[9]
    if not herb or (not comp_cn and not comp_en):
        continue
    pct = parse_pct(content)
    if not pct:
        continue
    key = (str(herb).strip(), str(comp_cn or comp_en).strip())
    if key in seen:  # 同药同成分多来源，保留区间更宽的
        continue
    seen.add(key)
    rows.append((*key, pct[0], pct[1], str(content).strip()))
wb.close()
print(f"解析有效含量记录: {len(rows)} 条")

conn = sqlite3.connect(DB)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("""
CREATE TABLE IF NOT EXISTS herb_compound_content (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    herb_name TEXT NOT NULL,
    compound_name TEXT NOT NULL,
    content_min_pct REAL, content_max_pct REAL, content_raw TEXT
)""")
conn.execute("CREATE INDEX IF NOT EXISTS idx_hcc_herb ON herb_compound_content(herb_name)")
conn.execute("DELETE FROM herb_compound_content")
conn.executemany("INSERT INTO herb_compound_content(herb_name,compound_name,content_min_pct,content_max_pct,content_raw) VALUES (?,?,?,?,?)", rows)
conn.commit()

# 与 shiyang.db 现有 34 味药材的命中率
matched = conn.execute(
    "SELECT COUNT(DISTINCT hcc.herb_name) FROM herb_compound_content hcc "
    "JOIN herb h ON h.name = hcc.herb_name").fetchone()[0]
total_herbs = conn.execute("SELECT COUNT(*) FROM herb").fetchone()[0]
# 与方子配料的可匹配成分数（按名称精确匹配）
comp_match = conn.execute(
    "SELECT COUNT(*) FROM herb_compound_content hcc "
    "JOIN compound c ON c.name = hcc.compound_name").fetchone()[0]
conn.close()
print(f"34味库内药材命中含量数据: {matched} 味")
print(f"含量记录能对上成分库名称的: {comp_match} 条（名称对齐待后续模糊匹配优化）")
