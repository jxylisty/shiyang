# 项目推进记录

> 由 project-driver 维护。只记事实与判断，不写代码、不替人做技术/产品决策。
> 依据全部来自本仓库实测（git / 文件 / 只读查库），核实时间 **2026-11-06 17:19**。
> 上一版核实时间 04:56，两版之间新增 **23 次提交**（详见「历史」）。

## 现状（2026-11-06 17:19）

| 项 | 状态 | 依据 |
|---|---|---|
| 能否运行 | 能 | `cd backend && python -X utf8 -m pytest tests/ -q` → **94 passed**（三次实测 8.71s / 7.24s / 4.52s）；`main.app.openapi()` 实测 **57 路径 / 61 端点**；`npx vite build` → 通过（2.00s）；`scripts/check_consistency.py` → 退出码 0「全部一致」 |
| 主流程 | 通 | 方子 73；证据链端点走双口径后 **73/73 方有链**（只算 v3 是 52/73）；自定义鉴方 HERB 未命中已改本地库兜底（`42a2e50`，槐米/灵芝/天麻 0.1-0.4s 命中）；`rel_recipe_material` 270 条中 198 条带 `herb_id`（72 条无） |
| 文档 | 有，但**计数又漂了** | `docs/` 下 **31 份 md**（`00-index.md` 索引 33 项）；`README.md:30` 写 6,098 化合物 / 10,151 靶点，实测 **6,205 / 10,154**；`AGENTS.md:17` 写 56 路径 60 端点、`AGENTS.md:111` 又写 55/59，实测 **57/61** |
| 测试 | 有，**覆盖不均** | `backend/tests/` **10 个文件 94 用例**（`test_custom_recipe.py` 16 例）；**粘贴解析有 4 例**（防幻觉/克重越界/空文案/端点校验）、**拍照识药有 7 例**（库外名进 unverified/性味回填/image_kind 归一/克重剔除/坏 JSON/空图/MIME+8MB 校验）、**web-lookup 仍零用例**（`grep -rn "web_lookup" backend/tests/` 无命中）；前端无自动化测试（`frontend/package.json` 无 vitest/jest 配置） |
| 最近活动 | 高频 | 最新 `ecc1161` 2026-11-06 17:12（Pantry 移动端货架重构，单文件 +986 行）；近 3 日 **54 次提交**（11-03 8 / 11-05 17 / 11-06 29） |
| 工作区 | **不干净（有并行在飞）** | 已改未提交：`backend/app/main.py`、`services/explain_service.py`、`docs/00-index.md`、`frontend/src/components/MiniChemMap.vue`、`views/ChemMap.vue`、`views/CompoundDetail.vue`、`views/Compounds.vue`、`scripts/compute_map_coords.py`；未跟踪 `backend/app/services/prob_caliber.py`、`scripts/backfill_model_predictions.py`、`scripts/predict_remaining_compounds.py`；`master` 领先 `origin/master` **2**（`f42c897`、`ecc1161` 未推）。本文件也在未提交列表中（本次修改） |
| 数据实测（只读连接，2026-11-06 17:19） | 见右 | herb **105** / compound **6,205**（`prob_cctcm` 非空仅 165、带 SMILES 4,562）/ target **10,154** / rel_herb_compound **9,348**（ccTCM 201 + 扩容 9,147）/ rel_compound_target **62,617** / rel_herb_compound_v3 **63**（覆盖 24 味）/ rel_herb_compound_herb 824 / rel_herb_target_herb 836 / recipe 73 / recipe_analysis 69 / recipe_pregen_ai 69 / recipe_pathway 61 / compound_map **4,558** / compound_chembl_activity 465 / herb_compound_content 3,970 / food 39 / constitution 9；业务表 **21 张** |
| 数据溯源完整性 | 达标（局部偏薄） | `herb.source` 为空 **0**；`compound_count=0` 的药材 **0**（`e55cf01` 补橘红 0→90、花椒 0→152）；香橼仅 2、铁皮石斛仅 1 个成分，非空但薄；`frontend/public/img/materials/` 实物图 **149** 张 |
| 部署 | **无实例证据** | 仓库内无 vercel/render/Dockerfile/compose 配置、无线上地址；`docs/DEPLOY.md` 6 项上线检查全未勾选；**新增风险**：5 个端点硬依赖本机 AI 网关 `127.0.0.1:7863`（见阻断 B3） |
| 真实用户 | **0** | `user.db` 的 `user` 表 **0 行**（历史测试账号 `myasw_520` 已按 §2.7 清理）；但 `herb_cache` 仍留 **31 行**（含 `x`/HERB000001、`龙须凤尾草`=None）、`herb_web_lookup` 6 行（雷公藤/断肠草/五指毛桃/灵芝/蒲公英/槐米） |

