# CHANGELOG —— 食养有据开发日志

> 记录按 git 提交整理（哈希可用 `git show <哈希>` 复核）。
> 「验证」列只写**有实际执行记录**的验证，未验证的如实标注，不做背书。
> 基线：`761c1f0`（2026-10-25 init，v0.2）。以下全部为 2026-10-26 增量，按时间正序。

## 功能梯队开发（清单来源：docs/功能扩展调研清单.md 第一/第二梯队）

| 提交 | 功能 | 关键文件 | 验证 |
|---|---|---|---|
| `9899116` | T1-1 方子对比实验室：`GET /recipes/compare?a=&b=` 成分/靶点重叠、机制雷达、体质适宜交叉 + `/recipes/compare` 页 | `compare_service.py` `CompareLab.vue` | TestClient 200/404/400 分支 + vite build ✅ |
| `541ab50` | T1-2 我的茶罐：`POST /pantry/match` 反向配伍（覆盖率两档+异名归一）+ `/pantry` 页、导航入口 | `pantry_service.py` `Pantry.vue` | TestClient 命中/缺失/空清单分支 + build ✅ |
| `472aff8` | T1-5 慢病安全滤镜：五人群档案禁忌检查（block/warn/pass）+ 方子库人群 chips + 详情页 SafetyBanner | `safety_service.py` `SafetyBanner.vue` | TestClient 五档抽检（控糖拦冰糖/孕期拦山楂等符合预期）✅ |
| `39aa88b` | T1-3 证据分级溯源：A 权威出处/B 实验数据库（PMID 直达）/C 模型预测 + 详情页 EvidenceCard | `evidence_service.py` `EvidenceCard.vue` | TestClient 银菊利咽茶三级归组正确 + build ✅ |
| `dba05fb` | T1-4 入血概率可解释：MW/logP 对照 Lipinski 逐项命中 + 人话解读面板 | `explain_service.py` `ExplainPanel.vue` | TestClient 化合物/方子/404 分支 + build ✅ |
| `5c287d4` | T1-6 开放数据 API：`/open` 自描述索引 + catalog/herbs/compounds/targets/constitutions/stats/snapshot 7 组只读端点 + 用法页 `/open-api` | `open_api.py` `OpenApi.vue` | TestClient 全端点 + snapshot 附件头 + 404 ✅ |
| `5b326c8` | T2-7 周期报告：`GET /report/cycle`（打卡墙/成分靶点覆盖/场景分布/体质曲线）+ `/report` 页 | `report_service.py` `Report.vue` | TestClient 登录态聚合正确 + build ✅；测试用户已清理 |
| `250d3da` | T2-9 节气推荐：寿星公式节气引擎（2026 立春 2/4、夏至 6/21、冬至 12/22 与公开历书核对一致）+ TermCard 挂方子库 | `term_service.py` `TermCard.vue` | 边界日期断言 + 端点 200 ✅ |
| `ef3f12f` `c360f3c` | T2-8 家庭档案：`family_member` 表+`member_id` 列（`_migrate` 自动迁移）、成员 CRUD、测评「替谁测评」、Me 页成员卡 | `user_service.py` `Me.vue` `Quiz.vue` | TestClient 增删查重/代测归挂正确 + build ✅；测试用户已清理。注：`ef3f12f` 拆分时带入 `Quiz.vue` 他人动画函数体，`c360f3c` 补齐配套模板绑定，两点均自洽可构建 |
| `b51a7b0` | T2-10 体质名片：Canvas 名片海报（主体质大字/九维分/本周打卡/二维码）挂 Me 页档案卡 | `ConstitutionCard.vue` | vite build ✅；渲染效果为纯前端，需浏览器目检（未做） |

## 并行线（其他 AI 当日提交，按提交信息记录）

| 提交 | 内容 |
|---|---|
| `e71d22f` | 叙事放大：全场景定位不绑定哮喘 |
| `47fa41f` | 多 AI 协作现场快照（标注未验证） |
| `8cbc5f8` | P0：暴露量×入血概率合并；靶点展示层仅人类蛋白 |
| `7db3875` | 全局搜索 `/search`、成分词典 `/foods`、周期报告海报、无障碍与代码质量 |
| `6146963` | 暗色模式硬编码色修复六处 |
| `7c4056b` | 三维机制评分按场景门控（仅呼吸/咽喉方展示） |
| `8c47247` | **数据修复**：药材-成分归属系统性错乱重建 + 四层证据链桑基图 `/recipes/{rid}/chain`、`/pathways`（报告见 docs/归属重建报告.md，备份 `data/shiyang.db.bak-before-rebuild`） |
| `4d7834c` | .gitignore 补充本地临时产物 |

