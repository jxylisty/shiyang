# -*- coding: utf-8 -*-
"""
入血概率口径统一（三列并存 → 一个明确的「该用哪个」）

## 为什么需要这一层（2026-11-06）

扩容后库里 `compound` 表同时有三列概率，来源与可信度都不同。任何接口/页面若直接
`SELECT prob_cctcm`（或随手 `COALESCE`），都会犯两类错误之一：
  - 只读 `prob_cctcm` → 4,300+ 个扩容成分显示「无数据」，回了也没用；
  - 无差别 COALESCE 三列 → 把「HERB 外推估计（C 级，实测偏差 0.135）」
    和「主力模型结论」摆在同一个位置上，用户分不清哪个能信。

三列的实测来源与精度（详见 scripts/backfill_model_predictions.py 与
scripts/predict_remaining_compounds.py 的脚本头注释）：

| 列 | 行数 | 来源 | 实测可信度 |
|---|---|---|---|
| `prob_cctcm` | 165 | 旧管线（源库 asthma_v2.db）+ 完整 ADME 特征 | 主力模型，训练集内 |
| `prob_cctcm_v2` | 795 | 官方正式版预测表结构回填（in-sample） | 主力模型，训练集内，偏乐观 |
| `prob_herb_v2` | 3,602 | HERB 兜底模型「仅 SMILES」外推 | **C 级外推估计**，误差明显更大 |

`prob_herb`（165 行）是旧管线随 `prob_cctcm` 一起来的老值，**不参与**这里的口径选择，
避免和 `prob_herb_v2` 混为一谈。

## 口径规则

按优先级选**唯一一个**概率作为「展示值」，并如实带回它的来源标签：
  1. `prob_cctcm`（旧主力，最可信）
  2. `prob_cctcm_v2`（主力正式版，训练集内）
  3. `prob_herb_v2`（兜底外推，C 级）
都没有则返回 None —— **绝不填 0**。0 是「模型认为完全不入血」，与「没有预测」是两个
完全不同的结论，混用会误导用户（AGENTS.md §2.3：模型预测 ≠ 实验事实，缺数据也要说清）。
"""

# 优先级：(列名, 口径标识, 是否主力模型, 人话说明)
PROB_CALIBERS = [
    ("prob_cctcm", "cctcm_legacy", True,
     "ccTCM 主力模型预测（课题既有管线）"),
    ("prob_cctcm_v2", "cctcm_v2", True,
     "ccTCM 主力模型预测（2026-08 正式版，训练集内）"),
    ("prob_herb_v2", "herb_extrapolated", False,
     "HERB 兜底模型外推估计（该成分不在主力模型训练集内，误差较大，仅供参考）"),
]

SQL_PROB = "COALESCE(c.prob_cctcm, c.prob_cctcm_v2, c.prob_herb_v2)"

# SQL 侧判定口径（CASE 表达式，供 SELECT 里一并取出）
SQL_CALIBER = (
    "CASE WHEN c.prob_cctcm IS NOT NULL THEN 'cctcm_legacy' "
    "WHEN c.prob_cctcm_v2 IS NOT NULL THEN 'cctcm_v2' "
    "WHEN c.prob_herb_v2 IS NOT NULL THEN 'herb_extrapolated' "
    "ELSE NULL END"
)

_CALIBER_META = {c[1]: {"is_primary": c[2], "label": c[3]} for c in PROB_CALIBERS}


def describe(caliber: str | None) -> dict | None:
    """把口径标识翻成前端要用的元信息；None 原样返回（前端据此隐藏概率区块）。"""
    if not caliber:
        return None
    meta = _CALIBER_META.get(caliber)
    if not meta:
        return None
    return {
        "key": caliber,
        "label": meta["label"],
        "is_primary": meta["is_primary"],
        # C 级外推估计：界面必须区别对待，不得与主力结论同样口径展示
        "is_extrapolated": not meta["is_primary"],
    }


def resolve(row) -> tuple[float | None, dict | None]:
    """从一行记录里取 (概率, 口径元信息)。row 需含三列名（sqlite3.Row 或 dict 皆可）。"""
    for col, key, _primary, _label in PROB_CALIBERS:
        try:
            val = row[col]
        except (IndexError, KeyError):
            continue
        if val is not None:
            return float(val), describe(key)
    return None, None
