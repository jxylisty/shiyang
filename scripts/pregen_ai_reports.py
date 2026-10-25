# -*- coding: utf-8 -*-
"""
AI 解读预生成：为 analysis_ready 的方子预生成通俗解读，存入 shiyang.db 的
recipe_pregen_ai 表。运行后无 Key 的用户也能在方子详情页直接看到 AI 解读（SSE 回放）。

AI 端点默认走本机 ZeroGate 网关（无需真实付费 key，见 ~/.zcode/skills/ai-key-policy）：
  Base URL: http://127.0.0.1:7863/v1    Key: zerogate    Model: deepseek-v4-flash
可用环境变量 SHIYANG_AI_BASE_URL / SHIYANG_AI_KEY / SHIYANG_AI_MODEL 覆盖。

用法：
  python -X utf8 pregen_ai_reports.py            # 全部缺失的
  python -X utf8 pregen_ai_reports.py --limit 5  # 只补 5 个（测试）
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend" / "app" / "services"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend" / "app"))
sys.stdout.reconfigure(encoding="utf-8")

import ai_service as ai  # noqa: E402
import sqlite3  # noqa: E402

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "shiyang.db"

# ZeroGate 网关默认值（本机，无需真实 key）
BASE_URL = "http://127.0.0.1:7863/v1"
API_KEY = "zerogate"
MODEL = "deepseek-v4-flash"


def load_recipe(rid: int):
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    r = conn.execute("SELECT * FROM recipe WHERE id=?", (rid,)).fetchone()
    if not r:
        return None, None
    recipe = dict(r)
    for k in ("scenes", "constitutions_suitable", "constitutions_unsuitable"):
        recipe[k] = json.loads(recipe.get(k) or "[]")
    mats = conn.execute("SELECT name, grams FROM rel_recipe_material WHERE recipe_id=?", (rid,)).fetchall()
    recipe["materials"] = [dict(m) for m in mats]
    a = conn.execute("SELECT * FROM recipe_analysis WHERE recipe_id=?", (rid,)).fetchone()
    analysis = None
    if a:
        analysis = dict(a)
        for k in ("top_compounds", "radar_summary", "top_targets"):
            analysis[k] = json.loads(analysis[k] or "null")
    conn.close()
    return recipe, analysis


import json  # noqa: E402


async def main(limit=None):
    import os
    base_url = os.environ.get("SHIYANG_AI_BASE_URL") or BASE_URL
    key = os.environ.get("SHIYANG_AI_KEY") or API_KEY
    model = os.environ.get("SHIYANG_AI_MODEL") or MODEL
    print(f"AI 端点: {base_url}  模型: {model}")
    ids = ai.pregen_missing(limit)
    print(f"待生成 {len(ids)} 个方子的 AI 解读")
    ok = fail = 0
    for i, rid in enumerate(ids, 1):
        recipe, analysis = load_recipe(rid)
        if not recipe:
            continue
        messages = ai.build_recipe_messages(recipe, analysis)
        try:
            full = ""
            async for chunk in ai.stream_chat(messages, key, "deepseek",
                                              base_url=base_url, model=model):
                full += chunk
            ai.save_pregen_report(rid, full, model)
            ok += 1
            print(f"[{i}/{len(ids)}] ✓ #{rid} {recipe['name']} ({len(full)}字)")
        except Exception as e:
            fail += 1
            print(f"[{i}/{len(ids)}] × #{rid} {recipe.get('name')}: {str(e)[:80]}")
        await asyncio.sleep(1.0)  # 限速
    print(f"\n完成：成功 {ok}，失败 {fail}")


if __name__ == "__main__":
    lim = None
    if "--limit" in sys.argv:
        lim = int(sys.argv[sys.argv.index("--limit") + 1])
    asyncio.run(main(lim))
