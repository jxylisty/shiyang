# -*- coding: utf-8 -*-
"""
零覆盖服务补测：安全滤镜 / 我的茶罐 / 对比实验室 / 周期报告 / 节气。
运行：cd backend && python -X utf8 -m pytest tests/test_services_gap.py -q
（与既有测试同风格：TestClient 直调，不依赖网络；涉及登录态的用例
 依赖 tests/conftest.py 的兜底清理，测完即删）
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


# ---------- 安全滤镜（T1-5） ----------

def test_safety_profiles_list():
    d = _data(client.get("/api/v1/safety/profiles"))
    codes = {p["code"] for p in d["items"]}
    assert {"diabetes", "hypertension", "pregnant", "lactation", "children"} <= codes
    for p in d["items"]:
        assert p["name"] and p["desc"]


def test_safety_check_verdict_shape():
    # 随便挑一个有配料的方子，三种 verdict（block/warn/pass）都合法，字段要齐
    recipes = _data(client.get("/api/v1/recipes"))["items"]
    assert recipes
    d = _data(client.get(f"/api/v1/safety/check/{recipes[0]['id']}",
                         params={"profile": "pregnant"}))
    assert d["verdict"] in ("block", "warn", "pass")
    assert d["profile"] == "pregnant" and d["profile_name"] == "孕期"
    for b in d["blocks"] + d["warns"]:
        assert b["material"] and b["reason"]


def test_safety_check_unknown_profile_or_recipe():
    assert client.get("/api/v1/safety/check/1", params={"profile": "nope"}).status_code == 404
    assert client.get("/api/v1/safety/check/99999",
                      params={"profile": "pregnant"}).status_code == 404


def test_safety_check_batch_clamped_and_filter():
    recipes = _data(client.get("/api/v1/recipes"))["items"]
    ids = [r["id"] for r in recipes[:5]]
    d = _data(client.post("/api/v1/safety/check-batch",
                          json={"recipe_ids": ids, "profile": "diabetes"}))
    assert d["profile_name"] == "控糖期"
    # 每个返回项的三态字段齐
    for rid, r in d["results"].items():
        assert r["verdict"] in ("block", "warn", "pass")
    # 未知 profile → 404
    assert client.post("/api/v1/safety/check-batch",
                       json={"recipe_ids": ids, "profile": "nope"}).status_code == 404


# ---------- 我的茶罐（反向配伍） ----------

def test_pantry_match_empty_owned():
    d = _data(client.post("/api/v1/pantry/match", json={"owned": []}))
    assert d == {"have": [], "suggestions": [], "partial": []}


def test_pantry_materials_sorted_by_freq():
    d = _data(client.get("/api/v1/pantry/materials"))
    assert d["total"] > 0
    counts = [i["count"] for i in d["items"]]
    assert counts == sorted(counts, reverse=True)


def test_pantry_match_full_coverage_and_alias():
    # 用一个真实方子的配料全集勾选 → 必须出现在 suggestions 且 coverage=1
    recipes = _data(client.get("/api/v1/recipes"))["items"]
    detail = _data(client.get(f"/api/v1/recipes/{recipes[0]['id']}"))
    required = [m["name"] for m in detail["materials"] if not m["optional"]] or \
               [m["name"] for m in detail["materials"]]
    d = _data(client.post("/api/v1/pantry/match", json={"owned": required}))
    hit = next(s for s in d["suggestions"] if s["id"] == recipes[0]["id"])
    assert hit["coverage"] == 1.0 and hit["missing"] == []
    # 别名归一：勾「枸杞」应等价「枸杞子」（库内配料名）
    d2 = _data(client.post("/api/v1/pantry/match", json={"owned": ["枸杞"]}))
    assert "枸杞子" in d2["have"] or any("枸杞" in h for s in d2["suggestions"] + d2["partial"]
                                        for h in s["hit"])


# ---------- 对比实验室 ----------

def test_compare_requires_distinct_ids():
    assert client.get("/api/v1/recipes/compare", params={"a": 1, "b": 1}).status_code == 400


def test_compare_404_and_shape():
    assert client.get("/api/v1/recipes/compare",
                      params={"a": 99999, "b": 1}).status_code == 404
    recipes = _data(client.get("/api/v1/recipes"))["items"]
    ids = [r["id"] for r in recipes if r["analysis_ready"]][:2]
    if len(ids) < 2:
        return
    d = _data(client.get("/api/v1/recipes/compare", params={"a": ids[0], "b": ids[1]}))
    for key in ("compound", "target", "material", "radar", "constitution"):
        assert key in d
    c = d["compound"]
    # shared + only_a/b 与 jaccard 口径自洽
    union = len(c["shared"]) + len(c["only_a"]) + len(c["only_b"])
    expect = round(len(c["shared"]) / union, 3) if union else 0.0
    assert c["jaccard"] == expect
    assert c["overlap_label"] in ("高度重叠", "中度重叠", "部分重叠", "几乎不同")


# ---------- 周期报告（T2-7，需登录态） ----------

def test_report_cycle_requires_auth():
    assert client.get("/api/v1/report/cycle").status_code == 401


def test_report_cycle_empty_user_zero_counts():
    import time
    uname = f"t_rep_{int(time.time())}"
    assert client.post("/api/v1/auth/register",
                       json={"username": uname, "password": "test1234"}).status_code == 200
    token = client.post("/api/v1/auth/login",
                        json={"username": uname, "password": "test1234"}).json()["data"]["token"]
    d = _data(client.get("/api/v1/report/cycle", headers={"Authorization": f"Bearer {token}"}))
    assert d["checkin_days"] == 0 and d["recipes_tried"] == 0
    assert d["period_days"] == 21 and len(d["wall"]) == 21
    assert d["note"]  # 参考口径说明必须在
    # 清理交给 conftest 兜底 fixture（本用例未走收藏/打卡）


# ---------- 节气（T2-9） ----------

def test_term_current_shape():
    d = _data(client.get("/api/v1/term/current"))
    cur = d["current"]
    assert cur["name"] and cur["date"] and cur["theme"]["scene"]
    assert isinstance(d["upcoming"], list) and d["recipes"] is not None
    # 钳制：count 超上限不炸
    assert client.get("/api/v1/term/current", params={"count": 99}).status_code == 200
