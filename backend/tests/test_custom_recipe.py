# -*- coding: utf-8 -*-
"""
自定义鉴方：中文性味归经补全 + 粘贴文案解析的离线单测。
运行：cd backend && python -X utf8 -m pytest tests/test_custom_recipe.py -q

这些用例**不联网**：只测本地知识库 / SymMap 匹配逻辑与参数校验，
AI 相关路径用 monkeypatch 替换，避免测试依赖外部网关。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402
from services import herb_service as hs  # noqa: E402

client = TestClient(app)


def _data(resp):
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["code"] == 0
    return body["data"]


# ---------- SymMap / 本地库匹配 ----------

def test_symmap_lookup_exact_and_suffix():
    smap = hs._symmap_dict()
    assert smap, "SymMap 字典为空：data/symmap_smhb_v2.xlsx 缺失？"
    # 正名精确
    assert hs._lookup_symmap("金银花", smap)["properties_cn"] == "甘,寒"
    # 后缀兜底：枸杞 → 枸杞子
    assert hs._lookup_symmap("枸杞", smap) is not None
    # 前缀剥离：鲜芦根 → 芦根
    assert hs._lookup_symmap("鲜芦根", smap) is not None


def test_symmap_lookup_no_false_positive():
    """查不到的药必须返回 None，不能模糊配到不相干的药"""
    smap = hs._symmap_dict()
    for bogus in ("龙须凤尾草", "紫霞仙草", "完全不存在的药"):
        assert hs._lookup_symmap(bogus, smap) is None


def test_enrich_prefers_curated_kb():
    """本地策展库优先于 SymMap，且带出中文功效"""
    r = hs._enrich_with_symmap({"name_cn": "金银花"})
    assert r["functions_cn"] == "清热、解毒、散风热"
    assert r["functions_cn_source"] == "curated"
    assert r["properties_cn"] == "甘,寒"


def test_enrich_unmatched_returns_none_fields():
    r = hs._enrich_with_symmap({"name_cn": "龙须凤尾草"})
    assert r["properties_cn"] is None
    assert r["meridians_cn"] is None
    assert r["functions_cn"] is None
    assert r["functions_cn_source"] is None


# ---------- 粘贴文案解析：模型输出必须经本地复核 ----------

def test_parse_rejects_hallucinated_names(monkeypatch):
    """模型编出来的药名必须进 rejected，不能混进 herbs"""
    fake = '[{"name":"龙须凤尾草","grams":20},{"name":"金银花","grams":10}]'
    monkeypatch.setattr(hs, "_call_parse_model", lambda text, api_key: fake)
    r = hs.parse_formula_text("测试文案")
    assert [h["name"] for h in r["herbs"]] == ["金银花"]
    assert [x["name"] for x in r["rejected"]] == ["龙须凤尾草"]


def test_parse_rejects_absurd_grams(monkeypatch):
    fake = '[{"name":"金银花","grams":500},{"name":"菊花","grams":5}]'
    monkeypatch.setattr(hs, "_call_parse_model", lambda text, api_key: fake)
    r = hs.parse_formula_text("测试文案")
    assert [h["name"] for h in r["herbs"]] == ["菊花"]
    assert "合理范围" in r["rejected"][0]["reason"]


def test_parse_empty_text_returns_error():
    r = hs.parse_formula_text("")
    assert r["ok"] is False and r["herbs"] == []


# ---------- 端点参数校验 ----------

def test_parse_text_endpoint_validation():
    assert client.post("/api/v1/custom-recipe/parse-text", json={"text": "  "}).status_code == 400
    assert client.post("/api/v1/custom-recipe/parse-text",
                       json={"text": "药" * 2001}).status_code == 400


def test_analyze_endpoint_requires_herbs():
    assert client.post("/api/v1/custom-recipe/analyze", json={"herbs": []}).status_code == 400
    too_many = [{"name": f"药{i}"} for i in range(21)]
    assert client.post("/api/v1/custom-recipe/analyze",
                       json={"herbs": too_many}).status_code == 400
