# -*- coding: utf-8 -*-
"""
补录配料克重（仅「原文有数量、非克重单位」的条目）

性质声明（AGENTS.md §2.5 编辑性规则）：
  本脚本使用的是「按通识整理的编辑换算表」，不是实验数据、不是原文标注。
  所有被改写的行会在 note 追加标注，发布前需真人医药背景审校。

处理规则：
  A. note 匹配「N颗/N枚/N片/N朵」且材料在换算表内 → grams = N × 单件克重，note 追加标注
  B. 「3~5克」区间 → 保守取下限 3g（茶饮用量宜轻），note 追加标注
  C. 原文为「适量/少许/未标克数/二两口径不一」→ 不猜，保持 NULL，报告如实列出

用法：
    python -X utf8 scripts/fill_missing_grams.py            # dry-run，只打印不写库
    python -X utf8 scripts/fill_missing_grams.py --apply    # 实际写库 + 生成报告
"""
import re
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "shiyang.db"
APPLY = "--apply" in sys.argv

# 编辑换算表（通识单件重，保守取低值；发布前需医药审校）
# key: (材料名, 单位)，value: 单件克重(g)
PIECE_GRAMS = {
    ("枣", "颗"): 5.0,        # 干红枣去核，单颗约4-6g
    ("龙眼肉", "颗"): 2.0,    # 干桂圆肉，单颗约1.5-2.5g
    ("生姜", "片"): 3.0,      # 鲜姜片，单片约2-4g
    ("胖大海", "枚"): 3.0,    # 单枚约2-4g
    ("山楂", "片"): 2.0,      # 山楂干片，单片约1.5-2.5g
    ("菊花", "朵"): 0.5,      # 杭白菊，单朵约0.4-0.6g
    ("玫瑰花", "朵"): 0.5,    # 重瓣红玫瑰干品，单朵约0.4-0.6g
    ("冰糖", "颗"): 5.0,      # 单晶冰糖，单颗约4-6g
}
RANGE_LOWER_G = 3.0  # 「3~5克」保守取下限

NOTE_TAG = "克重为编辑按通识单件重换算（依据见 scripts/fill_missing_grams.py），非原文标注，待医药审校"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
rows = conn.execute("""
    SELECT m.id, m.recipe_id, m.name, m.note, r.name AS rname
    FROM rel_recipe_material m JOIN recipe r ON r.id = m.recipe_id
    WHERE m.grams IS NULL ORDER BY m.recipe_id, m.id""").fetchall()

filled, kept = [], []
for row in rows:
    note = row["note"] or ""
    name = row["name"]
    grams = None
    basis = ""

    m = re.search(r"(\d+)\s*(颗|枚|片|朵)", note)
    if m and (name, m.group(2)) in PIECE_GRAMS:
        n, unit = int(m.group(1)), m.group(2)
        grams = n * PIECE_GRAMS[(name, unit)]
        basis = f"原文{n}{unit} × {PIECE_GRAMS[(name, unit)]}g"
    elif "3~5克" in note:
        grams = RANGE_LOWER_G
        basis = "原文3~5克，保守取下限"

    if grams is None:
        kept.append((row["rname"], name, note[:40]))
        continue

    new_note = (note.rstrip("；") + "；" + NOTE_TAG) if note else NOTE_TAG
    filled.append((row["rname"], name, grams, basis))
    if APPLY:
        conn.execute("UPDATE rel_recipe_material SET grams=?, note=? WHERE id=?",
                     (grams, new_note, row["id"]))

print(f"可换算补录: {len(filled)} 条；保持NULL（原文无量）: {len(kept)} 条；模式: {'APPLY' if APPLY else 'DRY-RUN'}\n")
print("== 补录明细 ==")
for rname, name, g, basis in filled:
    print(f"  {rname} | {name} -> {g}g  ({basis})")

if APPLY:
    conn.commit()
    report = ["# 配料克重补录报告（编辑换算，待医药审校）", "",
              "性质：AGENTS.md §2.5 编辑性规则 —— 按通识单件重换算，非原文标注、非实验数据。", "",
              "## 换算表", ""]
    for (n, u), g in sorted(PIECE_GRAMS.items()):
        report.append(f"- {n} 1{u} ≈ {g}g")
    report += [f"- 「3~5克」区间一律取下限 {RANGE_LOWER_G}g（茶饮保守）", "",
               f"## 已补录 {len(filled)} 条", ""]
    report += [f"- {r} | {n} -> {g}g（{b}）" for r, n, g, b in filled]
    report += ["", f"## 保持 NULL {len(kept)} 条（原文无量/口径不一，不猜测）", ""]
    report += [f"- {r} | {n} | {note}" for r, n, note in kept]
    (ROOT / "docs" / "克重补录报告.md").write_text("\n".join(report), encoding="utf-8")
    print("\n报告已写入 docs/克重补录报告.md")

conn.close()
