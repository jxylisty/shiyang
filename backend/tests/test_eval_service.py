# -*- coding: utf-8 -*-
"""食养科学评价三维体系（eval_service）单测：入血潜力、多靶协同、证据强度计算与自洽性"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from services import eval_service as evs  # noqa: E402


def test_compute_eval_scores_shape():
    recipe = {"id": 1, "name": "测试方", "materials": []}
    analysis = {
        "top_compounds": [{"name": "成分A", "prob_cctcm": 0.95}, {"name": "成分B", "prob_cctcm": 0.85}],
        "top_targets": [{"gene": "STAT3", "compound_count": 4}, {"gene": "AKT1", "compound_count": 2}],
    }
    evidence = {
        "A": {"items": [{"what": "官方"}, {"what": "名方"}]},
        "B": {"items": [{"what": "PMID"}, {"what": "ChEMBL"}]},
    }
    res = evs.compute_eval_scores(recipe, analysis, evidence)

    assert res["dims"] == ["absorption", "synergy", "evidence"]
    assert res["labels"] == ["入血潜力", "多靶协同", "证据强度"]
    assert 50.0 <= res["absorption"] <= 100.0
    assert 50.0 <= res["synergy"] <= 100.0
    assert 60.0 <= res["evidence"] <= 100.0
    # 入血均值: (0.95 + 0.85)/2 * 100 = 90.0
    assert res["absorption"] == 90.0
    # 兼容性字段存在且一致
    assert res["anti_inflammatory"] == res["absorption"]
    assert res["immune_regulation"] == res["synergy"]
    assert res["airway_repair"] == res["evidence"]


def test_compute_eval_scores_empty_fallback():
    res = evs.compute_eval_scores({}, None, None)
    assert res["absorption"] == 60.0
    assert res["synergy"] == 55.0
    assert res["evidence"] == 68.0


def test_get_recipe_eval_from_db():
    res = evs.get_recipe_eval(1)
    assert res is not None
    assert "absorption" in res
    assert "synergy" in res
    assert "evidence" in res
    assert res["absorption"] >= 60.0
    assert res["synergy"] >= 60.0
    assert res["evidence"] >= 70.0
