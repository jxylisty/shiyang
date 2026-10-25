# -*- coding: utf-8 -*-
"""
反向配伍服务（"我的茶罐"）：用户勾选手边有的食材 → 反向找出能直接煮的方子
- 覆盖率 = 命中的必需配料数 / 该方必需配料总数（optional=1 的配料不计入分母）
- 排序：覆盖率降序 → 缺失数升序 → 高入血成分数降序
"""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "shiyang.db"


def _db():
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# 常见异名归一（与前端拉图脚本 MAT_IMG_ALIAS 对齐，外加几组做菜常用名）
_ALIAS = {
    "枣": "大枣", "红枣": "大枣", "铁皮石斛": "石斛", "猪瘦肉": "猪肉", "排骨": "猪骨",
    "猪脊骨": "猪骨", "猪肚": "猪骨", "天冬": "麦冬", "地黄": "玉竹",
    "枸杞": "枸杞子", "杭白菊": "菊花", "胎菊": "菊花", "贡菊": "菊花",
    "薏米": "薏苡仁", "米仁": "薏苡仁", "陈皮丝": "陈皮", "桂圆": "龙眼肉",
    "桂圆肉": "龙眼肉", "莲肉": "莲子", "山药干": "山药", "淮山": "山药",
}


def _norm(name: str) -> str:
    n = (name or "").strip()
    return _ALIAS.get(n, n)


def match(owned: list[str], constitution: str | None = None) -> dict:
    """返回 {have, suggestions: [...], partial: [...]}"""
    owned_set = {_norm(x) for x in owned if x and x.strip()}
    if not owned_set:
        return {"have": [], "suggestions": [], "partial": []}

    conn = _db()
    try:
        recipes = conn.execute(
            "SELECT id,name,type,oneliner,scenes,constitutions_suitable,duration,analysis_ready "
            "FROM recipe WHERE status != '弃用'").fetchall()
        mats_by_rid: dict[int, list[dict]] = {}
        for row in conn.execute(
                "SELECT recipe_id,name,optional FROM rel_recipe_material").fetchall():
            mats_by_rid.setdefault(row["recipe_id"], []).append(
                {"name": row["name"], "optional": bool(row["optional"])})
        hi_blood = {}
        for row in conn.execute(
                "SELECT recipe_id,top_compounds FROM recipe_analysis").fetchall():
            comps = json.loads(row["top_compounds"] or "[]")
            hi_blood[row["recipe_id"]] = sum(1 for c in comps if (c.get("prob_cctcm") or 0) >= 0.7)
    finally:
        conn.close()

    suggestions, partial = [], []
    for r in recipes:
        mats = mats_by_rid.get(r["id"], [])
        required = [m["name"] for m in mats if not m["optional"]]
        if not required:
            required = [m["name"] for m in mats]
        req_n = [_norm(x) for x in required]
        hit = [required[i] for i, n in enumerate(req_n) if n in owned_set]
        miss = [required[i] for i, n in enumerate(req_n) if n not in owned_set]
        cover = len(hit) / len(req_n) if req_n else 0
        item = {
            "id": r["id"], "name": r["name"], "type": r["type"], "oneliner": r["oneliner"],
            "scenes": json.loads(r["scenes"] or "[]"),
            "constitutions_suitable": json.loads(r["constitutions_suitable"] or "[]"),
            "duration": r["duration"], "analysis_ready": bool(r["analysis_ready"]),
            "hit": hit, "missing": miss,
            "coverage": round(cover, 3),
            "hi_blood_count": hi_blood.get(r["id"], 0),
        }
        if constitution and constitution not in item["constitutions_suitable"]:
            continue
        if cover >= 1.0:
            suggestions.append(item)
        elif cover >= 0.5:
            partial.append(item)

    suggestions.sort(key=lambda x: (-x["coverage"], len(x["missing"]), -x["hi_blood_count"]))
    partial.sort(key=lambda x: (-x["coverage"], len(x["missing"]), -x["hi_blood_count"]))
    return {"have": sorted(owned_set), "suggestions": suggestions[:30], "partial": partial[:20]}
