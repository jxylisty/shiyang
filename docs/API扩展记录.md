# API 扩展记录（v0.2.0 基线之后）

- **实测方式**：`main.app.openapi()` 导出（非手抄），核实日期 **2026-10-26**。
- **规模**：**46 条路径 / 50 个端点**。docs/API接口设计文档.md 所记「24 端点」为 v0.2.0 基线口径，已过时，本文档补充增量部分；基线接口的设计原则与响应约定仍以该文档为准。
- ⚠️ **口径说明（数据真实）**：多工作线并行期间清单曾两次失真，最终于数据线提交 `578c54b` 后**重测复核**：本清单与届时 HEAD 完全一致（46 路径 / 50 端点，无未提交路由混入）。此后若再合并增量，须用文末命令重跑并更新本表。
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
| GET | /api/v1/checkins | 基线（打卡 P2） |
| POST / DELETE | /api/v1/checkins/{recipe_id} | 基线 |
| GET | /api/v1/compounds | 基线 |
| GET | /api/v1/constitution/questionnaire | 基线 |
| POST / GET | /api/v1/constitution/records | 基线；POST 增加 member_id（T2-8） |
| POST | /api/v1/constitution/submit | 基线 |
| GET | /api/v1/constitution/{code} | 基线 |
| GET | /api/v1/evidence/levels | **T1-3** 证据分级定义（A/B/C） |
| GET | /api/v1/evidence/recipe/{rid} | **T1-3** 单方三级证据链+PMID 链接 |
| GET | /api/v1/explain/compound?name= | **T1-4** 单成分入血解释（Lipinski 特征） |
| GET | /api/v1/explain/recipe/{rid} | **T1-4** 方子 Top 成分特征一览 |
| GET / POST | /api/v1/family/members | **T2-8** 家庭成员列表/添加 |
| DELETE | /api/v1/family/members/{member_id} | **T2-8** |
| GET | /api/v1/favorites | 基线 |
| POST / DELETE | /api/v1/favorites/{recipe_id} | 基线 |
| GET | /api/v1/foods | 数据线（食物成分表，具体批次见其提交） |
| GET | /api/v1/health | 基线 |
| GET | /api/v1/herbs | 基线 |
| GET | /api/v1/me | 基线 |
| GET | /api/v1/open | **T1-6** 开放数据自描述索引 |
| GET | /api/v1/open/catalog | **T1-6** 药食同源目录（实测 34 条命中药材） |
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
| GET | /api/v1/report/cycle | **T2-7** 周期报告（7/21/90 天，需登录） |
| POST | /api/v1/safety/check-batch | **T1-5** 批量人群安全检查 |
| GET | /api/v1/safety/check/{recipe_id} | **T1-5** |
| GET | /api/v1/safety/profiles | **T1-5** 五档人群档案 |
| GET | /api/v1/search | 数据线（全局搜索，见提交 7db3875） |
| GET | /api/v1/stats | 基线 |
| GET | /api/v1/term/current | **T2-9** 当前节气+食养主题+推荐方 |

## 维护约定

1. 本表「来源」列区分基线 / T1/T2 功能梯队 / 数据线其他批次（按提交归属如实标注，不合并叙事）。
2. 新增端点必须走 openapi 复核后补一行；删除/改名同步更新本表与 API接口设计文档。
3. 健康类响应必须带 `disclaimer` 字段（AGENTS.md §1 红线）。
