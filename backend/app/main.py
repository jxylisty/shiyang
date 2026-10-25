# -*- coding: utf-8 -*-
"""
食养有据 backend —— FastAPI 应用入口
路由：体质测评、方子库、成分分析、AI 流式解读（SSE）、用户系统（注册/档案/收藏）、暴露量估计、网络图数据
"""
import asyncio
import json
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
from services import constitution_service as cs
from services import user_service as us
from services import ai_service as ai
from services import exposure_service as es
from services import compare_service as cmp_svc
from services import pantry_service as pantry

DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "shiyang.db"
DISCLAIMER = "本平台内容为健康参考信息，不构成医疗建议，不用于诊断或治疗。"

VERSION = "0.2.0"


def get_db():
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not DB_PATH.exists():
        raise RuntimeError(f"数据库不存在: {DB_PATH}，请先运行 scripts/build_db.py")
    yield


app = FastAPI(title="食养有据 API", version=VERSION, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


def ok(data=None, message="success"):
    return {"code": 0, "message": message, "data": data}


# ==================== 体质测评 ====================

class QuizSubmit(BaseModel):
    answers: dict[str, list[float]] = Field(..., description="{维度code: [每题1-5分]}")
    username: str | None = None


@app.get("/api/v1/constitution/questionnaire")
def questionnaire():
    items, _note = cs.get_questionnaire()
    return ok({"items": items,
               "scoring": "每题：没有=1分、很少=2分、有时=3分、经常=4分、总是=5分",
               "disclaimer": DISCLAIMER})


@app.post("/api/v1/constitution/submit")
def submit_quiz(q: QuizSubmit):
    try:
        transformed = cs.calc_transformed(q.answers)
    except ValueError as e:
        raise HTTPException(400, str(e))
    judged = cs.judge(transformed)
    recs = cs.recommend_recipes(judged)
    main = judged["main"] or ("pinghe" if judged["results"]["pinghe"]["result"] in ("是", "基本是") else None)
    detail = cs.constitution_detail(main) if main else None
    return ok({"transformed": transformed, "judged": judged, "main_constitution": detail,
               "recommendations": recs, "disclaimer": DISCLAIMER})



# ==================== 方子库 ====================

@app.get("/api/v1/recipes")
def list_recipes(type: str | None = None, scene: str | None = None,
                 constitution: str | None = None, q: str | None = None,
                 page: int = 1, size: int = 20):
    page = max(1, min(page, 1000))
    size = max(1, min(size, 100))
    conn = get_db()
    where, params = ["status != '弃用'"], []
    if type:
        where.append("type=?"); params.append(type)
    if q:
        where.append("name LIKE ?"); params.append(f"%{q}%")
    sql = f"SELECT id,name,type,oneliner,scenes,constitutions_suitable,duration,analysis_ready FROM recipe WHERE {' AND '.join(where)}"
    rows = conn.execute(sql, params).fetchall()
    out = []
    for r in rows:
        scenes = json.loads(r["scenes"] or "[]")
        suits = json.loads(r["constitutions_suitable"] or "[]")
        if scene and scene not in scenes:
            continue
        if constitution and constitution not in suits:
            continue
        out.append({"id": r["id"], "name": r["name"], "type": r["type"], "oneliner": r["oneliner"],
                    "scenes": scenes, "constitutions_suitable": suits, "duration": r["duration"],
                    "analysis_ready": bool(r["analysis_ready"])})
    # 封面用首味配料名（卡片左图），一次查询按 recipe_id 取最小 id 配料
    if out:
        ph = ",".join("?" * len(out))
        first_mat = {}
        for row in conn.execute(
                f"SELECT recipe_id, name FROM rel_recipe_material "
                f"WHERE recipe_id IN ({ph}) AND id IN "
                f"(SELECT MIN(id) FROM rel_recipe_material WHERE recipe_id IN ({ph}) GROUP BY recipe_id)",
                [r["id"] for r in out] * 2).fetchall():
            first_mat[row["recipe_id"]] = row["name"]
        for r in out:
            r["materials"] = [first_mat[r["id"]]] if r["id"] in first_mat else []
    total = len(out)
    start = (page - 1) * size
    conn.close()
    return ok({"total": total, "page": page, "size": size, "items": out[start:start + size]})


@app.get("/api/v1/recipes/compare")
def recipes_compare(a: int, b: int):
    if a == b:
        raise HTTPException(400, "请选择两个不同的方子")
    result = cmp_svc.compare(a, b)
    if result is None:
        raise HTTPException(404, "方子不存在或无成分分析")
    return ok(result)


class PantryBody(BaseModel):
    owned: list[str] = Field(..., description="手边有的食材名列表")
    constitution: str | None = Field(None, description="可选：体质名（如 湿热）过滤")


@app.post("/api/v1/pantry/match")
def pantry_match(body: PantryBody):
    return ok(pantry.match(body.owned, body.constitution))


@app.get("/api/v1/pantry/materials")
def pantry_materials():
    """全部配料名（去重+按在方子里的出现频次排序），供前端勾选"""
    conn = get_db()
    rows = conn.execute(
        "SELECT name, COUNT(*) AS cnt FROM rel_recipe_material GROUP BY name ORDER BY cnt DESC").fetchall()
    conn.close()
    return ok({"total": len(rows), "items": [{"name": r["name"], "count": r["cnt"]} for r in rows]})


@app.get("/api/v1/recipes/{rid}")
def recipe_detail(rid: int):
    conn = get_db()
    r = conn.execute("SELECT * FROM recipe WHERE id=?", (rid,)).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "方子不存在")
    mats = conn.execute(
        "SELECT m.name, m.material_type, m.grams, m.optional, m.note, "
        "h.nature, h.flavor, h.functions, h.is_food_homology "
        "FROM rel_recipe_material m LEFT JOIN herb h ON h.id=m.herb_id WHERE m.recipe_id=?", (rid,)).fetchall()
    analysis = conn.execute("SELECT * FROM recipe_analysis WHERE recipe_id=?", (rid,)).fetchone()
    out = dict(r)
    for k in ("scenes", "constitutions_suitable", "constitutions_unsuitable"):
        out[k] = json.loads(out.get(k) or "[]")
    out["materials"] = [dict(m) for m in mats]
    out["analysis"] = None
    if analysis:
        a = dict(analysis)
        for k in ("top_compounds", "radar_summary", "top_targets"):
            a[k] = json.loads(a[k] or "null")
        out["analysis"] = a
    conn.close()
    out["disclaimer"] = DISCLAIMER
    return ok(out)


