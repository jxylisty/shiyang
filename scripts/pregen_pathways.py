# -*- coding: utf-8 -*-
"""
预生成方子通路富集（KEGG）→ 表 recipe_pathway
数据源：Enrichr 公开 API（KEGG_2021_Human），靶点仅人类蛋白、成分入血概率>=0.7

用法：
    python -X utf8 scripts/pregen_pathways.py            # 只跑缺失的方子
    python -X utf8 scripts/pregen_pathways.py --refresh   # 全部重跑
    python -X utf8 scripts/pregen_pathways.py --limit 5   # 只跑前 5 方（调试）
"""
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend" / "app"))

from services import pathway_service as ps  # noqa: E402

REFRESH = "--refresh" in sys.argv
LIMIT = None
if "--limit" in sys.argv:
    try:
        LIMIT = int(sys.argv[sys.argv.index("--limit") + 1])
    except (IndexError, ValueError):
        LIMIT = None

import sqlite3  # noqa: E402

DB = ROOT / "data" / "shiyang.db"
conn = sqlite3.connect(DB)
recipes = conn.execute(
    "SELECT id, name FROM recipe WHERE analysis_ready=1 ORDER BY id").fetchall()
if LIMIT:
    recipes = recipes[:LIMIT]
print(f"待处理: {len(recipes)} 方（refresh={REFRESH}）")

# 确保表存在（save() 也会建，这里提前建好便于统计）
conn.execute("""
CREATE TABLE IF NOT EXISTS recipe_pathway (
    recipe_id INTEGER PRIMARY KEY REFERENCES recipe(id),
    gene_count INTEGER, pathways TEXT, status TEXT,
    library TEXT, generated_at TEXT)""")
conn.commit()
conn.close()

stats = {"ok": 0, "insufficient": 0, "offline": 0}
for i, (rid, rname) in enumerate(recipes, 1):
    if not REFRESH:
        c = ps.cached(rid)
        if c and c["status"] in ("ok", "insufficient"):
            stats[c["status"]] += 1
            print(f"[{i}/{len(recipes)}] {rname}: 已有缓存({c['status']}, "
                  f"{len(c['pathways'])} 通路) 跳过")
            continue
    result = ps.for_recipe(rid, refresh=True)
    stats[result["status"]] = stats.get(result["status"], 0) + 1
    top = "、".join(p["term"] for p in result["pathways"][:2]) or "-"
    print(f"[{i}/{len(recipes)}] {rname}: {result['status']} "
          f"基因{result['n_genes']} 通路{len(result['pathways'])} → {top[:60]}")
    time.sleep(0.4)  # 对公共 API 友好限速

conn = sqlite3.connect(DB)
n = conn.execute("SELECT COUNT(*) FROM recipe_pathway").fetchone()[0]
n_ok = conn.execute(
    "SELECT COUNT(*) FROM recipe_pathway WHERE status='ok'").fetchone()[0]
conn.close()
print(f"\n完成: recipe_pathway 共 {n} 行，其中 status=ok {n_ok} 行")
print(f"本轮统计: {stats}")
