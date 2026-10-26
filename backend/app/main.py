# -*- coding: utf-8 -*-
"""
食养有据 backend —— FastAPI 应用入口
路由：体质测评、方子库、成分分析、AI 流式解读（SSE）、用户系统（注册/档案/收藏）、暴露量估计、网络图数据
"""
import asyncio
import json
import os
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
from services import pathway_service as ps
from services import compare_service as cmp_svc
from services import pantry_service as pantry
from services import safety_service as safety
from services import evidence_service as evidence
from services import explain_service as explain
from services import open_api
from services import report_service as report
from services import term_service as terms
from services import search_service as search

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
# 开放数据子路由（T1-6）：/api/v1/open/*
app.include_router(open_api.router)


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
    sql = f"SELECT id,name,type,oneliner,scenes,constitutions_suitable,duration,analysis_ready FROM recipe WHERE {' AND '.join(where)}"
    rows = conn.execute(sql, params).fetchall()
    # q 兑现搜索框承诺（搜方子名、体质需求或药材）：名称/简介/场景/体质/配料名内存过滤，
    # 配料名需查关联表所以不走 SQL；与 scene/constitution 同在内存层，and 语义一致
    mat_recipe_ids = set()
    if q:
        for row in conn.execute(
                "SELECT DISTINCT recipe_id FROM rel_recipe_material WHERE name LIKE ?",
                (f"%{q}%",)):
            mat_recipe_ids.add(row["recipe_id"])
    out = []
    for r in rows:
        scenes = json.loads(r["scenes"] or "[]")
        suits = json.loads(r["constitutions_suitable"] or "[]")
        if scene and scene not in scenes:
            continue
        if constitution and constitution not in suits:
            continue
        if q and not (q in r["name"] or q in (r["oneliner"] or "")
                      or any(q in s for s in scenes) or any(q in s for s in suits)
                      or r["id"] in mat_recipe_ids):
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


# ==================== 慢病安全滤镜（T1-5） ====================

@app.get("/api/v1/safety/profiles")
def safety_profiles():
    return ok({"items": safety._profile_summaries(),
               "disclaimer": "人群禁忌库基于药典与公开资料整理，仅供筛选参考，不构成医疗建议；服用药物或特殊健康状况请遵医嘱。"})


@app.get("/api/v1/safety/check/{recipe_id}")
def safety_check(recipe_id: int, profile: str):
    result = safety.check_recipe(recipe_id, profile)
    if result is None:
        raise HTTPException(404, "方子不存在或人群档案未知")
    return ok(result)


class SafetyBatchBody(BaseModel):
    recipe_ids: list[int]
    profile: str


@app.post("/api/v1/safety/check-batch")
def safety_check_batch(body: SafetyBatchBody):
    if body.profile not in safety.PROFILES:
        raise HTTPException(404, "人群档案未知")
    return ok(safety.filter_recipes(body.profile, body.recipe_ids[:100]))


# ==================== 证据分级与溯源（T1-3） ====================

@app.get("/api/v1/evidence/levels")
def evidence_levels():
    return ok(evidence.levels())


@app.get("/api/v1/evidence/recipe/{rid}")
def evidence_recipe(rid: int):
    result = evidence.recipe_evidence(rid)
    if result is None:
        raise HTTPException(404, "方子不存在")
    return ok(result)


# ==================== 入血概率可解释（T1-4） ====================

@app.get("/api/v1/explain/compound")
def explain_compound(name: str):
    result = explain.compound_explain(name)
    if result is None:
        raise HTTPException(404, "化合物不存在")
    return ok(result)


@app.get("/api/v1/explain/recipe/{rid}")
def explain_recipe(rid: int):
    result = explain.recipe_compounds(rid)
    if result is None:
        raise HTTPException(404, "方子不存在或无成分分析")
    return ok(result)


@app.get("/api/v1/recipes/{rid}")
def recipe_detail(rid: int):
    conn = get_db()
    r = conn.execute("SELECT * FROM recipe WHERE id=?", (rid,)).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "方子不存在")
    mats = conn.execute(
        "SELECT m.name, m.material_type, m.grams, m.optional, m.note, "
        "h.nature, h.flavor, h.functions, h.is_food_homology, f.nutrient_json AS nutrient "
        "FROM rel_recipe_material m LEFT JOIN herb h ON h.id=m.herb_id "
        "LEFT JOIN food f ON f.id=m.food_id WHERE m.recipe_id=?", (rid,)).fetchall()
    analysis = conn.execute("SELECT * FROM recipe_analysis WHERE recipe_id=?", (rid,)).fetchone()
    out = dict(r)
    for k in ("scenes", "constitutions_suitable", "constitutions_unsuitable"):
        out[k] = json.loads(out.get(k) or "[]")
    out["materials"] = [dict(m) | {"nutrient": json.loads(m["nutrient"] or "null")} for m in mats]
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
        "COALESCE(c.radar_anti_inflammatory_gsea,c.radar_anti_inflammatory) radar_anti_inflammatory,"
        "COALESCE(c.radar_immune_regulation_gsea,c.radar_immune_regulation) radar_immune_regulation,"
        "COALESCE(c.radar_airway_repair_gsea,c.radar_airway_repair) radar_airway_repair "
        "FROM compound c WHERE c.prob_cctcm>=? ORDER BY c.prob_cctcm DESC LIMIT ?",
        (min_prob, min(limit, 200))).fetchall()
    conn.close()
    return ok({"total": len(rows), "items": [dict(r) for r in rows]})


