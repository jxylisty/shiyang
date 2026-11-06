# API 扩展记录（v0.2.0 基线之后）

- **实测方式**：`main.app.openapi()` 导出（非手抄），最新核实日期 **2026-11-06**。
- **规模**：**56 条路径 / 60 个端点**。docs/API接口设计文档.md 所记「24 端点」为 v0.2.0 基线口径，已过时，本文档补充增量部分；基线接口的设计原则与响应约定仍以该文档为准。
- ⚠️ **口径说明（数据真实）**：多工作线并行期间清单曾两次失真，最终于数据线提交 `578c54b` 后**重测复核**：本清单与届时 HEAD 完全一致（46 路径 / 50 端点，无未提交路由混入）。此后若再合并增量，须用文末命令重跑并更新本表。2026-10-27 UX 线新增 2 端点后复核 48/52；同日 AI 助手线新增 `/assistant/chat` 后复核 49/53。2026-11-05/06 自定义茶罐线新增 5 端点（custom-recipe ×4、`/recipes/{rid}/plain`）、化学空间线补登记 `explain/map` 后，复核 **55 路径 / 59 端点**。同日食养科学体系重构线新增 /recipes/{rid}/eval 端点并重构雷达维度，实测复核 **56 路径 / 60 端点**。
- **复核命令**（数据或代码变动后重新生成此清单）：

```bash
cd backend && python -X utf8 -c "import sys; sys.path.insert(0,'app'); import main
for p in sorted(main.app.openapi()['paths']):
    print(','.join(m.upper() for m in main.app.openapi()['paths'][p]), p)"
```

## 全端点清单（按字母序，标注来源批次）

