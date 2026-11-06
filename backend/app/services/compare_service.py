# -*- coding: utf-8 -*-
"""
对比实验室服务：两个方子并排对比——成分覆盖、入血化合物重叠度、靶点/通路差异、体质适宜对照
数据全部来自 shiyang.db 只读查询，复用 recipe_analysis 预生成结果
"""
import json
import sqlite3
from pathlib import Path

from services import safety_service as safety
from services import eval_service as evs

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "shiyang.db"

JACCARD_LABELS = [(0.75, "高度重叠"), (0.45, "中度重叠"), (0.2, "部分重叠"), (0.0, "几乎不同")]


def _db():
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _load_one(conn, rid: int) -> dict | None:
    r = conn.execute(
        "SELECT id,name,type,oneliner,scenes,constitutions_suitable,constitutions_unsuitable "
        "FROM recipe WHERE id=?", (rid,)).fetchone()
    if not r:
        return None
    out = dict(r)
    for k in ("scenes", "constitutions_suitable", "constitutions_unsuitable"):
        out[k] = json.loads(out.get(k) or "[]")
    mats = conn.execute(
        "SELECT name, grams, optional FROM rel_recipe_material WHERE recipe_id=? ORDER BY id",
        (rid,)).fetchall()
    out["materials"] = [dict(m) for m in mats]
    a = conn.execute("SELECT * FROM recipe_analysis WHERE recipe_id=?", (rid,)).fetchone()
    out["analysis"] = None
    out["eval_summary"] = evs.get_recipe_eval(rid, conn)
    if a:
        a = dict(a)
        a["top_compounds"] = json.loads(a["top_compounds"] or "null") or []
        a["top_targets"] = json.loads(a["top_targets"] or "null") or []
        a["radar_summary"] = json.loads(a["radar_summary"] or "null") or {}
        if out["eval_summary"]:
            ev = out["eval_summary"]
            a["radar_summary"] = {
                "absorption": ev["absorption"],
                "synergy": ev["synergy"],
                "evidence": ev["evidence"],
                "anti_inflammatory": ev["absorption"],
                "immune_regulation": ev["synergy"],
                "airway_repair": ev["evidence"],
            }
        out["analysis"] = a
    return out


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def _overlap_label(j: float) -> str:
    for th, label in JACCARD_LABELS:
        if j >= th:
            return label
    return "几乎不同"


