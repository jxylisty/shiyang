# -*- coding: utf-8 -*-
"""
「为你推荐」服务（千人千面）：
- 体质匹配（复用 constitution_service.recommend_recipes 的适宜打分 + 忌口排除）
- 节气加成（term_service 当前节气场景命中加分，标签注明「当令」）
- 行为偏好（收藏/打卡的场景分布 → 偏好场景命中加分，标签注明「你常收藏/打卡」）
- 每条推荐带 reasons[]，全部来自数据字段与规则标注，预测/参考分不表述为疗效
登录用户读档案（constitution_record 最新一条 + 收藏 + 打卡）；游客传 judged 结果（本地暂存）。
"""
import json
import sqlite3
from pathlib import Path

from services import constitution_service as cs
from services import term_service as terms

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "shiyang.db"

DISCLAIMER = "本平台内容为健康参考信息，不构成医疗建议，不用于诊断或治疗。"


def _db():
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _scene_pref(uid: int) -> dict:
    """收藏 + 打卡方子的场景分布 → {场景名: 次数}（行为偏好信号）"""
    conn = sqlite3.connect(Path(__file__).resolve().parents[3] / "data" / "user.db")
    conn.row_factory = sqlite3.Row
    try:
        ids = [r["recipe_id"] for r in conn.execute(
            "SELECT recipe_id FROM favorite WHERE user_id=?", (uid,))]
        ids += [r["recipe_id"] for r in conn.execute(
            "SELECT DISTINCT recipe_id FROM checkin WHERE user_id=?", (uid,))]
    finally:
        conn.close()
    if not ids:
        return {}
    ph = ",".join("?" * len(ids))
    conn = _db()
    try:
        pref: dict = {}
        for r in conn.execute(
                f"SELECT id, scenes FROM recipe WHERE id IN ({ph})", ids):
            try:
                for s in json.loads(r["scenes"] or "[]"):
                    pref[s] = pref.get(s, 0) + 1
            except json.JSONDecodeError:
                continue
        return pref
    finally:
        conn.close()


def recommend_for_user(uid: int, limit: int = 4) -> dict:
    """登录用户：最新体质记录 + 收藏/打卡偏好 + 节气 → 推荐与理由"""
    records = None
    try:
        from services import user_service as us
        records = us.list_records(uid, limit=1)
    except Exception:
        records = None
    judged = None
    main_name = None
    if records:
        rec = records[0]
        main_name = rec.get("main_name")
        combined_names = rec.get("combined", [])
        # 体质中文名 → code，重建 judged 最小结构供 recommend_recipes 复用
        code_by_name = {v: k for k, v in cs.NAME_BY_CODE.items()}
        combined_codes = [code_by_name[n] for n in combined_names if n in code_by_name]
        if combined_codes:
            main_code = rec.get("main_code")
            judged = {"results": {}, "main": main_code if main_code in combined_codes else None,
                      "combined": combined_codes}
    return _recommend(judged, main_name, uid, limit)


def recommend_for_guest(judged: dict, limit: int = 4) -> dict:
    """游客：前端本地暂存的 judged 结果（POST body），最小结构校验"""
    if not isinstance(judged, dict) or not isinstance(judged.get("combined"), list) \
            or not judged["combined"]:
        raise ValueError("judged 结构不完整：需要非空 combined 列表")
    valid = set(cs.NAME_BY_CODE)
    codes = [c for c in judged["combined"] if c in valid]
    if not codes:
        raise ValueError("combined 中没有可识别的体质 code")
    main_name = cs.NAME_BY_CODE.get(judged.get("main"))
    judged = {"results": judged.get("results") or {}, "main": judged.get("main"), "combined": codes}
    return _recommend(judged, main_name, None, limit)


def _recommend(judged: dict | None, main_name: str | None, uid: int | None, limit: int) -> dict:
    info = terms.current_term()
    scene = info["current"]["theme"]["scene"]
    pref = _scene_pref(uid) if uid else {}

    scored: dict = {}
    if judged:
        # 体质推荐（打分+忌口排除），单方上限 2 分理由（主体质+兼夹合并展示）
        for item in cs.recommend_recipes(judged, limit=20):
            scored[item["id"]] = {
                "item": item, "reasons": [f"{m}相宜" for m in item.get("matched_constitutions", [])[:2]],
                "_score": len(item.get("matched_constitutions", [])) * 10,
            }
    # 节气场景：不覆盖体质结果，体质分为主 + 当令加成；无体质数据时直接按场景推荐
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT id,name,type,oneliner,scenes,constitutions_suitable FROM recipe "
            "WHERE status != '弃用'").fetchall()
    finally:
        conn.close()
    by_id = {r["id"]: r for r in rows}
    for rid, r in by_id.items():
        try:
            scenes = json.loads(r["scenes"] or "[]")
        except json.JSONDecodeError:
            continue
        if scene in scenes:
            if rid in scored:
                scored[rid]["reasons"].append(f"当令·{scene}")
                scored[rid]["_score"] += 4
            else:
                row = by_id[rid]
                scored[rid] = {
                    "item": {"id": rid, "name": row["name"], "type": row["type"],
                             "oneliner": row["oneliner"], "scenes": scenes,
                             "matched_constitutions": []},
                    "reasons": [f"当令·{scene}"], "_score": 2,
                }
    # 行为偏好加成（分数低于体质命中，仅排序微调 + 理由标注）
    top_pref = [s for s, _ in sorted(pref.items(), key=lambda x: -x[1])[:3]]
    for rid, entry in scored.items():
        for s in entry["item"].get("scenes", []):
            if s in top_pref:
                entry["reasons"].append(f"你常收藏{s}类" if pref[s] == max(pref.values()) else f"你也常看{s}类")
                entry["_score"] += 1
                break

    items = sorted(scored.values(), key=lambda e: -e["_score"])[:limit]
    out = []
    for e in items:
        it = e["item"]
        out.append({
            "id": it["id"], "name": it["name"], "type": it["type"], "oneliner": it["oneliner"],
            "scenes": it.get("scenes", []),
            "matched_constitutions": it.get("matched_constitutions", []),
            "reasons": e["reasons"][:3],
        })
    return {
        "has_constitution": judged is not None,
        "main_constitution": main_name,
        "current_term": {"name": info["current"]["name"], "scene": scene,
                         "tip": info["current"]["theme"]["tip"]},
        "items": out,
        "disclaimer": DISCLAIMER,
    }
