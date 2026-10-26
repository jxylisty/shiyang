# -*- coding: utf-8 -*-
"""
节气/季节推荐服务（T2-9）
- 节气日期：寿星通用公式（万年历算法，1900-2100 精度 ±1 天内，展示用途足够）
- 每个节气配食养主题（场景标签 + 体质倾向），联动方子库推荐
- 换季场景：立春/立夏/立秋/立冬 前后 15 天推荐「换季调理」
"""
import datetime as dt
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "shiyang.db"

# 二十四节气名（从立春起）
TERMS = ["立春", "雨水", "惊蛰", "春分", "清明", "谷雨",
         "立夏", "小满", "芒种", "夏至", "小暑", "大暑",
         "立秋", "处暑", "白露", "秋分", "寒露", "霜降",
         "立冬", "小雪", "大雪", "冬至", "小寒", "大寒"]

# 节气 → 食养主题：scene 联动方子库场景标签；suit 联动体质名；tip 一句话
THEMES = {
    "立春": {"scene": "换季调理", "tip": "阳气初生，宜温和升发，少酸增甘"},
    "雨水": {"scene": "换季调理", "tip": "湿气渐起，健脾祛湿正当时"},
    "惊蛰": {"scene": "情绪舒压", "tip": "肝气升发，注意疏肝理气"},
    "春分": {"scene": "熬夜护眼", "tip": "昼夜均分，养肝明目好时节"},
    "清明": {"scene": "情绪舒压", "tip": "踏青疏郁，顺时舒压"},
    "谷雨": {"scene": "换季调理", "tip": "雨湿渐重，脾胃为先"},
    "立夏": {"scene": "换季调理", "tip": "心火渐旺，清心养神"},
    "小满": {"scene": "控油祛痘", "tip": "湿热渐盛，清淡利湿"},
    "芒种": {"scene": "消化", "tip": "暑湿困脾，醒脾开胃"},
    "夏至": {"scene": "控油祛痘", "tip": "阳极阴生，清热不忘护脾胃"},
    "小暑": {"scene": "控油祛痘", "tip": "盛夏湿热，清暑利湿"},
    "大暑": {"scene": "控油祛痘", "tip": "一年最热，防暑祛湿并重"},
    "立秋": {"scene": "换季调理", "tip": "秋燥将至，润肺生津开始"},
    "处暑": {"scene": "护嗓润喉", "tip": "暑气渐退，咽干初起要润养"},
    "白露": {"scene": "护嗓润喉", "tip": "阴气渐重，温润防燥"},
    "秋分": {"scene": "护嗓润喉", "tip": "燥气当令，滋阴润燥"},
    "寒露": {"scene": "熬夜护眼", "tip": "深秋干燥，护眼润燥两手抓"},
    "霜降": {"scene": "换季调理", "tip": "秋末进补，平补为宜"},
    "立冬": {"scene": "换季调理", "tip": "闭藏之始，温润进补"},
    "小雪": {"scene": "情绪舒压", "tip": "日照渐短，防郁宽心"},
    "大雪": {"scene": "助眠", "tip": "长夜漫漫，安神助眠"},
    "冬至": {"scene": "助眠", "tip": "一阳来复，早睡养藏"},
    "小寒": {"scene": "经期温养", "tip": "天寒地冻，温阳驱寒"},
    "大寒": {"scene": "换季调理", "tip": "寒极将春，温养迎新"},
}


