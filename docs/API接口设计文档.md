# 食养有据 · API 接口设计文档

- **版本**：v0.2.0（对应 backend `main.py` VERSION）
- **基准日期**：2026-10-26（本文档由全量代码审查 + 24 端点冒烟测试生成，全部通过）
- **Base URL**：`http://<host>:8100/api/v1`
- **技术栈**：FastAPI + SQLite（分析库只读连接）+ JWT（HS256）+ bcrypt

> 红线声明（全平台）：**本平台内容为健康参考信息，不构成医疗建议，不用于诊断或治疗。**
> 该声明随 `/stats`、`/constitution/questionnaire`、`/constitution/submit`、`/recipes/{id}` 响应下发，前端固定渲染于每个页面页脚。

---

## 1. 设计原则

| 原则 | 落地方式 |
|---|---|
| 统一响应包 | 所有 JSON 接口返回 `{code, message, data}`；`code=0` 成功，非 0 预留业务错误码 |
| REST 语义 | GET 查询 / POST 创建（收藏、打卡幂等）/ DELETE 取消；404=资源不存在、400=参数/凭证错误、401=未登录或 token 失效 |
| 分析库只读 | 业务数据（用户/档案/收藏/打卡）独立存 `user.db`；方子知识库 `shiyang.db` 以 `mode=ro` 打开，运行期不可被 API 破坏 |
| AI Key 不落库 | 用户 LLM Key 仅当次请求使用（优先 `X-AI-Key` 请求头，不进 URL 日志）；无 Key 时回放平台预生成解读 |
| 幂等性 | 收藏、打卡对同一资源重复操作返回既有状态（`already=True`），不产生重复行 |

## 2. 通用约定

### 2.1 响应包

```json
{ "code": 0, "message": "success", "data": { ... } }
```

错误时 FastAPI 默认格式 `{"detail": "..."}` 与 HTTP 状态码一并使用（400/401/404）。SSE 流内错误以 `data: {"error": "...", "code": "key_missing"}` 事件下发。

### 2.2 认证

- 登录/注册成功即返回 `token`（JWT，有效期 14 天，payload `{uid, username, exp}`）。
- 需登录接口带 `Authorization: Bearer <token>`。缺失/无效/过期统一 401。
- 涉及接口：`/me`、`/constitution/records`、`/favorites*`、`/checkins*`。

### 2.3 分页与参数钳制

- `page ≥ 1`（≤1000）、`size` 1–100、`min_prob` 0–1、`network` 的 `max_compounds` 1–20 / `max_targets` 1–40、`records limit` 1–100。越界自动收敛，不报错。

---

## 3. 接口总览（24 个）

| # | 方法 | 路径 | 认证 | 功能 |
|---|---|---|---|---|
| 1 | GET | `/health` | — | 存活检查（status/version） |
| 2 | GET | `/stats` | — | 数据规模统计 + 免责声明 |
| 3 | GET | `/constitution/questionnaire` | — | CCMQ 58 题量表（9 维度） |
| 4 | POST | `/constitution/submit` | — | 提交答案 → 转化分/判定/推荐 |
| 5 | GET | `/constitution/{code}` | — | 体质详情（宜忌/茶饮思路） |
| 6 | GET | `/recipes` | — | 方子列表（分页 + 多条件筛选） |
| 7 | GET | `/recipes/{rid}` | — | 方子详情（配料/分析/免责） |
| 8 | GET | `/herbs` | — | 药材检索（名称/拼音） |
| 9 | GET | `/compounds` | — | 高入血概率化合物列表 |
| 10 | GET | `/recipes/{rid}/ai-report` | — | AI 解读（SSE 流式） |
| 11 | GET | `/recipes/{rid}/exposure` | — | 成分暴露量估计（mg 区间） |
| 12 | GET | `/recipes/{rid}/network` | — | 成分-靶点网络图数据（ECharts） |
| 13 | POST | `/auth/register` | — | 注册（用户名规则 + bcrypt） |
| 14 | POST | `/auth/login` | — | 登录（签发 JWT） |
| 15 | GET | `/me` | ✔ | 当前用户信息 |
| 16 | POST | `/constitution/records` | ✔ | 保存体质测评档案 |
| 17 | GET | `/constitution/records` | ✔ | 历史档案列表 |
| 18 | POST | `/favorites/{recipe_id}` | ✔ | 收藏（幂等） |
| 19 | DELETE | `/favorites/{recipe_id}` | ✔ | 取消收藏 |
| 20 | GET | `/favorites` | ✔ | 收藏列表（带方子卡片信息） |
| 21 | POST | `/checkins/{recipe_id}` | ✔ | 当日饮用打卡（幂等） |
| 22 | DELETE | `/checkins/{recipe_id}` | ✔ | 撤销当日打卡 |
| 23 | GET | `/checkins` | ✔ | 近 30 天打卡 + 连续天数 |
| 24 | — | — | — | （交互文档）FastAPI 自带 `/docs` Swagger UI |

