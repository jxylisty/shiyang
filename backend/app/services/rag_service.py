# -*- coding: utf-8 -*-
"""
RAG 检索服务（T3-11 AI 助手）：把用户问题限定到自家方子库/药材/成分数据，
产出 (blocks, citations)：
- blocks     注入 prompt 的资料文本块，每块自带 [F#]/[H#]/[C#] 编号头，供模型引用
- citations  独立返回的引用卡字段（方子名+配料+来源 URL、药材性味、成分入血概率），前端直接渲染
检索全部来自 shiyang.db（只读），本服务不做任何生成；
无命中时 no_context=true，由上层在 system prompt 里声明降级，而不是编造。
blocks 总字符硬上限 MAX_CHARS，防 prompt 爆炸。
"""
import json
import re
import sqlite3
from pathlib import Path

from services import constitution_service as cs
from services.search_service import global_search

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "shiyang.db"

MAX_CHARS = 6000
RECIPE_BLOCKS = 4
HERB_BLOCKS = 4
COMPOUND_BLOCKS = 3
MAX_QUERIES = 8  # 关键词展开的检索次数上限（每次 global_search 内部 3 条 LIKE，本地库毫秒级）

# 与 Recipes.vue SCENES 保持一致的名称（同源于 recipe.scenes JSON 字段，勿单方面改名）
SCENES = ["护嗓润喉", "熬夜护眼", "换季调理", "助眠", "消化",
          "控糖轻养", "控油祛痘", "久坐通气", "情绪舒压", "经期温养"]

# 口语→场景别名：按药典通识整理的产品规则（§2.5 编辑性规则，非实验数据），帮助把
# 「嗓子干」「睡不着」这类描述对上库内场景标签；宁可漏配也不夸配
SCENE_ALIASES = {
    "护嗓润喉": ("嗓", "喉咙", "咽", "干咳", "声"),
    "助眠": ("失眠", "睡不", "入睡", "安神"),
    "熬夜护眼": ("熬夜", "眼", "屏幕", "视"),
    "控油祛痘": ("痘", "出油", "油"),
    "经期温养": ("经期", "痛经", "姨妈", "月事"),
    "消化": ("胃", "腹胀", "消化", "积食"),
    "情绪舒压": ("压", "焦虑", "烦", "情绪"),
}

# 问句停用词：剔除后再拿剩余片段做关键词检索（「喝什么」「有哪些」这类词不参与匹配）
_STOP = re.compile(
    r"什么|哪些|怎么|如何|请问|有没有|适合|推荐|介绍一下|可以|应该|需要|"
    r"我想|帮我|我是|有点|最近|总是|容易|调理|缓解|改善|一下|的方|的茶|"
    r"喝|吃|泡|煮|炖|配|是|有|吗|呢|吧|啊|的|了|？|\?|！|!|。|，|,|、|；|;| ")


def _db():
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _intents(q: str) -> set:
    """轻量意图识别（正则关键词，不引外部 NLP）：决定哪些资料组值得给模型"""
    s = set()
    if re.search(r"方|茶|汤|羹|膳|粥|饮|食谱|搭配", q):
        s.add("recipe")
    if re.search(r"药材|中药|性味|归经|功效|食材", q):
        s.add("herb")
    if re.search(r"成分|化合物|分子|入血|靶点|概率|吸收", q):
        s.add("compound")
    return s


def _keywords(q: str) -> list[str]:
    """问题 → 检索关键词候选：原句优先，剔除停用词后的片段次之"""
    out = []
    if q:
        out.append(q)
    for seg in _STOP.split(q):
        seg = seg.strip()
        if len(seg) >= 2 and seg not in out:
            out.append(seg)
    return out


def _detect_constitutions(q: str) -> list[str]:
    """问句里点名的体质（「气虚」「阴虚」…）→ code 列表"""
    codes = []
    for code, name in cs.NAME_BY_CODE.items():
        short = name.replace("质", "")
        if short in q:
            codes.append(code)
    return codes


