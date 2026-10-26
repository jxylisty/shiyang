# -*- coding: utf-8 -*-
"""
全局搜索 + 成分词典 + 食材营养（补五脏迭代）接口测试
运行：python -m pytest backend/tests/test_search_and_compound.py -q
（与 test_p0_evidence_chain.py 同风格：直接调 service/用 TestClient，不依赖网络）
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

client = TestClient(app)


def _data(resp):
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0
    return body["data"]


# ---------- 全局搜索 ----------

def test_search_empty_q():
    d = _data(client.get("/api/v1/search"))
    assert d["recipes"] == [] and d["herbs"] == [] and d["compounds"] == []


def test_search_aggregates_three_groups():
    # 单字「菊」应同时命中方子（菊花类茶饮）、药材（菊花）、可能无成分
    d = _data(client.get("/api/v1/search", params={"q": "菊"}))
    assert isinstance(d["recipes"], list) and len(d["recipes"]) <= 5
    assert any("菊" in h["name"] for h in d["herbs"])
    for r in d["recipes"]:
        assert r["id"] and r["name"]


def test_search_no_hit():
    d = _data(client.get("/api/v1/search", params={"q": "不存在的关键词xyz"}))
    assert d["recipes"] == [] and d["herbs"] == [] and d["compounds"] == []


def test_search_recipe_matched_by_material():
    # 期望值从库实时构造（数据重建不碎）：任取一味配料名，应能搜到含它的方子且 matched_by 标注配料
    import sqlite3
    from services.explain_service import DB_PATH
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    row = conn.execute(
        "SELECT m.name, r.name FROM rel_recipe_material m JOIN recipe r ON r.id=m.recipe_id "
        "WHERE r.status != '弃用' AND m.name NOT IN (SELECT name FROM recipe) LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return  # 库无配料数据则跳过
    mat_name, _ = row
    d = _data(client.get("/api/v1/search", params={"q": mat_name}))
    hit = [r for r in d["recipes"] if mat_name in r.get("matched_by", "")]
    assert hit, f"配料名「{mat_name}」应命中至少一个方子并标注 matched_by"


def test_search_herb_matched_by_alias_or_function():
    # 找一个仅靠别名或功效（非名称/拼音）命中的药材来验证扩域
    import sqlite3
    from services.explain_service import DB_PATH
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    rows = conn.execute(
        "SELECT name, alias, functions FROM herb WHERE alias IS NOT NULL AND alias != ''").fetchall()
    conn.close()
    target = None
    for name, alias, funcs in rows:
        alias_parts = [a.strip() for a in (alias or "").replace("，", ",").replace("、", ",").split(",") if a.strip()]
        func_parts = [f.strip() for f in (funcs or "").replace("，", ",").replace(";", ";").split(",") if f.strip()]
        for part in alias_parts + func_parts:
            if part not in name and len(part) >= 2:
                target = (name, part)
                break
        if target:
            break
    if not target:
        return  # 无可用别名/功效语料则跳过
    herb_name, part = target
    d = _data(client.get("/api/v1/search", params={"q": part}))
    assert any(h["name"] == herb_name for h in d["herbs"]), \
        f"药材「{herb_name}」应通过别名/功效「{part}」被搜到"


# ---------- 成分词典（explain 扩展字段） ----------

def _any_compound_name():
    from services.search_service import global_search
    # 借搜索找一个真实成分名：直接查库取一个高概率成分
    import sqlite3
    from services.explain_service import DB_PATH
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    row = conn.execute(
        "SELECT c.name FROM compound c JOIN rel_compound_target rc ON rc.compound_id=c.id "
        "WHERE c.prob_cctcm >= 0.5 LIMIT 1").fetchone()
    conn.close()
    return row[0]


def test_explain_compound_has_recipes_and_targets():
    name = _any_compound_name()
    d = _data(client.get("/api/v1/explain/compound", params={"name": name}))
    assert d["name"] == name
    # 新增字段：出现在哪些方子 + 关联靶点
    assert "recipes" in d and "targets" in d
    for r in d["recipes"]:
        assert {"id", "name", "type"} <= set(r)
    if d["targets"]:
        assert {"gene", "target_type"} <= set(d["targets"][0])
    # 原有字段不受影响
    assert "features" in d and "band" in d


def test_explain_compound_404():
    resp = client.get("/api/v1/explain/compound", params={"name": "不存在的成分"})
    assert resp.status_code == 404


# ---------- 食材营养 ----------

def test_foods_list_has_nutrient():
    d = _data(client.get("/api/v1/foods"))
    assert d["total"] > 0
    with_nutri = [i for i in d["items"] if i["has_nutrient"]]
    assert with_nutri, "营养素数据未填充（先跑 scripts/fill_nutrients.py）"
    n = with_nutri[0]["nutrient"]
    assert "source" in n  # 口径标注必须存在


def test_recipe_detail_materials_nutrient_field():
    # 找一个含 food 型配料的方子验证 nutrient 字段下发
    import sqlite3
    from services.explain_service import DB_PATH
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    row = conn.execute(
        "SELECT recipe_id FROM rel_recipe_material WHERE material_type='food' AND food_id IS NOT NULL LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        return  # 库里没有 food 型配料则跳过
    d = _data(client.get(f"/api/v1/recipes/{row[0]}"))
    foods = [m for m in d["materials"] if m["material_type"] == "food"]
    assert foods
    assert "nutrient" in foods[0]  # 可为 None（未收录营养数据的条目）
