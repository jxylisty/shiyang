# -*- coding: utf-8 -*-
"""
入血概率可解释服务（T1-4）
把 PU-Learning 入血预测的模型特征科普化：
- 对单化合物：分子量 / 脂水分配系数(logP) 对照 Lipinski 口服生物利用度五规则，
  逐项打勾/超标，并按特征区间生成「为什么模型给它这个概率」的人话解读
- 对方子：说明书里 Top 成分的特征一览（讲解页入口）

科普口径：我们展示的是「模型的判断依据（特征区间）」，不是严格 SHAP 值——
模型完整特征与训练细节见课题论文。
"""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "shiyang.db"

# Lipinski 类五规则（Ro5）科普阈值（多氢键供体/受体数本库无，展示 mw/logp 两项+说明）
RO5 = {
    "mw": {"limit": 500, "label": "分子量 < 500 Da", "why": "小分子更容易穿过肠壁进入血液"},
    "logp": {"limit": 5, "label": "脂溶性 logP < 5", "why": "适度亲脂才溶得进细胞膜，过脂会在体液里『沉底』"},
}


def _db():
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _band(prob: float) -> dict:
    if prob >= 0.9:
        return {"tier": "很高", "color": "#2e7d5b",
                "say": "模型判断它大概率能被吸收入血"}
    if prob >= 0.7:
        return {"tier": "较高", "color": "#c98a2d",
                "say": "模型判断它有较大概率被吸收入血"}
    if prob >= 0.5:
        return {"tier": "中等", "color": "#8a978f",
                "say": "模型判断它入血可能性一般"}
    return {"tier": "偏低", "color": "#8a978f",
            "say": "模型判断它较难被吸收入血（多留在消化道）"}


def _explain(mw, logp, prob) -> list[dict]:
    """逐特征解读：命中/超标 + 人话"""
    feats = []
    if mw is not None:
        ok = mw < RO5["mw"]["limit"]
        if ok:
            say = f"分子量 {mw:.0f} Da，小于 500 Da 门槛——小分子更容易穿肠入血，这是加分项"
        else:
            say = f"分子量 {mw:.0f} Da，超过 500 Da 门槛——大分子难以直接穿越肠壁，模型会因此压低入血估计"
        feats.append({"key": "mw", "label": RO5["mw"]["label"], "why": RO5["mw"]["why"],
                      "value": round(mw, 1), "limit": RO5["mw"]["limit"], "pass": ok, "say": say})
    if logp is not None:
        ok = logp < RO5["logp"]["limit"]
        if ok:
            say = f"logP = {logp:.2f}，脂溶性适中——能溶进细胞膜又不会完全锁死在脂肪里，是加分项"
        else:
            say = f"logP = {logp:.2f}，脂溶性偏高——太『油』的分子容易滞留在脂肪组织，模型会因此下调入血估计"
        feats.append({"key": "logp", "label": RO5["logp"]["label"], "why": RO5["logp"]["why"],
                      "value": round(logp, 2), "limit": RO5["logp"]["limit"], "pass": ok, "say": say})
    return feats


def compound_explain(name: str) -> dict | None:
    conn = _db()
    try:
        row = conn.execute(
            "SELECT id,name,smiles,mw,logp,prob_cctcm,prob_herb,target_count FROM compound WHERE name=?",
            (name,)).fetchone()
        if not row:
            return None
        herbs = [r[0] for r in conn.execute(
            "SELECT h.name FROM rel_herb_compound rc JOIN herb h ON h.id=rc.herb_id "
            "WHERE rc.compound_id=?", (row["id"],)).fetchall()]
    finally:
        conn.close()

    band = _band(row["prob_cctcm"] or 0)
    feats = _explain(row["mw"], row["logp"], row["prob_cctcm"] or 0)
    n_pass = sum(1 for f in feats if f["pass"])
    return {
        "name": row["name"], "smiles": row["smiles"], "mw": row["mw"], "logp": row["logp"],
        "prob_cctcm": row["prob_cctcm"], "prob_herb": row["prob_herb"],
        "target_count": row["target_count"], "herbs": herbs,
        "band": band, "features": feats,
        "rule_summary": f"Lipinski 口服有利特征 {n_pass}/{len(feats)} 项命中",
        "note": "以上为模型判断依据的科普化展示（特征区间），非严格贡献值；"
                "模型为课题自研 PU-Learning 入血预测，prob 越高表示越可能被吸收入血。",
    }


def recipe_compounds(rid: int) -> dict | None:
    """方子说明书 Top 成分的特征一览（可解释页主体）"""
    conn = _db()
    try:
        r = conn.execute("SELECT id,name FROM recipe WHERE id=?", (rid,)).fetchone()
        if not r:
            return None
        a = conn.execute("SELECT top_compounds FROM recipe_analysis WHERE recipe_id=?", (rid,)).fetchone()
    finally:
        conn.close()
    if not a:
        return None
    out = []
    for c in json.loads(a["top_compounds"] or "[]")[:10]:
        name = c["name"]
        row = None
        conn = _db()
        try:
            row = conn.execute("SELECT mw, logp, prob_cctcm, prob_herb FROM compound WHERE name=?",
                               (name,)).fetchone()
        finally:
            conn.close()
        if not row:
            continue
        feats = _explain(row["mw"], row["logp"], row["prob_cctcm"] or 0)
        out.append({"name": name, "mw": row["mw"], "logp": row["logp"],
                    "prob_cctcm": row["prob_cctcm"], "prob_herb": row["prob_herb"],
                    "band": _band(row["prob_cctcm"] or 0),
                    "pass_count": sum(1 for f in feats if f["pass"]), "feat_count": len(feats),
                    "features": feats})
    return {"recipe_id": rid, "recipe_name": r["name"], "compounds": out,
            "rules": [v for v in RO5.values()],
            "note": "prob_cctcm：模型预测的「被吸收入血」概率；特征命中越多、概率通常越高，"
                    "但模型还参考了训练数据中的其他规律。"}