@app.get("/api/v1/foods")
def list_foods(q: str | None = None):
    """普通食材（食物型）列表：性味功效 + 营养素（中国食物成分表常见值）"""
    conn = get_db()
    if q:
        rows = conn.execute(
            "SELECT id,name,category,nature,flavor,functions,contraindication,nutrient_json "
            "FROM food WHERE name LIKE ? ORDER BY category,name", (f"%{q}%",)).fetchall()
    else:
        rows = conn.execute(
            "SELECT id,name,category,nature,flavor,functions,contraindication,nutrient_json "
            "FROM food ORDER BY category,name").fetchall()
    conn.close()
    items = [dict(r) | {"nutrient": json.loads(r["nutrient_json"] or "null"),
                        "has_nutrient": bool(r["nutrient_json"])}
             for r in rows]
    for it in items:
        del it["nutrient_json"]
    return ok({"total": len(items), "items": items})


# ==================== 全局搜索 ====================

@app.get("/api/v1/search")
def global_search(q: str | None = None, limit: int = 5):
    """全局聚合搜索（顶栏下拉用默认 5；独立搜索页传大 limit）；空关键词返回空分组"""
    return ok(search.global_search(q or "", max(1, min(limit, 20))))


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
    member_id: int | None = None


@app.post("/api/v1/constitution/records")
def save_constitution_record(body: SaveRecordBody, authorization: str | None = Header(None)):
    uid = auth_uid(authorization)
    rid = us.save_record(uid, body.judged, body.transformed, body.answers, body.member_id)
    return ok({"id": rid})


@app.get("/api/v1/constitution/records")
def list_constitution_records(authorization: str | None = Header(None), limit: int = 20):
    uid = auth_uid(authorization)
    return ok(us.list_records(uid, max(1, min(limit, 100))))


# ---------- 家庭成员档案（T2-8） ----------

class MemberBody(BaseModel):
    name: str
    relation: str | None = None
    color: str | None = None


@app.get("/api/v1/family/members")
def family_list(authorization: str | None = Header(None)):
    uid = auth_uid(authorization)
    return ok(us.list_members(uid))


@app.post("/api/v1/family/members")
def family_add(body: MemberBody, authorization: str | None = Header(None)):
    uid = auth_uid(authorization)
    try:
        return ok(us.add_member(uid, body.name, body.relation, body.color))
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.delete("/api/v1/family/members/{member_id}")
def family_remove(member_id: int, authorization: str | None = Header(None)):
    uid = auth_uid(authorization)
    if not us.remove_member(uid, member_id):
        raise HTTPException(404, "成员不存在")
    return ok({"removed": True})


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


# ==================== 21 天食养周期报告（T2-7） ====================

@app.get("/api/v1/report/cycle")
def cycle_report(authorization: str | None = Header(None), days: int = 21):
    uid = auth_uid(authorization)
    days = max(7, min(days, 90))
    return ok(report.build_report(uid, days))


# ==================== 节气/季节推荐（T2-9） ====================

@app.get("/api/v1/term/current")
def term_current(count: int = 4):
    """当前节气 + 未来节气 + 主题方子推荐"""
    return ok(terms.recommend(max(1, min(count, 8))))


# ==================== 「为你推荐」（千人千面） ====================
# 注意：/constitution/recommend 字面量路径必须注册在 /constitution/{code} 之前（§5.1 路由顺序坑）

from services import rec_service as rec  # noqa: E402


class GuestJudgeBody(BaseModel):
    judged: dict


@app.get("/api/v1/me/recommend")
def me_recommend(authorization: str | None = Header(None), count: int = 4):
    """登录用户推荐：最新体质记录 + 收藏/打卡偏好 + 当令节气"""
    uid = auth_uid(authorization)
    return ok(rec.recommend_for_user(uid, max(1, min(count, 8))))


