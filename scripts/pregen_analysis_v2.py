# -*- coding: utf-8 -*-
"""
基于修复后的 herb→compound 归属，重建 recipe_analysis（top成分 / 三维评分 / 靶点）

与 pregen_analysis.py 的区别：读 rel_herb_compound_v2（原始 Excel 真源）而非错乱的旧表。
同时把「成分来源药材」写进 top_compounds，供前端桑基图/溯源展示。

用法：python -X utf8 scripts/pregen_analysis_v2.py
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "shiyang.db"
MIN_PROB = 0.7

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA journal_mode=WAL")

recipes = conn.execute(
    "SELECT id, name FROM recipe WHERE analysis_ready=1 ORDER BY id").fetchall()
print(f"待重建分析: {len(recipes)} 方")

updated = skipped = 0
report = ["# 方子成分分析重建报告（归属修复后）", "",
          f"数据源：rel_herb_compound_v2（原始 Excel「药材-化合物-含量-赵玉男」重建）",
          f"筛选：入血概率 ≥ {MIN_PROB}；靶点仅人类蛋白", ""]

for r in recipes:
    rid, rname = r["id"], r["name"]

    # 该方配料 → 真实成分（带来源药材），去重后按入血概率排序
    rows = conn.execute("""
        SELECT c.id, c.name, c.prob_cctcm,
               c.radar_anti_inflammatory, c.radar_immune_regulation, c.radar_airway_repair,
               GROUP_CONCAT(DISTINCT h.name) AS herbs
        FROM rel_recipe_material m
        JOIN rel_herb_compound_v2 rc ON rc.herb_id = m.herb_id
        JOIN compound c ON c.id = rc.compound_id
        JOIN herb h ON h.id = rc.herb_id
        WHERE m.recipe_id = ?
        GROUP BY c.id
        ORDER BY c.prob_cctcm DESC
    """, (rid,)).fetchall()

    if not rows:
        skipped += 1
        report.append(f"- #{rid} {rname}：无成分数据（配料不在成分库覆盖范围）")
        continue

    top = [x for x in rows if (x["prob_cctcm"] or 0) >= MIN_PROB][:10]
    top_json = [{"name": x["name"], "prob_cctcm": round(x["prob_cctcm"], 2),
                 "herbs": x["herbs"] or "",
                 "radar": [x["radar_anti_inflammatory"], x["radar_immune_regulation"],
                           x["radar_airway_repair"]]} for x in top]

    def avg(idx):
        vals = [x[idx] for x in rows if x[idx] is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    radar = {"anti_inflammatory": avg("radar_anti_inflammatory"),
             "immune_regulation": avg("radar_immune_regulation"),
             "airway_repair": avg("radar_airway_repair")}

    # 主要靶点：top 成分关联的人类蛋白
    top_ids = [x["id"] for x in top]
    targets = []
    if top_ids:
        ph = ",".join("?" * len(top_ids))
        for gene, cnt in conn.execute(f"""
                SELECT t.gene, COUNT(DISTINCT rt.compound_id) c
                FROM rel_compound_target rt
                JOIN target t ON t.gene = rt.target_gene
                WHERE t.target_type='Protein' AND t.species='Homo sapiens'
                  AND rt.compound_id IN ({ph})
                GROUP BY t.gene ORDER BY c DESC LIMIT 8""", top_ids):
            targets.append({"gene": gene, "compound_count": cnt})

    herb_count = conn.execute(
        "SELECT COUNT(*) FROM rel_recipe_material WHERE recipe_id=?", (rid,)).fetchone()[0]

    conn.execute("""INSERT OR REPLACE INTO recipe_analysis
        (recipe_id, herb_count, compound_count, top_compounds, radar_summary, top_targets, generated_at)
        VALUES (?,?,?,?,?,?,datetime('now'))""",
        (rid, herb_count, len(rows),
         json.dumps(top_json, ensure_ascii=False),
         json.dumps(radar, ensure_ascii=False),
         json.dumps(targets, ensure_ascii=False)))
    updated += 1
    report.append(f"- #{rid} {rname}：{len(rows)} 成分（Top10 中 {len(top)} 个 ≥{MIN_PROB}），"
                  f"主成分 {top[0]['name'] if top else '—'}")

conn.commit()
print(f"重建完成：更新 {updated} 方，跳过 {skipped} 方")

# 校验：方子1 是否已正确
chk = conn.execute("SELECT top_compounds FROM recipe_analysis WHERE recipe_id=1").fetchone()
print("\n方子1 修复后 Top5：")
for c in json.loads(chk["top_compounds"])[:5]:
    print(f"  {c['name']} ({c['prob_cctcm']}) 来源: {c['herbs']}")

(ROOT / "docs" / "归属重建报告.md").write_text("\n".join(report), encoding="utf-8")
print(f"\n报告已写入 docs/归属重建报告.md")
conn.close()
