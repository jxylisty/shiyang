# -*- coding: utf-8 -*-
"""
回填 rel_recipe_material.herb_id —— 用扩容后的 105 味药材库匹配 73 方配料

背景：2026-11-05 药食同源目录扩容（34→105 味）后，73 方里 53 条配料的
herb_id 仍是 NULL（建库时库里没有这味药，例如枣/莲子/决明子/荷叶）。
后果是证据链（/recipes/{rid}/chain）在这些配料上断链，21/73 方 Sankey
为空。本脚本按「正名精确 → 别名 → 异名表」顺序回填，只改 herb_id，
不动克重/名称/其他字段。

匹配口径（不猜、不模糊）：
1. herb.name 精确等于配料名
2. herb.alias 逗号分隔项精确等于配料名
3. 显式异名表（本脚本内 _EXTRA_ALIAS，依据药典通识整理）
4. 都不中 → 保持 NULL，并打印到「仍无法匹配」清单，不强行指派

用法：
    python -X utf8 scripts/backfill_material_herb_id.py           # 只看计划
    python -X utf8 scripts/backfill_material_herb_id.py --apply   # 实际写库（先自动备份）
"""
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "shiyang.db"
APPLY = "--apply" in sys.argv

# 药典通识异名（编辑性规则，非实验数据）：配料写法 → 库内正名
_EXTRA_ALIAS = {
    "桂圆": "龙眼肉",
    "桂圆肉": "龙眼肉",
    "红枣": "枣",
    "大枣": "枣",
    "生姜": "姜",
    "干姜": "姜",
    "橘皮": "陈皮",
    "陈皮": "橘皮",
}


def build_index(conn):
    """{候选名: herb_id}，正名与别名同权重；正名冲突时正名优先（先写别名再用正名覆盖）"""
    idx = {}
    for hid, alias in conn.execute("SELECT id, alias FROM herb"):
        for a in (alias or "").replace("，", ",").split(","):
            a = a.strip()
            if a:
                idx.setdefault(a, hid)
    for hid, name in conn.execute("SELECT id, name FROM herb"):
        idx[name] = hid  # 正名覆盖别名，避免别名抢正名
    return idx


def main():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    idx = build_index(conn)

    rows = conn.execute(
        "SELECT id, recipe_id, name FROM rel_recipe_material "
        "WHERE material_type='herb' AND herb_id IS NULL ORDER BY recipe_id").fetchall()
    if not rows:
        print("[ok] 没有待回填的配料（herb_id 均已匹配）")
        conn.close()
        return 0

    plan, unresolved = [], []
    for r in rows:
        name = (r["name"] or "").strip()
        hid = idx.get(name)
        how = "正名/别名"
        if not hid:
            alt = _EXTRA_ALIAS.get(name)
            if alt:
                hid = idx.get(alt)
                how = f"异名 {name}→{alt}"
        if hid:
            plan.append((r["id"], r["recipe_id"], name, hid, how))
        else:
            unresolved.append((r["recipe_id"], name))

    print(f"待回填配料 {len(rows)} 条；可匹配 {len(plan)} 条，无法匹配 {len(unresolved)} 条")
    for _, rid, name, hid, how in plan:
        print(f"  方#{rid:<3} {name:<8} → {hid}  ({how})")
    if unresolved:
        print("\n[仍无法匹配]（保持 NULL，不猜）：")
        for rid, name in unresolved:
            print(f"  方#{rid} {name}")

    if not APPLY:
        print("\n未加 --apply，未写库。")
        conn.close()
        return 0

    if plan:
        stamp = datetime.now().strftime("%Y%m%d%H%M%S")
        bak = DB.with_name(f"shiyang.db.bak-before-backfill-{stamp}")
        conn.execute("PRAGMA wal_checkpoint(FULL)")
        shutil.copy2(DB, bak)
        print(f"\n已备份 → {bak.name}")

    conn.executemany(
        "UPDATE rel_recipe_material SET herb_id=? WHERE id=?",
        [(hid, mid) for mid, _, _, hid, _ in plan])
    conn.commit()

    # 回填后校验：每个方子有多少条药材料子还能对上 herb 表
    print("\n[回填后每方药材料子匹配情况]")
    bad = conn.execute("""
        SELECT r.id, r.name,
               SUM(CASE WHEN m.herb_id IS NOT NULL THEN 1 ELSE 0 END) AS matched,
               SUM(CASE WHEN m.herb_id IS NULL THEN 1 ELSE 0 END) AS missing
        FROM recipe r JOIN rel_recipe_material m ON m.recipe_id=r.id
        WHERE m.material_type='herb' GROUP BY r.id
        HAVING matched = 0 ORDER BY r.id""").fetchall()
    if bad:
        print(f"  仍有 {len(bad)} 个方子完全没有匹配上药材料的配料：")
        for b in bad:
            print(f"    方#{b['id']} {b['name']}（{b['missing']} 条未匹配）")
    else:
        print("  [ok] 所有方子至少有一条药材料子能对上药材库")

    conn.close()
    print(f"\n回填完成：{len(plan)} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