@app.post("/api/v1/constitution/recommend")
def guest_recommend(body: GuestJudgeBody, count: int = 4):
    """游客推荐：body 传本地暂存的体质判定结果（combined 至少一项）"""
    try:
        return ok(rec.recommend_for_guest(body.judged, max(1, min(count, 8))))
    except ValueError as e:
        raise HTTPException(422, str(e))


# ==================== AI 助手对话（T3-11：RAG 限定库内 + 强制引用，SSE） ====================

from services import rag_service as rag  # noqa: E402


class AssistantChatBody(BaseModel):
    question: str = Field(..., min_length=1, max_length=300)
    history: list[dict] = Field(default_factory=list, description="[{role, content}] 最多6条")
    constitution_code: str | None = None


@app.post("/api/v1/assistant/chat")
async def assistant_chat(body: AssistantChatBody,
                         key: str | None = Query(None),
                         x_ai_key: str | None = Header(None, alias="X-AI-Key")):
    """食养问答：RAG 检索库内资料 → 流式回答。SSE 事件：delta / citations / error / [DONE]"""
    question = body.question.strip()
    if not question:
        raise HTTPException(422, "问题不能为空")
    ctx = rag.retrieve_context(question, body.constitution_code)
    messages = ai.build_chat_messages(question, ctx, body.history, ctx.get("constitution"))

    async def gen():
        # citations 先行发出：前端在打字开始前就能渲染引用卡
        yield f"data: {json.dumps({'citations': ctx['citations'], 'no_context': ctx['no_context'], 'disclaimer': DISCLAIMER}, ensure_ascii=False)}\n\n"
        # Key 解析：X-AI-Key 头 → ZeroGate 平台级默认（本机网关，key=zerogate，不落库不进日志）
        user_key = (x_ai_key or key or "").strip() or None
        api_key, base_url, model = user_key, "", ""
        if not api_key:
            api_key = os.environ.get("SHIYANG_AI_KEY") or "zerogate"
            base_url = os.environ.get("SHIYANG_AI_BASE_URL") or "http://127.0.0.1:7863/v1"
            model = os.environ.get("SHIYANG_AI_MODEL") or "deepseek-v4-flash"
        try:
            async for chunk in ai.stream_chat(messages, api_key, "deepseek", base_url, model):
                yield f"data: {json.dumps({'delta': chunk}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except ai.AIConfigError as e:
            yield f"data: {json.dumps({'error': e.message, 'code': e.code}, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'error': f'AI 服务异常: {e}', 'code': 'gateway_down'}, ensure_ascii=False)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


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


# ==================== 四层证据链 Sankey 数据 ====================