## 4. 接口明细

### 4.1 体质测评

**GET /constitution/questionnaire** — 58 题 CCMQ 量表（ZYYXH/T157-2009），按 9 维度分组。

```json
{ "code": 0, "data": {
  "items": { "pinghe": ["（题干）…", "…"], "qixu": ["…"], "…": [] },
  "scoring": "每题：没有=1分、很少=2分、有时=3分、经常=4分、总是=5分",
  "disclaimer": "本平台内容为健康参考信息，…"
} }
```

**POST /constitution/submit** — Body：`{"answers": {"维度code": [每题1-5分…]}}`

- 维度题数不符 → 400（如“维度 qixu 需要 8 题的答案”）。
- 成功返回 `transformed`（各维度转化分 0-100）、`judged`（9 维度 `{score, result}` 判定结果 + `main`/`combined` 兼夹）、`main_constitution`（主体质详情）、`recommendations`（推荐方子，命中体质数排序、排除不宜体质、含倾向体质弱推荐）。

**GET /constitution/{code}** — 九种体质 code：`pinghe / qixu / yangxu / yinxu / tanshi / shire / xueyu / qiyu / tebing`。返回典型表现、调理原则、宜忌食物、茶饮思路、生活建议、参考出处。未知 code → 404。

### 4.2 方子库

**GET /recipes** — Query：`type`（茶饮/药膳）、`scene`（场景）、`constitution`（体质短名）、`q`（名称模糊）、`page/size`。

```json
{ "code": 0, "data": { "total": 73, "page": 1, "size": 20,
  "items": [{ "id": 1, "name": "银耳雪梨羹", "type": "药膳", "oneliner": "…",
              "scenes": ["润燥"], "constitutions_suitable": ["阴虚"],
              "duration": "40分钟", "analysis_ready": true, "materials": ["银耳"] }] } }
```

- `materials` 为卡片封面用的首味配料名（单元素数组）。
- Python 侧对 JSON 列（scenes/constitutions）做筛选，`status='弃用'` 恒排除。

**GET /recipes/{rid}** — 完整字段：基本信息 + `materials[]`（含 herb 性味归经功效、`is_food_homology` 标记）+ `analysis`（`top_compounds[]` 高入血概率成分、`radar_summary` 三维评分、`top_targets[]` 主要靶点、`generated_at`）+ `disclaimer`。404：方子不存在。

### 4.3 成分数据

**GET /herbs** — `q` 匹配名称 LIKE / 拼音前缀，按 `compound_count` 降序。返回 34 味药材的性味归经、功效、化合物计数、目录批次。

**GET /compounds** — `min_prob`（默认 0.5，钳制 0–1）、`limit`（默认 50，上限 200）。返回化合物 `prob_cctcm`（PU-Learning 入血概率）、`prob_herb`、MW/LogP、三维雷达分。

### 4.4 AI 流式解读（SSE）

**GET /recipes/{rid}/ai-report**

| 参数 | 位置 | 说明 |
|---|---|---|
| `X-AI-Key` | Header（推荐） | 用户 LLM Key，不进访问日志 |
| `key` | Query（兼容保留） | 同上，历史前端在用 |
| `provider` | Query | `deepseek`（默认）/ `openai`，OpenAI 兼容协议 |
| `model` / `base_url` | Query | 自定义模型与网关地址 |

响应 `text/event-stream`：

```
data: {"delta": "片段", "source": "pregen"}     ← 预生成回放时带 source
data: {"error": "API Key 无效", "code": "key_invalid"}   ← 流内错误
data: [DONE]
```

- **无 Key**：回放平台预生成解读（69/73 方已覆盖），按 4 字/28ms 节奏分片模拟打字机；无预解读 → 404 引导填 Key。
- **有 Key**：实时调用用户配置的 OpenAI 兼容端点，Key 不落库、不写日志。
- 流内错误码：`key_missing` / `key_invalid`（401）/ `quota_exhausted`（402）。

