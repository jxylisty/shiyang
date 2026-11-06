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
    """替换模型的 HTTP 调用，返回给定的输出（OCR 场景是纯文本，不是 JSON）"""
    class _Resp:
        def __init__(self, text):
            self._text = text
        def raise_for_status(self):
            pass
        def json(self):
            return {"choices": [{"message": {"content": self._text}}]}
    monkeypatch.setattr(hs.requests, "post", lambda *a, **k: _Resp(model_output))


def test_ocr_returns_raw_text(monkeypatch):
    """OCR 只负责把文字抄出来，原样返回"""
    raw = "代茶饮方\n金银花 10g 菊花 5g\n枸杞 8g 陈皮 6g\n甘草 3g"
    _fake_vision(monkeypatch, raw)
    r = hs.extract_text_from_image(b"fake-bytes")
    assert r["status"] == "ok"
    assert "金银花" in r["text"] and "10g" in r["text"]


def test_ocr_strips_code_fence(monkeypatch):
    _fake_vision(monkeypatch, "```\n金银花 10g\n```")
    r = hs.extract_text_from_image(b"fake-bytes")
    assert r["status"] == "ok"
    assert r["text"].startswith("金银花")


def test_ocr_empty_text_returns_no_text(monkeypatch):
    """图里没字（如药材实物照）→ no_text，不瞎猜"""
    _fake_vision(monkeypatch, "")
    r = hs.extract_text_from_image(b"fake-bytes")
    assert r["status"] == "no_text"
    assert r["text"] is None