## 当前回归基线（2026-10-26 实测）

- 端点：46 路径 / 50 端点（`app.openapi()` 实测）
- 单测：`cd backend && python -X utf8 -m pytest tests/ -v` → **23 passed**（本文档撰写时为 14，数据线补充测试后 2026-10-26 复核实测 23）
- 构建：`cd frontend && npx vite build` → 通过
- T1/T2 全部端点在数据重建（`8c47247`）后复测通过（对比 Jaccard 由 0.333 变 0.667 属归属修复的正常反映，接口如实读取最新库）

## UX 体验线（2026-10-27：搜索增强 + 首页时令接真节气 + 千人千面推荐）

| 提交 | 功能 | 关键文件 | 验证 |
|---|---|---|---|
| `72fcbf5` | 搜索扩域：全局搜索方子加配料名、药材加别名/功效，每条带 matched_by 命中来源标注 | `search_service.py` | 实测「枸杞」命中配料含枸杞子方、「润肺」命中功效·润肺药材；**29 passed** ✅ |
| `c5a4c39` | 列表页 q 扩域：兑现搜索框「搜方子名、体质需求或药材」承诺（此前只搜名称） | `main.py list_recipes` | 实测「气虚」24 方、「枸杞」9 方；26 passed ✅ |
| `2f956bc` | 搜索面板升级：matched_by 标签 + 最近搜索（本地 8 条）+ 快搜词 | `SearchBox.vue` | vite build ✅ |
| `a72915c` | 首页时令专区接真节气：节气横幅（霜降·第 N 天·tip）+ 当令方真数据横滑，失败回退写死场景卡；场景卡计数改实算 | `Home.vue` | 实测当前霜降·换季调理 6 款当令；build ✅ |
| `b82a68d` | 「为你推荐」服务 + 双端点：`GET /me/recommend`（登录，档案+收藏打卡+节气）、`POST /constitution/recommend`（游客），每条带 reasons | `rec_service.py` `main.py` | 全流程测试（注册→存档→收藏→打卡→推荐，测试数据已清理）；端点 50→52；29 passed ✅ |
| `868c4c4` | 首页三态「为你推荐」：ForYou 自包含组件（登录/本地暂存/未测引导），渲染成功时替换通用今日推荐；Quiz 结果本地暂存；列表支持 `?constitution=` 深链 | `ForYou.vue` `Quiz.vue` `Recipes.vue` `api/index.js` | build ✅ |
| `43d92d6` | 方子库列表露出已收藏角标（朱砂星标，封面右上角） | `Recipes.vue` | build ✅ |

**UX 线回归基线（2026-10-27 实测）**：端点 48 路径 / 52 端点（`app.openapi()`）；单测 **29 passed**；vite build 通过。

## 质量审计线（2026-10-27：全仓审查缺口修补）

| 内容 | 关键文件 | 验证 |
|---|---|---|
| 清理 user.db 残留：12 个历史测试账号（tester01/uitest01/smoke_*/t_* 等）及其打卡/收藏/档案，按 §2.7 顺序删除，清零 | `data/user.db`（不入库） | 清理后四表全 0，且确认无真实用户数据混入 |
| 测试防复发：pytest 新增 autouse 兜底 fixture（用例后清理本用例新建的测试前缀账号，断言失败也清）；冒烟脚本收尾自动删自己的测试账号 | `backend/tests/conftest.py`（新） `scripts/smoke_test.py` | 全量套件跑完 user.db 四表全 0 ✅ |
| 零覆盖服务补测：安全滤镜/我的茶罐/对比实验室/周期报告/节气 + user_service 密码哈希/令牌/校验规则单元级用例 | `tests/test_services_gap.py`（新） `tests/test_user_service.py`（新） | 单测 29 → **61 passed** ✅ |
| 修复用户名校验漏洞：`str.isalnum()` 会放行中文（提示语说「字母数字下划线」实际却注册成功），收紧为 ASCII `[A-Za-z0-9_]` | `user_service.py register()` | 参数化用例覆盖（ab/超长/中文/空格/连字符）✅ |
| 新增部署文档：环境变量（SHIYANG_JWT_SECRET 生产必设）、Nginx SSE 反代 `proxy_buffering off`、CORS 收紧建议、数据库重建/备份、上线检查清单 | `docs/DEPLOY.md`（新） | 文中路径与环境变量名逐一对照代码核实 |
| 移除仓库根目录空文件 `wdj.html`（0 字节快照残留）；`logs_*.txt` 已被 .gitignore 覆盖无需处理 | `wdj.html`（删除） | `git rm` 生效 ✅ |

