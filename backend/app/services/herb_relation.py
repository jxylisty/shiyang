# -*- coding: utf-8 -*-
"""药材 → 成分归属关系的双口径读取（2026-11-06）

背景：本项目有两套「药材-成分」归属数据，口径不同、都不能丢：

1. `rel_herb_compound_v3`（63 条）：大创 73 方旧 34 味的**修复后**归属，
   是 asthma_v2 错乱表重建的权威版本（见 docs/归属重建报告.md）。这些成分
   带 PU-Learning 入血概率与三维机制评分。
2. `rel_herb_compound`（v1，2026-11-05 扩容新增 8,905 行）：药食同源目录
   新增 71 味的 HERB 全量成分归属。这些成分**没有**入血概率预测（模型输入
   域外不发分，预测列全 NULL）。

v1 里另有过往 201 行属于旧 34 味，是**未修复的错乱快照**（asthma 原库把
人参皂苷挂到薄荷上那版），必须排除——否则修复成果会被污染回来。

因此凡是「按药材取成分」的查询都应走 DUAL_RELATION_SQL，而不是直接
JOIN 单张表。

证据等级口径（AGENTS.md §2）：v3 成分可标 C 级（模型预测）；v1 新成分只有
B 级（数据库关联，来源 herb.ac.cn），展示层不得写成疗效或预测结论。
"""

# 双口径归属子查询，产出 (herb_id, compound_id) 两列，可直接当表用：
#   f"FROM ({DUAL_RELATION_SQL}) rc JOIN compound c ON c.id = rc.compound_id"
#
# 三个来源依次合并：
#   a) v3：旧 34 味里的 24 味（修复后权威口径，成分带入血概率预测）
#   b) v1 非 ccTCM 行：2026-11-05 扩容的 71 味（HERB 全量成分，prob 为 NULL）
#   c) rel_herb_compound_herb：2026-11-06 补的 10 味旧药材（v3 漏、v1 错乱，
#      故从 HERB 重拉；表可能不存在于旧库，调用方需容忍）
# 注意：v1 里旧 34 味那 201 行是未修复的错乱快照，必须排除。
DUAL_RELATION_SQL = (
    "SELECT herb_id, compound_id FROM rel_herb_compound_v3 "
    "UNION "
    "SELECT herb_id, compound_id FROM rel_herb_compound WHERE herb_id NOT LIKE 'ccTCM%' "
    "UNION "
    "SELECT herb_id, compound_id FROM rel_herb_compound_herb"
)

# 单味药是否有 v3 修复口径数据（成分带入血概率预测），供列表/详情如实标注用
HERB_HAS_PROB_SQL = (
    "EXISTS(SELECT 1 FROM rel_herb_compound_v3 v WHERE v.herb_id = h.id)"
)
