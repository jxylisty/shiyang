# -*- coding: utf-8 -*-
"""
数据一致性自检 + 冗余计数字段修复

检查项：
  1. rel_herb_compound_v2 与 rel_herb_compound_v3 内容是否一致（应一致，v3 为准）
  2. herb.compound_count 与 rel_herb_compound_v3 实际关系数是否一致（--apply 时以 v3 重算修复）
  3. compound.target_count 与 rel_compound_target 实际关系数是否一致（--apply 时重算修复）
  4. 旧错乱表 rel_herb_compound 残留提示（代码已禁用，留待下次重建删除）

用法：
    python -X utf8 scripts/check_consistency.py            # 只检查
    python -X utf8 scripts/check_consistency.py --apply    # 检查并修复计数
退出码：全部一致为 0，有不一致为 1（可挂到提交前自检）
"""
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "shiyang.db"
APPLY = "--apply" in sys.argv

conn = sqlite3.connect(DB)
problems = 0

# 1. v2 vs v3
v2 = set(conn.execute("SELECT herb_id, compound_id FROM rel_herb_compound_v2"))
v3 = set(conn.execute("SELECT herb_id, compound_id FROM rel_herb_compound_v3"))
if v2 == v3:
    print(f"[ok] v2 与 v3 内容一致（{len(v3)} 条）")
else:
    problems += 1
    print(f"[不一致] v2={len(v2)} 条, v3={len(v3)} 条, 差集 {len(v2 ^ v3)} 条")

# 2. herb.compound_count
bad_h = conn.execute("""
    SELECT h.id, h.name, h.compound_count,
           (SELECT COUNT(*) FROM rel_herb_compound_v3 v WHERE v.herb_id=h.id) AS actual
    FROM herb h
    WHERE COALESCE(h.compound_count,0) != actual""").fetchall()
if bad_h:
    problems += 1
    print(f"[不一致] herb.compound_count {len(bad_h)} 行过期：")
    for hid, name, old, new in bad_h:
        print(f"    {name}: {old} -> {new}")
    if APPLY:
        conn.execute("""UPDATE herb SET compound_count =
            (SELECT COUNT(*) FROM rel_herb_compound_v3 v WHERE v.herb_id=herb.id)""")
        conn.commit()
        print("    已按 v3 重算修复")
else:
    print("[ok] herb.compound_count 与 v3 一致")

# 3. compound.target_count
bad_c = conn.execute("""
    SELECT c.id, c.name, c.target_count,
           (SELECT COUNT(*) FROM rel_compound_target r WHERE r.compound_id=c.id) AS actual
    FROM compound c
    WHERE COALESCE(c.target_count,0) != actual""").fetchall()
if bad_c:
    problems += 1
    print(f"[不一致] compound.target_count {len(bad_c)} 行过期：")
    for cid, name, old, new in bad_c:
        print(f"    {name}: {old} -> {new}")
    if APPLY:
        conn.execute("""UPDATE compound SET target_count =
            (SELECT COUNT(*) FROM rel_compound_target r WHERE r.compound_id=compound.id)""")
        conn.commit()
        print("    已按 rel_compound_target 重算修复")
else:
    print("[ok] compound.target_count 与 rel_compound_target 一致")

# 4. 旧错乱表残留
n_legacy = conn.execute("SELECT COUNT(*) FROM rel_herb_compound").fetchone()[0]
print(f"[提示] 旧错乱表 rel_herb_compound 仍在库中（{n_legacy} 行），代码已禁用，下次重建时删除")

conn.close()
print(f"\n{'发现问题并已修复' if APPLY and problems else ('发现问题 ' + str(problems) + ' 项（未 --apply）' if problems else '全部一致')}")
sys.exit(1 if problems and not APPLY else 0)
