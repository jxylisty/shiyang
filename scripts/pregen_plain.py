# -*- coding: utf-8 -*-
"""
「说人话」白话解读预生成：为方子库每个方子生成大众版解读，写入 data/recipe_plain_ai.json。

- 输入只用方子库已有的传统资料（定位/配料传统功效/禁忌），不喂入血概率等预测值
- 输出经 plain_service.parse_and_validate 校验：结构完整、无红线词、配料名不越界
- 全部为 AI 生成，reviewed=false；医药背景人员审校后可直接改 JSON 并把 reviewed 置 true
  （后端按文件 mtime 自动重载，无需重启）

AI 端点默认本机 ZeroGate 网关，可用 SHIYANG_AI_BASE_URL / SHIYANG_AI_KEY / SHIYANG_AI_MODEL 覆盖。

用法：
  python -X utf8 scripts/pregen_plain.py             # 只补缺失的
  python -X utf8 scripts/pregen_plain.py --limit 3   # 试跑 3 个
  python -X utf8 scripts/pregen_plain.py --force     # 全部重生成（会覆盖已审校条目，慎用）
"""
import json
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend" / "app" / "services"))
sys.stdout.reconfigure(encoding="utf-8")

import plain_service as plain  # noqa: E402

DB_PATH = ROOT / "data" / "shiyang.db"
OUT = plain.PLAIN_JSON


def load_recipes():
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    out = []
    for r in conn.execute("SELECT * FROM recipe ORDER BY id").fetchall():
        recipe = dict(r)
        for k in ("scenes", "constitutions_suitable", "constitutions_unsuitable"):
            recipe[k] = json.loads(recipe.get(k) or "[]")
        mats = conn.execute(
            "SELECT m.name, m.material_type, m.grams, h.nature, h.flavor, h.functions "
            "FROM rel_recipe_material m LEFT JOIN herb h ON h.id=m.herb_id "
            "WHERE m.recipe_id=?", (recipe["id"],)).fetchall()
        out.append((recipe, [dict(m) for m in mats]))
    conn.close()
    return out


def main():
    limit = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
    force = "--force" in sys.argv
    store = {"note": ("AI 生成的大众版白话解读（scripts/pregen_plain.py）。输入仅限方子库传统资料，"
                      "未经医药背景人员审校前 reviewed=false；审校后可直接修改本文件。"),
             "items": {}}
    if OUT.exists():
        store = json.loads(OUT.read_text(encoding="utf-8"))
    items = store.setdefault("items", {})

    todo = [(r, m) for r, m in load_recipes() if force or str(r["id"]) not in items]
    if limit:
        todo = todo[:limit]
    print(f"AI 端点 {plain.AI_BASE_URL}  模型 {plain.AI_MODEL}；待生成 {len(todo)} 个")
    ok = fail = 0
    for i, (recipe, mats) in enumerate(todo, 1):
        try:
            content = plain.generate(plain.build_recipe_input(recipe, mats))
            items[str(recipe["id"])] = {
                "name": recipe["name"], "content": content, "model": plain.AI_MODEL,
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"), "reviewed": False,
            }
            ok += 1
            print(f"[{i}/{len(todo)}] ✓ #{recipe['id']} {recipe['name']}：{content['headline']}")
            # 每条落盘一次，中途失败不丢已生成的
            OUT.write_text(json.dumps(store, ensure_ascii=False, indent=1), encoding="utf-8")
        except Exception as e:
            fail += 1
            print(f"[{i}/{len(todo)}] × #{recipe['id']} {recipe['name']}：{str(e)[:120]}")
        time.sleep(0.5)
    print(f"\n完成：成功 {ok}，失败 {fail}；文件 {OUT}")


if __name__ == "__main__":
    main()