@app.get("/api/v1/recipes/{rid}/chain")
def evidence_chain(rid: int, max_herbs: int = 6, max_compounds: int = 10,
                   max_targets: int = 10):
    """方子 → 药材(克重) → 活性成分(入血概率) → 人类蛋白靶点，四层证据链。
    归属关系取自 rel_herb_compound_v2（原始文献含量表重建，非旧错乱表）。"""
    max_herbs = max(1, min(max_herbs, 12))
    max_compounds = max(1, min(max_compounds, 20))
    max_targets = max(1, min(max_targets, 20))
    conn = get_db()
    r = conn.execute("SELECT name FROM recipe WHERE id=?", (rid,)).fetchone()
    if not r:
        conn.close()
        raise HTTPException(404, "方子不存在")

    # 药材层：有成分数据的配料，按克重降序
    herbs = conn.execute("""
        SELECT m.herb_id, m.name, m.grams FROM rel_recipe_material m
        WHERE m.recipe_id=? AND m.herb_id IS NOT NULL AND m.herb_id IN (
            SELECT DISTINCT herb_id FROM rel_herb_compound_v2)
        ORDER BY COALESCE(m.grams, 0) DESC LIMIT ?""", (rid, max_herbs)).fetchall()
    if not herbs:
        conn.close()
        return ok({"nodes": [], "links": [], "levels": ["方子", "药材", "活性成分", "作用靶点"]})

    herb_ids = [h["herb_id"] for h in herbs]
    hp = ",".join("?" * len(herb_ids))

    # 成分层：这些药材的真实成分，按入血概率降序取 Top N
    comps = conn.execute(f"""
        SELECT c.id, c.name, c.prob_cctcm,
               GROUP_CONCAT(DISTINCT h.name) AS herbs
        FROM rel_herb_compound_v2 rc
        JOIN compound c ON c.id = rc.compound_id
        JOIN herb h ON h.id = rc.herb_id
        WHERE rc.herb_id IN ({hp})
        GROUP BY c.id ORDER BY c.prob_cctcm DESC LIMIT ?""",
        (*herb_ids, max_compounds)).fetchall()
    if not comps:
        conn.close()
        return ok({"nodes": [], "links": [], "levels": ["方子", "药材", "活性成分", "作用靶点"]})

    comp_ids = [c["id"] for c in comps]
    cp = ",".join("?" * len(comp_ids))

    # 靶点层：成分关联的人类蛋白
    targets = conn.execute(f"""
        SELECT t.gene, COUNT(DISTINCT rt.compound_id) c
        FROM rel_compound_target rt
        JOIN target t ON t.gene = rt.target_gene
        WHERE t.target_type='Protein' AND t.species='Homo sapiens'
          AND rt.compound_id IN ({cp})
        GROUP BY t.gene ORDER BY c DESC LIMIT ?""", (*comp_ids, max_targets)).fetchall()

    nodes, links = [], []

    def nid(level, key):
        return f"{level}:{key}"

    nodes.append({"name": r["name"], "depth": 0, "kind": "recipe"})
    for h in herbs:
        nodes.append({"name": h["name"], "depth": 1, "kind": "herb",
                      "value": h["grams"]})
    for c in comps:
        nodes.append({"name": c["name"], "depth": 2, "kind": "compound",
                      "value": round(c["prob_cctcm"], 2)})
    for t in targets:
        nodes.append({"name": t["gene"], "depth": 3, "kind": "target"})

    for h in herbs:
        links.append({"source": r["name"], "target": h["name"],
                      "value": h["grams"] or 5})
    # 药材 → 成分（真实归属，来自重建表）
    hc = conn.execute(f"""
        SELECT h.name hn, c.name cn, c.prob_cctcm p
        FROM rel_herb_compound_v2 rc
        JOIN compound c ON c.id = rc.compound_id
        JOIN herb h ON h.id = rc.herb_id
        WHERE rc.herb_id IN ({hp}) AND rc.compound_id IN ({cp})""",
        (*herb_ids, *comp_ids)).fetchall()
    for row in hc:
        links.append({"source": row["hn"], "target": row["cn"],
                      "value": round(1 + (row["p"] or 0) * 4, 2)})
    # 成分 → 靶点
    ct = conn.execute(f"""
        SELECT c.name cn, t.gene g FROM rel_compound_target rt
        JOIN compound c ON c.id = rt.compound_id
        JOIN target t ON t.gene = rt.target_gene
        WHERE t.target_type='Protein' AND t.species='Homo sapiens'
          AND rt.compound_id IN ({cp})""", comp_ids).fetchall()
    tg = {t["gene"] for t in targets}
    for row in ct:
        if row["g"] in tg:
            links.append({"source": row["cn"], "target": row["g"], "value": 1})
    conn.close()

    # 同名节点去重（药材名/成分名/基因名可能重复）
    seen, uniq = set(), []
    for n in nodes:
        k = (n["depth"], n["name"])
        if k in seen:
            continue
        seen.add(k)
        uniq.append(n)
    return ok({"nodes": uniq, "links": links,
               "levels": ["方子", "药材", "活性成分", "作用靶点"],
               "note": "药材-成分归属来自文献含量表重建；靶点仅人类蛋白"})


# ==================== 暴露量估计（P2.5） ====================
@app.get("/api/v1/recipes/{rid}/exposure")
def exposure(rid: int):
    result = es.estimate(rid)
    if result is None:
        raise HTTPException(404, "方子不存在或无可估计配料")
    return ok(result)


# ==================== 通路富集（GO BP + KEGG，Enrichr） ====================

@app.get("/api/v1/recipes/{rid}/pathways")
def pathways(rid: int, refresh: bool = False):
    """方子 Top 成分靶点集合的通路富集（GO 生物学过程为主，KEGG 为辅）。
    优先返回预生成缓存；无缓存时实时调用 Enrichr 并落库。"""
    conn = get_db()
    try:
        exists = conn.execute("SELECT 1 FROM recipe WHERE id=?", (rid,)).fetchone()
    finally:
        conn.close()
    if not exists:
        raise HTTPException(404, "方子不存在")
    return ok(ps.for_recipe(rid, refresh=refresh))


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
        # 仅取人类蛋白靶点：非人物种（小鼠/大鼠/斑马鱼等）关系不进用户可见网络
        links = conn.execute(
            f"SELECT rc.compound_id, rc.target_gene FROM rel_compound_target rc "
            f"JOIN compound c ON c.id=rc.compound_id "
            f"JOIN target t ON t.gene=rc.target_gene AND t.species='Homo sapiens' "
            f"WHERE c.name IN ({ph})", names).fetchall()
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
               "legend": ["方子", "活性成分", "作用靶点"],
               "note": "仅展示人类蛋白靶点（Homo sapiens），非人物种关系已过滤"})


@app.get("/api/v1/constitution/{code}")
def constitution_info(code: str):
    d = cs.constitution_detail(code)
    if not d:
        raise HTTPException(404, f"未知体质: {code}")
    return ok(d)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8100)
