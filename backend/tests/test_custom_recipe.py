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


# ---------- 拍照识药（离线：模型调用用 monkeypatch 注入） ----------

def _fake_vision(monkeypatch, model_output):
    """替换模型的 HTTP 调用，返回给定的 JSON 字符串"""
    class _Resp:
        def __init__(self, text):
            self._text = text
        def raise_for_status(self):
            pass
        def json(self):
            return {"choices": [{"message": {"content": self._text}}]}
    monkeypatch.setattr(hs.requests, "post", lambda *a, **k: _Resp(model_output))


def test_recognize_filters_unverified_names(monkeypatch):
    """模型给的库外名字必须进 unverified，不能标成 verified"""
    _fake_vision(monkeypatch, '{"image_kind":"herb","items":['
                              '{"name":"金银花","grams":null,"confidence":0.9},'
                              '{"name":"龙须凤尾草","grams":null,"confidence":0.8}]}')
    r = hs.recognize_herb_image(b"fake-bytes")
    assert r["status"] == "ok"
    assert [i["name"] for i in r["items"] if i["verified"]] == ["金银花"]
    assert r["unverified"] == ["龙须凤尾草"]


def test_recognize_enriches_verified_items(monkeypatch):
    """入库的药材要回填中文性味与功效"""
    _fake_vision(monkeypatch, '{"image_kind":"herb","items":['
                              '{"name":"金银花","grams":null,"confidence":0.9}]}')
    r = hs.recognize_herb_image(b"fake-bytes")
    it = r["items"][0]
    assert it["verified"] is True
    assert it["properties_cn"] == "甘,寒"
    assert it["functions_cn"]


def test_recognize_normalizes_chinese_kind(monkeypatch):
    """模型偶尔吐中文 image_kind，要归一化成固定枚举"""
    _fake_vision(monkeypatch, '{"image_kind":"文本","items":['
                              '{"name":"菊花","grams":5,"confidence":1.0}]}')
    r = hs.recognize_herb_image(b"fake-bytes")
    assert r["image_kind"] == "text"


def test_recognize_drops_absurd_grams(monkeypatch):
    _fake_vision(monkeypatch, '{"image_kind":"text","items":['
                              '{"name":"甘草","grams":999,"confidence":0.9}]}')
    r = hs.recognize_herb_image(b"fake-bytes")
    assert r["items"][0]["grams"] is None


def test_recognize_bad_json_returns_error(monkeypatch):
    _fake_vision(monkeypatch, "这不是 JSON")
    r = hs.recognize_herb_image(b"fake-bytes")
    assert r["status"] == "error"


def test_recognize_empty_image():
    assert hs.recognize_herb_image(b"")["status"] == "error"


def test_recognize_endpoint_checks_mime_and_size():
    # 非图片类型
    r = client.post("/api/v1/custom-recipe/recognize-image",
                    files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 400
    # 空文件
    r = client.post("/api/v1/custom-recipe/recognize-image",
                    files={"file": ("x.jpg", b"", "image/jpeg")})
    assert r.status_code == 400
    # 超过 8MB
    big = b"\xff" * (hs.MAX_IMAGE_BYTES + 1)
    r = client.post("/api/v1/custom-recipe/recognize-image",
                    files={"file": ("x.jpg", big, "image/jpeg")})
    assert r.status_code == 413


# ---------- 联网搜索兜底（离线：模型调用用 monkeypatch 注入） ----------

def test_web_lookup_returns_sources_from_web_search(monkeypatch):
    """来源必须只取网关 web_search[]，正文不能替代来源"""
    class _Resp:
        def raise_for_status(self): pass
        def json(self):
            return {
                "choices": [{"message": {"content": "这东西有健脾祛湿的作用。"}}],
                "web_search": [
                    {"title": "五指毛桃的功效", "link": "https://example.com/a",
                     "publish_date": "2026-10-01"},
                    {"title": "祛湿食材", "link": "https://example.com/b"},
                ],
            }
    monkeypatch.setattr(hs.requests, "post", lambda *a, **k: _Resp())
    # 用不会被真实缓存命中的名字（web_lookup 有 30 天缓存，真实药名可能已缓存）
    r = hs.web_lookup_herb("测试用药材AAA")
    assert r["status"] == "ok"
    assert len(r["sources"]) == 2
    assert r["sources"][0]["url"] == "https://example.com/a"
    assert r["summary_cn"]


def test_web_lookup_no_sources_returns_no_result(monkeypatch):
    """web_search[] 为空 = 没搜到，必须如实报 no_result，不许产出无来源结果"""
    class _Resp:
        def raise_for_status(self): pass
        def json(self):
            return {"choices": [{"message": {"content": "我编一段话。"}}], "web_search": []}
    monkeypatch.setattr(hs.requests, "post", lambda *a, **k: _Resp())
    r = hs.web_lookup_herb("测试用药材BBB")
    assert r["status"] == "no_result"
    assert r["summary_cn"] is None
    assert r["sources"] == []


def test_web_lookup_service_error(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("gateway down")
    monkeypatch.setattr(hs.requests, "post", _boom)
    r = hs.web_lookup_herb("测试用药材CCC")
    assert r["status"] == "error"
    assert r["sources"] == []


def test_web_lookup_empty_name():
    assert hs.web_lookup_herb("")["status"] == "error"
    assert hs.web_lookup_herb("   ")["status"] == "error"


def test_web_lookup_endpoint_validation():
    assert client.post("/api/v1/custom-recipe/web-lookup", json={"name": ""}).status_code == 400
    assert client.post("/api/v1/custom-recipe/web-lookup",
                       json={"name": "药" * 51}).status_code == 400
