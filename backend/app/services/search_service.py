# -*- coding: utf-8 -*-
"""
全局搜索服务：一次关键词聚合查三类实体（方子/药材/成分），各取前 5 条
- 数据型产品基本功：顶栏统一入口，替代三页各自的局部搜索
- SQL 全部参数化 LIKE；q 为空或去空白后为空返回空分组
- 搜索域：方子=名称/一句话/场景/配料名；药材=名称/拼音/别名/功效；成分=名称
  命中来源以 matched_by 标注（如「配料含枸杞」「别名」），让用户知道为什么出这条
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "shiyang.db"

LIMIT = 5  # 顶栏下拉默认每类条数；端点可传 limit 覆盖（独立搜索页用大值）


def _db():
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _search_recipes(conn, q: str, kw: str, limit: int = LIMIT) -> list:
    """方子按 名称/一句话/场景/配料名 匹配，标注 matched_by"""
    rows = conn.execute(
        "SELECT id,name,type,oneliner,scenes,constitutions_suitable FROM recipe "
        "WHERE status != '弃用' AND (name LIKE ? OR oneliner LIKE ? OR scenes LIKE ? "
        "OR id IN (SELECT recipe_id FROM rel_recipe_material WHERE name LIKE ?)) "
        "ORDER BY analysis_ready DESC, id LIMIT ?",
        (kw, kw, kw, kw, limit)).fetchall()
    out = []
    for r in rows:
        matched = []
        if q in (r["name"] or ""):
            matched.append("名称")
        if q in (r["oneliner"] or ""):
            matched.append("简介")
        if q in (r["scenes"] or ""):
            scenes = r["scenes"] or ""
            hit = [s for s in scenes.replace("[", ",").replace("]", ",").replace('"', ",").split(",") if s.strip() and q in s]
            if hit:
                matched.append(f"场景·{hit[0]}")
        if not matched:
            mat = conn.execute(
                "SELECT name FROM rel_recipe_material WHERE recipe_id=? AND name LIKE ? "
                "ORDER BY id LIMIT 1", (r["id"], kw)).fetchone()
            if mat:
                matched.append(f"配料含{mat['name']}")
        out.append({**dict(r), "matched_by": "、".join(matched) if matched else ""})
    return out


def _search_herbs(conn, q: str, kw: str, limit: int = LIMIT) -> list:
    """药材按 名称/拼音/别名/功效 匹配，标注 matched_by"""
    rows = conn.execute(
        "SELECT id,name,category,nature,flavor,functions,compound_count,alias "
        "FROM herb WHERE name LIKE ? OR pinyin LIKE ? OR alias LIKE ? OR functions LIKE ? "
        "ORDER BY compound_count DESC LIMIT ?",
        (kw, f"{q}%", kw, kw, limit)).fetchall()
    out = []
    for r in rows:
        matched = []
        if q in (r["name"] or ""):
            matched.append("名称")
        else:
            # 别名/功效是「、」或「，」分隔的词串，按词命中才标注具体词
            fields = (r["alias"] or "") + "、" + (r["functions"] or "")
            parts = [p.strip() for p in fields.replace("，", "、").split("、") if p.strip()]
            hit = next((p for p in parts if q in p), None)
            if hit and hit in (r["alias"] or ""):
                matched.append(f"别名·{hit}")
            elif hit:
                matched.append(f"功效·{hit}")
        out.append({**dict(r), "matched_by": "、".join(matched)})
    return out


def global_search(q: str, limit: int = LIMIT) -> dict:
    q = (q or "").strip()
    empty = {"query": q, "recipes": [], "herbs": [], "compounds": []}
    if not q:
        return empty
    kw = f"%{q}%"
    conn = _db()
    try:
        recipes = _search_recipes(conn, q, kw, limit)
        herbs = _search_herbs(conn, q, kw, limit)
        compounds = conn.execute(
            "SELECT id,name,mw,logp,prob_cctcm,target_count "
            "FROM compound WHERE name LIKE ? AND prob_cctcm IS NOT NULL "
            "ORDER BY prob_cctcm DESC LIMIT ?",
            (kw, limit)).fetchall()
    finally:
        conn.close()
    return {
        "query": q,
        "recipes": recipes,
        "herbs": herbs,
        "compounds": [dict(c) for c in compounds],
    }
