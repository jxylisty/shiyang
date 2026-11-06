# 部署与运行指南（DEPLOY）

> 面向把「食养有据」跑在本地服务器 / 云主机 / 校内环境的人。
> 开发环境快速启动见 [README.md](README.md)；AI 协作规范见 [AGENTS.md](AGENTS.md)。

## 1. 组成与端口

| 组件 | 技术 | 端口 | 说明 |
|---|---|---|---|
| 后端 | FastAPI + SQLite（Python ≥3.12） | 8100 | `backend/`，知识库只读、用户库可写 |
| 前端 | Vue3 + Vant + Vite（Node ≥20） | 5174（dev） | `frontend/`，dev 模式 `/api` 代理到 127.0.0.1:8100 |

数据库（均在 `data/`，**不进 git**，可由脚本重建）：
- `shiyang.db` —— 方子/药材/成分/靶点知识库，**运行时只读**（`mode=ro`）。
- `user.db` —— 账号/体质档案/收藏/打卡/家庭成员，运行时可写（WAL）。

## 2. 后端部署

```bash
cd backend
python -m venv .venv && source .venv/Scripts/activate   # Windows Git Bash；Linux 为 bin/activate
pip install -r requirements.txt          # 生产不装 requirements-dev.txt（那是 pytest）
uvicorn app.main:app --host 0.0.0.0 --port 8100
```

### 必设环境变量

| 变量 | 必要性 | 说明 |
|---|---|---|
| `SHIYANG_JWT_SECRET` | **生产必设** | 用户登录令牌签名密钥。缺省值 `shiyang-dev-secret-change-in-prod` 仅供本地开发（见 `backend/app/services/user_service.py`）；生产不设等于所有登录令牌可被伪造 |

```bash
# Linux/macOS
export SHIYANG_JWT_SECRET="$(python -c 'import secrets; print(secrets.token_hex(32))')"
# Windows PowerShell
$env:SHIYANG_JWT_SECRET = (python -c "import secrets; print(secrets.token_hex(32))")
```

### 反向代理注意（Nginx 等）

AI 解读接口 `/api/v1/recipes/{rid}/ai-report` 是 **SSE 流式响应**，代理需关闭缓冲，否则打字机效果会整段卡住：
```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8100;
    proxy_buffering off;          # SSE 必须
    proxy_read_timeout 300s;
}
```

### CORS

`main.py` 当前 `allow_origins=["*"]`（演示口径）。若前后端同域部署（前端打包后由同一域名/反代伺服），建议把 `allow_origins` 收紧为实际域名再上线。

## 3. 前端部署

```bash
cd frontend
npm install
npx vite build        # 产物在 frontend/dist/
```

生产用任何静态服务器伺服 `dist/`，并把 `/api` 反代到后端 8100。前端默认走相对路径 `/api/v1`（`frontend/src/api/index.js`），同域部署无需改代码。

本地 dev 模式：`npm run dev`（5174 端口，vite 已配置 `/api` → 127.0.0.1:8100 代理，见 `frontend/vite.config.js`）。

## 4. 数据库准备与重建

> **完整链路、依赖表、每步校验点与实测记录见
> [知识库重建链路_2026-11-06.md](知识库重建链路_2026-11-06.md)。本节只给最短可用命令。**

> ### ⚠️ 不要单独运行 `scripts/build_db.py`
>
> `build_db.py` 第 20-21 行是 `if OUT.exists(): OUT.unlink()`——**它会先删掉
> `data/shiyang.db`**，然后只建 **11 张表**（34 味药材 / 165 或 138 个成分），
> **扩容得到的 71 味新药材、5,478 个新成分、59,437 条成分-靶点关联全部丢失**，
> 且中途失败时库里只剩半成品。
> 它只是完整链路的第一步，**不是**"重建知识库"的命令。

重建（沙箱模式，不碰生产库）：

```bash
# 1) 只打印计划 + 资源检查，不建任何文件
python -X utf8 scripts/rebuild_all.py --dry-run

# 2) 在临时目录重建（推荐先这样验证；无 AI key 时加 --skip-ai）
python -X utf8 scripts/rebuild_all.py --target-dir data/_rebuild_test/run1 --skip-ai
#    注：若仓库内有 .venv-rebuild/（见 scripts/requirements-rebuild.txt），脚本会自动
#    用它跑子进程，UMAP 步骤（compound_map）才能生成；也可 --python 显式指定。

# 3) 校验通过后，部署时用新库替换生产库（先备份！）
cp data/shiyang.db data/shiyang.db.bak-before-replace-$(date +%Y%m%d%H%M%S)
cp data/_rebuild_test/run1/root/data/shiyang.db data/shiyang.db
```

说明：

- `rebuild_all.py` 在 `<target-dir>/root/` 镜像仓库并复制外部资源，脚本里的 `ROOT`
  全部解析到沙箱，**生产库 `data/shiyang.db` 全程只读**。因此不存在"先删库再失败"的窗口。
- 缺 AI key / 无本机 ZeroGate 网关时用 `--skip-ai`：AI 解读表（`recipe_pregen_ai`）与
  白话解读 JSON 不生成，其余 19 张业务表照常重建。
- 只想复刻 2026-11-06 的 19 表基线（不含当天新增的 10 味补录）加 `--skip-legacy10`。
- 重建**不影响** `user.db`（两库独立是有意设计）。
- 历史备份：`data/shiyang.db.bak-before-rebuild` 与 `shiyang.db.bak-sync-*` 已入库备查
  （其中 `bak-before-rebuild` 是唯一能 100% 复刻现库 `recipe_analysis` 的种子，见链路文档 §5）。

冒烟测试（需后端已在本机 8100 起好；脚本会自动清理测试账号）：

```bash
python -X utf8 scripts/smoke_test.py
```

## 5. 测试与自检

```bash
cd backend && python -X utf8 -m pytest tests/ -v    # 单测（依赖见 requirements-dev.txt）
cd frontend && npx vite build                        # 前端构建门禁
```

## 6. 上线检查清单

- [ ] `SHIYANG_JWT_SECRET` 已设为随机值
- [ ] CORS `allow_origins` 已收紧（或前后端同域）
- [ ] 每页红线免责声明可见（`main.py` 的 `DISCLAIMER` 常量 + `App.vue` 页脚）
- [ ] Nginx `proxy_buffering off`（SSE）
- [ ] `user.db` 已纳入备份计划（用户数据唯一正本）
- [ ] 健康检查 `GET /api/v1/health` 返回 `{"code":0}`