## 一、本阶段（AI 交互三件 + 数据收口）在全局的位置

**位置：产品入口的「输入方式」补全，不是可信度或数据底座的新突破。**

项目已走过四段：①功能梯队（T1/T2/T3 十项）②可信度工程（应用域 / 独立交叉验证 / ChEMBL / 暴露量三档）③数据扩容（34→105 味）④**数据收口 + AI 输入三件**（本阶段）。

本阶段实际落库的交付：

- **联网搜索兜底**（`00c47a6`）：HERB 与本地库都查不到的名字，走网关 `web-search` 模型；来源只取网关 `web_search[]` 真实结果，无来源即报 `no_result`，30 天缓存（`herb_web_lookup`）。前端 `Pantry.vue` 在 `not_found` 时自动并发查询并展示来源链接。
- **拍照识药**（`15b9f53`，与 Me 页图标徽章同一提交）：`glm-5v-turbo` 多模态识别，返回 Top-N 候选 + 本地库复核（库外名进 `unverified`），**不做自动采纳**；方案见 `docs/拍照识药_方案调研.md`（8 味实测 7/7 正确或诚实弃权，降质图会高置信度答错，故保留人工确认）。后端校验 MIME 与 8MB 上限，图片仅内存处理。
- **粘贴文案解析**（`e15c36b`）：AI 抽药材+克重，逐条本地复核，编造名进 `rejected`、克重越界（<0.5g 或 >200g）剔除，单次上限 25 味。
- **验收 P2 修复**（`e820357`、`938addc`）：去掉错误信息里的内部 7863 地址与空态文案；前端识别请求单独设 70s 超时（后端 `VISION_TIMEOUT` 60s），消除前端 15s 先掐断。
- **同期数据/展示线收口**：重建链路 `df2c722`（沙箱驱动、两条链实测对齐）、口径收尾 `7079bd6`、新药材入证据链 `c99bdd3`（73/73）、UMAP 扩到全库 `c2fd1e7`+`5e9e9e9`（165→4,558）、采集缓存 gz 入库 `98b72ef`（新克隆可离线重建扩容数据）、对比实验室与茶罐页视觉重构（`f42c897`、`ecc1161`）。

**上一版定的「下一步」（重建链路定稿）已完成并复核**：`df2c722` 两条链实测跑通且行数对齐（`docs/知识库重建链路_2026-11-06.md` §7 有逐表实测记录），`docs/DEPLOY.md` §4 已从「先跑 build_db.py」改为醒目的删库警告 + `rebuild_all.py` 沙箱命令；我本次重跑 `check_consistency.py` 退出码 0。

**离答辩/结题还差三件，按缺口硬度排序：**

1. **部署 + 用户验证（最贵，需人拍板）**：`docs/用户验证方案.md` 六项执行清单全未勾选，无实例、无 SUS、无访谈。答辩「用户验证」章节仍为空。
2. **AI 运行时依赖未落成配置（本阶段新出现，agent 可解）**：5 个端点硬依赖本机 ZeroGate 网关，代码默认 `SHIYANG_AI_BASE_URL=http://127.0.0.1:7863/v1`、key 默认字符串 `"zerogate"`（`herb_service.py:341-342,393`、`plain_service.py:27,109`、`main.py:819-821`），`web-search` 与 `glm-5v-turbo` 模型名硬编码；`DEPLOY.md` 只提了重建时的 `--skip-ai`，**没有任何一节讲运行时怎么配**，仓库也没有 `.env.example`。
3. **材料成品化**：`docs/答辩材料_挑战杯算法PPT完整设计方案.md` 仍是方案，仓库内无 `.pptx`。

