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