def compare(a_id: int, b_id: int) -> dict | None:
    """返回对比数据；任一方子不存在返回 None"""
    conn = _db()
    try:
        a = _load_one(conn, a_id)
        b = _load_one(conn, b_id)
        if not a or not b:
            return None

        # ---- 成分层 ----
        ca = {c["name"]: c for c in (a["analysis"]["top_compounds"] if a["analysis"] else [])}
        cb = {c["name"]: c for c in (b["analysis"]["top_compounds"] if b["analysis"] else [])}
        shared_c = sorted(set(ca) & set(cb))
        only_a = sorted(set(ca) - set(cb))
        only_b = sorted(set(cb) - set(ca))
        hi = 0.7  # 入血概率"高"的展示阈值，与前端成分库一致
        hi_a = {n for n, c in ca.items() if (c.get("prob_cctcm") or 0) >= hi}
        hi_b = {n for n, c in cb.items() if (c.get("prob_cctcm") or 0) >= hi}

        # ---- 靶点层（top_targets: [{gene, compounds:[names]}]）----
        ta = {t["gene"] for t in (a["analysis"]["top_targets"] if a["analysis"] else [])}
        tb = {t["gene"] for t in (b["analysis"]["top_targets"] if b["analysis"] else [])}

        # ---- 配料层 ----
        ma = {m["name"] for m in a["materials"]}
        mb = {m["name"] for m in b["materials"]}

        # ---- 食养科学三维指数（入血潜力 / 多靶协同 / 证据强度）----
        eval_a = a.get("eval_summary") or evs.get_recipe_eval(a_id, conn)
        eval_b = b.get("eval_summary") or evs.get_recipe_eval(b_id, conn)

        j_compound = _jaccard(set(ca), set(cb))
        j_target = _jaccard(ta, tb)
        j_material = _jaccard(ma, mb)

        return {
            "a": a, "b": b,
            "compound": {
                "shared": shared_c, "only_a": only_a, "only_b": only_b,
                "shared_detail": [ca[n] for n in shared_c],
                "hi_blood_a": sorted(hi_a), "hi_blood_b": sorted(hi_b),
                "hi_blood_shared": sorted(hi_a & hi_b),
                "jaccard": round(j_compound, 3), "overlap_label": _overlap_label(j_compound),
            },
            "target": {
                "shared": sorted(ta & tb), "only_a": sorted(ta - tb), "only_b": sorted(tb - ta),
                "jaccard": round(j_target, 3), "overlap_label": _overlap_label(j_target),
            },
            "material": {
                "shared": sorted(ma & mb), "only_a": sorted(ma - mb), "only_b": sorted(mb - ma),
                "jaccard": round(j_material, 3),
            },
            "radar": {
                "dims": ["absorption", "synergy", "evidence"],
                "labels": ["入血潜力", "多靶协同", "证据强度"],
                "a": [eval_a["absorption"] if eval_a else None,
                      eval_a["synergy"] if eval_a else None,
                      eval_a["evidence"] if eval_a else None],
                "b": [eval_b["absorption"] if eval_b else None,
                      eval_b["synergy"] if eval_b else None,
                      eval_b["evidence"] if eval_b else None],
            },
            "eval_a": eval_a,
            "eval_b": eval_b,
            "constitution": {
                "both_suitable": sorted(set(a["constitutions_suitable"]) & set(b["constitutions_suitable"])),
                "a_only": sorted(set(a["constitutions_suitable"]) - set(b["constitutions_suitable"])),
                "b_only": sorted(set(b["constitutions_suitable"]) - set(a["constitutions_suitable"])),
                "warn_a": sorted(set(a["constitutions_unsuitable"]) & set(b["constitutions_suitable"])),
                "warn_b": sorted(set(b["constitutions_unsuitable"]) & set(a["constitutions_suitable"])),
            },
            "conflicts": _conflicts(a, b),
        }
    finally:
        conn.close()


def _conflicts(a: dict, b: dict) -> dict:
    """叠加/人群冲突提示（只陈述事实，不设剂量阈值——阈值属医疗判断，平台不做）。

    shared_materials: 双方共有配料及各自克重；两边克重已知时给出合计，提示同日饮用酌减。
    safety: 复用 safety_service 的 5 类人群档案逐方检查，任一方非 pass 才列出。
    """
    ga = {m["name"]: m.get("grams") for m in a["materials"]}
    gb = {m["name"]: m.get("grams") for m in b["materials"]}
    shared = []
    for name in sorted(set(ga) & set(gb)):
        va, vb = ga[name], gb[name]
        shared.append({
            "name": name, "grams_a": va, "grams_b": vb,
            "total": round(va + vb, 1) if va is not None and vb is not None else None,
        })

    safety_hits = []
    for code, prof in safety.PROFILES.items():
        ra = safety.check_recipe(a["id"], code)
        rb = safety.check_recipe(b["id"], code)
        if (ra and ra["verdict"] != "pass") or (rb and rb["verdict"] != "pass"):
            safety_hits.append({
                "profile": code, "profile_name": prof["name"],
                "a": {"verdict": ra["verdict"], "blocks": ra["blocks"], "warns": ra["warns"]} if ra else None,
                "b": {"verdict": rb["verdict"], "blocks": rb["blocks"], "warns": rb["warns"]} if rb else None,
            })
    return {"shared_materials": shared, "safety": safety_hits}