## 二、阻断项

| # | 问题 | 影响 | 谁去解 |
|---|---|---|---|
| ~~B1~~ | ~~`DEPLOY.md` 引导人跑 `build_db.py` 会删库~~ | **已解除**：`df2c722` 落 `scripts/rebuild_all.py`（沙箱重建、19/21 表两口径、实测记录在 `docs/知识库重建链路_2026-11-06.md` §7），`DEPLOY.md` §4 已改为删库警告 + 新命令；本次复核 `check_consistency` 退出码 0 | 已完成 |
| B2 | 无部署实例 → 30 人 SUS 验证无法启动 | 答辩缺「真实用户验证」；核心价值假设仍 0 验证 | **用户拍板落点/费用**，再交 fullstack-bridge 执行 |
| B3 | AI 运行时依赖未落成配置。硬依赖网关（无网关即失败）的 5 个：`POST /custom-recipe/parse-text`（502）、`/web-lookup`（返回 status=error，前端显示「联网查询失败」）、`/recognize-image`（502）、`/plain`（502）、`POST /assistant/chat`（SSE 发 `gateway_down`）。软降级 1 个：`/custom-recipe/analyze` 本身读本地库可用，仅中文功效翻译回落英文。`GET /recipes/{rid}/ai-report` 在**无用户 Key** 时回放 `recipe_pregen_ai`（69 行齐全），不依赖网关 | 换机器或公网部署后，拍照识药 / 粘贴解析 / 联网兜底 / 白话解读 / 问一问**静默或明示失败**；答辩若不在本机演示，这 5 个入口会当场坏掉，而 `DEPLOY.md` 没有任何提示 | doc-scribe（写配置节 + `.env.example`） |
| B4 | 权威口径文件计数再次过期（`README.md:30` 6,098/10,151、`AGENTS.md:17` 56/60 与 `:111` 55/59） | 后续 agent 与答辩材料继续引用作废数字 | doc-scribe（见「警告」B：建议改写法而非再改一次数字） |

## 三、假设验证状态

- **核心价值假设（用户愿意为「一杯茶凭什么有用」的证据链买单/使用）：未验证。** 依据：`docs/用户验证方案.md` 六项执行清单全未勾选；无 SUS、无访谈、无部署实例。
- **目标用户在用了：否。** `user.db` 的 `user` 表实测 **0 行**（此前 1 个 2026-10-27 的 `myasw_520` 已清理）。注意：`herb_cache` 31 行与 `herb_web_lookup` 6 行是开发/验收过程产物，不是用户行为数据。
- **差异化假设（成分→入血→靶点→通路 方剂级证据链无同类）：有文档支撑，无外部验证。** 依据 `docs/竞品对比分析.md`（2026-10 版，14 个产品对比）。
- **新增假设（AI 输入三件提升首次使用成功率）：仅本机实测。** `docs/拍照识药_方案调研.md` 记录 8 味 7/7；联网兜底与粘贴解析只有开发时点测，`docs/` 下无落盘验收报告（`docs/验收_数据扩容_2026-11-06.md` 是扩容线的，不含 AI 三件）。

## 四、并行工作核查

**本次核实结论：工作区不干净，是「并行在飞」，不是遗留半成品；但已在飞的线不止一条。**