def _detect_scenes(q: str) -> list[str]:
    """问句 → 命中的场景标签（先按场景全名，再按口语别名）"""
    hits = [s for s in SCENES if s in q]
    for scene, words in SCENE_ALIASES.items():
        if scene not in hits and any(w in q for w in words):
            hits.append(scene)
    return hits


def _recipes_by_scene(conn, scene: str, limit: int) -> list[dict]:
    rows = conn.execute(
        "SELECT id,name,type,oneliner,scenes FROM recipe "
        "WHERE status != '弃用' AND scenes LIKE ? "
        "ORDER BY analysis_ready DESC, id LIMIT ?", (f"%{scene}%", limit)).fetchall()
    out = []
    for r in rows:
        try:
            scenes = json.loads(r["scenes"] or "[]")
        except json.JSONDecodeError:
            scenes = []
        out.append({**dict(r), "scenes": scenes, "matched": f"场景·{scene}"})
    return out


def _recipes_by_constitution(conn, codes: list[str], limit: int) -> list[dict]:
    """体质适宜方子（复用 constitution_service 打分），标注「XX相宜」"""
    judged = {"results": {}, "main": codes[0], "combined": codes}
    matched: dict[int, list] = {}
    ids: list[int] = []
    for it in cs.recommend_recipes(judged, limit=limit * 2):
        if it["id"] not in matched:
            ids.append(it["id"])
        matched[it["id"]] = it.get("matched_constitutions", [])
    if not ids:
        return []
    ph = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT id,name,type,oneliner,scenes FROM recipe WHERE id IN ({ph})", ids).fetchall()
    short_names = [cs.SHORT_NAME[c] for c in codes if c in cs.SHORT_NAME]
    out = []
    for r in rows:
        try:
            scenes = json.loads(r["scenes"] or "[]")
        except json.JSONDecodeError:
            scenes = []
        out.append({**dict(r), "scenes": scenes,
                    "matched": "、".join(f"{s}相宜" for s in short_names)})
    out.sort(key=lambda x: ids.index(x["id"]))
    return out[:limit]


def _recipe_full(conn, ids: list[int]):
    """按给定顺序取方子完整资料（出处/禁忌/配料），无则跳过"""
    if not ids:
        return []
    ph = ",".join("?" * len(ids))
    rows = conn.execute(
        f"SELECT id,name,type,oneliner,description,constitutions_suitable,contraindication,"
        f"source,reference_url FROM recipe WHERE id IN ({ph})", ids).fetchall()
    by_id = {r["id"]: r for r in rows}
    return [by_id[i] for i in ids if i in by_id]


def _materials(conn, rid: int) -> str:
    rows = conn.execute(
        "SELECT name FROM rel_recipe_material WHERE recipe_id=? ORDER BY id", (rid,)).fetchall()
    return "、".join(r["name"] for r in rows)


def _herb_full(conn, herb_ids: list[str]):
    if not herb_ids:
        return []
    ph = ",".join("?" * len(herb_ids))
    rows = conn.execute(
        f"SELECT id,name,category,nature,flavor,meridians,functions,"
        f"is_food_homology,food_catalog_batch,compound_count FROM herb WHERE id IN ({ph})",
        herb_ids).fetchall()
    by_id = {r["id"]: r for r in rows}
    return [by_id[i] for i in herb_ids if i in by_id]


def _herb_top_compounds(conn, herb_id: str, limit: int) -> list:
    return conn.execute(
        "SELECT c.name, c.prob_cctcm, c.target_count FROM rel_herb_compound hc "
        "JOIN compound c ON c.id=hc.compound_id WHERE hc.herb_id=? AND c.prob_cctcm IS NOT NULL "
        "ORDER BY c.prob_cctcm DESC LIMIT ?", (herb_id, limit)).fetchall()


