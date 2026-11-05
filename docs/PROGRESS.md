# 项目推进记录

> 由 project-driver 维护。只记事实与判断，不写代码、不替人做技术/产品决策。
> 依据全部来自本仓库实测（git / 文件 / 只读查库），核实时间 **2026-11-06 04:56**。

## 现状（2026-11-06）

| 项 | 状态 | 依据 |
|---|---|---|
| 能否运行 | 能 | 本日实跑 `cd backend && python -X utf8 -m pytest tests/ -q` → **84 passed**（4.38s）；`main.app.openapi()` 实测 **55 路径 / 59 端点** |
| 主流程 | 通 | 方子 73 / 有成分分析 69 / 有通路 61；证据链、解读、RAG 读 `rel_herb_compound_v3`（24 味覆盖）；检索、自定义鉴方、open API 读 `rel_herb_compound`（105 味） |
| 文档 | 有，但**口径互相矛盾** | docs/ 下 26 份 md；`README.md:30`、`CONTRIBUTING.md:11,19`、`AGENTS.md:17,92`、`docs/数据库设计文档.md` §1.3 仍写 34 味 / 165 成分 / 2,807 靶点 / 12,168 关联 / 46 路径 50 端点；同一份设计文档 §6 又写了扩容方案 |
| 测试 | 有，有缺口 | `backend/tests/` 9 个文件 84 用例；**web-lookup 零用例**（`grep -rn "web_lookup" backend/tests/` 无命中）；Pantry 前端改动无自动化验证 |
| 最近活动 | 高频 | `af61495` 2026-11-06 04:47；近 3 日 **31 次提交**（11-03 8 / 11-05 17 / 11-06 6） |
| 工作区 | **干净** | `git status` 空；`master` 与 `origin/master` 为 0 ahead / 0 behind；无 stash、无额外 worktree |
| 数据实测（只读连接） | 见右 | herb **105** / compound **5,643**（其中带 `prob_cctcm` 仅 165）/ target **10,091** / rel_herb_compound **9,106** / rel_compound_target **59,437** / recipe 73 / recipe_analysis 69 / recipe_pathway 61 / compound_map 165 / compound_chembl_activity 465 |
| 数据溯源完整性 | 达标 | `herb.source` 为空的行 **0**；`added_batch=20261105` 覆盖 105 行；HBIN 新成分预测列非空行 **0** |
| 部署 | **无实例证据** | 仓库内无 vercel/render 配置、无线上地址；`docs/DEPLOY.md` 只有清单，6 项检查全为未勾选状态 |
| 真实用户 | **0** | `docs/用户验证方案.md` 五个执行项全部未勾选；全仓 `grep "SUS\|N="` 除该方案外无任何结果；`user.db` 仅 1 个 2026-10-27 创建的账号（`myasw_520`，带 3 条家庭成员 `11/321/231`） |

## 一、本阶段（数据扩容线 11-05/06）在全局的位置

**位置：产品化的「数据底座收口」，不是产品线的收口。**

项目已经走过三段：①功能梯队（T1/T2/T3 十项）②可信度工程（应用域 / 独立交叉验证 / ChEMBL / 暴露量三档）③数据扩容（34→105 味）。前两段都有验收报告落盘（`docs/验收测试_可信度功能_2026-10-30.md`、`docs/验收_化学空间地图_2026-10-30.md`），**扩容这一段只有执行报告，没有产品层验收**——执行报告 §三 的 D4 核查是「接口不报错」级别，不是「界面说法与数据一致」级别。

**离答辩/结题还差三件，按缺口硬度排序：**