# ==================== 成分查询 ====================

@app.get("/api/v1/herbs")
def list_herbs(q: str | None = None):
    conn = get_db()
    if q:
        rows = conn.execute(
            "SELECT id,name,category,nature,flavor,meridians,functions,compound_count,food_catalog_batch "
            "FROM herb WHERE name LIKE ? OR pinyin LIKE ? ORDER BY compound_count DESC",
            (f"%{q}%", f"{q}%")).fetchall()
    else:
        rows = conn.execute(
            "SELECT id,name,category,nature,flavor,meridians,functions,compound_count,food_catalog_batch "
            "FROM herb ORDER BY compound_count DESC").fetchall()
    conn.close()
    return ok({"total": len(rows), "items": [dict(r) for r in rows]})


@app.get("/api/v1/compounds")
def list_compounds(min_prob: float = 0.5, limit: int = 50):
    min_prob = max(0.0, min(min_prob, 1.0))
    conn = get_db()
    rows = conn.execute(
        "SELECT c.id,c.name,c.prob_cctcm,c.prob_herb,c.mw,c.logp,"
        "c.radar_anti_inflammatory,c.radar_immune_regulation,c.radar_airway_repair "
        "FROM compound c WHERE c.prob_cctcm>=? ORDER BY c.prob_cctcm DESC LIMIT ?",
        (min_prob, min(limit, 200))).fetchall()
    conn.close()
    return ok({"total": len(rows), "items": [dict(r) for r in rows]})


# ==================== 系统 ====================

@app.get("/api/v1/stats")
def stats():
    conn = get_db()
    out = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
           for t in ("herb", "compound", "target", "food", "recipe", "constitution")}
    out["recipe_analysis"] = conn.execute("SELECT COUNT(*) FROM recipe_analysis").fetchone()[0]
    out["throat_scene"] = conn.execute(
        "SELECT COUNT(*) FROM recipe WHERE scenes LIKE '%护嗓润喉%'").fetchone()[0]
    out["content_records"] = conn.execute("SELECT COUNT(*) FROM herb_compound_content").fetchone()[0]
    conn.close()
    return ok({"version": VERSION, "stats": out, "disclaimer": DISCLAIMER})


@app.get("/api/v1/health")
def health():
    return ok({"status": "up", "version": VERSION})


# ==================== 用户系统（P1.1） ====================

class RegBody(BaseModel):
    username: str
    password: str
    nickname: str | None = None


class LoginBody(BaseModel):
    username: str
    password: str


def auth_uid(authorization: str | None) -> int:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "请先登录")
    payload = us.parse_token(authorization[7:])
    if not payload:
        raise HTTPException(401, "登录已过期，请重新登录")
    return payload["uid"]


