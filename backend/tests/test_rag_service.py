# -*- coding: utf-8 -*-
"""RAG 检索服务（T3-11 AI 助手 A1）测试：检索正确性 + citations 结构 + 降级标记"""
import json

from services import rag_service as rag
from services import constitution_service as cs


def _ids(result):
    return [c["id"] for c in result["citations"]]


def test_scene_alias_hits_throat_recipes():
    """「嗓子干」→ 护嗓润喉场景兜底，方子块带编号/配料/出处"""
    r = rag.retrieve_context("嗓子干喝什么茶")
    assert not r["no_context"]
    assert r["blocks"] and r["total_chars"] <= rag.MAX_CHARS
    f_cites = [c for c in r["citations"] if c["kind"] == "recipe"]
    assert f_cites and all(c["id"].startswith("F") for c in f_cites)
    assert all(c["matched"].startswith("场景·护嗓润喉") for c in f_cites)
    b0 = r["blocks"][0]
    assert b0.startswith(f"[F{f_cites[0]['ref_id']}]") and "配料：" in b0
    # 出处必须随块给出（RAG 红线：回答可溯源）
    assert "出处：" in b0 and f_cites[0]["source"]


def test_insomnia_alias():
    """「睡不着」口语 → 助眠场景"""
    r = rag.retrieve_context("晚上睡不着")
    assert not r["no_context"]
    assert any(c["matched"] == "场景·助眠" for c in r["citations"] if c["kind"] == "recipe")


def test_material_keyword_finds_recipe():
    """配料名关键词命中（global_search 扩域）"""
    r = rag.retrieve_context("枸杞有什么成分")
    assert not r["no_context"]
    assert _ids(r), "枸杞问题应有任何引用"
    kinds = {c["kind"] for c in r["citations"]}
    assert "recipe" in kinds or "herb" in kinds
    # 问了成分 → 成分块应补位（方子配料或药材成分）
    assert any(c["kind"] == "compound" for c in r["citations"])


def test_herb_intent():
    """药材问题 → 药材块带性味归经与目录批次"""
    r = rag.retrieve_context("黄精是什么药材")
    assert not r["no_context"]
    h_cites = [c for c in r["citations"] if c["kind"] == "herb"]
    assert h_cites and h_cites[0]["title"] == "黄精"
    assert h_cites[0]["ref_id"].startswith("ccTCM")
    assert "功效：" in h_cites[0]["detail"]
    assert any(b.startswith("[H1] 黄精") for b in r["blocks"])


def test_constitution_fallback():
    """体质入参 → 适宜方子兜底，matched 标注「相宜」"""
    r = rag.retrieve_context("最近想调理一下", constitution_code="qixu")
    assert not r["no_context"]
    f_cites = [c for c in r["citations"] if c["kind"] == "recipe"]
    assert f_cites and all("气虚相宜" in (c["matched"] or "") for c in f_cites)
    assert r["constitution"] == "气虚质"


def test_constitution_named_in_question():
    """问句自带体质名 → 同样走体质兜底"""
    r = rag.retrieve_context("气虚体质适合什么")
    assert r["constitution"] == "气虚质"
    assert not r["no_context"]


def test_no_context_honest_degradation():
    """无关问题 → 空 blocks + no_context=true，上层据此声明降级"""
    r = rag.retrieve_context("今天天气怎么样")
    assert r["no_context"] is True
    assert r["blocks"] == [] and r["citations"] == []


def test_blocks_citations_paired():
    """blocks 与 citations 一一对应，不允许孤儿引用"""
    for q, code in [("嗓子干喝什么", None), ("枸杞", None), ("黄精", None)]:
        r = rag.retrieve_context(q, code)
        assert len(r["blocks"]) == len(r["citations"])
        for b, c in zip(r["blocks"], r["citations"]):
            assert b.startswith(f"[{c['id']}]")
            assert c["kind"] in ("recipe", "herb", "compound")


def test_chars_hard_cap():
    """blocks 总字符不超过 MAX_CHARS 硬上限"""
    r = rag.retrieve_context("枸杞 菊花 金银花 麦冬 黄芪 成分")
    assert r["total_chars"] <= rag.MAX_CHARS
    assert sum(len(b) for b in r["blocks"]) == r["total_chars"]


def test_recipe_cite_source_url():
    """有出处的方子引用必须带 source/url（A 级证据要求）"""
    r = rag.retrieve_context("嗓子干喝什么茶")
    with_src = [c for c in r["citations"] if c["kind"] == "recipe" and c["source"]]
    assert with_src, "库内方子应带出处"
    assert all(c["url"] for c in with_src)


def test_constitution_json_rendered_readable():
    """适宜体质 JSON 串在块里渲染成顿号分隔的人话，不是原始 JSON"""
    r = rag.retrieve_context("气虚体质适合什么")
    assert not any('["' in b for b in r["blocks"])
