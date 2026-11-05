# -*- coding: utf-8 -*-
"""
数据一致性自检 + 冗余计数字段修复

检查项：
  1. rel_herb_compound_v2 与 rel_herb_compound_v3 内容是否一致（应一致，v3 为准）
     —— 该口径仅覆盖大创 73 方的旧 34 味药材
  2. herb.compound_count 与实际关联数是否一致（--apply 时重算修复）
     —— 2026-11-05 扩容后口径：新增药材（herb.id='HERB%'/'imp:%'）按
        rel_herb_compound（v1，HERB 全量成分）计；旧 34 味仍按 v3 计
        （与 docs/数据扩容方案_2026-11-05.md §2 的 v1/v3 双口径决定一致）
  3. compound.target_count 与 rel_compound_target 实际关系数是否一致（--apply 时重算修复）
  4. rel_herb_compound（v1）现状提示：2026-11-05 起为「旧 34 味 v3 快照 + 扩容新增药材」
     的混合表，不再是待删除的错乱表；修复旧口径时只更新 ccTCM 前缀行的计数，不触碰新数据

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

# 1. v2 vs v3（旧 34 味口径，两者应一致）
v2 = set(conn.execute("SELECT herb_id, compound_id FROM rel_herb_compound_v2"))
v3 = set(conn.execute("SELECT herb_id, compound_id FROM rel_herb_compound_v3"))
if v2 == v3:
    print(f"[ok] v2 与 v3 内容一致（{len(v3)} 条）")
else:
    problems += 1
    print(f"[不一致] v2={len(v2)} 条, v3={len(v3)} 条, 差集 {len(v2 ^ v3)} 条")

# 2. herb.compound_count（双口径：ccTCM 旧药按 v3，HERB/imp 新药按 v1）
bad_h = conn.execute("""
    SELECT h.id, h.name, h.compound_count,
           CASE WHEN h.id LIKE 'ccTCM%' THEN
               (SELECT COUNT(*) FROM rel_herb_compound_v3 v WHERE v.herb_id=h.id)
           ELSE
               (SELECT COUNT(*) FROM rel_herb_compound v WHERE v.herb_id=h.id)
           END AS actual
    FROM herb h
    WHERE COALESCE(h.compound_count,0) != actual""").fetchall()
if bad_h:
    problems += 1
    print(f"[不一致] herb.compound_count {len(bad_h)} 行过期：")
    for hid, name, old, new in bad_h[:20]:
        print(f"    {name}: {old} -> {new}")
    if len(bad_h) > 20:
        print(f"    ...（共 {len(bad_h)} 行）")
    if APPLY:
        conn.execute("""UPDATE herb SET compound_count =
            CASE WHEN herb.id LIKE 'ccTCM%' THEN
                (SELECT COUNT(*) FROM rel_herb_compound_v3 v WHERE v.herb_id=herb.id)
            ELSE
                (SELECT COUNT(*) FROM rel_herb_compound v WHERE v.herb_id=herb.id)
            END""")
        conn.commit()
        print("    已按双口径重算修复（ccTCM→v3，HERB/imp→v1）")
else:
    print("[ok] herb.compound_count 与双口径（ccTCM→v3 / HERB→v1）一致")

# 3. compound.target_count
bad_c = conn.execute("""
    SELECT c.id, c.name, c.target_count,
           (SELECT COUNT(*) FROM rel_compound_target r WHERE r.compound_id=c.id) AS actual
    FROM compound c
    WHERE COALESCE(c.target_count,0) != actual""").fetchall()
if bad_c:
    problems += 1
    print(f"[不一致] compound.target_count {len(bad_c)} 行过期：")
    for cid, name, old, new in bad_c[:20]:
        print(f"    {name}: {old} -> {new}")
    if len(bad_c) > 20:
        print(f"    ...（共 {len(bad_c)} 行）")
    if APPLY:
        conn.execute("""UPDATE compound SET target_count =
            (SELECT COUNT(*) FROM rel_compound_target r WHERE r.compound_id=compound.id)""")
        conn.commit()
        print("    已按 rel_compound_target 重算修复")
else:
    print("[ok] compound.target_count 与 rel_compound_target 一致")

# 4. v1 表构成提示（2026-11-05 扩容后不再是纯错乱表）
n_legacy = conn.execute("SELECT COUNT(*) FROM rel_herb_compound").fetchone()[0]
n_herb = conn.execute(
    "SELECT COUNT(*) FROM rel_herb_compound WHERE herb_id NOT LIKE 'ccTCM%'").fetchone()[0]
print(f"[提示] rel_herb_compound（v1）共 {n_legacy} 行 = 旧 34 味快照 {n_legacy - n_herb} 行"
      f"（与 v3 同源，代码仅在双口径计数中引用）+ 2026-11-05 扩容新增 {n_herb} 行（HERB/imp 药材）")

conn.close()
print(f"\n{'发现问题并已修复' if APPLY and problems else ('发现问题 ' + str(problems) + ' 项（未 --apply）' if problems else '全部一致')}")
sys.exit(1 if problems and not APPLY else 0)