- 未提交改动：`backend/app/main.py`、`backend/app/services/explain_service.py`、`docs/00-index.md`、`frontend/src/components/MiniChemMap.vue`、`views/ChemMap.vue`、`views/CompoundDetail.vue`、`views/Compounds.vue`、`scripts/compute_map_coords.py`。
- 未跟踪新文件：`backend/app/services/prob_caliber.py`（入血概率三列口径统一层）、`scripts/backfill_model_predictions.py`、`scripts/predict_remaining_compounds.py`——同日开工的「概率口径 + 模型补算」线，脚本头注释显示仍在编写。
- 该线**未改动**本次实测结果：当前 HEAD 上 pytest 94 passed、openapi 57/61（把未提交改动一起导入也不变）。
- `master` 领先 `origin/master` 2（`f42c897` 17:00、`ecc1161` 17:12，均未推）。
- 本次只改 `docs/PROGRESS.md`，未触碰上述任何文件。

## 五、下一步（只写一个）

**做什么**：在 `docs/DEPLOY.md` 新增「运行时 AI 依赖」一节，并新增仓库根 `.env.example`，写清 `SHIYANG_AI_BASE_URL` / `SHIYANG_AI_KEY` / `SHIYANG_AI_MODEL` 三个变量、`web-search` 与 `glm-5v-turbo` 两个模型依赖，以及「无网关时哪些端点失败、哪些只降级、失败时界面表现是什么」。

**为什么是现在**：这是本阶段新增的、**唯一会「换台机器就静默坏掉」**的面，且不需要用户拍板（B2 才需要）。上一版定的重建链路已完成，B2 只能等人，B4 是文案；B3 是唯一能立刻推进且能防止答辩现场翻车的动作。同时它不碰正在飞的 `prob_caliber` 线（只动 docs + 新增一个 example 文件）。

**派给**：doc-scribe。

**完成标志（可判定）**：
1. `docs/DEPLOY.md` §2（环境变量）含该节，逐项可与 `backend/app/services/herb_service.py:341-342,393`、`plain_service.py:27,109`、`main.py:819-821` 的默认值对上。
2. `.env.example` 入库（且确认 `.gitignore` 不误伤），三个变量 + 两个模型名齐全。
3. 文中降级清单与代码实际行为一致：硬失败 5 个（`parse-text` / `web-lookup` / `recognize-image` / `plain` / `assistant/chat`）、软降级 1 个（`custom-recipe/analyze` 仅中文功效回落英文）、`ai-report` 无用户 Key 时回放预生成。
4. 不改任何代码默认值（本次只做文档与示例文件）。

## 六、候补（按性价比排序，未启动）

1. **web-lookup 补离线单测**（backend-engineer，约半小时）：照 `test_custom_recipe.py` 已有的 monkeypatch 手法，覆盖三条红线——①网关无 `web_search[]` → 必须 `no_result`、不得产出摘要；②`link` 为空的结果行必须丢弃；③30 天缓存命中不走网络。理由：三个新功能里唯一零覆盖，而它守的正是「没来源就不许说」的数据真实红线。
2. **口径数字改为「给命令」而非硬编码**（doc-scribe）：README/CONTRIBUTING/AGENTS/数据库设计文档 §1.3 里的计数改为「跑 §6 自检命令取真值」。理由：同一批数字一天内已过期两次（见「警告」B），再改一次还会过期。
3. **部署 + 30 人 SUS**（用户决策 + 人工执行）：见 B2。战略价值最高，但 lead time 最长，且不是 agent 能独立完成的活。

## 七、警告

**A. 打转迹象（第三次复发，间隔 22 秒）。**
`e55cf01`（16:07:20）提交信息写「删除 user.db 里 1 条编造药名测试缓存（龙须凤尾草）」；实测 `user.db.herb_cache` 中该行 `cached_at = 16:07:42`——**22 秒后同一条被写回**。往前推：`af61495`（04:47）清 8 条 not_found，4 分钟后 `龙须凤尾草`/`槐米` 重新写入。根因已从「查询顺序」转移到「测试卫生 + 负缓存策略」：手工 GUI 验收直接打生产 `user.db`，且 `get_herb_detail` 把 not_found 也按 30 天 TTL 缓存（`herb_service.py:28` `CACHE_TTL_DAYS=30`，`:700` 附近的 not_found 分支写缓存）。不隔离测试库或不改负缓存策略，第四次必然复发——这是贴膏药，不是治病。