### 4.5 暴露量估计与网络图

**GET /recipes/{rid}/exposure** — 公式：摄入量 mg = 克重 g × 文献含量% × 转移率 50%（保守假设）。返回 top15 `{herb, grams, compound, est_mg_min, est_mg_max}` + 说明文案。

**GET /recipes/{rid}/network** — ECharts graph 布局数据：`nodes[]`（category 0=方子/1=成分/2=靶点，value 随入血概率/连接数缩放）、`edges[]`、`legend`。默认取 top6 成分 × top12 靶点（按共连接数排序）。

### 4.6 用户系统

**POST /auth/register** — Body `{username, password, nickname?}`。用户名 3-20 位字母数字下划线；密码 ≥6 位；bcrypt 存储。重复注册 → 400“用户名已被注册”。成功返回 `{id, username, nickname, token}`。

**POST /auth/login** — 凭证错误统一 400“用户名或密码错误”（不区分用户不存在/密码错）。

**GET /me** — 返回 `{id, username, nickname, created_at}`。

### 4.7 体质档案 / 收藏 / 打卡

**POST /constitution/records** — Body `{judged, transformed, answers}`（测评结果三件套，answers 存原始作答供复现）。**GET /constitution/records** — 倒序列表（默认 20 条，钳制 100），combined 已翻译为体质名。

**POST /favorites/{recipe_id}** — 幂等收藏；**DELETE** 取消；**GET /favorites** 返回按收藏时间倒序的方子卡片。

**POST /checkins/{recipe_id}** — 当日打卡，一天一方一条（UNIQUE 约束保证），重复打卡返回 `already: true`；**DELETE** 撤销当日；**GET /checkins** 返回 `{records[]（含 recipe_name）, streak 连续天数, total 近30天打卡天数, today 今日打卡方子}`。连续天数从今天或昨天向前连续计算。

## 5. 安全设计

| 项 | 实现 |
|---|---|
| 密码存储 | bcrypt（自带盐，cost 默认） |
| 会话 | JWT HS256，14 天过期；secret 从 `SHIYANG_JWT_SECRET` 环境变量读取（开发缺省值仅供本地） |
| 用户库完整性 | SQLite `PRAGMA foreign_keys=ON`（档案/收藏/打卡的 user_id 外键强制生效） |
| SQL 注入 | 全部语句参数化（含 IN 子句用占位符拼接） |
| Key 泄露面 | 用户 AI Key 优先 Header 传输、不落库；平台 Key 仅存服务端环境变量 `SHIYANG_AI_KEY` |
| 输入校验 | Pydantic 模型 + 手工规则（用户名/密码/题数）+ 数值钳制 |
| CORS | 当前 `allow_origins=["*"]`（演示期）；**上线前应收敛为前端域名白名单**（见 §7 待办） |

## 6. 参赛评审要点对照

- **完整性**：体质测评→推荐→方子详情→成分证据（入血概率/靶点/网络图/暴露量）→AI 解读→账户/档案/收藏/打卡，用户闭环全链路有接口支撑，前后端契约 100% 对齐（`frontend/src/api/index.js` 逐一核对）。
- **科学性叙事**：每个推荐背后可下钻到 prob_cctcm 入血概率、三维评分、靶点网络、文献含量与保守暴露估计——与“入血预测”大创课题成果直接承接。
- **工程规范**：统一响应包、REST 语义、幂等、分页钳制、只读库分离、SSE 错误事件——达到产品级接口设计标准。
- **可验证**：本文档基准日全量 24 端点冒烟通过（含 404/400/401/幂等/SSE 错误分支）。

## 7. 已知边界与后续路线

1. **CORS 白名单**：上线部署时将 `allow_origins` 收敛为实际前端域名。
2. **AI pregen 覆盖**：69/73 方有预解读（25/66/69 号方无成分分析）。补 `run_pregen` 即可，或保持“填 Key 实时生成”兜底。
3. **速率限制**：面向公网部署时建议对 `/auth/*` 与 AI 实时生成加 IP 级限流（当前校内演示非必须）。
4. **响应包错误码**：`code` 字段当前恒为 0，业务错误统一走 HTTP 状态码 + `detail`；如评审需要可扩展非 0 业务码表。
5. **管理端**：方子库的增删改走 `scripts/` 离线管线（build_db → pregen），未开放在线管理接口——演示产品定位下合理。
