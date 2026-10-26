# 「补五脏」四功能落地计划（对照竞品报告的借鉴项）

背景：调研清单一、二梯队 10 个功能已全部实现，本轮补的是对照竞品（Examine 成分词典模式 / 知源中医全局搜索 / 膳时营养素 / 传播链路）的基础完备度缺口。按优先级排序，前两项是核心。

---

## 1. 全局搜索（对标知源中医；成本最低）

**后端** `backend/app/main.py` + 新建 `backend/app/services/search_service.py`：
- `GET /api/v1/search?q=关键词`，一次查询聚合三类结果，各取前 5 条：
  - 方子：`recipe` 表 name LIKE（复用方子列表的行结构：id/name/type/scene/suitable_constitutions）
  - 药材：`herb` 表 name/pinyin LIKE（复用 `/herbs` 的字段）
  - 成分：`compound` 表 name LIKE，按 prob_cctcm 排序（name/mw/logp/prob_cctcm）
- q 长度 <1 或空返回空分组；SQL 全部参数化 LIKE。

**前端** `frontend/src/App.vue`（顶栏）+ 新建 `frontend/src/components/SearchBox.vue`：
- 顶栏 nav 右侧加搜索框（复用现有 topbar 样式变量），300ms 防抖调 `/search`
- 下拉浮层分三组展示（方子/药材/成分），药材行点击 → 跳 `/herbs` 并打开对应详情弹窗（用 query 参数 `?h=药材名`，Herbs.vue onMounted 读取后设置 active）；成分行点击 → 跳新成分词典页 `/compounds/:name`；方子行 → `/recipes/:id`
- 点击外部/Esc/选中后关闭；无结果时显示空态文案；键盘上下键+回车可不做（保持简单）
- 新增 `frontend/src/api/index.js` 的 `search(q)` 封装

## 2. 成分词典页（对标 Examine.com；打通已断线的 explain 链路）

**后端**：
- `explain_service.compound_explain()` 扩展返回 `recipes` 字段：通过 herbs 反查 `rel_recipe_material`（herb_id IN 关联药材 AND material_type='herb'），返回方子 id/name/type（最多 8 个，去重）——即「这个成分出现在哪些方子里」
- 该接口已含：双模型概率、Lipinski 逐项解读（band/features/rule_summary）、关联药材，前端补页面即可
- `open_api.py` 的 targets 端点已有，可并页展示（`GET /open/compounds/{name}/targets`），但为免跨模块，词典页直接在 main.py 的 explain 响应里补 `targets`（复用 open_api 内部查询逻辑，取前 12 个，含 name 与三维分如有）

**前端**：
- 新建 `frontend/src/views/CompoundDetail.vue`，路由 `/compounds/:name`（`router/index.js` 注册，注意放在 `:id(\d+)` 类路由前不冲突——本路由参数为名称）
- 页面结构（沿用现有页头/卡片风格）：
  1. 页头：成分名 + SMILES + 概率档位徽章（复用 `_band` 返回的 tier/color）
  2. 双模型概率对比条（从 Compounds.vue 抽取/复用其绘制方式：prob_cctcm vs prob_herb）
  3. ExplainPanel 同款的 Lipinski 特征解读区（直接复用 `frontend/src/components/ExplainPanel.vue` 的展示逻辑，若其耦合方子语境则抽子组件）
  4. 关联药材 chips（点击跳 `/herbs?h=名`）
  5. 关联靶点列表（前 12）
  6. 「出现在这些方子」卡片列表（点击进方子详情）
- `Compounds.vue` 每行加点击 → `router.push(/compounds/${name})`；方子详情页 ExplainPanel 中成分名也可点击跳转
- `api/index.js` 的死代码 `getExplainCompound` 正式启用

## 3. 周期报告导出海报（打通传播链路）

- 新建 `frontend/src/components/ReportPoster.vue`：Canvas 绘制（参考 SharePoster 的绘制与下载代码模式，但数据源改为传入 props——周期天数、打卡天数、Top 覆盖成分/靶点数、场景分布、体质变化曲线简化为文字/迷你条），固定 750×1334 竖版
- `Report.vue` 加「保存分享图」按钮：把 `report_service` 已返回的数据整理进 props，下载 PNG（文件名 `食养有据-我的${n}天食养报告.png`），底部带站点二维码（复用 SharePoster 的二维码绘制方式）
- 不做第三方 SDK 分享（维持现状，海报下载+二维码即可）

## 4. 营养素数据填充（对标膳时的现代营养标准维度）

- 新建 `scripts/fill_nutrients.py`：为 `food` 表 39 条填充 `nutrient_json`（每 100g：能量 kcal/蛋白质/脂肪/碳水/膳食纤维 + 1 条亮点说明如「维C 含量高」）。数据按《中国食物成分表》公开常见值人工整理成脚本内字典，脚本幂等（已有值跳过，`--force` 覆盖），写完打印统计
- 后端 `GET /api/v1/recipes/{rid}` 的配料行里，material_type='food' 的行带上 `nutrient` 字段（join food 表）；新建轻量 `GET /api/v1/foods`（列表页用，含 nutrient_json 供茶罐/图鉴展示）
- 前端：`RecipeDetail.vue` 食材行展开时显示营养素小结（能量/三大营养素一行 + 亮点）；`Pantry.vue` 食材卡 tooltip/副行展示能量——保持轻量，不做独立营养页
- 营养数据标注口径：`nutrient_json` 里带 `"source": "中国食物成分表（第6版）常见值，约值"`，避免精确值误导

---

## 实施顺序与验证

1 → 2 → 3 → 4（搜索为词典页提供入口流量，词典页依赖搜索跳转目标）

每步验证：
- 后端：curl 各新端点（search 三分组 / explain 含 recipes+targets / foods / recipe 配料含 nutrient）；参照 `backend/tests/test_p0_evidence_chain.py` 风格补 `test_search_and_compound.py`（搜索聚合正确性 + compound_explain 含 recipes 字段）
- 前端：`npm run build` 通过；本地起 dev 用浏览器过一遍四条链路（搜索→词典页、报告→海报下载、方子详情→营养素展示）
- 收尾：`docs/API接口设计文档.md` 追加新端点条目（该文档本就滞后，只补本次新增的 3 个）

不做：舌诊/问诊/电商/扫码/自由问答（调研清单已判定），第三方分享 SDK。