**B. 打转迹象（文档计数一天内过期两次）。**
`42a2e50`（05:26）把门面数字更新为 105/5,643/10,091/55·59；随后 `c99bdd3`、`e55cf01` 又加了数据，实际变成 6,205/10,154/57·61；`7079bd6`（14:01）再改成 6,098/10,151——**仍差 107 个化合物、3 个靶点**。这不是谁偷懒，是「硬编码实时计数」这个做法本身必然过期。建议下阶段把文档改成「写命令 + 写核实日期」，而不是继续追着改数字。

**C. AI 三功能的「准」只在本机成立。**
拍照识药 7/7 的实测对象是本机 ZeroGate 的 `glm-5v-turbo`（调研文档 §2）；联网兜底依赖网关返回的 `web_search[]` 结构；粘贴解析依赖同一个 chat 接口。三者在外部网关/模型换版后没有复现记录。另外 recognize 只有「修 2 个 P2」的提交记录（`e820357`），`docs/` 下没有落盘验收报告。

**D. 上一版的三个警告已关闭，记录在此避免重复报警。**
- 警告 A（`Herbs.vue` 对全部药材声称「含预测入血概率」）：已由 `42a2e50` 加 `has_prob_data` 分档 + `f047b41` 重塑弹层文案关闭；实测 v3 覆盖 24 味、全库带 `prob_cctcm` 的成分仍 165 个。
- 警告 B（`get_herb_detail` 不查本地库）：已由 `42a2e50` 的 `_local_kb_detail()` 兜底关闭，`槐米` 现命中 `imp:槐米`（179 成分）。
- 警告 C（`rel_herb_compound` 语义漂移）：已由 `services/herb_relation.py` 的 `DUAL_RELATION_SQL` 与 `AGENTS.md §5.8` 写成代码+文档口径关闭；`v2≡v3` 两张同内容表（各 63 行）仍在，属未清理而非未定口径。

**E. `user.db` 残留（演示前需判定）。**
`herb_cache` 31 行中至少两条明显是测试残留：`x` → `HERB000001`（2026-11-05 22:22）、`龙须凤尾草` → NULL（2026-11-06 16:07）。按 `AGENTS.md §2.7` 测试数据测完即删；演示前应确认并清理，同时注意清理动作会再次被手工测试写回（见警告 A）。

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

### 2026-11-06 17:19（本版更新）
- **推进了什么**：①上一版定的「重建链路定稿」已完成（`df2c722` + `DEPLOY.md §4` 改写 + 链路文档 §7 实测记录），本次复核 `check_consistency` 退出码 0；②AI 输入三件落库（联网兜底 `00c47a6`、粘贴解析 `e15c36b`、拍照识药 `15b9f53`）并修 2 个验收 P2（`e820357`、`938addc`）；③数据/展示线同步收口（`c99bdd3` 证据链 73/73、`c2fd1e7`+`5e9e9e9` UMAP 4,558、`98b72ef` 采集缓存 gz 入库、`f42c897`+`ecc1161` 对比实验室与茶罐页重构）。
- **实测数字**：pytest **94 passed**；openapi **57 路径 / 61 端点**；vite build 通过；herb 105 / compound 6,205 / target 10,154 / rel_compound_target 62,617 / rel_herb_compound 9,348 / compound_map 4,558 / 业务表 21；`user` 表 0 行。
- **卡在哪**：B2（部署+用户验证）等人拍板；B3（AI 运行时依赖未落配置）本次定为下一步；B4（计数又过期）见警告 B。
- **状态变化**：上一版三个警告（Herbs.vue 过度声称 / get_herb_detail 不查本地库 / 归属表语义漂移）已关闭，详见「警告」D；新增打转证据两处（缓存 22 秒复写、文档计数二次过期），详见「警告」A、B。
- **与上一版的判断差异**：上一版把 `ai-report` 算作 AI 网关依赖，本版核实为「无用户 Key 时回放 `recipe_pregen_ai`，不走网关」；依赖网关的实为 5 个端点 + 1 个软降级。