def test_ocr_service_error(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("gateway down")
    monkeypatch.setattr(hs.requests, "post", _boom)
    r = hs.extract_text_from_image(b"fake-bytes")
    assert r["status"] == "error"
    # 不能泄露内部服务地址
    assert "7863" not in (r["error"] or "")
    assert "127.0.0.1" not in (r["error"] or "")


def test_ocr_empty_image():
    assert hs.extract_text_from_image(b"")["status"] == "error"


def test_parse_image_reuses_formula_parser(monkeypatch):
    """OCR 出文字后必须复用 parse_formula_text 的复核逻辑（库外名字被拒）"""
    # 第一次调用是 OCR，其余是 parse_formula_text 的模型调用
    outputs = iter([
        "金银花 10g 龙须凤尾草 15g",       # OCR 结果
        '[{"name":"金银花","grams":10},{"name":"龙须凤尾草","grams":15}]',  # 抽取结果
    ])

    class _Resp:
        def __init__(self, text):
            self._text = text
        def raise_for_status(self):
            pass
        def json(self):
            return {"choices": [{"message": {"content": self._text}}]}

    monkeypatch.setattr(hs.requests, "post", lambda *a, **k: _Resp(next(outputs)))
    # 复核阶段会联网查 HERB，测试里挡掉：库外名字直接判不存在
    monkeypatch.setattr(hs, "_name_exists_locally", lambda n: n == "金银花")
    monkeypatch.setattr(hs, "get_herb_detail",
                        lambda n: {"status": "not_found", "name_cn": n})
    r = hs.parse_recipe_image(b"fake-bytes")
    assert r["status"] == "ok"
    assert [h["name"] for h in r["herbs"]] == ["金银花"]
    assert [x["name"] for x in r["rejected"]] == ["龙须凤尾草"]
    assert "龙须凤尾草" in r["text"]


def test_parse_image_no_text_short_circuits(monkeypatch):
    """OCR 没认到字 → 直接返回 no_text，不再浪费一次模型调用"""
    _fake_vision(monkeypatch, "")
    r = hs.parse_recipe_image(b"fake-bytes")
    assert r["status"] == "no_text"
    assert r["herbs"] == []


def test_parse_image_no_herbs(monkeypatch):
    """有字但没药名 → no_herbs（与 no_text 区分开，前端提示不同）"""
    outputs = iter([
        "今日天气晴，气温 20 度",     # OCR
        "[]",                        # 抽取结果：没有药材
    ])

    class _Resp:
        def __init__(self, text):
            self._text = text
        def raise_for_status(self):
            pass
        def json(self):
            return {"choices": [{"message": {"content": self._text}}]}

    monkeypatch.setattr(hs.requests, "post", lambda *a, **k: _Resp(next(outputs)))
    r = hs.parse_recipe_image(b"fake-bytes")
    assert r["status"] == "no_herbs"
    assert r["text"]


def test_parse_image_endpoint_checks_mime_and_size():
    # 非图片类型
    r = client.post("/api/v1/custom-recipe/parse-image",
                    files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 400
    # 空文件
    r = client.post("/api/v1/custom-recipe/parse-image",
                    files={"file": ("x.jpg", b"", "image/jpeg")})
    assert r.status_code == 400
    # 超过 8MB
    big = b"\xff" * (hs.MAX_IMAGE_BYTES + 1)
    r = client.post("/api/v1/custom-recipe/parse-image",
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


# ---------- OCR 形近字纠错（解决「认错一个字，后面全错」） ----------

def test_correct_name_fixes_confusable_chars():
    """形近字错认要能纠正回正确药名"""
    cases = [("金银化", "金银花"), ("簿荷", "薄荷"), ("甘革", "甘草"),
             ("麦各", "麦冬"), ("黄茂", "黄芪"), ("获苓", "茯苓"),
             ("决名子", "决明子"), ("山查", "山楂")]
    for wrong, expect in cases:
        r = hs.correct_herb_name(wrong)
        assert r["name"] == expect, f"{wrong} 应纠正为 {expect}，实际 {r['name']}"
        assert r["corrected"] is True


def test_correct_name_never_touches_valid_names():
    """已在词表里的正确药名绝不能被改（零误纠正是最重要的安全指标）"""
    good = ["金银花", "陈皮", "山楂", "茯苓", "甘草", "薄荷", "菊花", "黄芪",
            "枸杞子", "决明子", "麦冬", "生姜", "红枣", "乌梅", "党参", "山药",
            "百合", "莲子", "银耳", "蜂蜜", "葛根", "荷叶", "桑椹", "胖大海",
            "西洋参", "石斛", "桂圆", "薏苡仁", "白术", "当归", "桂枝", "紫苏"]
    for g in good:
        r = hs.correct_herb_name(g)
        assert r["name"] == g and r["corrected"] is False, f"{g} 被误改为 {r['name']}"


def test_correct_name_rejects_unrelated_substitution():
    """毫不相干的字被硬换（桂圆→桂枝）必须拒绝，宁可不动也不瞎猜"""
    r = hs.correct_herb_name("桂圆")     # 不在词表，但与桂枝无字形关系
    assert r["corrected"] is False


def test_correct_name_empty():
    for v in ("", "   ", None):
        r = hs.correct_herb_name(v or "")
        assert r["corrected"] is False


def test_parse_image_reports_corrections(monkeypatch):
    """parse_recipe_image 要把纠正记录进 corrections 返回给前端"""
    outputs = iter([
        "金银花 10g 甘革 3g",      # OCR 原文（含错字）
        '[{"name":"金银花","grams":10},{"name":"甘革","grams":3}]',
    ])

    class _Resp:
        def __init__(self, text):
            self._text = text
        def raise_for_status(self):
            pass
        def json(self):
            return {"choices": [{"message": {"content": self._text}}]}

    # OCR 走视觉模型路径（跳过本地 RapidOCR，便于注入）
    monkeypatch.setattr(hs, "_ocr_with_rapidocr", lambda b: None)
    monkeypatch.setattr(hs.requests, "post", lambda *a, **k: _Resp(next(outputs)))
    r = hs.parse_recipe_image(b"fake-bytes")
    names = [h["name"] for h in r["herbs"]]
    assert "金银花" in names
    assert any(c["from"] == "甘革" and c["to"] == "甘草" for c in r["corrections"])
