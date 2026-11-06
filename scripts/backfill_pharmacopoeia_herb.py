# -*- coding: utf-8 -*-
"""
补全扩容药材缺失的「功能主治 / 类别」（药典口径，非实验数据）

问题（2026-11-06 实测）：HERB 源数据本身缺列，导致 7 味药材入库后 functions 或
category 为 NULL：
  - 香橼 HERB006055、橘红 HERB003028：summary 整条几乎全空（连 Therapeutic class 都无）
  - 沙棘 HERB004849：Function/Indication 为空
  - 代代花/白扁豆花：无 Meridians
  - 花椒/铁皮石斛：Therapeutic class 为空；铁皮石斛 Function 是「See Dendrobium nobile.」

前端虽然已有 frontend/src/utils/pharmacopoeiaFunctions.js 做展示兜底，但**接口层**
（/api/v1/herbs、/api/v1/open/*、问一问检索）拿到的是裸 NULL。本脚本把药典文字写进库，
并在 herb.source 追加典籍出处，保证开放 API 的消费者也能溯源。

数据性质（AGENTS.md §2.5 要求标注）：
  **编辑性权威典籍整理**，不是实验数据、不是模型预测。取值来自《中华人民共和国药典》
  2020 年版一部对应品种「功能与主治」的功能项，无药典单列品种的（代代花、白扁豆花）
  取《中华本草》。与 frontend/src/utils/pharmacopoeiaFunctions.js 同源同值。

只填空，不覆盖：仅当目标列为 NULL/空串时写入；已有值一律不动（HERB 有值的以 HERB 为准）。
缺归经的（代代花/白扁豆花）**不猜**——HERB/SymMap 都没有，宁可留空由前端隐藏该区块。

用法：
  python -X utf8 scripts/backfill_pharmacopoeia_herb.py            # 预览
  python -X utf8 scripts/backfill_pharmacopoeia_herb.py --apply    # 写入（自动备份）
"""
import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "shiyang.db"

# 药材名 -> 补全项。取值与 frontend/src/utils/pharmacopoeiaFunctions.js **逐字一致**，
# 避免前后端两套文本（前端显示一套、接口返回另一套，对不上就是数据不一致）。
# src 会写进 herb.source 供溯源；不写 reference_url（那是具体条目链接，
# 药典是纸质出版物，没有可点链接，宁可不填也不编一个 URL）。
BACKFILL = {
    "橘红": {
        "category": "化痰药",
        "functions": "理气宽中、燥湿化痰",
        "src": "《中国药典》2020年版",
    },
    "香橼": {
        "category": "理气药",
        "functions": "疏肝理气、宽中化痰",
        "src": "《中国药典》2020年版",
    },
    "沙棘": {
        "functions": "健脾消食、止咳祛痰、活血散瘀",
        "src": "《中国药典》2020年版",
    },
    "花椒": {
        "category": "温里药",
        "functions": "温中止痛、杀虫止痒",
        "src": "《中国药典》2020年版",
    },
    "铁皮石斛": {
        "category": "补阴药",
        "functions": "益胃生津、滋阴清热",
        "src": "《中国药典》2020年版",
    },
    "代代花": {
        "functions": "行气宽中、消食、化痰",
        "src": "《中华本草》",   # 药典未单列该品种
    },
    "白扁豆花": {
        "functions": "健脾和胃、消暑化湿",
        "src": "《中华本草》",   # 药典未单列该品种（扁豆花非白扁豆正条）
    },
}

TARGETS = ("functions", "category")


def plan(conn):
    """返回 [(herb_row, {col: value})]，只含真正需要改的行。"""
    out = []
    for name, patch in BACKFILL.items():
        rows = conn.execute(
            "SELECT id, name, functions, category, source, added_batch "
            "FROM herb WHERE name=?", (name,)).fetchall()
        if not rows:
            print(f"  [跳过] {name}：库内无此药材")
            continue
        if len(rows) > 1:
            print(f"  [警告] {name} 在库内有 {len(rows)} 行，全部处理")
        for r in rows:
            changes = {}
            for col in TARGETS:
                if col in patch and not (r[col] or "").strip():
                    changes[col] = patch[col]
            if changes:
                out.append((dict(r), changes))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正写库（默认只预览）")
    args = ap.parse_args()

    if not DB.exists():
        print(f"数据库不存在：{DB}")
        return 1
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    todo = plan(conn)
    if not todo:
        print("没有需要补全的行。")
        conn.close()
        return 0

    print(f"待补全 {len(todo)} 行：")
    for r, changes in todo:
        desc = "，".join(f"{k}={v if len(v) < 40 else v[:40] + '…'}" for k, v in changes.items())
        print(f"  {r['id']:14s} {r['name']:6s}  {desc}")

    if not args.apply:
        print("\n未加 --apply，未写库。")
        conn.close()
        return 0

    backup = DB.with_name(f"{DB.name}.bak-pharm-{datetime.now():%Y%m%d%H%M%S}")
    shutil.copy2(DB, backup)
    print(f"\n[备份] {backup.name}（{backup.stat().st_size:,} bytes）")

    n = 0
    for r, changes in todo:
        sets, vals = [], []
        for col, val in changes.items():
            sets.append(f"{col}=?")
            vals.append(val)
        # 出处只追加一次：已在 source 里的不重复加
        src_note = BACKFILL[r["name"]]["src"]
        src = (r["source"] or "").strip()
        if src_note not in src:
            new_src = f"{src} + {src_note}" if src else src_note
            sets.append("source=?")
            vals.append(new_src)
        vals.append(r["id"])
        conn.execute(f"UPDATE herb SET {', '.join(sets)} WHERE id=?", vals)
        n += 1
    conn.commit()

    left = conn.execute(
        "SELECT COUNT(*) FROM herb WHERE functions IS NULL OR TRIM(functions)=''").fetchone()[0]
    left_cat = conn.execute(
        "SELECT COUNT(*) FROM herb WHERE category IS NULL OR TRIM(category)=''").fetchone()[0]
    left_mer = conn.execute(
        "SELECT COUNT(*) FROM herb WHERE meridians IS NULL OR TRIM(meridians)=''").fetchone()[0]
    conn.close()
    print(f"\n[完成] 更新 {n} 行。剩余 functions 空 {left} 行 / category 空 {left_cat} 行 / "
          f"meridians 空 {left_mer} 行（归经缺失为源数据本身没有，不猜）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