**审计线回归基线（2026-10-27 实测）**：端点 48 路径 / 52 端点（`app.openapi()`）；单测 **61 passed**；测试后 user.db 零残留。

## 分页/独立搜索/AI 助手线（2026-10-27：便宜三件 + T3-11 RAG 问答）

| 提交 | 功能 | 关键文件 | 验证 |
|---|---|---|---|
| `c6421a5` | 方子库真分页 + van-list 无限滚动（size 100→20，reqId 竞态保护，筛选变化重置页码） | `Recipes.vue` | build ✅ |
| `8f68fa1` | 独立搜索页 `/search`（大搜索框+历史/快搜+三分组全量结果+深链）+ `/api/v1/search` limit 参数（默认 5 上限 20）+ searchPrefs 共享工具 | `Search.vue`（新） `searchPrefs.js`（新） `SearchBox.vue` `search_service.py` | 29 passed；build ✅ |
| `98c2f60` | RAG 检索服务 `retrieve_context`：关键词漏斗（复用 global_search 扩域）→ 场景标签兜底 → 体质适宜兜底；产出 [F#]/[H#]/[C#] 编号块（≤6000 字符硬上限）+ citations 引用卡；无命中 no_context=true 诚实降级 | `rag_service.py`（新） | 11 例新测，52 passed ✅ |
| `dd7653a` | `POST /api/v1/assistant/chat` SSE 端点：RAG 注入 + citations 先行事件 + Key 解析 X-AI-Key 头→ZeroGate 平台级默认（SHIYANG_AI_* 可覆盖，不落库）；`CHAT_SYSTEM_PROMPT` 强制引用编号/降级声明/禁疗效词红线 | `main.py` `ai_service.py` | 6 例 mock 测试 + 真 ZeroGate 端到端冒烟（带编号回答+降级声明均通过）；端点 52→53；67 passed ✅ |
| `d98831f` | 「问一问」对话页 + 顶栏第 6 项：流式光标/停止生成/引用卡跳转/历史 20 轮/体质快捷注入/快捷提问 chips/AI 生成小标；**加粗**拆段渲染防注入 | `Assistant.vue`（新） `App.vue` `icons.js` `api/index.js` | headless Chrome CDP 实测：375px 顶栏 6 项不溢出、对话/引用跳转 `/recipes/1`/历史持久化/清空均通过 ✅ |
| 本提交 | `streamAIReport` 的用户 Key 从 URL query 改 `X-AI-Key` 头（还债：不进 URL/日志） | `api/index.js` | build ✅ |

**本线回归基线（2026-10-27 实测）**：端点 49 路径 / **53 端点**（`app.openapi()`）；单测 **67 passed**；vite build 通过。AI 链路只走本机 ZeroGate 网关（key=zerogate），不接触用户密钥文件。

## 可信度加固线（2026-10-29：应用域 + ChEMBL 实验活性 + 暴露量三档情景）

> 来源：南京中医药大学「人工智能赋能药物研发」研修班资料包（Compound Profile Agent 项目 + AutoMolDesigner 数据集 + 定量药理学课件）。只取可落地的三件，不做分子生成/对接/MD。

| 提交 | 功能 | 关键文件 | 验证 |
|---|---|---|---|
| 本提交 | **入血模型应用域标注**：对 165 成分算「与训练集最大 Morgan Tanimoto 相似度」，留一法定阈值（5%分位 0.333 / 25%分位 0.582）→ 域内 160 / 边缘 2 / 域外 3；成分页展示可信度徽章 | `scripts/compute_applicability.py`（新）`explain_service._applicability` `CompoundDetail.vue` | 实测 165/165 写入；域外成分（白皮杉醇 sim=0.246 等）与其低入血概率自洽 ✅ |
| 本提交 | **ChEMBL 实验活性补数据**：InChIKey 精确匹配 → 拉活性记录 → 自算 pChEMBL（官方值大量缺失，实测人参皂苷 Re 全为 None）→ 靶点类型白名单（target.json 查 SINGLE PROTEIN 等，剔除细胞系污染）→ 按靶点聚合 | `scripts/fetch_chembl_activity.py`（新）`compound_chembl_activity`（新表） | 全量实测：**126/165 命中（76%），465 条活性（L1 强证据 127 条），0 错误，耗时 1603s** ✅ |
| 本提交 | **暴露量三档情景**：转移率由单常数 0.5 改为 低0.3/基准0.5/高0.7 三档 × 含量区间，输出 `est_mg_min/base/max`；旧字段保留向后兼容 | `exposure_service.py` `RecipeDetail.vue` | TestClient `/recipes/1/exposure` 返回 transfer_scenarios ✅ |
| 本提交 | **证据链纳入 ChEMBL**：方子级 B 级证据新增「本方 N 个成分有 M 条体外实测活性」汇总；A/B/C 与 L1/L2 两套体系在注释中明确区分（前者说出处类型，后者说活性强度） | `evidence_service.py` | 银菊利咽茶实测：3 成分 12 条记录（1 条 L1）✅ |

**本线回归基线（2026-10-29 实测）**：端点 49 路径 / 53 端点（未新增路由）；单测 **67 passed**；vite build 通过。

**边界声明**：ChEMBL 活性为**体外实验测定**（Ki/IC50 等），不等于人体内有效，更不等于食疗功效；页面已标注「非疗效结论」。应用域标注是**量化披露**，不是性能提升——模型本身未重训。

## 独立交叉验证线（2026-10-30：AutoMolDesigner 评估 + 多算法族独立验证）

| 提交 | 功能 | 关键文件 | 验证 |
|---|---|---|---|
| 本提交 | **AutoMolDesigner 可用性评估**：exe 能启动（324MB 进程）但为纯 GUI 无 CLI（exe 内扫描 `--smiles` 0 次），不可脚本化集成；datasets 目录 3 组 ADMET 数据集（PPB 3,921 条 / Tox 9,668 条 / Accum 186 条）为真正可用资产 | `docs/AutoMolDesigner可用性评估.md`（新） | 实测启动 + exe 字符串扫描 ✅ |
| 本提交 | **独立算法族交叉验证**：LR/XGBoost/MLP 三个不同族算法在同一 ccTCM 标签独立训练（标准二分类协议，未标注全当负例）→ 全量重训预测 165 成分 → 与主模型一致性 | `scripts/cross_validate_independent.py`（新）`compound.prob_indep`（新列）`meta.indep_threshold` | 实测：XGB ROC-AUC **0.8961±0.0055**（主模型 0.903 几乎持平）；一致率 **73.3%**（Spearman 0.580）；44 个分歧成分全部系统化集中于皂苷/脂肪酸，与"PU 协议 vs 标准协议对未标注样本的处理差异"完全对应 ✅ |
| 本提交 | **成分页独立模型对比区块**：双模型概率对比条 + 四档一致性徽章（一致·高/一致·低/主模型单独高/独立模型单独高），分歧说明文案直接引用皂苷案例 | `explain_service._cross_validation`（新）`CompoundDetail.vue` | 甘草苷=一致高 / 落新妇苷=主单独高 / 白皮杉醇=一致低，三案例实测正确 ✅ |

**本线回归基线（2026-10-30 实测）**：端点 49 路径 / 53 端点（未新增路由）；单测 **67 passed**；vite build 通过。

**答辩要点**：独立验证的价值不在"全一致"（那反而不真实），而在 ①AUC 持平证明信号稳健 ②分歧全部集中在皂苷类且方向与文献（皂苷代谢物可入血）吻合——主模型 PU 协议在这个点上是**更贴近标签定义**的一方，分歧本身成为"我们理解自己模型"的证据。

## P1 修复与验收收口（2026-10-30）

| 提交 | 内容 | 验证 |
|---|---|---|
| `87c5e2e` | 验收发现的 4 P1 + 1 P2 修复：成分页移动端横向溢出（cd-target min-width:0 + ellipsis）、交叉验证判定口径上屏（main_threshold 字段 + 阈值说明行）、main_only 文案按分子量动态生成（黄酮苷不再误写皂苷）、ChEMBL 截断提示、暴露量截断提示 | 落新妇苷文案断言 PASS；单测 67 passed；vite build 通过 |
| 本提交 | ux-tester 验收报告（P0=0，4 P1，数据层 165 成分+232 暴露量行零数值错误）+ 浏览器复验报告（4 项全过，375px scrollWidth=375）落盘 | Playwright headless 375x812 实测 |

**验收结论**：可信度三区块（应用域/独立交叉验证/ChEMBL 实验活性）+ 暴露量三档情景可对外演示。
**P2/P3 遗留**：徽章对比度不足 4.5:1、/compounds 的 total 字段语义误导（见 docs/验收测试_可信度功能_2026-10-30.md，留待下阶段）。

## P3 修复 + 答辩素材 + 衍生新功能：化学空间地图（2026-10-30 第二轮）

| 提交 | 功能 | 关键文件 | 验证 |
|---|---|---|---|
| 本提交 | **P3 修复**：①徽章白字底色加深至 WCAG AA（灰绿 #8a978f→#6b7a72 4.51:1、琥珀 #c98a2d→#9a6b1f 4.67:1，前后端共 10 处）②`/compounds` 的 total 改为真实 COUNT(*)，新增 returned 字段标实际返回量（实测 min_prob=0.5 时 total=96/returned=50） | `main.py` `explain_service.py` `evidence_service.py` `CompoundDetail.vue` | pytest + TestClient 断言 ✅ |
| 本提交 | **开源资源清单收尾**：补 ChEMBL（已接入，2026-10-30 净新增）与 AutoMolDesigner 数据集（实测取舍：PPB/Tox/Accum 全不采用，理由落盘）两条目 | `docs/开源资源清单.md` | 链接与数字对照评估报告 ✅ |
| 本提交 | **答辩话术文档**：可信度四件套 30 秒总话术 + 逐条追问应答 + 3 分钟演示动线，全部带实测数字 | `docs/答辩话术_可信度四件套.md`（新） | 数字与各报告一致 ✅ |
| 本提交 | **衍生新功能：成分化学空间地图**——165 成分 Morgan 指纹 UMAP 降维（random_state=42 可复现），SVG 散点三视角切换（入血概率着色/应用域着色/主模型 vs 独立模型一致性着色），点按圆点出成分卡跳详情页。**分歧点聚团 = "分歧来自皂苷等结构类别而非随机噪声"的可视化证据** | `scripts/compute_map_coords.py`（新）`compound_map` 表（新）`GET /explain/map`（新端点）`ChemMap.vue`（新页）`/chem-map` 路由 + 成分库页入口链接 | 端点 200/count=165；端点 50 路径/54 端点；单测 67 passed；vite build 通过；浏览器验收见 docs/验收_化学空间地图_2026-10-30.md ✅ |

**备注**：`umap-learn` 为开发期依赖（坐标离线预计算，运行时只读表），不进 backend/requirements.txt。

## 数据质量与体验优化线（2026-11-03，分支 feat/data-and-ux-improvements）

| 提交 | 功能 | 关键文件 | 验证 |
|---|---|---|---|
| （数据，无提交） | 通路富集补跑：8 个缺 `recipe_pathway` 的方子补齐——1 方（温阳暖身茶）ok 8 通路，7 方基因数 0 记 `insufficient`（诚实状态非缺失）；4 方（#25/66/69/72）配料全不在 34 味库内，保持 `analysis_ready=0` 不改 | `data/shiyang.db` | `pregen_pathways.py` 运行记录：62 ok / 7 insufficient |
| （撤销） | 克重换算尝试已回退：15 条「颗/枚/片/朵」按通识换算的克重全部还原为 NULL，备注同步清理；原文未标克重的 83 条一律保持空白，**不做编辑换算** | — | 还原后 `grams IS NULL` 回落至 83 条、note 无残留 ✅ |
| `080e81d` | 药材-成分归属统一到 v3：`rag_service` 此前仍读旧错乱表 `rel_herb_compound`（活 bug）已修；`explain_service`/证据链端点由 v2 切 v3（两表内容一致，v3 为权威）；新增一致性自检脚本并重算 33 行 `herb.compound_count` + 10 行 `compound.target_count` | `main.py` `explain_service.py` `rag_service.py` `scripts/check_consistency.py` | TestClient 冒烟：health/recipes/detail/chain 全 200，chain 26 节点 70 边；自检脚本退出码 0 ✅ |
| `74a1ed4` | axios 全局响应拦截：401 清会话跳登录页（带回跳地址，web/hash 两模式兼容，登录页不重复跳）；错误对象原样透传不破坏各页面 `e.response` 分支 | `api/index.js` | build ✅ |
| `acad9ca` | RecipeDetail 瘦身：echarts 按需引入（GraphChart/SankeyChart + 所需组件）+ qrcode 改弹层打开时动态加载 | `NetworkGraph.vue` `EvidenceChain.vue` `SharePoster.vue` | RecipeDetail chunk **1150 kB → 533 kB**（gzip 384 → 180），build ✅ |
| `c839bcb` | 对比页「同饮注意」：共有配料克重合计（两边已知才合计，只陈述事实不设阈值）+ 复用 safety 词表的 5 类人群冲突提示 | `compare_service.py` `CompareLab.vue` | TestClient：1v8 人群命中（控糖/孕期 block B），1v2 共有配料合计（桔梗 20g 等）正确；build ✅ |
| `e960d86` | 详情页「家人适配」：登录用户按每位成员（含本人）最新体质档案对照本方适宜/不宜体质，未登录不渲染 | `FamilyFit.vue`（新） `RecipeDetail.vue` | build ✅；交互为纯前端组装既有 `/constitution/records` 数据，浏览器目检未做 |

**本线回归基线（2026-11-03 实测）**：端点 49 路径 / 53 端点不变（纯服务层改造）；vite build 通过；`scripts/check_consistency.py` 全绿。**单测（pytest 67 基线）因沙箱限制未跑，需在本机 PowerShell 复测后随 PR 记录**。另：`rel_herb_compound` 旧错乱表（201 行）仍在库中、代码已全部禁用，下次重建数据库时删除。

## 知识库扩容线（2026-11-05/06：药食同源目录 34→105 味，数据源 herb.ac.cn）

| 提交 | 功能 | 关键文件 | 验证 |
|---|---|---|---|
| `1673588` | 前置调研：自定义茶罐外部数据源实测（HERB 接口免注册可用、SymMap 整包可下、死库名单与许可红线） | `docs/自定义茶罐_数据来源调研.md` | 全部结论当日 curl 实测 ✅ |
| `81c3132` | 扩容方案定稿 + schema 增量：herb 加 source/reference_url/added_batch 三列；ID 命名决定（herb.id=HERB ID、compound.id=HBIN ID、target.gene=gene name，均不伪造 ccTCM 前缀）；幂等迁移函数（时间戳备份→pragma 检查→行数对比校验） | `docs/数据扩容方案_2026-11-05.md`（新）`docs/数据库设计文档.md` §6 `scripts/_migrate_20261105.py`（新） | 内存库语法验证 + 临时副本幂等二遍 PASS；六表行数不变 ✅ |
| `a540a7d` | **灌库执行**：105 味药材（106 目录−蝮蛇，槐米/槐花共用 HERB002472 落 imp: 惯例行）+ 5,478 新成分（4,397 带 SMILES，预测列全 NULL）+ 7,284 新靶点 + 9,106 成分归属 + 59,437 成分-靶点关联（P/FDR 只在药材级命中时记值，34,909 条如实 P=NA）；采集缓存 2.75MB 断点续传、脚本幂等二遍 0 变更 | `scripts/import_herbs_20261105.py`（新） | 五表行数复核、105/105 带溯源字段、HBIN 预测列 0 非空、pytest 84 passed、TestClient 检索/鉴方/web-lookup 冒烟 ✅ |
| 本提交 | **双口径一致性自检**：check_consistency.py 的 compound_count 校验改为 ccTCM→v3（修复口径）/HERB·imp→v1（扩容口径），修复 D3 全量按 v1 重算导致的 31 行旧药计数回归（乌梅 3→4、生姜 15→2 等）；清 user.db 8 条 not_found 脏缓存（含槐米——曾致鉴方误报）；扩容执行报告落盘 | `scripts/check_consistency.py` `docs/数据扩容执行报告_2026-11-06.md`（新） | `check_consistency.py` 全绿（v2≡v3、双口径计数一致、target_count 一致）；pytest 84 passed；herbs total=105 ✅ |

**数据真实红线执行情况**：新成分 prob_cctcm/radar 等模型列全 NULL（实测 0 污染）；新靶点 species='未知(herb.ac.cn)'；每味药材带 HERB ID 溯源；蝮蛇无 HERB 条目如实缺（105≠106）。
**已知口径边界**：证据链/解读端点仍读 v3（旧 34 味），新 71 味成分数据在检索/自定义鉴方/open API 可见、暂不进证据链（双口径取舍，扩容报告 §四 有升级路径）；custom-recipe 先查本地再打 API 的优化（P2）留待下阶段。
**注意**：`docs/数据扩容方案_2026-11-05.md` 修正了调研文档两处口径——HERB detail_api 数据在响应顶层（无 res_data 包裹）；74 味待新增药材异名映射后全可命中。

## 扩容二期收口 + 重建链路（2026-11-06：证据链全打通 / 一键重建）

| 提交 | 功能 | 关键文件 | 验证 |
|---|---|---|---|
| `c99bdd3` | **新药材全量入证据链**：①`backfill_material_herb_id.py` 回填 53 条配料 `herb_id`（枣/莲子/决明子/荷叶等，扩容前库里没这味药所以 NULL，是 21 方空链根因；正名→别名→药典异名三级匹配，53/53 精确命中 0 条靠猜）②`import_herbs_legacy10.py` 补 10 味旧药材（天冬/玉竹/百合/胖大海/薏苡仁/蜂蜜/酸枣仁/麦冬/麦芽/黄芪：v3 只覆盖 24 味，v1 对这 10 味与自建含量表重叠 0/10 判定错乱，故从 HERB 重拉；成分详情按 top20 逐个拉 `ingredient_target` 取真实靶点，**不做药材级靶点×全部成分的交叉积**）③新增 `services/herb_relation.py` 三口径统一读取 ④`/chain`、`explain/compound`、`rag_service` 改用三口径 | `scripts/backfill_material_herb_id.py`（新）`scripts/import_herbs_legacy10.py`（新）`backend/app/services/herb_relation.py`（新）`main.py` `explain_service.py` `rag_service.py` `EvidenceChain.vue` | **`/recipes/{rid}/chain` 覆盖 52/73 → 73/73（空链 0）**；成分反查打通（coumestrol → 枣/葛根/酸枣仁 + 8 方）；pytest 84 passed；check_consistency 全绿；vite build ✓ |
| `c99bdd3` | **口径对齐**：`API扩展记录.md` 补 6 条缺失端点（实测 55 路径/59 端点，清单 55 行 × 59 方法逐条与 openapi 对齐）；`CONTRIBUTING.md`（库 2.7MB→15.5MB、规模口径、pytest 基线 67→84、build_db 删库警告）；`数据库设计文档` §1.3 规模表全部更新 + 扩容对照 + 构建管线完整链路；`check_consistency.py` 计数改三口径 | `docs/API扩展记录.md` `CONTRIBUTING.md` `docs/数据库设计文档.md` `scripts/check_consistency.py` | 清单行数与端点数均与 openapi 复核一致 ✅ |
| `df2c722` | **知识库一键重建链路**：`rebuild_all.py`（926 行，沙箱驱动 19 步，每步可判定校验点，`--dry-run`/`--skip-ai`/`--skip-network`/`--skip-legacy10`/`--seed-from`/`--start-at`）+ 依赖表 + 实测记录；`DEPLOY.md` §4 移除「先跑 build_db.py」引导，改为醒目删库警告 + 链路指引 | `scripts/rebuild_all.py`（新）`docs/知识库重建链路_2026-11-06.md`（新）`docs/DEPLOY.md` | **两条链实测跑通并与现库行数完全对齐**：19 表口径 105/5,643/10,091/9,106/59,437、21 表口径 6,098/10,151/62,617/824/627；`check_consistency` 退出码 **0**；`recipe_analysis` 69 行逐字段 0 差异（`--seed-from`）；生产库全程只读、`integrity_check=ok` ✅ |
| 本提交 | **收尾**：`.gitignore` 补 `*.db.bak-*`/`*.bak-migrate-*`（`*.db` 匹配不到 `shiyang.db.bak-xxx`，15MB 备份一度会被误提交）；README/CONTRIBUTING/数据库设计文档同步最终口径（6,098 成分 / 10,151 靶点 / 62,617 关联）；AGENTS.md 补两条已知坑（三口径归属不要直接 JOIN v1；build_db.py 会删库） | `.gitignore` `README.md` `CONTRIBUTING.md` `docs/数据库设计文档.md` `AGENTS.md` | pytest 84 passed；openapi 55/59；vite build ✓；check_consistency exit=0 ✅ |

**实测发现的三个上游陷阱（已写进链路文档 §7.7，后续重建必读）**：
1. `build_db.py` 读修复**后**表只有 138 个成分，现库 165 来自修复**前**的旧表——直接跑复刻不出现库，需 `--seed-from`。
2. `pregen_analysis_v3.py` **不建表**，必须先跑 v1 否则崩溃。
3. `import_herbs_20261105.py` 按 v1 重算 `compound_count`，会把旧药的三口径计数覆盖掉（31 行偏差）——链路必须紧跟 `12b-recount`，否则 `check_consistency` 退出码 1。

**仍做不到逐行复刻的三项（依赖环境或外部 API，已在文档标注）**：`compound_map`（umap 0.5.12 需 sklearn≥1.5，本机 1.4.2）、`recipe_pathway`（Enrichr 判定漂移，58/57/61）、`compound_chembl_activity`（外部 API 数据随时间变，468 vs 465）。

## 配料图片补全（2026-11-06：缺图 63→0，署名 0→149 条全齐）

| 项 | 前 | 后 | 说明 |
|---|---|---|---|
| 药材有图 | 42/105 | **105/105** | 缺的 63 味几乎全是扩容新增（词表没跟着扩） |
| 食材有图 | 36/39 | **39/39** | 猪瘦肉/猪肚/猪脊骨 |
| 配料有图 | 76/82 | **82/82** | 与上面取并集，实际图片总数 82→**149** |
| credits 署名 | 1/82（81 条 null） | **149/149** | CC BY / CC BY-SA 要求署名，原为真实合规缺口 |

**根因（三个，都不是「拿不到」）**：
1. **词表没随扩容更新**——`MATERIALS` 只覆盖旧 34 味，扩容的 71 味一个词都没有；
2. **限流误判**——批量抓时 Wikimedia 返回 429，脚本一次就放弃（实测 42 项因此「失败」）；
3. **许可白名单漏了 CC BY-SA**——这是 Commons 上最常见的可用许可，漏掉导致大量「无合适许可图片」误报。

**修复**（`scripts/fetch_material_images.py`）：
- 词表 34→150 项；值支持 `list` 做**学名回退**。实测规律：搜索词带 `dried`/`rhizome`/`slices`
  会把结果压进文献扫描区（返回一堆 PDF 书页），纯学名命中率高得多（24 项里 22 项靠学名救回，多为 CC0）；
- API 调用加 429/5xx 指数退避重试（3/6/12/24s），单张下载 3 次重试，间隔 0.4s→1.2s；
- 许可白名单补 `CC BY-SA`；
- 新增 `BAD_TITLE` 过滤：排除 `(IA ...)`/`catalogue`/`journal`/`EUR 20xx`/`.pdf` 等扫描件与
  法条文献——它们许可虽是 PD，但图是书页不是实物照；
- 下载后统一用 PIL 转真 JPEG（Commons「缩略图」对 PNG 原图仍返回 PNG，实测 4 张 90-330KB，
  转换后 24-38KB，总体积 12MB→11.2MB）。

**署名回填**：81 条历史 `null` 无法可靠回填——本地存的是 480px 缩略图，sha1 与原图不同，
按搜索词重查会拿到**另一张图**，那样补出来的署名是错的（比留空更糟）。处置：只对这 81 项
**重抓**（图与署名必然对应），不动已合规的 68 张。结果 78 项一次成功，剩 3 项（乌梅/蒲公英/黄芪）
换词后补齐，可用词已写回词表。新增 `scripts/audit_image_credits.py` 做常态核查。

**顺带修掉一个数据失真**：`api/index.js` 的 `MAT_IMG_ALIAS` 里有 4 个「缺图兜底」映射
（当归→党参、天冬→麦冬、地黄→玉竹、猪肚→猪骨），现在这些药材都有真图了，继续用会显示
**别的药材的照片**。已删除错误映射，只保留真同物异名（枣→大枣）。

验证：149 张图魔数全为 JPEG、无损坏；149 条 credits 无 null；覆盖率 105/105 + 39/39 + 82/82；
`npx vite build` ✓。

## 食养评价体系科学重构与大众/专业分层落地（2026-11-06）

**背景**：
原大创课题（中药入血成分预测与哮喘机制研究）在方剂分析中遗留了专门针对哮喘的 Enrichr 三维机制评分（抗炎、免疫调节、气道修复），移植至全平台食养茶饮/汤羹后存在明显的场景失真（如失眠、消化方剂计算“气道修复”）。同时，导师与真实用户反馈方剂详情页专业数据门槛过高，缺乏接地气的大白话指引。

**核心改动**：
1. **食养科学三维指数（`eval_service.py`）**：
   - 彻底废除 `RESP_SCENES` 呼吸场景硬编码门控，重构为适用于全库 73 个方剂的科学评价三维体系（满分 100）：
     - **入血潜力 (`absorption`)**：PU-Learning 核心成分预测入血概率均值 × 100（60～96 分）；
     - **多靶协同 (`synergy`)**：网络药理学人类功能蛋白靶点互联对数映射（55～95 分）；
     - **证据强度 (`evidence`)**：药食同源目录/医家方源与 PubMed/ChEMBL 实验证据分级加权（70～95 分）。
   - 新增独立端点 `GET /api/v1/recipes/{rid:int}/eval`；`recipe_detail` 注入 `eval_summary`，`compare_service` 对比雷达全面切换。
2. **大众与专业双层分级模式（Pro 模式）**：
   - 全局顶部导航新增专业模式开关（`proMode.js`，持久化状态）；
   - 默认大众模式下优先展示「说人话」大白话卡片（`PlainCard.vue`，73 方离线预生成），折叠深层生物计算；开启专业模式后展开成分入血、靶点网络与证据链。
3. **食养核心功效 Agent 重塑与排版去虚长**：
   - 提示词与预生成链路升级，剔除哮喘科研指标，形成四段式标准解读（【核心功效与主打场景】【配伍组合的奥秘】【为什么感觉舒服（通俗机理）】【冲泡建议与避坑提醒】）；
   - 修复详情页 `.col-side` 栅格在 flex 布局下高度被强制拉伸至 1500px 造成大量空白的排版 Bug。

**验证指标**：
- 端点规模：实测 **56 路径 / 60 端点**；
- 后端单测：`backend/tests/test_eval_service.py` 补充 3 个用例，全套测试 **87 passed**；
- 前端构建：`npx vite build` 1.42s 顺利编译；
- 提交：`0ac98e4` (plain-pro), `7fecc18` (ai-report), `2f32871` (eval-system)。
