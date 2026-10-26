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
- 单测：`cd backend && python -X utf8 -m pytest tests/ -v` → **14 passed**
- 构建：`cd frontend && npx vite build` → 通过
- T1/T2 全部端点在数据重建（`8c47247`）后复测通过（对比 Jaccard 由 0.333 变 0.667 属归属修复的正常反映，接口如实读取最新库）
