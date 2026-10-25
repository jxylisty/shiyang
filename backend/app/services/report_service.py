# -*- coding: utf-8 -*-
"""
21 天食养周期报告服务（T2-7）
聚合用户的打卡与体质档案：
- 周期概览：打卡天数/连续天数/喝过的方子数
- 成分覆盖：周期内喝过方子的 top 成分去重集合 + 高入血数
- 靶点覆盖：去重靶点 + 出现频次 top
- 场景分布：各场景打卡次数
- 体质曲线：周期内体质档案的转化分变化（如有 ≥2 次测评）
"""
import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path

from services import user_service as us

SHIYANG_DB = Path(__file__).resolve().parents[3] / "data" / "shiyang.db"


def _sdb():
    conn = sqlite3.connect(f"file:{SHIYANG_DB.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def build_report(uid: int, days: int = 21) -> dict:
    since = (date.today() - timedelta(days=days - 1)).isoformat()

    # ---- 打卡数据（user.db）----
    uconn = us.db()
    try:
        ck_rows = uconn.execute(
            "SELECT recipe_id, day FROM checkin WHERE user_id=? AND day>=? ORDER BY day",
            (uid, since)).fetchall()
        rec_rows = uconn.execute(
            "SELECT main_code, main_name, combined, transformed, created_at "
            "FROM constitution_record WHERE user_id=? AND created_at>=? ORDER BY id",
            (uid, since)).fetchall()
    finally:
        uconn.close()

    records = [dict(r) for r in ck_rows]
    day_set = {r["day"] for r in records}
    streak = us._streak(day_set)
    rids = sorted({r["recipe_id"] for r in records})

    # ---- 方子成分/场景（shiyang.db 只读）----
    conn = _sdb()
    try:
        recipe_names, scenes_hist, comp_seen, hi_set, target_hist = {}, {}, set(), set(), {}
        if rids:
            ph = ",".join("?" * len(rids))
            for row in conn.execute(
                    f"SELECT id,name,scenes FROM recipe WHERE id IN ({ph})", rids):
                recipe_names[row["id"]] = row["name"]
                for s in json.loads(row["scenes"] or "[]"):
                    scenes_hist[s] = scenes_hist.get(s, 0) + 1
            for row in conn.execute(
                    f"SELECT top_compounds, top_targets FROM recipe_analysis WHERE recipe_id IN ({ph})", rids):
                for c in json.loads(row["top_compounds"] or "[]"):
                    comp_seen.add(c["name"])
                    if (c.get("prob_cctcm") or 0) >= 0.7:
                        hi_set.add(c["name"])
                for t in json.loads(row["top_targets"] or "[]"):
                    target_hist[t["gene"]] = target_hist.get(t["gene"], 0) + 1
    finally:
        conn.close()

    top_targets = sorted(target_hist.items(), key=lambda x: -x[1])[:10]

    # ---- 体质曲线（周期内测评的转化分）----
    constitution_curve = []
    for r in rec_rows:
        tf = json.loads(r["transformed"] or "{}")
        constitution_curve.append({
            "date": r["created_at"][:10],
            "main_code": r["main_code"], "main_name": r["main_name"],
            "top3": sorted(tf.items(), key=lambda x: -x[1])[:3],
        })

    # ---- 周期格视图（前端打卡墙）----
    wall = []
    by_day = {}
    for r in records:
        by_day.setdefault(r["day"], []).append(r["recipe_id"])
    for i in range(days):
        d = (date.today() - timedelta(days=days - 1 - i)).isoformat()
        wall.append({"day": d, "count": len(by_day.get(d, [])), "today": d == date.today().isoformat()})

    return {
        "period_days": days, "since": since,
        "checkin_days": len(day_set), "streak": streak, "recipes_tried": len(rids),
        "recipe_names": [recipe_names.get(r, f"#{r}") for r in rids],
        "compounds_covered": len(comp_seen),
        "hi_blood_covered": sorted(hi_set),
        "targets_covered": len(target_hist),
        "top_targets": [{"gene": g, "hits": n} for g, n in top_targets],
        "scenes_hist": sorted(scenes_hist.items(), key=lambda x: -x[1]),
        "constitution_curve": constitution_curve,
        "wall": wall,
        "note": "成分/靶点覆盖按方子预生成分析聚合（Top 成分口径）；报告为饮用记录的参考汇总，不构成功效评价。",
    }
