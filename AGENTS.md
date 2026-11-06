# AGENTS.md —— 食养有据仓库 AI 协作规范

> 本文件面向所有在此仓库工作的 AI agent（含并行协作的多 agent 场景）。
> **开始动手前先读完本文件。** 所有规则基于 2026-10-26 实测事实，非推测。
> 与用户最新指示冲突时，以用户指示为准，但要在回复中说明偏离了哪条规则。

## 1. 项目速览（事实卡）

| 项 | 值 | 怎么核实 |
|---|---|---|
| 定位 | 药食同源食疗·茶饮有效成分分析平台（大创课题「中药入血成分预测」的用户级产品化） | README.md |
| 后端 | FastAPI + SQLite，`uvicorn app.main:app --port 8100` | `backend/app/main.py`（VERSION 以代码为准） |
| 前端 | Vue3 + Vant + Vite，dev 端口 5174，`/api` 代理到 127.0.0.1:8100 | `frontend/vite.config.js` |
| 知识库 | `data/shiyang.db`（方子/药材/成分/靶点，**运行时只读** `mode=ro`） | `main.py` 的 `get_db()` |
| 用户库 | `data/user.db`（账号/档案/收藏/打卡/家庭成员，运行时可写，WAL） | `backend/app/services/user_service.py` |
| 数据库是否入库 | **否**。`*.db` 在 .gitignore；`scripts/build_db.py` 可重建；重建前的备份 `data/shiyang.db.bak-before-rebuild` 已提交 | `git ls-files data/` |
| 端点规模 | 2026-11-06 实测 **57 路径 / 61 端点**（v0.2.0 旧文档写 24 个，历史口径 46/50、55/59、56/60 均已过时；清单见 docs/API扩展记录.md，以 §6 复跑结果为准） | 见 §6 自检命令 |
| 运行环境 | Python 3.12 / Node 20（Windows + Git Bash） | `python --version; node --version` |

**红线（每页、每个接口响应都要在）**：
`本平台内容为健康参考信息，不构成医疗建议，不用于诊断或治疗。`
代码里对应 `main.py` 的 `DISCLAIMER` 常量，新增接口凡涉及健康内容必须带上。

**前端视觉红线（严禁颜文字与 Emoji，太掉价）**：
**全站前端界面严禁使用 Emoji 表情符号（如 🎯🌿💡🍵✨★ 等）或字符颜文字（如 `^_^`、`orz`）**。
本项目定位为严肃、学术、精致的药食同源科学分析平台，使用颜文字会显得极度廉价与业余。
- 图标统一采用 `@lucide/vue` 矢量线性 SVG 图标（如 `<Target />`, `<Leaf />`, `<Lightbulb />`, `<Coffee />`）或规范内联 SVG；
- Toast / Alert / 按钮提示语保持纯文本精炼，严禁带特殊字符尾巴（写「已加入收藏」而非「已加入收藏 ★」）。

## 2. 数据真实铁律（最高优先级）

**不准胡编乱造。文档、代码、界面、答辩材料里的每个数字和每条数据主张都必须可溯源。**

1. **数字只能来自实测**。引用「多少个方子/成分/靶点/端点」之前，先跑查询（§6 有现成命令），并写明核实日期。数据会被重建（2026-10 已发生过一次药材-成分归属系统性重建，见 docs/归属重建报告.md），**旧数字即刻作废**。
2. **来源字段不许留空**。新增药材/方子/成分关联必须带出处（`source`/`reference_url`），录入模板与 `recipe.source` 的既有惯例是「机构名+篇名+链接」。没有来源的数据宁可不录。
3. **模型预测 ≠ 实验事实**。入血概率（`prob_cctcm`）是 PU-Learning 模型预测值；三维机制评分沿用大创课题靶点富集框架、按场景门控（提交 7c4056b）。任何文案不得把预测/参考分写成疗效或临床结论。
   **入血概率有三档口径，不要直接 `SELECT prob_cctcm`**（那只有 165 行，会把 4,200+ 成分显示成"无数据"）：
   统一走 `services/prob_caliber.py` 的 `SQL_PROB` / `SQL_CALIBER`，它按
   `prob_cctcm`(165, 旧主力) → `prob_cctcm_v2`(795, 正式版) → `prob_herb_v2`(3,602, C 级外推) 选唯一值并带回来源标签。
   **缺预测返回 None，绝不填 0**：0 表示"模型判定完全不入血"，与"没有预测"是两个结论。
