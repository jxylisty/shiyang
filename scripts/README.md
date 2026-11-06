# 脚本索引（scripts/）

> 2026-11-06 实测：**41 个 Python 脚本**，此前除重建链路文档提及少数几个外没有统一索引。
> 本文件按「**能不能直接跑、会不会改数据**」分类。改库前先读「四、危险脚本」。

## 一、先读这三条

1. **`build_db.py` 会删库**。它开头就 `OUT.unlink()`，且只建 11 张表。单独跑 = 丢掉扩容药材、成分、靶点、证据链。
   「从零重建知识库」的正确入口是 `rebuild_all.py`，见 `docs/知识库重建链路_2026-11-06.md`。
2. **写库脚本默认要加 `--apply`** 才落盘（`check_consistency`、`import_herb_imp_rows`、`backfill_pharmacopoeia_herb`）。
   不加参数只做检查/预览。这是有意的：先看 diff 再写。
3. **所有命令加 `python -X utf8`**，否则 Windows 下中文输出乱码。

## 二、按用途分类

### 2.1 知识库重建链（19 步，由 `rebuild_all.py` 驱动）

| 脚本 | 作用 | 是否写库 |
|---|---|---|
| `rebuild_all.py` | **重建总入口**。在隔离沙箱里按序调用下列脚本，每步校验关键表行数，失败即停；默认不碰生产库。支持 `--dry-run` / `--skip-ai` / `--skip-network` / `--skip-legacy10` / `--seed-from` / `--start-at` | 只写沙箱 |
| `build_db.py` | 链路第一步：从大创库抽 73 方涉及的药材/化合物/靶点，建基础 11 表 | **删库重建** |
| `_migrate_20261105.py` | 扩容 schema 迁移（herb 加 source/reference_url/added_batch 三列 + 反向索引），纯 DDL、幂等。**不是独立步骤**：由 `import_herbs_20261105.py` 内部调用 | 是（ALTER） |
| `rebuild_herb_compound.py` | 以溯源 Excel 为唯一真源重建 `rel_herb_compound_v2`（修复 v1 系统性错乱） | 是（DROP+CREATE） |
| `sync_from_repaired_db.py` | 从修复后的大创库同步数据（归属/理化/radar_gsea/入血概率） | 是 |
| `import_herbs_20261105.py` | 34→105 味扩容灌库（HERB API，读 `data/cache/`） | 是 |
| `import_herbs_legacy10.py` | 补 v3 未覆盖的 10 味旧药材归属（天冬/玉竹/百合等） | 是 |
| `import_content.py` | 解析「药材-化合物-含量」Excel → `herb_compound_content` | 是 |
| `backfill_material_herb_id.py` | 回填 73 方配料的 `herb_id`（正名→别名→异名三级匹配，53/53 精确命中） | 是 |
| `backfill_pharmacopoeia_herb.py` | 补 7 味药材缺失的功能主治/类别（药典口径，自动备份） | 是（需 `--apply`） |
| `backfill_model_predictions.py` | 回填官方预测表里已算好的入血概率（零重训，165 行） | 是 |
| `predict_remaining_compounds.py` | 对官方预测表外的成分跑兜底模型 + 全库补应用域标注 | 是 |
| `compute_applicability.py` | 应用域标注（与训练集最大 Tanimoto 相似度） | 是 |
| `cross_validate_independent.py` | 独立算法族交叉验证（LR/XGBoost/MLP），产出 `prob_indep` + CSV | 是 |
| `compute_map_coords.py` | UMAP 二维坐标 → `compound_map`（**当前环境需跳过**：umap 0.5.12 + sklearn 1.4.2 不兼容） | 是（DELETE+INSERT） |
| `fetch_chembl_activity.py` | ChEMBL 实验活性补数据（唯一一条实测证据） | 是 |
| `fill_nutrients.py` | 填 `food.nutrient_json`（中国食物成分表约值） | 是 |
| `pregen_analysis.py` | 链路里负责**建表** `recipe_analysis` 并出 v1 口径（必须跑，后续被 v3 覆盖） | 是 |
| `pregen_analysis_v3.py` | 用 v3 归属 + 真实 GSEA 覆盖 `recipe_analysis` | 是 |
| `pregen_pathways.py` | KEGG 通路富集 → `recipe_pathway`（需网络 Enrichr；条数不稳定，只校验 ≥1 行） | 是 |
| `pregen_ai_reports.py` | AI 解读预生成 → `recipe_pregen_ai`（需 AI 网关） | 是 |
| `pregen_plain.py` | 白话解读预生成 → `data/recipe_plain_ai.json`（不写库） | 写 JSON |