1. **可复现性（最硬）**：`scripts/build_db.py` 先 `OUT.unlink()` 删库再重建，只建 **11 张表**、数据源在仓库外（`../my-asthma-system/asthma-core/data/asthma_v2.db`）；`scripts/rebuild_herb_compound.py` 还依赖仓库外的 `../数据库溯源/.../药材-化合物-含量-赵玉男.xlsx`。实测库有 **19 张表**（不含 sqlite_sequence）。仓库内唯一入库的库副本 `data/shiyang.db.bak-before-rebuild` 是**扩容前**的 34 味 / 165 成分 / 16 表。→ 一旦 `data/shiyang.db`（15.5MB）丢失，本仓库**无法自行重建出当前状态**。
2. **部署 + 用户验证（最贵）**：`docs/用户验证方案.md` 第一步就是「部署到公网」，至今无部署产物。没有实例 → 30 人试用与 SUS 无法开始 → 答辩「用户验证」章节为空。
3. **材料成品化**：`docs/答辩材料_挑战杯算法PPT完整设计方案.md`（37KB，16 页逐页讲稿 + 6 条 Q&A）是**方案**，仓库内无 `.pptx`（`find` 零命中）。且有 9 个 11-05 提交未进 CHANGELOG。

## 二、阻断项

| # | 问题 | 影响 | 谁去解 |
|---|---|---|---|
| B1 | `docs/DEPLOY.md` §4 让人「知识库需重建时」直接跑 `build_db.py`，该脚本**先删现有库**，产出 34 味 / 11 表残缺库，且不跑 v3 / 扩容 / pregen / chembl / map 五条后续链 | 任何按文档操作的人（含答辩前救急）会**静默毁掉** 105 味库并得到方子详情大片空白；结题评审问「能否复现」时无答案 | db-architect（定义重建链）+ backend-engineer（执行） |
| B2 | 无部署实例 → 30 人 SUS 验证无法启动 | 答辩缺「真实用户验证」；核心价值假设仍为 0 验证 | **用户拍板落点/费用**，再交 fullstack-bridge 执行 |
| B3 | 权威口径文件（`AGENTS.md`）与 README/CONTRIBUTING/设计文档 §1.3 仍写 34 味 / 46 路径 50 端点 | 后续 agent 与答辩材料会持续引用作废数字（AGENTS.md §2.1 自己就写着「旧数字即刻作废」） | doc-scribe |

## 三、假设验证状态

- **核心价值假设（用户愿意为「一杯茶凭什么有用」的证据链买单/使用）：未验证。** 依据：`docs/用户验证方案.md` 五项执行清单全未勾选；无 SUS 数据、无访谈记录、无部署实例。
- **目标用户在用了：否。** `user.db` 仅 1 个 2026-10-27 的账号，无法区分真实用户与历史测试残留（其 3 个家庭成员名为 `11/321/231`，符合 AGENTS.md §2.7 需清理的形态）。
- **差异化假设（成分→入血→靶点→通路 方剂级证据链无同类）：有文档支撑，无外部验证。** 依据 `docs/竞品对比分析.md`（14 个产品对比，2026-10 版）。

## 四、并行工作核查（对「git status 有未提交前端/后端改动」前提的核实结论）

**该前提不成立。** 实测：

- `git status` 输出 `nothing to commit, working tree clean`；`git status --porcelain --untracked-files=all` 亦为空。
- `master` 与 `origin/master` 同为 `af61495`，0/0。
- 唯一另一条远端分支 `origin/feat/data-and-ux-improvements` **已合并**（`git branch -r --merged origin/master` 含它，`git log origin/master..origin/feat/...` 为空）。
- 无 stash、无额外 worktree、无 `-dirty` 标记。

所以「其他 AI 在做前端视觉与 web-lookup」的工作**已全部落库**，不是未完结工作流。但**这条线的收尾不完整**，三点证据：

1. `00c47a6` 的 web-lookup（`backend/app/services/herb_service.py` 的 `web_lookup_herb`，174 行改动）**没有任何单测**；84 个用例里没有一个覆盖它。
2. `frontend/src/views/Herbs.vue:108` 对新数据过度声称（见「警告」A）。
3. 同一提交声称「清空 8 条 not_found 脏缓存」，**4 分钟后脏缓存又被写回**（见「警告」B）。

结论：不是未提交的半成品，是**已提交但未验收的半成品**——这类比未提交更危险，因为看起来像做完了。

## 五、下一步（只写一个）

**做什么**：把「从零重建 19 表 / 105 味库」的完整链路定稿为一个可执行命令，实测跑通一次，并用它替换 `docs/DEPLOY.md` §4 与 `docs/数据库设计文档.md:5` 的现有重建指令（现有指令会删库并产出残缺库）。