@app.post("/api/v1/auth/register")
def register(body: RegBody):
    try:
        return ok(us.register(body.username, body.password, body.nickname))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.post("/api/v1/auth/login")
def login(body: LoginBody):
    try:
        return ok(us.login(body.username, body.password))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/v1/me")
def me(authorization: str | None = Header(None)):
    uid = auth_uid(authorization)
    conn = us.db()
    row = conn.execute("SELECT id,username,nickname,created_at FROM user WHERE id=?", (uid,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(404, "用户不存在")
    return ok(dict(row))


# ---------- 体质档案 ----------

class SaveRecordBody(BaseModel):
    judged: dict
    transformed: dict
    answers: dict


@app.post("/api/v1/constitution/records")
def save_constitution_record(body: SaveRecordBody, authorization: str | None = Header(None)):
    uid = auth_uid(authorization)
    rid = us.save_record(uid, body.judged, body.transformed, body.answers)
    return ok({"id": rid})


@app.get("/api/v1/constitution/records")
def list_constitution_records(authorization: str | None = Header(None), limit: int = 20):
    uid = auth_uid(authorization)
    return ok(us.list_records(uid, max(1, min(limit, 100))))


# ---------- 收藏 ----------

@app.post("/api/v1/favorites/{recipe_id}")
def add_fav(recipe_id: int, authorization: str | None = Header(None)):
    uid = auth_uid(authorization)
    us.add_favorite(uid, recipe_id)
    return ok({"recipe_id": recipe_id, "favorited": True})


@app.delete("/api/v1/favorites/{recipe_id}")
def remove_fav(recipe_id: int, authorization: str | None = Header(None)):
    uid = auth_uid(authorization)
    us.remove_favorite(uid, recipe_id)
    return ok({"recipe_id": recipe_id, "favorited": False})


@app.get("/api/v1/favorites")
def list_fav(authorization: str | None = Header(None)):
    uid = auth_uid(authorization)
    ids = us.list_favorites(uid)
    if not ids:
        return ok([])
    conn = get_db()
    ph = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT id,name,type,oneliner,scenes FROM recipe WHERE id IN ({ph})", ids).fetchall()
    conn.close()
    order = {rid: i for i, rid in enumerate(ids)}
    items = sorted([dict(r) | {"scenes": json.loads(r["scenes"] or "[]")} for r in rows],
                   key=lambda x: order[x["id"]])
    return ok(items)


# ---------- 饮用打卡（P2） ----------

@app.post("/api/v1/checkins/{recipe_id}")
def do_checkin(recipe_id: int, authorization: str | None = Header(None)):
    uid = auth_uid(authorization)
    return ok(us.add_checkin(uid, recipe_id))


@app.delete("/api/v1/checkins/{recipe_id}")
def undo_checkin(recipe_id: int, authorization: str | None = Header(None)):
    uid = auth_uid(authorization)
    return ok(us.remove_checkin(uid, recipe_id))


@app.get("/api/v1/checkins")
def list_checkins(authorization: str | None = Header(None)):
    uid = auth_uid(authorization)
    data = us.list_checkins(uid)
    # 附方子名（周视图和 Me 页展示用）
    rids = list({r["recipe_id"] for r in data["records"]})
    if rids:
        conn = get_db()
        ph = ",".join("?" * len(rids))
        names = dict(conn.execute(
            f"SELECT id,name FROM recipe WHERE id IN ({ph})", rids).fetchall())
        conn.close()
        for r in data["records"]:
            r["recipe_name"] = names.get(r["recipe_id"], f"#{r['recipe_id']}")
    return ok(data)


# ==================== AI 流式解读（P1.2，SSE；P2 支持预生成回放） ====================

@app.get("/api/v1/recipes/{rid}/ai-report")
async def ai_report(rid: int, key: str | None = Query(None), provider: str = "deepseek",
                    model: str = "", base_url: str = "",
                    x_ai_key: str | None = Header(None, alias="X-AI-Key")):
    # Key 优先取请求头 X-AI-Key（不进 URL，避免被代理/访问日志记录）；query 参数保留向后兼容
    key = (x_ai_key or key or "").strip() or None
    conn = get_db()
    r = conn.execute("SELECT * FROM recipe WHERE id=?", (rid,)).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "方子不存在")
    recipe = dict(r)
    for k in ("scenes", "constitutions_suitable", "constitutions_unsuitable"):
        recipe[k] = json.loads(recipe.get(k) or "[]")
    mats = conn.execute(
        "SELECT name, grams FROM rel_recipe_material WHERE recipe_id=?", (rid,)).fetchall()
    recipe["materials"] = [dict(m) for m in mats]
    a = conn.execute("SELECT * FROM recipe_analysis WHERE recipe_id=?", (rid,)).fetchone()
    analysis = None
    if a:
        analysis = dict(a)
        for k in ("top_compounds", "radar_summary", "top_targets"):
            analysis[k] = json.loads(analysis[k] or "null")
    conn.close()

    messages = ai.build_recipe_messages(recipe, analysis)

    # 无用户 Key：回放平台预生成的解读（SSE 节奏分片，保留打字机体验）
    if not key:
        pregen = ai.get_pregen_report(rid)
        if pregen is None:
            raise HTTPException(404, "该方暂无 AI 解读；可在面板里填自己的 Key 实时生成")

        async def replay():
            # 按 2-6 字分片推送，模拟流式节奏
            CHUNK, DELAY_MS = 4, 28
            buf = ""
            for ch in pregen:
                buf += ch
                if len(buf) >= CHUNK or ch in "\n。！？；":
                    yield f"data: {json.dumps({'delta': buf, 'source': 'pregen'}, ensure_ascii=False)}\n\n"
                    buf = ""
                    await asyncio.sleep(DELAY_MS / 1000)
            if buf:
                yield f"data: {json.dumps({'delta': buf, 'source': 'pregen'}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(replay(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    async def gen():
        try:
            async for chunk in ai.stream_chat(messages, key, provider, base_url, model):
                yield f"data: {json.dumps({'delta': chunk}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except ai.AIConfigError as e:
            yield f"data: {json.dumps({'error': e.message, 'code': e.code}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': f'AI 服务异常: {e}'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ==================== 暴露量估计（P2.5） ====================

@app.get("/api/v1/recipes/{rid}/exposure")
def exposure(rid: int):
    result = es.estimate(rid)
    if result is None:
        raise HTTPException(404, "方子不存在或无可估计配料")
    return ok(result)


# ==================== 成分-靶点网络图数据（P2.6） ====================

@app.get("/api/v1/recipes/{rid}/network")
def network(rid: int, max_compounds: int = 6, max_targets: int = 12):
    max_compounds = max(1, min(max_compounds, 20))
    max_targets = max(1, min(max_targets, 40))
    conn = get_db()
    a = conn.execute("SELECT top_compounds FROM recipe_analysis WHERE recipe_id=?", (rid,)).fetchone()
    if not a:
        conn.close()
        raise HTTPException(404, "该方无成分分析")
    top = json.loads(a["top_compounds"])[:max_compounds]
    names = [c["name"] for c in top]
    nodes, edges, seen_t = [], [], set()
    # 方子中心节点
    r = conn.execute("SELECT name FROM recipe WHERE id=?", (rid,)).fetchone()
    nodes.append({"id": "recipe", "name": r["name"], "category": 0, "value": 30})
    for c in top:
        cid = f"c:{c['name']}"
        nodes.append({"id": cid, "name": c["name"], "category": 1,
                      "value": 10 + (c.get("prob_cctcm") or 0) * 20})
        edges.append({"source": "recipe", "target": cid})
    if names:
        ph = ",".join("?" * len(names))
        links = conn.execute(
            f"SELECT compound_id, target_gene FROM rel_compound_target rc "
            f"JOIN compound c ON c.id=rc.compound_id WHERE c.name IN ({ph})", names).fetchall()
        tcount = {}
        for row in links:
            tcount.setdefault(row["target_gene"], []).append(row["compound_id"])
        hot = sorted(tcount.items(), key=lambda x: -len(x[1]))[:max_targets]
        name_by_id = {c: c for c in names}
        cname_by_id = dict(conn.execute(
            f"SELECT id,name FROM compound WHERE name IN ({ph})", names).fetchall())
        for gene, comps in hot:
            if gene in seen_t:
                continue
            seen_t.add(gene)
            nodes.append({"id": f"t:{gene}", "name": gene, "category": 2,
                          "value": 8 + min(len(comps), 4) * 3})
            for cid in set(comps):
                if cid in cname_by_id:
                    edges.append({"source": f"c:{cname_by_id[cid]}", "target": f"t:{gene}"})
    conn.close()
    return ok({"nodes": nodes, "edges": edges,
               "legend": ["方子", "活性成分", "作用靶点"]})


@app.get("/api/v1/constitution/{code}")
def constitution_info(code: str):
    d = cs.constitution_detail(code)
    if not d:
        raise HTTPException(404, f"未知体质: {code}")
    return ok(d)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8100)
