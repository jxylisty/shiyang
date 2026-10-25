# -*- coding: utf-8 -*-
"""
开放数据 API（T1-6）：只读、免鉴权的公共数据子路由 /api/v1/open/*
定位：把 106 种药食同源目录 × 药材 × 化合物 × 靶点数据以稳定 JSON 接口开放，
供科研/教学复用（挑战杯与大创材料的「开放共享」亮点）。
所有端点返回统一 envelope {code, message, data}，并在 meta 里带数据版本与许可说明。
"""
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "shiyang.db"

router = APIRouter(prefix="/api/v1/open", tags=["open-data"])

LICENSE = {
    "data_license": "CC BY-NC-SA 4.0（数据汇编；原始条目版权归原作者/数据库所有）",
    "cite": "食养有据 · 药食同源食疗成分分析平台（大创课题「中药入血成分预测」）",
    "disclaimer": "内容为健康参考信息，不构成医疗建议；入血概率为模型预测值。",
}


def _db():
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _meta(n_items: int = 0) -> dict:
    return {"generated_at": datetime.now().isoformat(timespec="seconds"),
            "items": n_items, **LICENSE}


@router.get("")
def index():
    """自描述索引：列出全部开放端点"""
    endpoints = {
        "catalog": "/api/v1/open/catalog —— 卫健委药食同源目录（106 种，含批次与异名）",
        "herbs": "/api/v1/open/herbs —— 药材库（性味归经/功效/化合物数/目录归属）",
        "compounds": "/api/v1/open/compounds —— 化合物库（MW/logP/入血概率/三维评分，可 min_prob 过滤）",
        "compounds/{name}/targets": "/api/v1/open/compounds/{name}/targets —— 单化合物作用靶点（含数据源与 PMID）",
        "constitutions": "/api/v1/open/constitutions —— 九种体质（宜忌食物/茶饮思路/调养原则）",
        "stats": "/api/v1/open/stats —— 库存统计",
        "snapshot": "/api/v1/open/snapshot —— 全量数据集打包（catalog+herbs+compounds 一次拉取）",
    }
    return {"code": 0, "message": "食养有据开放数据 API", "data": {"endpoints": endpoints, **LICENSE}}


@router.get("/catalog")
def catalog():
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT id,name,pinyin,alias,latin_name,nature,flavor,meridians,functions,"
            "food_catalog_batch FROM herb WHERE food_catalog_batch IS NOT NULL ORDER BY food_catalog_batch,name"
        ).fetchall()
    finally:
        conn.close()
    items = [dict(r) | {"alias": [a for a in (r["alias"] or "").replace("；", ";").split(";") if a]}
             for r in rows]
    return {"code": 0, "message": "success",
            "data": {"items": items}, "meta": _meta(len(items))}


@router.get("/herbs")
def herbs(limit: int = 300):
    limit = max(1, min(limit, 500))
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT id,name,pinyin,category,nature,flavor,meridians,functions,dosage,"
            "contraindication,compound_count,is_food_homology,food_catalog_batch "
            "FROM herb ORDER BY compound_count DESC LIMIT ?", (limit,)).fetchall()
    finally:
        conn.close()
    items = [dict(r) for r in rows]
    return {"code": 0, "message": "success", "data": {"items": items}, "meta": _meta(len(items))}


@router.get("/compounds")
def compounds(min_prob: float = 0.0, limit: int = 200):
    min_prob = max(0.0, min(min_prob, 1.0))
    limit = max(1, min(limit, 500))
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT id,name,mw,logp,prob_cctcm,prob_herb,"
            "radar_anti_inflammatory,radar_immune_regulation,radar_airway_repair,target_count "
            "FROM compound WHERE prob_cctcm>=? ORDER BY prob_cctcm DESC LIMIT ?",
            (min_prob, limit)).fetchall()
    finally:
        conn.close()
    items = [dict(r) for r in rows]
    return {"code": 0, "message": "success",
            "data": {"query": {"min_prob": min_prob, "limit": limit}, "items": items},
            "meta": _meta(len(items))}


@router.get("/compounds/{name}/targets")
def compound_targets(name: str):
    conn = _db()
    try:
        row = conn.execute("SELECT id,name,mw,logp,prob_cctcm FROM compound WHERE name=?", (name,)).fetchone()
        if not row:
            conn.close()
            raise HTTPException(404, "化合物不存在")
        links = conn.execute(
            "SELECT target_gene,activity_type,activity_value,activity_unit,reference,source_db "
            "FROM rel_compound_target WHERE compound_id=?", (row["id"],)).fetchall()
    finally:
        conn.close()
    items = [dict(l) | ({"pmid": l["reference"], "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{l['reference']}/"}
                        if (l["reference"] or "").isdigit() else {})
             for l in links]
    return {"code": 0, "message": "success",
            "data": {"compound": dict(row), "targets": items}, "meta": _meta(len(items))}


@router.get("/constitutions")
def constitutions():
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT code,name,typical_signs,principle,foods_suitable,foods_avoid,tea_ideas,lifestyle "
            "FROM constitution ORDER BY code").fetchall()
    finally:
        conn.close()
    items = [dict(r) for r in rows]
    return {"code": 0, "message": "success", "data": {"items": items}, "meta": _meta(len(items))}


@router.get("/stats")
def stats():
    conn = _db()
    try:
        out = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
               for t in ("herb", "compound", "target", "food", "recipe", "constitution")}
        out["catalog_herbs"] = conn.execute(
            "SELECT COUNT(*) FROM herb WHERE food_catalog_batch IS NOT NULL").fetchone()[0]
        out["compound_target_links"] = conn.execute(
            "SELECT COUNT(*) FROM rel_compound_target").fetchone()[0]
    finally:
        conn.close()
    return {"code": 0, "message": "success", "data": out, "meta": _meta()}


@router.get("/snapshot")
def snapshot():
    """全量数据集一次拉取（供论文/复现；约几 MB）"""
    conn = _db()
    try:
        herbs = [dict(r) for r in conn.execute(
            "SELECT id,name,pinyin,nature,flavor,meridians,functions,food_catalog_batch FROM herb")]
        compounds = [dict(r) for r in conn.execute(
            "SELECT id,name,mw,logp,prob_cctcm,prob_herb,target_count FROM compound")]
        links = [dict(r) for r in conn.execute(
            "SELECT compound_id,target_gene,source_db,reference FROM rel_compound_target")]
    finally:
        conn.close()
    data = {"herbs": herbs, "compounds": compounds, "compound_target_links": links}
    n = len(herbs) + len(compounds) + len(links)
    resp = JSONResponse({"code": 0, "message": "success", "data": data, "meta": _meta(n)})
    resp.headers["Content-Disposition"] = 'attachment; filename="shiyang-open-snapshot.json"'
    return resp
