# -*- coding: utf-8 -*-
"""
全局搜索服务：一次关键词聚合查三类实体（方子/药材/成分），各取前 5 条
- 数据型产品基本功：顶栏统一入口，替代三页各自的局部搜索
- SQL 全部参数化 LIKE；q 为空或去空白后为空返回空分组
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "shiyang.db"

LIMIT = 5


def _db():
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def global_search(q: str) -> dict:
    q = (q or "").strip()
    empty = {"query": q, "recipes": [], "herbs": [], "compounds": []}
    if not q:
        return empty
    kw = f"%{q}%"
    conn = _db()
    try:
        recipes = conn.execute(
            "SELECT id,name,type,oneliner,scenes,constitutions_suitable "
            "FROM recipe WHERE name LIKE ? AND status != '弃用' "
            "ORDER BY analysis_ready DESC, id LIMIT ?",
            (kw, LIMIT)).fetchall()
        herbs = conn.execute(
            "SELECT id,name,category,nature,flavor,functions,compound_count "
            "FROM herb WHERE name LIKE ? OR pinyin LIKE ? "
            "ORDER BY compound_count DESC LIMIT ?",
            (kw, f"{q}%", LIMIT)).fetchall()
        compounds = conn.execute(
            "SELECT id,name,mw,logp,prob_cctcm,target_count "
            "FROM compound WHERE name LIKE ? AND prob_cctcm IS NOT NULL "
            "ORDER BY prob_cctcm DESC LIMIT ?",
            (kw, LIMIT)).fetchall()
    finally:
        conn.close()
    return {
        "query": q,
        "recipes": [dict(r) for r in recipes],
        "herbs": [dict(r) for r in herbs],
        "compounds": [dict(r) for r in compounds],
    }
