# -*- coding: utf-8 -*-
"""P0 改动单测：暴露量×入血概率合并（估计吸收暴露量）+ 靶点展示层仅人类蛋白。
直接跑在真实 shiyang.db 上（只读），用法：
    cd backend && python -X utf8 -m pytest tests/ -v
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

import main  # noqa: E402  (backend/app/main.py)

DB = APP_DIR.parents[1] / "data" / "shiyang.db"
client = TestClient(main.app)


def _db():
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# ---------- P0-1 暴露量 × 入血概率 ----------

def _recipe_with_exposure():
    """挑一个既有克重又有可匹配成分的方子 id"""
    conn = _db()
    try:
        row = conn.execute(
            "SELECT m.recipe_id FROM rel_recipe_material m "
            "JOIN herb_compound_content hc ON hc.herb_name=m.name "
            "JOIN compound c ON c.name=hc.compound_name "
            "WHERE m.material_type='herb' AND m.grams>0 LIMIT 1").fetchone()
        return row["recipe_id"] if row else None
    finally:
        conn.close()


def test_exposure_has_absorbed_fields():
    rid = _recipe_with_exposure()
    assert rid, "库里没有可测的方子（克重+含量+成分全链）"
    r = client.get(f"/api/v1/recipes/{rid}/exposure")
    assert r.status_code == 200
    data = r.json()["data"]
    items = data["items"]
    assert items, "暴露量结果为空"
    matched = [e for e in items if "absorbed_mg_max" in e]
    assert matched, "没有一条结果带上吸收期望字段（JOIN compound 失败？）"


def test_exposure_math_consistent():
    """absorbed = est × prob，区间单调，排序按 est_mg_max 降序"""
    rid = _recipe_with_exposure()
    data = client.get(f"/api/v1/recipes/{rid}/exposure").json()["data"]
    for e in data["items"]:
        if "absorbed_mg_max" in e:
            assert e["est_mg_min"] <= e["est_mg_max"]
            assert e["absorbed_mg_min"] <= e["absorbed_mg_max"]
            # absorbed 用全精度概率计算、est 与 absorbed 各自 round(…,2)，容差按比例放宽
            assert abs(e["absorbed_mg_max"] - e["est_mg_max"] * e["prob_cctcm"]) < 0.05
            assert 0.0 <= e["prob_cctcm"] <= 1.0
    mx = [e["est_mg_max"] for e in data["items"]]
    assert mx == sorted(mx, reverse=True), "items 未按 est_mg_max 降序"


def test_exposure_unmatched_compound_has_no_absorbed():
    """含量表里对不上 compound 主表的成分：应只有摄入量字段，不能有吸收期望"""
    rid = _recipe_with_exposure()
    data = client.get(f"/api/v1/recipes/{rid}/exposure").json()["data"]
    for e in data["items"]:
        if "absorbed_mg_max" not in e:
            assert "prob_cctcm" not in e, "无吸收期望却带概率，字段语义不一致"
    # 全库口径：含量表 3970 条里 41 个成分对不上主表，暴露量接口必须两者都兼容
    assert data["note"] and "入血概率" in data["note"], "note 未声明吸收期望为模型预测"


def test_exposure_recipe_not_found():
    assert client.get("/api/v1/recipes/99999/exposure").status_code == 404


# ---------- P0-2 靶点仅人类蛋白 ----------

def _analysis_recipe():
    conn = _db()
    try:
        row = conn.execute("SELECT recipe_id FROM recipe_analysis LIMIT 1").fetchone()
        return row["recipe_id"] if row else None
    finally:
        conn.close()


def test_network_targets_all_human():
    rid = _analysis_recipe()
    assert rid
    r = client.get(f"/api/v1/recipes/{rid}/network")
    assert r.status_code == 200
    data = r.json()["data"]
    genes = [n["name"] for n in data["nodes"] if n["category"] == 2]
    assert genes, "网络图没有任何靶点节点"
    conn = _db()
    try:
        ph = ",".join("?" * len(genes))
        bad = conn.execute(
            f"SELECT gene, species FROM target WHERE gene IN ({ph}) "
            f"AND species != 'Homo sapiens'", genes).fetchall()
    finally:
        conn.close()
    assert not bad, f"网络图混入非人类靶点: {[dict(b) for b in bad][:5]}"
    assert "人类蛋白" in (data.get("note") or ""), "note 未注明仅人类蛋白"


def test_open_compound_targets_default_human_only():
    """开放接口默认只出人类靶点，species=all 才含其他物种"""
    conn = _db()
    try:
        row = conn.execute(
            "SELECT c.name FROM rel_compound_target rc "
            "JOIN compound c ON c.id=rc.compound_id "
            "JOIN target t ON t.gene=rc.target_gene "
            "GROUP BY c.id HAVING SUM(t.species='Homo sapiens')>0 "
            f"AND SUM(t.species!='Homo sapiens')>0 LIMIT 1").fetchone()
    finally:
        conn.close()
    assert row, "库里找不到'既有人类又有非人类靶点关系'的成分来验证过滤"
    name = row["name"]
    r = client.get(f"/api/v1/open/compounds/{name}/targets")
    assert r.status_code == 200
    body = r.json()["data"]
    species = {t.get("target_species") for t in body["targets"]}
    assert species == {"Homo sapiens"}, f"默认查询混入非人类物种: {species}"
    assert "人类蛋白" in (body.get("note") or "")

    r_all = client.get(f"/api/v1/open/compounds/{name}/targets?species=all")
    assert r_all.status_code == 200
    species_all = {t.get("target_species") for t in r_all.json()["data"]["targets"]}
    assert len(species_all) > 1, "species=all 应包含非人物种"


# ---------- 证据等级回归（确保没被改坏） ----------

def test_evidence_levels_still_ok():
    r = client.get("/api/v1/evidence/levels")
    assert r.status_code == 200
    levels = r.json()["data"]["levels"]
    assert set(levels.keys()) == {"A", "B", "C"}
