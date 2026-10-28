# 协作指南（CONTRIBUTING）

> 面向第一次参与本仓库的协作者。跟着做完 0→3 节就能把项目跑起来，
> 4→6 节讲怎么提改动。仓库铁律见 [AGENTS.md](AGENTS.md)，本文不重复，只讲怎么上手。

## 0. 你需要先拿到的两样东西

| 东西 | 从哪来 | 说明 |
|---|---|---|
| 仓库代码 | `git clone https://github.com/jxylisty/shiyang.git` | 公开仓库 |
| `data/shiyang.db` | **向项目维护者索取**（约 2.7 MB） | 知识库，见下方说明，不在仓库里 |

### 关于数据库（重要，别自己造）

`data/*.db` 都在 `.gitignore` 里，**clone 下来是没有数据库的**，后端跑不起来。两个库处理方式不同：

**`data/shiyang.db`（知识库，需要索取）**

34 味药材 / 165 化合物 / 2807 靶点 / 73 方 —— 这是项目的核心数据，必须向维护者要一份，放到 `shiyang/data/` 下。

不要试图用 `scripts/build_db.py` 自己重建，它有两个限制：

1. 它的数据源是 `../my-asthma-system/asthma-core/data/asthma_v2.db`（仓库外部路径），你本地没有；
2. 它只建 13 张表，而实际库有 18 张 —— `recipe_analysis`（成分分析）、`recipe_pregen_ai`（AI 预生成解读）、`recipe_pathway`（通路富集）是后续脚本产出的，`build_db.py` 不覆盖，你重建出来的库会缺这些，方子详情页会大片空白。

**`data/user.db`（用户库，不用索取）**

后端第一次启动时 `user_service` 会自动建表（`CREATE TABLE IF NOT EXISTS` + `_migrate()`），你那边生成的就是干净空库。**不要**把别人的 `user.db` 拷过来，会把自己的测试数据和他的历史数据混在一起。

> `data/shiyang.db` 是**只读**的（`get_db()` 用 `mode=ro` 打开），运行时任何接口都不会写它，尽管放心。

## 1. 环境要求

- Python 3.12
- Node 20
- Windows + Git Bash（其他系统也能跑，命令略有差异）

## 2. 装依赖

```bash
# 后端
cd backend
pip install -r requirements.txt
# 跑测试还需要：
pip install -r requirements-dev.txt

# 前端
cd ../frontend
npm install
```

## 3. 跑起来

```bash
# 终端 1：后端（8100 端口）
cd backend
python -m uvicorn app.main:app --port 8100

# 终端 2：前端（5174 端口，/api 已代理到 8100）
cd frontend
npm run dev
```

浏览器打开 http://127.0.0.1:5174 。后端接口文档在 http://127.0.0.1:8100/docs 。

**Windows 上跑任何读库的 Python 命令，都加 `-X utf8`**，否则中文输出乱码：

```bash
python -X utf8 -c "import sqlite3; ..."
```

## 4. 提改动：完整流程

### 第一次：配置 Git 身份

```bash
git config --global user.name "你的名字"
git config --global user.email "你的邮箱"
```

### 每次干活：四步

```bash
# ① 开工前同步，永远在最新 master 上拉分支
git checkout master
git pull origin master

# ② 建自己的分支（名字要有意义）
git checkout -b feat/简短描述

# ③ 改完提交
git status                      # 先看自己改了哪些文件
git add 具体的文件名             # 只加自己改的文件，别用 git add -A / git commit -a
git commit -m "feat(scope): 一句话说明改了什么"

# ④ 推分支（推自己的分支，不是 master）
git push origin feat/简短描述
```

推上去后终端会直接给一条 PR 创建链接，形如
`https://github.com/jxylisty/shiyang/pull/new/feat/简短描述`，点开即可。

### 提 PR 要填什么

1. 确认左边 **base: master**，右边 **compare: 你的分支**
2. 标题：一句话说清改了什么
3. 描述写三件事：**改了什么 / 为什么改 / 怎么验证的**（跑了什么命令、看到什么结果）
4. 点 **Create pull request**

## 5. 提交规范

- 类型前缀：`feat(scope):` / `fix(scope):` / `docs:` / `chore:` / `refactor(scope):`
- scope 用功能名（如 `T1-5`、`ui`、`ai`）
- **一个可验证的改动提交一次**，不要攒一堆功能到最后一次性提交
- **提交信息里不写没做过的测试** —— 写了什么验证就得真跑过

## 6. 提交前必须跑一遍

```bash
# 后端单测（当前基线 67 passed，以实际运行为准）
cd backend && python -X utf8 -m pytest tests/ -q

# 端点规模（真实数字，别抄文档）
cd backend && python -X utf8 -c "import sys; sys.path.insert(0,'app'); import main; \
  s=main.app.openapi(); print('paths', len(s['paths']), 'endpoints', sum(len(v) for v in s['paths'].values()))"

# 前端构建（通过才允许提交前端改动）
cd frontend && npx vite build
```

**没通过就不提交。** 提交前不声称做过没做过的测试。

## 7. 最容易踩的坑

1. **只 `git add` 自己改的文件**。本仓库常有多个 AI/人并行工作，工作区里可能有别人未提交的半成品。`git commit -a` 会把它们一起提交。
2. **别用这些命令**：`git clean -fd`、对他人未提交文件 `checkout/restore`、`push --force`、在 master 上 rebase/reset 改写已共享历史 —— 会毁掉别人的工作。
3. **不提交**：`*.db`、`node_modules/`、`dist/`、`__pycache__/`、`.zcode/`（都已在 `.gitignore`，别手动 add）。
4. **测试数据用完即删**。往 `user.db` 写过测试账号/打卡后，收尾要删干净（顺序：checkin → favorite → constitution_record → family_member → user）。真实用户数据禁止用于测试。
5. **FastAPI 路由顺序**：字面量路径（`/recipes/compare`）必须注册在动态路径（`/recipes/{rid}`）之前，否则 422。
6. **`user.db` 加列**：新列一律进 `user_service._migrate()` 做增量 `ALTER TABLE`；`CREATE TABLE IF NOT EXISTS` 不会给存量表补列。

更多已知坑见 [AGENTS.md](AGENTS.md) §5。

## 8. 内容红线（不可破）

本平台是健康参考信息平台，**任何文案不得把模型预测/参考分写成疗效或临床结论**。

- 每个涉及健康内容的页面/接口响应都要带免责声明：`本平台内容为健康参考信息，不构成医疗建议，不用于诊断或治疗。`
- 入血概率（`prob_cctcm`）是 PU-Learning **模型预测值**，不是实验事实
- 证据分级 A=权威出处 / B=实验数据库 / C=模型预测，定义在 `services/evidence_service.py`，不许为好看而拔高
- AI 生成内容必须标注来源（现有约定 `source: 'pregen'`）

细节见 [AGENTS.md](AGENTS.md) §2「数据真实铁律」。

## 9. 卡住了怎么办

- 接口清单：`docs/API扩展记录.md`（实测全清单）
- 数据库表结构：`docs/数据库设计文档.md`
- 部署/上线：`docs/DEPLOY.md`
- 功能规划与撞车分析：`docs/功能扩展调研清单.md`
- 提交历史与每步验证记录：`CHANGELOG.md`

还是不清楚，直接在 PR 里问，或开 issue。