**为什么是现在**：它是唯一**不依赖用户决策**的硬阻断（B2 需要用户拍板落点，B3 只是文案）。它同时是答辩前最危险的活雷——文档现在主动引导人删库。且所有零件已存在（`build_db` → `rebuild_herb_compound` → `_migrate_20261105` → `import_herbs_20261105` → `pregen_analysis_v3`/`pregen_pathways`/`pregen_ai_reports`/`pregen_plain` → `fetch_chembl_activity` → `compute_map_coords` → `compute_applicability`），只缺串起来与验证。

**派给**：db-architect（定链路与顺序），执行可交 backend-engineer。

**完成标志（可判定）**：
1. 在 `data/` 以外的临时目录产出一份新库，只读核对：19 张表、herb=105、compound=5,643、target=10,091、rel_compound_target=59,437、rel_herb_compound_v3=63 行、`herb.source` 空值 0。
2. `scripts/check_consistency.py` 对着新库退出码 0。
3. `cd backend && pytest tests/ -q` 对着新库 84 passed。
4. `docs/DEPLOY.md` §4 与设计文档构建管线段改为新链路，并显式写明「`build_db.py` 单独运行会产出残缺库、会先删除目标文件」。

## 六、候补（已按性价比排序，未启动）

1. **口径对齐**（doc-scribe，约 1 小时）：README/CONTRIBUTING/AGENTS/设计文档 §1.3 的 34 味 / 165 成分 / 2,807 靶点 / 46 路径 50 端点 → 105 / 5,643 / 10,091 / 55 路径 59 端点；并把 `docs/API扩展记录.md`（49/53）一并更新。理由：最便宜，且能阻止后续 agent 与答辩材料继续引用作废数字。
2. **custom-recipe 本地优先 + Herbs.vue 收口**（backend-engineer + 一行前端）：见「警告」A、B。理由：同一个 bug 已修两次又复发，是活跃的数据真实红线风险。
3. **部署 + 30 人 SUS**（用户决策 + 人工执行）：见 B2。理由：战略价值最高，但 lead time 最长（方案写「周期建议 2 周」），且不是 agent 能完成的活。

## 七、警告

**A. 低价值区投入的反面：数据先行，界面未接，且已出现过度声称。**
- `frontend/src/views/Herbs.vue:108` 对**所有**药材写死「关联 N 个活性成分，含预测入血概率与靶点数据」。实测 105 味中 **73 味**的成分**全部** `prob_cctcm IS NULL`（有任一预测成分的药材只有 32 味）。→ 对 73 味药材这是把「模型未覆盖」说成「有预测」，触碰 AGENTS.md §2.3。
- 同一处 `router-link to="/compounds"` 写「到成分库按「来源药材」继续查看」，但 `/api/v1/compounds` 只接受 `min_prob`/`limit`，前端 `listCompounds(minProb, limit)` 也无 herb 参数——**这条承诺的路径不存在**。

**B. 打转迹象（同一问题已修两次，4 分钟内复发）。**
`af61495`（04:47）提交信息写「清 user.db 8 条 not_found 脏缓存（含槐米）」；实测 `user.db.herb_cache` 在 **04:45:21 写入 `龙须凤尾草=None`**、**04:51:09 写入 `槐米=None`**。而 `shiyang.db` 里 `imp:槐米` 有 179 条成分。根因清楚：`herb_service.get_herb_detail()` 只查 `herb_cache` 再打 HERB `search_api`，**从不查本地 `herb` 表**（`_name_exists_locally` 只被 `web_lookup` 用）。清缓存是贴膏药；不修 `get_herb_detail` 的查询顺序，第三次复发只是时间问题。

**C. 决策摇摆（口径语义漂移，无一次正式定稿）。**
`rel_herb_compound` 的语义在 5 次提交里变了三次：`8c47247` 定为「系统性错乱表」→ `080e81d` 注释「禁用」→ `a540a7d` 写入新数据 → `af61495` 改称「旧快照+扩容新增的混合表」。同时 v2≡v3 内容一致（63 行）却保留两张表，`check_consistency` 用注释维持口径。→ 这是决策依据没有落成文档的表现，不是代码问题；建议下阶段一次性定稿「哪张表是唯一真源」，否则每次扩容都要再补一次计数口径。

