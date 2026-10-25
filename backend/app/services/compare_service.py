# -*- coding: utf-8 -*-
"""
对比实验室服务：两个方子并排对比——成分覆盖、入血化合物重叠度、靶点/通路差异、体质适宜对照
数据全部来自 shiyang.db 只读查询，复用 recipe_analysis 预生成结果
"""
import json
import sqlite3
from pathlib import Path

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
    if a:
        a = dict(a)
        a["top_compounds"] = json.loads(a["top_compounds"] or "null") or []
        a["top_targets"] = json.loads(a["top_targets"] or "null") or []
        a["radar_summary"] = json.loads(a["radar_summary"] or "null") or {}
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

        # ---- 雷达（三通路强度）----
        ra = a["analysis"]["radar_summary"] if a["analysis"] else {}
        rb = b["analysis"]["radar_summary"] if b["analysis"] else {}

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
                "dims": ["anti_inflammatory", "immune_regulation", "airway_repair"],
                "a": [ra.get(d) for d in ("anti_inflammatory", "immune_regulation", "airway_repair")],
                "b": [rb.get(d) for d in ("anti_inflammatory", "immune_regulation", "airway_repair")],
            },
            "constitution": {
                "both_suitable": sorted(set(a["constitutions_suitable"]) & set(b["constitutions_suitable"])),
                "a_only": sorted(set(a["constitutions_suitable"]) - set(b["constitutions_suitable"])),
                "b_only": sorted(set(b["constitutions_suitable"]) - set(a["constitutions_suitable"])),
                "warn_a": sorted(set(a["constitutions_unsuitable"]) & set(b["constitutions_suitable"])),
                "warn_b": sorted(set(b["constitutions_unsuitable"]) & set(a["constitutions_suitable"])),
            },
        }
    finally:
        conn.close()
