# -*- coding: utf-8 -*-
"""通路富集集成测试：Enrichr 双库（GO BP + KEGG）富集、缓存、红线过滤、降级。

用法：cd backend && python -X utf8 -m pytest tests/ -v
"""
import json
import sqlite3
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

APP_DIR = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP_DIR))

import main  # noqa: E402
from services import pathway_service as ps  # noqa: E402

DB = APP_DIR.parents[1] / "data" / "shiyang.db"
client = TestClient(main.app)


def _db():
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _recipe_with_analysis():
    conn = _db()
    try:
        row = conn.execute("SELECT recipe_id FROM recipe_analysis LIMIT 1").fetchone()
        return row["recipe_id"] if row else None
    finally:
        conn.close()


# ---------- 纯逻辑单测（不依赖网络） ----------

def test_zh_mapping_covers_core_terms():
    """中文映射必须覆盖食养语境的核心生理过程词条"""
    cases = {
        "Inflammatory Response (GO:0006954)": "炎症反应",
        "Response To Oxidative Stress (GO:0006979)": "氧化应激反应",
        "Apoptotic Process (GO:0006915)": "凋亡过程",
        "Response To Reactive Oxygen Species": "活性氧反应",
        "Immune Response": "免疫反应",
    }
    for term, expect in cases.items():
        assert ps._zh_term(term) == expect, f"{term} 未映射为 {expect}"


def test_zh_mapping_rejects_technical_terms():
    """技术性词条不应有中文映射（用于过滤掉无解释力的 GO 条目）"""
    for term in ("Positive Regulation Of Nucleic Acid-Templated Transcription",
                 "DNA-templated Transcription", "Protein Phosphorylation"):
        assert ps._zh_term(term) is None, f"{term} 不应被保留"


def test_kegg_blocklist_filters_disease_terms():
    """癌症/感染/疾病类 KEGG 词条必须被黑名单拦住（医疗红线）"""
    for term in ("Pathways in cancer", "Pancreatic cancer", "Chemical carcinogenesis",
                 "Viral carcinogenesis", "Hepatitis B", "Measles",
                 "AGE-RAGE signaling pathway in diabetic complications"):
        low = term.lower()
        assert any(b in low for b in ps._KEGG_BLOCKLIST), f"{term} 未被过滤"
    for term in ("FoxO signaling pathway", "Apoptosis",
                 "Metabolism of xenobiotics by cytochrome P450"):
        low = term.lower()
        assert not any(b in low for b in ps._KEGG_BLOCKLIST), f"{term} 被误过滤"


def test_insufficient_genes_skips_enrichment():
    """基因数 < 3 直接返回 insufficient，不调 API"""
    r = ps.enrich(["TP53", "STAT3"])
    assert r["status"] == "insufficient"
    assert r["pathways"] == []
    assert "少于" in r["note"]


# ---------- 缓存与数据口径 ----------

def test_recipe_genes_are_human_protein_only():
    rid = _recipe_with_analysis()
    genes = ps.recipe_genes(rid)
    assert genes, "Top 成分没有关联到任何人类蛋白靶点"
    conn = _db()
    try:
        ph = ",".join("?" * len(genes))
        bad = conn.execute(
            f"SELECT gene, species, target_type FROM target WHERE gene IN ({ph}) "
            f"AND (species != 'Homo sapiens' OR target_type != 'Protein')",
            genes).fetchall()
    finally:
        conn.close()
    assert not bad, f"基因集混入非人类蛋白: {[dict(b) for b in bad][:3]}"


def test_cache_roundtrip():
    """save → cached 往返一致，且 KEGG 副列表不丢"""
    rid = _recipe_with_analysis()
    fake = {"status": "ok", "n_genes": 12,
            "pathways": [{"term": "Apoptotic Process", "term_zh": "凋亡过程",
                          "p_value": 1e-10, "overlap_count": 5, "overlap": ["TP53"]}],
            "pathways_kegg": [{"term": "Apoptosis", "p_value": 2e-9}]}
    ps.save(rid, fake)
    got = ps.cached(rid)
    assert got["status"] == "ok"
    assert got["n_genes"] == 12
    assert got["pathways"][0]["term_zh"] == "凋亡过程"
    assert got["pathways_kegg"][0]["term"] == "Apoptosis"


# ---------- API ----------

def test_pathways_api_returns_cached_without_network():
    """有缓存时接口必须能离线返回（预生成过的方子不依赖第三方可用性）"""
    rid = _recipe_with_analysis()
    ps.save(rid, {"status": "ok", "n_genes": 9,
                  "pathways": [{"term": "Immune Response", "term_zh": "免疫反应",
                                "p_value": 1e-8, "overlap_count": 4, "overlap": []}],
                  "pathways_kegg": []})
    r = client.get(f"/api/v1/recipes/{rid}/pathways")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["status"] == "ok" and d["pathways"][0]["term_zh"] == "免疫反应"
    assert "生物信息学推断" in d["note"]


def test_pathways_api_404():
    assert client.get("/api/v1/recipes/99999/pathways").status_code == 404


def test_cached_pathways_have_no_disease_terms():
    """已预生成的缓存里不得出现疾病/癌症类 KEGG 词条（红线回归检查）"""
    conn = _db()
    try:
        try:
            rows = conn.execute(
                "SELECT recipe_id, pathways_kegg FROM recipe_pathway "
                "WHERE status='ok'").fetchall()
        except sqlite3.OperationalError:
            pytest.skip("recipe_pathway 表尚未生成，先跑 scripts/pregen_pathways.py")
    finally:
        conn.close()
    assert rows, "没有已预生成的通路数据"
    violations = []
    for row in rows:
        for p in json.loads(row["pathways_kegg"] or "[]"):
            low = (p.get("term") or "").lower()
            if any(b in low for b in ps._KEGG_BLOCKLIST):
                violations.append((row["recipe_id"], p["term"]))
    assert not violations, f"缓存里出现疾病类词条: {violations[:5]}"