4. **证据分级不许越级**。A=权威出处 / B=实验数据库（含 PMID）/ C=模型预测，定义在 `services/evidence_service.py`；新增数据按此定义如实归级，禁止为好看而拔高。
5. **编辑性规则要标注**。安全滤镜禁忌词表（`services/safety_service.py`）、节气食养主题映射（`services/term_service.py`）等属于「按药典通识/常识整理的产品规则」，改动时在注释里注明性质与依据，不得伪装成实验数据；涉及人群安全的内容发布前需真人医药背景审校。
6. **AI 生成内容必须标注**。`recipe_pregen_ai` 预生成解读回放时要显示来源为 AI（现有 `source: 'pregen'` 约定），新界面不得移除该标注。
7. **测试数据测完即删**。往 `user.db` 写过测试账号/打卡（TestClient 冒烟也会写），收尾必须删干净（外键关闭后按 checkin→favorite→constitution_record→family_member→user 顺序删）。真实用户数据绝对禁止用于测试。

## 3. Git 纪律（改完必提交）

1. **完成一个可验证的改动就提交一次**，禁止大批量功能攒到最后一次性提交；提交类型用 `feat(scope):` / `fix(scope):` / `docs:` / `chore:`，scope 用功能名（如 `T1-5`）。
2. **提交前先 `git status` + `git log --oneline -5`** 了解现场：本仓库常有**多个 AI 并行工作**，工作区里可能有别人未提交的半成品。
3. **只 `git add` 自己改的文件**。禁止 `git commit -a`。同一个文件被他人并行修改时，用 `git add -p`（或过滤 diff 生成 patch 再 `git apply --cached`）只暂存自己的 hunk，并**提交前用 `git diff --cached <file>` 逐块核对暂存内容是否是你以为的那些**。
4. **严禁以下操作**（会毁掉他人工作）：`git clean -fd`、对他人未提交文件 `checkout/restore`、`push --force`、在 master 上 rebase/reset 改写已共享历史。需要中断他人运行进程用任务停止工具，不要 kill 进程树。
5. **提交必须通过验证**（§6），未验证不提交；提交信息里不声称做过没做过的测试。
6. **不提交**：`*.db`、`node_modules/`、`dist/`、`__pycache__/`、截图目录、`logs_*.txt`、`.zcode/`（均已在 .gitignore，别手动 add 它们）。schema 变更**代码**要提交（迁移函数本身），数据库文件不提交。
7. 误把他人代码提交了的善后：用 `fixup(...)` 提交补齐，保证每个提交点工作区自洽可构建；不要改写已提交历史来"摘除"。

## 4. 多 AI 并行协作守则

1. **动文件前**先查它是否干净：`git status --short <file>`。有未提交改动 = 别人在改它 → 优先选替代方案：
   - 新建独立组件/服务再挂载一行（`SafetyBanner.vue` / `EvidenceCard.vue` / `ConstitutionCard.vue` 模式即为此设计）
   - 必须改同一处时，改最小 diff，避开对方的语义区。
2. **新功能落点惯例**：后端 = `backend/app/services/xxx_service.py` 纯函数服务 + `main.py` 挂 3-5 行路由；前端 = 新页面进 `views/` + 路由 1 行 + API helper 集中 `api/index.js` + 入口尽量走独立组件。
3. 改了共享热文件（`App.vue`/`style.css`/`motion.js`/`Home.vue`）后提交前，务必 `git diff` 复核只含你的 hunk。
4. 文档类交付也要提交（本仓库 docs/ 是答辩材料区，改动同样走 git 纪律）。

## 5. 已知坑（全部本项目实际踩过，勿重蹈）

1. **FastAPI 路由顺序**：字面量路径（`/recipes/compare`）**必须注册在动态路径（`/recipes/{rid}`）之前**，否则 422。兜底做法：`{rid:int}` 类型转换器（已加，别去掉）。
2. **user.db 加列**：`CREATE TABLE IF NOT EXISTS` 不会给存量表补列。新列一律进 `user_service._migrate()`（增量 `ALTER TABLE` + try/except）。
3. **Windows 编码**：跑 Python 查库/脚本一律 `python -X utf8`，否则中文输出乱码；Git Bash 的 CRLF 警告无害。
4. **后台标签页 rAF 冻结**：动画收尾计时不要用双 `requestAnimationFrame`，用双 `setTimeout`（提交 7c4056b 之前的教训，`Quiz.vue`/`RecipeDetail.vue` 已修，新动画沿用）。
5. **Vant `van-popup` 的 show 是布尔值**：「选中哪个槽位」这类字符串状态需要 computed 桥接（`CompareLab.vue` 的做法）。
6. **测试依赖不在正式 requirements**：pytest 装在运行环境里（9.1.1），正式依赖见 `backend/requirements.txt`，测试依赖见 `backend/requirements-dev.txt`。
7. **图片资源**：配料图构建期预拉取（`scripts/fetch_material_images.py` → `frontend/public/img/materials/`）。
   新增食材必须同步补词表（`MATERIALS`，值可写 `list` 做学名回退——带 dried/rhizome 等限定词
   会把 Commons 结果压进文献扫描区，纯学名命中率高得多）。三条硬规矩：
   ① 不要为「缺图兜底」写跨物种映射（`当归→党参` 这类会显示**别的药材**照片，属数据失真）；
   ② 每次抓完跑 `scripts/audit_image_credits.py` 确认「图 ↔ 署名」齐全（CC BY/CC BY-SA 要求署名）；
   ③ Commons 的「缩略图」对 PNG 原图仍返回 PNG，脚本已统一转真 JPEG，勿绕过。