def retrieve_context(question: str, constitution_code: str | None = None) -> dict:
    """问题 → {blocks, citations, no_context, total_chars, constitution}

    检索漏斗：原句/关键词组逐个 global_search（各组独立收口，空组才继续尝试下一关键词）
    → 方子按场景标签兜底 → 体质适宜方子兜底（入参 constitution_code 或问句点名体质）。
    """
    q = (question or "").strip()
    intents = _intents(q)
    codes = _detect_constitutions(q)
    if constitution_code and constitution_code in cs.NAME_BY_CODE and constitution_code not in codes:
        codes.insert(0, constitution_code)
    scenes = _detect_scenes(q)

    conn = _db()
    try:
        # ---- 1. 关键词漏斗：各组独立收口，命中即停（保持首见顺序） ----
        recipe_hits: dict[int, dict] = {}
        herb_hits: dict[str, dict] = {}
        compound_hits: dict[str, dict] = {}
        nq = 0
        for kw in _keywords(q)[:MAX_QUERIES]:
            nq += 1
            gs = global_search(kw, 6)
            for r in gs["recipes"]:
                if r["id"] not in recipe_hits:
                    recipe_hits[r["id"]] = {**r, "matched": r.get("matched_by") or f"搜索「{kw}」"}
            for h in gs["herbs"]:
                if h["id"] not in herb_hits:
                    herb_hits[h["id"]] = {**h, "matched": h.get("matched_by") or f"搜索「{kw}」"}
            for c in gs["compounds"]:
                if c["name"] not in compound_hits:
                    compound_hits[c["name"]] = c
            # 三组都有料（或问句明确不涉及某组）就不烧剩余查询次数
            if recipe_hits and herb_hits and (compound_hits or "compound" not in intents):
                break

        # ---- 2. 方子兜底：场景标签 → 体质适宜 ----
        recipe_list = [recipe_hits[i] for i in list(recipe_hits)[:RECIPE_BLOCKS]]
        if len(recipe_list) < RECIPE_BLOCKS:
            have = {r["id"] for r in recipe_list}
            for scene in scenes:
                for r in _recipes_by_scene(conn, scene, RECIPE_BLOCKS):
                    if r["id"] not in have:
                        have.add(r["id"])
                        recipe_list.append(r)
                        if len(recipe_list) >= RECIPE_BLOCKS:
                            break
                if len(recipe_list) >= RECIPE_BLOCKS:
                    break
        if len(recipe_list) < RECIPE_BLOCKS and codes:
            have = {r["id"] for r in recipe_list}
            for r in _recipes_by_constitution(conn, codes, RECIPE_BLOCKS):
                if r["id"] not in have:
                    have.add(r["id"])
                    recipe_list.append(r)
                    if len(recipe_list) >= RECIPE_BLOCKS:
                        break

        herb_list = [herb_hits[i] for i in list(herb_hits)[:HERB_BLOCKS]]
        compound_list = [compound_hits[k] for k in list(compound_hits)[:COMPOUND_BLOCKS]]

        # ---- 3. 组装 blocks + citations（加 blocks 同步加 citations，不产生孤儿引用） ----
        blocks: list[str] = []
        citations: list[dict] = []
        total = 0

        def add(block: str, cite: dict) -> bool:
            nonlocal total
            if total + len(block) > MAX_CHARS:
                return False
            total += len(block)
            blocks.append(block)
            citations.append(cite)
            return True

        for r in _recipe_full(conn, [r["id"] for r in recipe_list]):
            rid = r["id"]
            meta = recipe_hits.get(rid) or next((x for x in recipe_list if x["id"] == rid), {})
            mats = _materials(conn, rid)
            try:
                rscenes = json.loads(next((x.get("scenes") or "[]") for x in recipe_list if x["id"] == rid))
            except (json.JSONDecodeError, StopIteration, TypeError):
                rscenes = []
            try:
                rcon = json.loads(r["constitutions_suitable"] or "[]")
            except json.JSONDecodeError:
                rcon = [r["constitutions_suitable"]] if r["constitutions_suitable"] else []
            parts = [f"[F{rid}] {r['name']}（{r['type'] or '食养方'}"]
            if rscenes:
                parts[0] += f" · {'/'.join(rscenes[:2])}"
            parts[0] += f"）：{r['oneliner'] or r['description'] or ''}"
            if mats:
                parts.append(f"配料：{mats}")
            if rcon:
                parts.append(f"适宜体质：{'、'.join(rcon)}")
            if r["contraindication"]:
                parts.append(f"禁忌：{r['contraindication']}")
            if r["source"]:
                parts.append(f"出处：{r['source']}")
            if meta.get("matched"):
                parts.append(f"命中：{meta['matched']}")
            cite = {"id": f"F{rid}", "kind": "recipe", "ref_id": rid, "title": r["name"],
                    "sub": " · ".join(filter(None, [r["type"], *rscenes[:1]])),
                    "detail": f"配料：{mats}" if mats else "",
                    "source": r["source"], "url": r["reference_url"],
                    "matched": meta.get("matched") or ""}
            if not add("；".join(parts), cite):
                break

        h_seq = 0
        for h in _herb_full(conn, [h["id"] for h in herb_list]):
            h_seq += 1
            meta = herb_hits.get(h["id"], {})
            meridians = (h["meridians"] or "").replace(",", "、")
            batch = f"；药食同源目录第{h['food_catalog_batch']}批" if h["food_catalog_batch"] else ""
            funcs = "、".join((h["functions"] or "").replace("，", "、").split("、")[:6])
            block = (f"[H{h_seq}] {h['name']}（{h['category'] or '药材'} · 性{h['nature'] or '平'}味{h['flavor'] or '—'}"
                     f"{f' · 归{meridians}经' if meridians else ''}）：{funcs}{batch}；"
                     f"库内关联成分 {h['compound_count'] or 0} 个")
            cite = {"id": f"H{h_seq}", "kind": "herb", "ref_id": h["id"], "title": h["name"],
                    "sub": " · ".join(filter(None, [h["category"], h["nature"], h["flavor"]])),
                    "detail": f"功效：{funcs}", "url": None,
                    "matched": meta.get("matched") or ""}
            if not add(block, cite):
                break

        c_seq = 0
        for c in compound_list:
            c_seq += 1
            prob = c["prob_cctcm"]
            block = (f"[C{c_seq}] {c['name']}：入血概率 {prob * 100:.1f}%（模型预测值，非实验事实），"
                     f"关联靶点 {c['target_count'] or 0} 个")
            cite = {"id": f"C{c_seq}", "kind": "compound", "ref_id": c["name"], "title": c["name"],
                    "sub": f"入血概率 {prob * 100:.0f}%（模型预测）",
                    "detail": f"关联 {c['target_count'] or 0} 个靶点", "url": None, "matched": ""}
            if not add(block, cite):
                break

        # 问句明确问成分而成分组为空时，给命中方子/药材的代表性成分补位
        if "compound" in intents and not compound_list:
            if herb_list:
                for row in _herb_top_compounds(conn, herb_list[0]["id"], COMPOUND_BLOCKS):
                    c_seq += 1
                    block = (f"[C{c_seq}] {row['name']}（来自{herb_list[0]['name']}）："
                             f"入血概率 {row['prob_cctcm'] * 100:.1f}%（模型预测值，非实验事实），"
                             f"关联靶点 {row['target_count'] or 0} 个")
                    cite = {"id": f"C{c_seq}", "kind": "compound", "ref_id": row["name"],
                            "title": row["name"], "sub": f"入血概率 {row['prob_cctcm'] * 100:.0f}%（模型预测）",
                            "detail": f"{herb_list[0]['name']}所含 · 关联 {row['target_count'] or 0} 个靶点",
                            "url": None, "matched": ""}
                    if not add(block, cite):
                        break

        return {"blocks": blocks, "citations": citations, "no_context": not blocks,
                "total_chars": total, "constitution": cs.NAME_BY_CODE.get(codes[0]) if codes else None}
    finally:
        conn.close()
