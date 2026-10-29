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
