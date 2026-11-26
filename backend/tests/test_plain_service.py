# -*- coding: utf-8 -*-
"""「说人话」白话解读（plain_service）测试：校验逻辑 + 两个端点。模型调用全部 mock，不依赖网关。"""
import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import main  # noqa: E402
from services import plain_service as plain  # noqa: E402

GOOD = {
    "headline": "一杯偏清凉的护嗓茶",
    "suits": "嗓子干的时候喝比较舒服",
    "caution": "脾胃虚寒的人少喝",
    "ingredients": [{"name": "菊花", "role": "帮身体降降火（清热）"},
                    {"name": "人参", "role": "模型编出来的配料"}],
}


def test_validate_ok_and_filters_unknown_ingredient():
    out = plain.parse_and_validate("```json\n" + json.dumps(GOOD, ensure_ascii=False) + "\n```", ["菊花"])
    assert out["headline"] == GOOD["headline"]
    assert [i["name"] for i in out["ingredients"]] == ["菊花"]  # 越界配料被剔除


@pytest.mark.parametrize("word", ["治疗", "抗癌", "疗效"])
def test_validate_rejects_banned_words(word):
    bad = dict(GOOD, suits=f"可以{word}咽炎")
    with pytest.raises(ValueError):
        plain.parse_and_validate(json.dumps(bad, ensure_ascii=False), ["菊花"])


def test_validate_rejects_missing_field():
    bad = {k: v for k, v in GOOD.items() if k != "caution"}
    with pytest.raises(ValueError):
        plain.parse_and_validate(json.dumps(bad, ensure_ascii=False), ["菊花"])


def test_recipe_plain_endpoint_reads_json(tmp_path, monkeypatch):
    f = tmp_path / "plain.json"
    f.write_text(json.dumps({"items": {"1": {"content": GOOD, "model": "m", "reviewed": False}}},
                            ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(plain, "PLAIN_JSON", f)
    monkeypatch.setattr(plain, "_cache", None)
    c = TestClient(main.app)
    d = c.get("/api/v1/recipes/1/plain").json()
    assert d["data"]["source"] == "ai" and d["data"]["reviewed"] is False
    assert d["disclaimer"] == main.DISCLAIMER
    assert c.get("/api/v1/recipes/999999/plain").json()["data"] is None


def test_custom_plain_endpoint(monkeypatch):
    calls = []

    def fake(payload, api_key=None, **kwargs):
        calls.append(payload)
        return json.dumps(GOOD, ensure_ascii=False)

    monkeypatch.setattr(plain, "_call_model", fake)
    monkeypatch.setattr(plain, "_custom_cache", {})
    c = TestClient(main.app)
    body = {"herbs": [{"name": "菊花", "grams": 5, "functions": "疏散风热，平肝明目"}]}
    r = c.post("/api/v1/custom-recipe/plain", json=body)
    assert r.status_code == 200
    assert r.json()["data"]["source"] == "ai"
    assert "预测" not in json.dumps(calls[0], ensure_ascii=False)  # 不喂预测值
    c.post("/api/v1/custom-recipe/plain", json=body)
    assert len(calls) == 1  # 相同组合命中缓存


def test_custom_plain_model_failure_returns_existing_references(monkeypatch):
    monkeypatch.setattr(plain, "_call_model", lambda *a, **k: "不是 JSON")
    monkeypatch.setattr(plain, "_custom_cache", {})
    c = TestClient(main.app)
    r = c.post("/api/v1/custom-recipe/plain", json={"herbs": [{"name": "菊花"}]})
    assert r.status_code == 200
    assert r.json()["data"]["source"] == "reference"


def test_preview_plain_uses_database_references_without_calling_model(monkeypatch):
    monkeypatch.setenv("SHIYANG_CUSTOM_PLAIN_REFERENCE_ONLY", "1")
    monkeypatch.setattr(plain, "_call_model", lambda *a, **k: pytest.fail("model called in preview"))
    monkeypatch.setattr(main.herb_svc, "cached_reference_details", lambda names: [
        {"name_cn": "菊花", "functions_cn": "清热、平肝明目", "functions_cn_source": "curated"},
    ], raising=False)
    c = TestClient(main.app)
    data = c.post("/api/v1/custom-recipe/plain", json={"herbs": [
        {"name": "菊花", "functions": "不会核验的客户端文案"},
        {"name": "库外药材", "functions": "降糖"},
    ]}).json()["data"]
    assert data["source"] == "reference"
    assert [i["name"] for i in data["ingredients"]] == ["菊花"]
    assert "清热" in data["ingredients"][0]["role"]
    assert "库外药材" not in json.dumps(data, ensure_ascii=False)


def test_preview_analyze_includes_plain_reference_card(monkeypatch):
    monkeypatch.setenv("SHIYANG_CUSTOM_PLAIN_REFERENCE_ONLY", "1")
    monkeypatch.setattr(plain, "_call_model", lambda *a, **k: pytest.fail("model called in preview"))
    monkeypatch.setattr(main.herb_svc, "analyze_recipe", lambda *a, **k: {
        "status": "ok", "herbs": [{"name_cn": "陈皮", "functions_cn": "理气健脾",
                                    "functions_cn_source": "curated"}],
        "not_found": ["库外药材"],
    })
    c = TestClient(main.app)
    data = c.post("/api/v1/custom-recipe/analyze",
                  json={"herbs": [{"name": "陈皮"}, {"name": "库外药材"}]}).json()["data"]
    assert data["plain"]["source"] == "reference"
    assert [i["name"] for i in data["plain"]["ingredients"]] == ["陈皮"]
    assert data["not_found"] == ["库外药材"]


def test_cached_references_exclude_negative_matches(monkeypatch):
    monkeypatch.setattr(main.herb_svc, "_kb_herb_dict", lambda: {})
    cached = {
        "人参": {"herb_name": "人参", "herb_id": "HERB1", "function_en": "To reinforce the vital energy."},
        "玛咖": {"herb_name": "玛咖", "herb_id": None},
    }
    monkeypatch.setattr(main.herb_svc, "_cache_get", cached.get)
    card = plain.custom_reference(main.herb_svc.cached_reference_details(["人参", "玛咖"]))
    assert [item["name"] for item in card["ingredients"]] == ["人参"]