**D. 文档与代码不符（答辩风险）。**
`README.md:30`（34 味 / 165 化合物 / 2,807 靶点 / 12,168 关联）、`CONTRIBUTING.md:11`（约 2.7 MB）、`AGENTS.md:17`（46 路径 / 50 端点）、`docs/数据库设计文档.md` §1.3 —— 全部与实测（105 / 5,643 / 10,091 / 59,437、15.5MB、55/59）不符。`docs/答辩材料_...PPT完整设计方案.md` 末段自己写着「55 路径 59 端点」「不抄过时旧文案」，但 README 就是过时旧文案。

**E. 数据卫生。**
`user.db` 有 1 个 2026-10-27 账号 `myasw_520` 与 3 条家庭成员（`11/321/231`）。答辩演示前需确认它是真实用户还是历史测试残留——按 AGENTS.md §2.7，测试残留必须删，真实用户数据不可用于演示。

## 历史

### 2026-11-06
- 本文件创建（此前不存在；无 doc-scribe 并行写入冲突）。
- 核实：工作区干净、分支已同步、远端唯一分支已合并 —— 「有未提交改动」前提不成立。
- 记录数据扩容线收口状态与三项阻断，下一步定为重建链路定稿。
- **doc-scribe 增补（2026-11-06 05:18，独立复核）**：本文档所引全部关键数字已逐项实测复核一致——五表行数（herb 105 / compound 5,643 / target 10,091 / rel_herb_compound 9,106 / rel_compound_target 59,437，只读连接）、pytest 84 passed、openapi 55/59、`check_consistency.py` 退出码 0、shiyang.db 19 表、`herb.source` 空值 0、HBIN 预测列非空 0。警告 A（`frontend/src/views/Herbs.vue:108` 过度声称）与警告 B 根因（`backend/app/services/herb_service.py:558` 的 `get_herb_detail` 只查缓存不打本地库）均已亲自复核属实；另实测 `user.db.herb_cache` 现存 1 条 `龙须凤尾草` not_found 脏缓存（04:45:21 写入，槐米行已被清）。
  - **产出**：`docs/00-index.md` 已建（27 份文档全量索引 + 6 项确认矛盾 + 105/106 与 74/71 口径专项核对）。
  - **下一步候选补引**（源自 docs/数据扩容执行报告_2026-11-06.md §四，与本文档 §五/候补互补，优先级不替人定）：①custom-recipe 本地优先（=本文档候补 2、警告 B 根因）；②新药材入证据链 `v1 UNION v3`（含「新成分 prob 为 NULL 时前端展示『无入血预测』而非 0」的前端注意点）；③UMAP 化学空间扩样（报告建议只对有预测值的成分扩图）。
  - **并行落盘发现**：ux-tester 于同日（05 时后）落盘 `docs/验收_数据扩容_2026-11-06.md`（扩容 GUI 验收：1 P1 / 4 P2 / 3 P3）。其 P1（自定义鉴方对本地已有数据的药材报「未找到」，`get_herb_detail` 无本地库 fallback）与本文档警告 B 是**同一根因的两个面**——警告 B 记的是脏缓存复发表象，验收报告 P1 记的是用户可见缺口，修复方案收敛到同一处（`get_herb_detail` 加本地 `rel_herb_compound` + `rel_compound_target` fallback）。该验收报告的 P2「药材详情弹窗虚假承诺」与本文档警告 A 同源（Herbs.vue:108）。两份报告互为印证，均已实测复核。
  - **口径专项结论**：全库未发现写「扩容后 106 味」的文档（106 均指目录项数）；唯一过期表述在 `docs/答辩材料_挑战杯算法PPT完整设计方案.md:363`（扩容写成进行时）。74→71 差额已核实：姜→生姜、橘皮→陈皮由存量行覆盖 + 蝮蛇缺（执行报告 §二.2 未并列写全，已登记 00-index 疑似不一致 #3）。