8. **药材-成分归属有三种口径，不要 `JOIN rel_herb_compound` 了事**：`rel_herb_compound`(v1) 里旧 34 味的
   201 行是**未修复的错乱快照**（人参皂苷挂薄荷那版），v3 才是修复口径；扩容的 71 味写在 v1 的非 ccTCM 行，
   补录的 10 味在新表 `rel_herb_compound_herb`。凡按药材取成分/按成分反查药材，统一用
   `services/herb_relation.DUAL_RELATION_SQL`，否则要么丢扩容数据、要么把错乱数据捞回来。
9. **`scripts/build_db.py` 会删库**（开头 `OUT.unlink()`），且只建 11 表。它是重建链路的**第一步**，
   不是「重建知识库」的命令；单独跑会丢 71 味药材 + 5,478 成分。完整链路见
   `docs/知识库重建链路_2026-11-06.md` / `scripts/rebuild_all.py`。
10. **前端绝不使用颜文字与 Emoji**：分块标题、按钮、标签、弹窗禁止手塞 Emoji 表情或符号字符（极其掉价）；图标一律走 `@lucide/vue` 矢量 SVG。

## 6. 自检命令（改完提交前跑一遍）

```bash
# 后端可导入 + 端点规模（真实数字，别抄文档）
cd backend && python -X utf8 -c "import sys; sys.path.insert(0,'app'); import main; \
  s=main.app.openapi(); print('paths', len(s['paths']), 'endpoints', sum(len(v) for v in s['paths'].values()))"

# 单测（2026-11-06 实测 106 passed，10 个文件；测试索引见 backend/tests/README.md。
# 数量随测试线补用例增长，以实际运行为准，别抄文档）
cd backend && python -X utf8 -m pytest tests/ -v

# 冒烟（TestClient，不占端口；注意测试数据清理规则见 §2.7）
cd backend && python -X utf8 -c "import sys; sys.path.insert(0,'app'); \
  from fastapi.testclient import TestClient; import main; c=TestClient(main.app); \
  print(c.get('/api/v1/health').status_code)"

# 前端构建（通过才允许提交前端改动）
cd frontend && npx vite build

# 知识库只读性抽查（运行期不应有任何写接口动 shiyang.db）
```

## 7. 文档区索引（现状 2026-11-06）

**先看 [`docs/00-index.md`](docs/00-index.md)**：它维护全量文档地图、已确认的矛盾登记和过期警告，
是本仓库文档的导航权威。下表只列最常被引用的几份。

| 文档 | 内容 | 时效 |
|---|---|---|
| docs/00-index.md | 全量文档索引 + 一致性矛盾登记 + 过期警告 | 有改动后需同步 |
| README.md | 项目门面（数据规模为 2026-11-06 只读实测口径） | 数据变动后需复核 |
| docs/PROGRESS.md | 项目进度、阻断项、下一步判断 | project-driver 维护 |
| docs/API接口设计文档.md | v0.2.0 基线 24 端点设计 | **基线过时**，增量见下 |
| docs/API扩展记录.md | 实测 57 路径/61 端点全清单与增量说明 | 加端点后须复跑补行 |
| docs/数据库设计文档.md | 两库表结构（§1.3 实测行数，§6 扩容 schema 增量） | user.db 含 family_member（T2-8） |
| docs/知识库重建链路_2026-11-06.md | 从零重建 19 步链路（输入/校验点/跳过后果） | **重建唯一权威**，别照旧文档跑 build_db.py |
| docs/数据扩容执行报告_2026-11-06.md | 34→105 味扩容落库结果 | 现行数据口径权威 |
| docs/归属重建报告.md | 药材-成分归属系统性修复 | 重建后数据以此为准 |
| docs/功能扩展调研清单.md | T1/T2 梯队功能与竞品对照 | 功能已按此实现 |
| docs/竞品对比分析.md / 支撑论文清单.md / 开源资源清单.md / 数据应用与真实化方案.md / 用户验证方案.md | 课题材料 | 逐链接/逐条核实版 |
| backend/tests/README.md | 测试索引：10 文件 106 用例、跑法、排障 | 加测试后需同步 |
| scripts/README.md | 41 个脚本分类索引 + 危险脚本清单 | 加脚本后需同步 |
| CHANGELOG.md | 开发日志（含提交哈希） | 持续维护 |