| 方法 | 路径 | 来源 |
|---|---|---|
| POST | /api/v1/auth/login | 基线（用户系统 P1.1） |
| POST | /api/v1/auth/register | 基线 |
| POST | /api/v1/assistant/chat | **AI助手线** 食养问答（SSE：citations 先行→delta→[DONE]；RAG 限定库内资料+强制引用编号，2026-10-27 提交 dd7653a；Key 走 X-AI-Key 头，无头时用平台级 ZeroGate 网关默认） |
| GET | /api/v1/checkins | 基线（打卡 P2） |
| POST / DELETE | /api/v1/checkins/{recipe_id} | 基线 |
| GET | /api/v1/compounds | 基线 |
| GET | /api/v1/constitution/questionnaire | 基线 |
| POST / GET | /api/v1/constitution/records | 基线；POST 增加 member_id（T2-8） |
| POST | /api/v1/constitution/submit | 基线 |
| POST | /api/v1/constitution/recommend | **UX线** 为你推荐·游客态（body 传本地暂存 judged，2026-10-27 提交 b82a68d；注册在 {code} 之前） |
| GET | /api/v1/constitution/{code} | 基线 |
| POST | /api/v1/custom-recipe/analyze | **自定义茶罐线** 多味药材合并分析（成分/靶点/疾病去重统计；HERB 未命中时本地 105 味知识库兜底，2026-11-06 提交 42a2e50） |
| POST | /api/v1/custom-recipe/parse-text | **自定义茶罐线** 粘贴文案 AI 抽取药材+克重（逐条本地复核防幻觉，提交 e15c36b） |
| POST | /api/v1/custom-recipe/plain | **自定义茶罐线** 自定义方大白话通俗解读 |
| POST | /api/v1/custom-recipe/web-lookup | **自定义茶罐线** HERB/本地库均未命中的药材联网搜索兜底（返回真实搜索来源，AI 摘要须标注，提交 00c47a6） |
| GET | /api/v1/evidence/levels | **T1-3** 证据分级定义（A/B/C） |
| GET | /api/v1/evidence/recipe/{rid} | **T1-3** 单方三级证据链+PMID 链接 |
| GET | /api/v1/explain/compound?name= | **T1-4** 单成分入血解释（Lipinski 特征） |
| GET | /api/v1/explain/map | **化学空间线** 165 成分 UMAP 二维坐标（入血/应用域/一致性能着色），2026-10-30 |
| GET | /api/v1/explain/recipe/{rid} | **T1-4** 方子 Top 成分特征一览 |
| GET / POST | /api/v1/family/members | **T2-8** 家庭成员列表/添加 |
| DELETE | /api/v1/family/members/{member_id} | **T2-8** |
| GET | /api/v1/favorites | 基线 |
| POST / DELETE | /api/v1/favorites/{recipe_id} | 基线 |
| GET | /api/v1/foods | 数据线（食物成分表，具体批次见其提交） |
| GET | /api/v1/health | 基线 |
| GET | /api/v1/herbs | 基线 |
| GET | /api/v1/me | 基线 |
| GET | /api/v1/me/recommend | **UX线** 为你推荐·登录态（体质档案+收藏打卡偏好+当令节气，2026-10-27 提交 b82a68d） |
| GET | /api/v1/open | **T1-6** 开放数据自描述索引 |
| GET | /api/v1/open/catalog | **T1-6** 药食同源目录（2026-11-05 扩容后实测 105 条命中药材） |
| GET | /api/v1/open/compounds | **T1-6** |
| GET | /api/v1/open/compounds/{name}/targets | **T1-6** |
| GET | /api/v1/open/constitutions | **T1-6** |
| GET | /api/v1/open/herbs | **T1-6** |
| GET | /api/v1/open/snapshot | **T1-6** 全量打包下载（JSON 附件） |
| GET | /api/v1/open/stats | **T1-6** |
| POST | /api/v1/pantry/match | **T1-2** 反向配伍 |
| GET | /api/v1/pantry/materials | **T1-2** |
| GET | /api/v1/recipes | 基线 |
| GET | /api/v1/recipes/compare?a=&b= | **T1-1** 方子对比（注意：注册在 {rid} 之前） |
| GET | /api/v1/recipes/{rid} | 基线（`{rid:int}` 转换器兜底 compare 误吞问题） |
| GET | /api/v1/recipes/{rid}/ai-report | 基线（SSE；无 Key 回放预生成） |
| GET | /api/v1/recipes/{rid}/chain | 数据线（四层证据链，见提交 8c47247） |
| GET | /api/v1/recipes/{rid}/exposure | 基线（P2.5；P0 合并见提交 8cbc5f8） |
| GET | /api/v1/recipes/{rid}/network | 基线（P2.6） |
| GET | /api/v1/recipes/{rid}/pathways | 数据线（通路富集，见提交 8c47247） |
| GET | /api/v1/recipes/{rid:int}/eval | **食养科学指数线** 方剂食养科学三维指数（入血潜力 / 多靶协同 / 证据强度，2026-11-06 提交 2f32871） |
| GET | /api/v1/recipes/{rid}/plain | **普通模式线** 方剂大白话通俗解读（专业模式对照，提交 0ac98e4） |
| GET | /api/v1/report/cycle | **T2-7** 周期报告（7/21/90 天，需登录） |
| POST | /api/v1/safety/check-batch | **T1-5** 批量人群安全检查 |
| GET | /api/v1/safety/check/{recipe_id} | **T1-5** |
| GET | /api/v1/safety/profiles | **T1-5** 五档人群档案 |
| GET | /api/v1/search | 数据线（全局搜索，见提交 7db3875）；2026-10-27 UX 线扩域至配料名/药材别名/功效并带 matched_by（提交 72fcbf5），recipes 列表 q 同步扩域（提交 c5a4c39）；同日加 `limit` 参数（默认 5 上限 20，独立搜索页用，提交 8f68fa1） |
| GET | /api/v1/stats | 基线 |
| GET | /api/v1/term/current | **T2-9** 当前节气+食养主题+推荐方 |

## 维护约定

1. 本表「来源」列区分基线 / T1/T2 功能梯队 / 数据线其他批次（按提交归属如实标注，不合并叙事）。
2. 新增端点必须走 openapi 复核后补一行；删除/改名同步更新本表与 API接口设计文档。
3. 健康类响应必须带 `disclaimer` 字段（AGENTS.md §1 红线）。