### 2.2 一次性补数（不在重建链内，手动按需跑）

| 脚本 | 作用 | 是否写库 |
|---|---|---|
| `import_herb_imp_rows.py` | 补齐 `imp:橘红` / `imp:花椒` 镜像行的成因与性味归经（原先空白，药材详情页点开是空的）。**不在 `rebuild_all.py` 链路里**，重建后如需修这两味要手动跑 | 是（需 `--apply`） |
| `_cache_seed.py` | 从入库的 gzip 还原 HERB 采集缓存，让新克隆可离线重建。不是独立步骤，被三个 `import_herbs_*` 脚本 import | 写 `data/cache/` |

### 2.3 校验与体检（只读或可选修复）

| 脚本 | 作用 | 退出码语义 |
|---|---|---|
| `check_consistency.py` | 三口径一致性自检：v2≡v3、`compound_count`、`target_count`。`--apply` 才重算修复 | 0 = 全绿，1 = 有偏差 |
| `smoke_test.py` | API 冒烟：覆盖全部公开接口 + 用户系统主路径。**需后端已起在 8100**，会写测试账号（跑完自删） | 非 0 = 有失败 |
| `audit_image_credits.py` | 核查「图 ↔ Commons 署名」齐全（CC BY/BY-SA 要求署名），标出缺口 | — |
| `check_overlap.py` | 药食同源目录 × 药材库重合度盘点 → `docs/overlap_report.md` | — |

### 2.4 数据采集落盘（一次性，已提交产物）

| 脚本 | 作用 |
|---|---|
| `_batch1.py` ~ `_batch4.py` | 分四批往 `data/recipes_raw/tea.json` / `diet.json` 追加方子（共 73 方）。重跑按 name 去重，无业务意义 |
| `merge_recipes.py` | 校验合并 `recipes_raw/*.json` → `data/recipes_v0.1.json` + `docs/方子库_v0.1.xlsx`。**会覆盖已提交产物** |
| `fetch_symmap.py` | 下载 SymMap v2 药材表（中文性味归经/别名），学术用途 |
| `fetch_material_images.py` | 从 Wikimedia Commons 预拉配料实物图 → `frontend/public/img/materials/` |
| `make_recipe_template.py` | 生成 `docs/方子整理模板.xlsx` |

### 2.5 打包与运维

| 脚本 | 作用 |
|---|---|
| `build_app.py` | 前端构建成 5+App 产物（中文图名转 ASCII、`--mode app`、注入 API 地址） |
| `serve_apk.py` | 局域网只读下载站，手机浏览器直接装 APK |
| `start_backend_lan.py` | 监听 0.0.0.0 + 放行防火墙，打印手机可用地址（需管理员权限） |
| `shot_readme.py` | Playwright 抓 README 展示图 → `docs/screenshots/`（需前后端已起） |

## 三、脚本与文档的对应

重建链路每一步的口径、输入输出、跳过后果、校验点，逐条写在
[`docs/知识库重建链路_2026-11-06.md`](../docs/知识库重建链路_2026-11-06.md) §2，
那份文档是重建的权威说明，本文件只做速查。依赖清单见 `requirements-rebuild.txt`。

## 四、危险脚本（会不可逆改数据）

| 脚本 | 危险点 | 前置动作 |
|---|---|---|
| `build_db.py` | **删库**（`OUT.unlink()`），只建 11 表 | 绝不要在生产库上单独跑；用 `rebuild_all.py` |
| `rebuild_herb_compound.py` | DROP 后重建 v2 表 | 先备份 `data/shiyang.db` |
| `merge_recipes.py` | 覆盖 `data/recipes_v0.1.json` 与 `docs/方子库_v0.1.xlsx` | 先 `git status` 确认这两个文件干净 |
| `pregen_analysis*.py` | `INSERT OR REPLACE` 覆盖分析层 | 先备份；注意 v1 必须跑，否则表不存在 |
| `import_herbs_20261105.py` | 会按 v1 全量重算 `compound_count`，覆盖旧药三口径计数 | **必须紧跟 `check_consistency.py --apply`**，否则退出码 1 |

自动备份命名：`data/shiyang.db.bak-<用途>-<时间戳>`，已由 `.gitignore` 的 `*.db.bak-*` 排除，不会误提交。
