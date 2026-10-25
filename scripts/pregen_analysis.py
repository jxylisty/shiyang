# -*- coding: utf-8 -*-
"""
预生成方子成分分析报告 → 表 recipe_analysis + 文档抽样报告
每方输出：成分总数/高入血成分Top10/三维评分(按成分radar均值)/主要靶点

数据可信度约束（写死在本脚本，防止回归）：
- 靶点只保留 target_type='Protein' 且 species='Homo sapiens' 的行，
  组织/细胞系/物种/活性描述（如 'Radical scavenging activity'）一律不进用户界面
- 成分入血概率 prob_cctcm >= 0.7 才进 Top 列表（低于阈值展示价值低）
- 三维评分为成分均值，展示层按 0-100 整数呈现，不给伪精度
- compounds 源库的 mw/logp 列与 name/smiles 错位，本脚本不输出 mw/logp
用法：python -X utf8 pregen_analysis.py
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
conn.execute("PRAGMA journal_mode=WAL")

conn.execute("""
CREATE TABLE IF NOT EXISTS recipe_analysis (
    recipe_id INTEGER PRIMARY KEY REFERENCES recipe(id),
    herb_count INTEGER,
    compound_count INTEGER,
    top_compounds TEXT,      -- JSON: [{name, prob_cctcm, radar...}]
    radar_summary TEXT,      -- JSON: {anti_inflammatory, immune_regulation, airway_repair}
    top_targets TEXT,        -- JSON: [{gene, compound_count}] 仅人类蛋白靶点
    generated_at TEXT
)""")

recipes = conn.execute(
    "SELECT r.id, r.name FROM recipe r WHERE r.analysis_ready=1").fetchall()
print(f"待分析: {len(recipes)} 方")

report_lines = ["# 方子成分分析预生成报告（抽样）", "",
                f"生成范围：{len(recipes)} 个可分析方子（配料含成分库覆盖药材）", "",
                f"筛选口径：入血概率 ≥ {MIN_PROB}；靶点仅计人类蛋白（Homo sapiens Protein）", ""]

for rid, rname in recipes:
    herbs = conn.execute(
        "SELECT h.id, h.name FROM rel_recipe_material m JOIN herb h ON h.id=m.herb_id "
        "WHERE m.recipe_id=?", (rid,)).fetchall()
    if not herbs:
        continue
    hp = ",".join("?" * len(herbs))
    hids = [h[0] for h in herbs]
    comp_rows = conn.execute(
        f"SELECT DISTINCT c.id,c.name,c.prob_cctcm,"
        f"c.radar_anti_inflammatory,c.radar_immune_regulation,c.radar_airway_repair "
        f"FROM compound c JOIN rel_herb_compound r ON r.compound_id=c.id WHERE r.herb_id IN ({hp}) "
        f"ORDER BY c.prob_cctcm DESC", hids).fetchall()

    top = [c for c in comp_rows if (c[2] or 0) >= MIN_PROB][:10]
    top_json = [{"name": c[1],
                 "prob_cctcm": round(c[2], 2) if c[2] else None,
                 "radar": [c[3], c[4], c[5]]} for c in top]

    # 三维评分：成分均值，保留 1 位小数（0-100 整数感展示由前端取整）
    def avg(idx):
        vals = [c[idx] for c in comp_rows if c[idx] is not None]
        return round(sum(vals) / len(vals), 1) if vals else None
    radar = {"anti_inflammatory": avg(3), "immune_regulation": avg(4), "airway_repair": avg(5)}

    # 主要靶点：top 成分关联的人类蛋白靶点，按覆盖成分数排序
    top_ids = [c[0] for c in top]
    targets = []
    if top_ids:
        tp = ",".join("?" * len(top_ids))
        for gene, cnt in conn.execute(
                f"SELECT t.gene, COUNT(DISTINCT rt.compound_id) c FROM rel_compound_target rt "
                f"JOIN target t ON t.gene=rt.target_gene AND t.target_type='Protein' AND t.species='Homo sapiens' "
                f"WHERE rt.compound_id IN ({tp}) GROUP BY t.gene ORDER BY c DESC LIMIT 8", top_ids):
            targets.append({"gene": gene, "compound_count": cnt})
    conn.execute("INSERT OR REPLACE INTO recipe_analysis VALUES (?,?,?,?,?,?,datetime('now'))",
                 (rid, len(herbs), len(comp_rows),
                  json.dumps(top_json, ensure_ascii=False), json.dumps(radar, ensure_ascii=False),
                  json.dumps(targets, ensure_ascii=False)))

    # 抽样报告：挑 6 个代表方
    SAMPLE = {"清咽利喉饮", "酸枣仁百合安睡茶", "开胃消食解腻茶", "当归生姜羊肉汤", "黄芪芡实杞菊茶", "古法酸梅茶"}
    if rname in SAMPLE:
        report_lines += [f"## {rname}", f"- 药材 {len(herbs)} 味（{'、'.join(h[1] for h in herbs)}）",
                         f"- 关联化合物 {len(comp_rows)} 个，其中入血概率≥{MIN_PROB} 的 {len(top)} 个"]
        for t in top_json[:5]:
            report_lines.append(
                f"  - {t['name']} 入血概率 {t['prob_cctcm']}｜雷达 抗炎{t['radar'][0]} 免疫{t['radar'][1]} 气道{t['radar'][2]}")
        report_lines.append(f"- 三维评分均值：抗炎 {radar['anti_inflammatory']}｜免疫调节 {radar['immune_regulation']}｜气道修复 {radar['airway_repair']}")
        if targets:
            report_lines.append(f"- 主要人类蛋白靶点：{'、'.join(t['gene'] for t in targets)}")
        report_lines.append("")

conn.commit()
n = conn.execute("SELECT COUNT(*) FROM recipe_analysis").fetchone()[0]
hi = conn.execute(
    "SELECT COUNT(*) FROM recipe_analysis WHERE json_extract(top_compounds,'$[0].prob_cctcm') >= 0.5").fetchone()[0]
conn.close()
report_lines += ["## 汇总", f"- 已生成分析 {n} 方；Top1 成分入血概率≥0.5 的 {hi} 方",
                 "- 注：入血概率为 PU-Learning 模型预测值；三维评分为成分库既有雷达分均值，报告页须标注'预测值/参考'",
                 "- 注：成分-药材归属（rel_herb_compound）经抽查与常识不符（如人参皂苷挂薄荷），",
                 "  已在展示层移除'来自某药材'字样，归属修正留待 TCMSP 原始数据重建关联后恢复"]
(ROOT / "docs" / "成分分析抽样报告.md").write_text("\n".join(report_lines), encoding="utf-8")
print(f"分析完成: {n} 方（Top1入血概率≥0.5: {hi}）")
print(f"抽样报告: docs/成分分析抽样报告.md")
