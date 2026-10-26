# -*- coding: utf-8 -*-
"""
重建 recipe_analysis（v3：基于大创库修复后的数据）

与 v2 的区别：
  - 归属关系读 rel_herb_compound_v3（大创库修复后的 rel_herb_compound）
  - 三维评分读 radar_*_gsea（真实 Enrichr GSEA），而非旧的随机 radar_*
  - 入血概率为重训模型输出

三维聚合口径：只对有 GSEA 值的成分取均值，并记录覆盖成分数，
避免「无 GSEA 值的成分被当成 0 分」拉低整体。

用法：python -X utf8 scripts/pregen_analysis_v3.py
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
report = ["# 方子成分分析重建报告 v3（同步大创库修复后数据）", "",
          "数据源：rel_herb_compound_v3（大创库 2026-10-26 修复版）",
          "三维评分：radar_*_gsea（Enrichr 真实富集）",
          f"筛选：入血概率 ≥ {MIN_PROB}；靶点仅人类蛋白", ""]

for r in recipes:
    rid, rname = r["id"], r["name"]

    rows = conn.execute("""
        SELECT c.id, c.name, c.prob_cctcm,
               c.radar_anti_inflammatory_gsea AS g_anti,
               c.radar_immune_regulation_gsea AS g_imm,
               c.radar_airway_repair_gsea AS g_air,
               GROUP_CONCAT(DISTINCT h.name) AS herbs
        FROM rel_recipe_material m
        JOIN rel_herb_compound_v3 rc ON rc.herb_id = m.herb_id
        JOIN compound c ON c.id = rc.compound_id
        JOIN herb h ON h.id = rc.herb_id
        WHERE m.recipe_id = ?
        GROUP BY c.id
        ORDER BY c.prob_cctcm DESC
    """, (rid,)).fetchall()

    if not rows:
        skipped += 1
        report.append(f"- #{rid} {rname}：无成分数据")
        continue

    top = [x for x in rows if (x["prob_cctcm"] or 0) >= MIN_PROB][:10]
    top_json = [{"name": x["name"], "prob_cctcm": round(x["prob_cctcm"], 2),
                 "herbs": x["herbs"] or "",
                 "radar": [x["g_anti"], x["g_imm"], x["g_air"]]} for x in top]

    # 三维：只用有 GSEA 值的成分取均值，并记录覆盖数
    def avg_g(col):
        vals = [x[col] for x in rows if x[col] is not None]
        return round(sum(vals) / len(vals), 1) if vals else None

    gse_count = sum(1 for x in rows if x["g_anti"] is not None)
    radar = {"anti_inflammatory": avg_g("g_anti"),
             "immune_regulation": avg_g("g_imm"),
             "airway_repair": avg_g("g_air"),
             "gsea_covered": gse_count,
             "compound_total": len(rows),
             "source": "Enrichr GSEA (asthma_v2.db radar_*_gsea)"}

    # 靶点
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
    report.append(f"- #{rid} {rname}：{len(rows)} 成分（GSEA 覆盖 {gse_count}），"
                  f"主成分 {top[0]['name'] if top else '—'}")

conn.commit()
print(f"重建完成：更新 {updated} 方，跳过 {skipped} 方")

chk = conn.execute("SELECT top_compounds, radar_summary FROM recipe_analysis WHERE recipe_id=1").fetchone()
print("\n方子1 重建后 Top3：")
for c in json.loads(chk["top_compounds"])[:3]:
    print(f"  {c['name']} ({c['prob_cctcm']}) 来源: {c['herbs']} GSEA雷达: {c['radar']}")
print("三维聚合：", chk["radar_summary"])

(ROOT / "docs" / "成分分析重建报告_v3.md").write_text("\n".join(report), encoding="utf-8")
print("\n报告已写入 docs/成分分析重建报告_v3.md")
conn.close()