def _term_day(year: int, n: int) -> dt.date:
    """TERMS 序 n（0=立春…23=大寒）的日期。寿星通用公式（C 表按小寒起的时间序）。

    C 表时间序：0=小寒 1=大寒 2=立春 3=雨水 … 23=冬至。
    TERMS[k]（立春起）→ 表序 (k+2)%24；表序 22/23（小寒/大寒）历法上落在「次年 1 月」，
    由调用方 current_term 按实际日期排序归位，这里直接返回 (year+1, 1, day)。
    """
    century = 21 if year >= 2000 else 20
    C21 = [5.4055, 20.12, 3.87, 18.73, 5.63, 20.646, 4.81, 20.1, 5.52, 21.04,
           5.678, 21.37, 7.108, 22.83, 7.5, 23.13, 7.646, 23.042, 8.318, 23.0,
           7.9, 22.7, 7.648, 22.62]
    C20 = [6.11, 20.84, 4.6295, 19.4599, 6.3826, 21.4155, 5.59, 20.888, 6.318, 21.86,
           6.5, 22.2, 7.928, 23.656, 8.35, 23.95, 8.44, 23.822, 9.098, 24.218, 8.718,
           23.7, 8.4312, 23.3545]
    table_n = (n + 2) % 24
    C = (C21 if century == 21 else C20)[table_n]
    y = year % 100
    day = int(y * 0.2422 + C) - int(y / 4)
    if century == 20:
        day += 1  # 20 世纪修正
    if table_n in (0, 1):       # 小寒/大寒 → 次年 1 月
        month, real_year = 1, year + 1
    else:
        month, real_year = table_n // 2 + 1, year
    try:
        return dt.date(real_year, month, day)
    except ValueError:          # 闰年 2 月 29 边界兜底
        return dt.date(real_year, month, min(day, 28))


def current_term(today: dt.date | None = None) -> dict:
    """当前节气 + 未来两个节气（跨年处理）"""
    today = today or dt.date.today()
    year = today.year
    all_terms = []
    for y in (year - 1, year, year + 1):
        for i, name in enumerate(TERMS):
            d = _term_day(y, i)
            all_terms.append({"name": name, "date": d.isoformat(),
                              "theme": THEMES[name]})
    all_terms.sort(key=lambda x: x["date"])
    cur_idx = 0
    for i, t in enumerate(all_terms):
        if dt.date.fromisoformat(t["date"]) <= today:
            cur_idx = i
    upcoming = all_terms[cur_idx + 1:cur_idx + 3]
    cur = dict(all_terms[cur_idx])
    days_in = (today - dt.date.fromisoformat(cur["date"])).days
    next_in = (dt.date.fromisoformat(upcoming[0]["date"]) - today).days if upcoming else None
    cur["days_in"] = days_in
    return {"current": cur, "upcoming": upcoming, "next_in_days": next_in,
            "today": today.isoformat()}


def _db():
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def recommend(rid_count: int = 4) -> dict:
    """当前节气主题下的方子推荐（按节气场景标签筛选）"""
    info = current_term()
    scene = info["current"]["theme"]["scene"]
    conn = _db()
    try:
        rows = conn.execute(
            "SELECT id,name,type,oneliner,scenes,constitutions_suitable FROM recipe "
            "WHERE status != '弃用' AND scenes LIKE ? ORDER BY analysis_ready DESC, id LIMIT ?",
            (f'%{scene}%', rid_count)).fetchall()
        # 封面用首味配料（与方子列表同口径），一次查询取每方最小 id 的配料名
        first_mat = {}
        if rows:
            ph = ",".join("?" * len(rows))
            for m in conn.execute(
                    f"SELECT recipe_id, name FROM rel_recipe_material "
                    f"WHERE recipe_id IN ({ph}) AND id IN "
                    f"(SELECT MIN(id) FROM rel_recipe_material WHERE recipe_id IN ({ph}) GROUP BY recipe_id)",
                    [r["id"] for r in rows] * 2).fetchall():
                first_mat[m["recipe_id"]] = m["name"]
    finally:
        conn.close()
    items = []
    for r in rows:
        scenes = json.loads(r["scenes"] or "[]")
        if scene in scenes:
            items.append({"id": r["id"], "name": r["name"], "type": r["type"],
                          "oneliner": r["oneliner"], "scenes": scenes,
                          "constitutions_suitable": json.loads(r["constitutions_suitable"] or "[]"),
                          "materials": [first_mat[r["id"]]] if r["id"] in first_mat else []})
    info["scene"] = scene
    info["recipes"] = items
    return info
