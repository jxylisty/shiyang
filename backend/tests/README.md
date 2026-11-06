# 测试索引（backend/tests/）

> 2026-11-06 实测：**10 个测试文件 / 106 个用例，全绿**（`python -X utf8 -m pytest tests/ -q` → `106 passed`，7.2s）。
> 本文件是测试的导航与口径说明，测试失败时先看「四、排障」再改代码。

## 一、跑法

```bash
cd backend
python -X utf8 -m pytest tests/ -q                 # 全量（基线 106 passed）
python -X utf8 -m pytest tests/ -v                 # 逐条用例名
python -X utf8 -m pytest tests/test_services_gap.py -q   # 单文件
python -X utf8 -m pytest tests/ -q -k "plain"       # 按名字过滤
```

测试依赖不在正式 `requirements.txt` 里，见 `backend/requirements-dev.txt`（pytest 9.1.1）。

## 二、文件清单

| 文件 | 用例 | 覆盖对象 | 是否依赖网络/外部服务 |
|---|---|---|---|
| `test_custom_recipe.py` | 28 | 自定义鉴方：HERB 性味归经补全、粘贴文案解析（防幻觉/克重越界/空文案/≤25 味）、拍照识药（库外名进 `unverified`/坏 JSON/空图/MIME+8MB 校验）、联网兜底 5 例（`web_lookup` 用 `monkeypatch` 打桩 `requests.post`） | 否（全部打桩） |
| `test_search_and_compound.py` | 13 | 全局搜索 `matched_by` 扩域、成分词典、食材营养、注册/登录端到端 | 否 |
| `test_services_gap.py` | 12 | 零覆盖服务补测：安全滤镜、我的茶罐、对比实验室、周期报告、节气 | 否 |
| `test_rag_service.py` | 11 | RAG 检索正确性 + `citations` 结构 + 降级标记（AI 助手 A1） | 否 |
| `test_pathway_enrichment.py` | 9 | Enrichr 双库（GO BP + KEGG）富集、缓存往返、疾病词黑名单、基因数不足降级 | 否：断言走库内已缓存行与纯函数，不调 Enrichr；会读真实库（`restore_pathway_row` fixture 快照并恢复 `recipe_pathway`） |
| `test_user_service.py` | 9 | 密码哈希、令牌签发/校验、注册规则边界（临时库语义，不写 `user.db`） | 否 |
| `test_plain_service.py` | 8 | 白话解读 `plain_service.parse_and_validate` + 两个端点（模型调用全 mock） | 否 |
| `test_p0_evidence_chain.py` | 7 | 暴露量×入血概率合并、靶点展示层仅人类蛋白 | **是**：直读真实 `data/shiyang.db`（只读） |
| `test_assistant_chat.py` | 6 | 助手 SSE 事件序 / mock `stream_chat` / prompt 组装 / 入参校验 | 否 |
| `test_eval_service.py` | 3 | 食养科学三维指数：入血潜力 / 多靶协同 / 证据强度计算与自洽性 | 否 |
| `conftest.py` | — | autouse 兜底清理：用例失败时也删掉本次新建的测试账号（AGENTS.md §2.7） | — |

## 三、口径与约束（改测试前必读）

1. **不写真实 `user.db`**。需要登录态的用例走 `conftest.py` 的测试前缀账号机制，用例结束自动清理。
   手动跑端到端脚本（`scripts/smoke_test.py`）也会写测试账号，跑完必须删干净。
2. **`test_p0_evidence_chain.py` 直读生产库**（`mode=ro` 只读）。它会随库重建而失败——
   若重建后 `herb`/`compound` 行数或人类蛋白靶点口径变了，先确认真实数字再改断言，**不要为了绿灯放宽断言**。
3. **外部服务一律打桩**。AI 网关、Enrichr、HERB API 在测试里全部 `monkeypatch`，
   所以这套套件可以在飞行模式下跑。新增用例若需要真实网络，必须显式标注并默认跳过。
4. **断言里的数字要有来源**（AGENTS.md §2）。写死行数的地方，注释说明口径与核实日期。
5. 新增测试文件遵循现有风格：文件头一行中文说明覆盖对象，docstring 里写运行命令。

## 四、排障

| 症状 | 常见原因 | 处置 |
|---|---|---|
| 大量 `sqlite3.OperationalError: no such table` | `data/shiyang.db` 不存在或建成了残缺库（`build_db.py` 只建 11 表） | 按 `docs/知识库重建链路_2026-11-06.md` 用 `scripts/rebuild_all.py` 重建，别单独跑 `build_db.py` |
| `test_p0_evidence_chain` 行数断言失败 | 知识库重建后行数变化 | 只读查库确认真实值，同步更新断言与注释日期 |
| 测试账号残留在 `user.db` | 用例中途异常退出 | `conftest.py` 会兜底；仍残留时按 checkin→favorite→constitution_record→family_member→user 顺序删 |
| `ModuleNotFoundError: services` | 不在 `backend/` 目录下跑 | `cd backend` 后再执行 pytest（`sitecustomize.py` 负责注入 `app/` 路径） |
| 中文输出乱码 | Windows 未加 `-X utf8` | 统一 `python -X utf8 -m pytest` |
