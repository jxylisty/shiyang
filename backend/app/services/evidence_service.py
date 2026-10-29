# -*- coding: utf-8 -*-
"""
证据分级与溯源服务（T1-3）
给平台上每类数据打「证据等级」标签并汇总溯源出处：

等级定义（对齐循证医学惯例做科普化）：
  A  权威典籍/官方目录 —— 药食同源目录（卫健委公告）、药典功效、权威媒体中医师出处（方子来源）
  B  实验数据库 —— TCMSP/CTD/KEGG/BindingDB/PubChem/DrugBank/ChEMBL 的成分-靶点关系（PMID 可溯源）
  C  模型预测 —— 入血概率（PU-Learning 模型，课题自研，给出模型特征而非文献）

补充：成分级的「实验活性强度」另有一套 L1/L2 标（compound_chembl_activity.evidence_level）：
  L1  pChEMBL >= 6（IC50/Ki <= 1 μM，强实验证据）
  L2  5 <= pChEMBL < 6（中等活性）
  两套体系不冲突：A/B/C 说「出处类型」，L1/L2 说「实验活性有多强」。
"""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "shiyang.db"

LEVELS = {
    "A": {"name": "权威出处", "color": "#2e7d5b",
          "desc": "卫健委药食同源目录、药典功效或权威媒体中医师出处"},
    "B": {"name": "实验数据库", "color": "#c98a2d",
          "desc": "TCMSP/CTD/KEGG/BindingDB/PubChem/DrugBank/ChEMBL 收录的成分-靶点关系，附文献编号"},
    "C": {"name": "模型预测", "color": "#8a978f",
          "desc": "课题 PU-Learning 入血预测模型输出，非文献直接结论"},
}

# rel_compound_target.source_db → 证据等级
_DB_LEVEL = {
    "CTD": "B", "KEGG": "B", "BindingDB": "B", "PubChem": "B", "DrugBank": "B",
}


def _db():
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def levels():
    return {"levels": {k: v for k, v in LEVELS.items()},
            "note": "同一方子的「成分说明书」里可能同时含 A/B/C 三级证据；等级只表示出处类型，不表示疗效强弱。"}


def recipe_evidence(rid: int) -> dict | None:
    """一个方子的完整证据链溯源：来源出处(A) + 靶点数据源(B) + 预测说明(C)"""
    conn = _db()
    try:
        r = conn.execute("SELECT id,name,source,reference_url FROM recipe WHERE id=?", (rid,)).fetchone()
        if not r:
            return None
        mats = conn.execute(
            "SELECT m.name, m.material_type, h.is_food_homology, h.food_catalog_batch, "
            "f.note "
            "FROM rel_recipe_material m "
            "LEFT JOIN herb h ON h.id=m.herb_id "
            "LEFT JOIN food f ON f.id=m.food_id WHERE m.recipe_id=?", (rid,)).fetchall()
        a = conn.execute("SELECT top_compounds, top_targets FROM recipe_analysis WHERE recipe_id=?",
                         (rid,)).fetchone()
    finally:
        conn.close()

    # ---- A 级：方子出处 + 配料的官方目录归属 ----
    a_items = []
    if r["source"]:
        a_items.append({"what": "方子出处", "text": r["source"], "url": r["reference_url"]})
    catalog = [{"what": "官方目录配料",
                "text": f"{m['name']}（卫健委药食同源目录第{m['food_catalog_batch']}批）"}
               for m in mats if m["material_type"] == "herb" and m["food_catalog_batch"]]
    a_items.extend(catalog)

    # ---- B 级：成分-靶点关系的数据源分布（带 PMID 示例）----
    b_items = []
    if a:
        names = [c["name"] for c in (json.loads(a["top_compounds"] or "[]"))][:8]
        if names:
            ph = ",".join("?" * len(names))
            conn = _db()
            try:
                rows = conn.execute(
                    f"SELECT rc.source_db, COUNT(*) AS cnt, rc.reference, rc.target_gene, c.name AS compound "
                    f"FROM rel_compound_target rc JOIN compound c ON c.id=rc.compound_id "
                    f"WHERE c.name IN ({ph}) GROUP BY rc.source_db ORDER BY cnt DESC", names).fetchall()
                pmid = conn.execute(
                    f"SELECT rc.reference, rc.target_gene, c.name AS compound FROM rel_compound_target rc "
                    f"JOIN compound c ON c.id=rc.compound_id WHERE c.name IN ({ph}) "
                    f"AND rc.reference IS NOT NULL AND rc.reference != '' LIMIT 3", names).fetchall()
            finally:
                conn.close()
            for row in rows:
                b_items.append({"what": row["source_db"], "text": f"本方成分相关靶点关系 {row['cnt']} 条"})
            for p in pmid:
                if p["reference"] and p["reference"].isdigit():
                    b_items.append({"what": "文献编号 PMID",
                                    "text": f"{p['compound']} ↔ {p['target_gene']}（PMID {p['reference']}）",
                                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{p['reference']}/"})
            # ChEMBL 实验活性汇总（体外实测，区别于上述数据库关联）
            conn = _db()
            try:
                ch = conn.execute(
                    f"SELECT COUNT(DISTINCT cca.compound_id) AS n_comp, "
                    f"COUNT(*) AS n_act, "
                    f"SUM(CASE WHEN cca.evidence_level='L1' THEN 1 ELSE 0 END) AS n_l1 "
                    f"FROM compound_chembl_activity cca JOIN compound c ON c.id=cca.compound_id "
                    f"WHERE c.name IN ({ph})", names).fetchone()
            finally:
                conn.close()
            if ch and ch["n_act"]:
                b_items.append({
                    "what": "ChEMBL 实验活性",
                    "text": f"本方 {ch['n_comp']} 个成分有 {ch['n_act']} 条体外实测活性记录"
                            f"（其中 {ch['n_l1'] or 0} 条为强证据 pChEMBL≥6）",
                    "url": "https://www.ebi.ac.uk/chembl/",
                })

    # ---- C 级：入血概率模型说明 ----
    c_items = [{"what": "PU-Learning 入血预测", "text":
                "入血概率为课题自研模型预测值（训练于中药成分-入血标注集），表示成分被吸收入血的可能性估计，"
                "非文献直接结论；模型特征含分子量/脂水性等，详见「入血概率怎么算」"}]

    return {
        "recipe_id": rid, "recipe_name": r["name"],
        "A": {"level": "A", **LEVELS["A"], "items": a_items},
        "B": {"level": "B", **LEVELS["B"], "items": b_items},
        "C": {"level": "C", **LEVELS["C"], "items": c_items},
    }
