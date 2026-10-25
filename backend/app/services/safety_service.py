# -*- coding: utf-8 -*-
"""
慢病/特殊人群安全滤镜（T1-5）
对任一方子按人群档案做配料禁忌检查：
- block：含明确禁忌配料（如孕妇 × 番泻叶），前端置灰并说明
- warn ：配料功效提示需要注意（如高血压 × 甘草久服），前端黄条提醒
- pass ：无提示

数据来源：
1) herb.contraindication / food.contraindication 字段全文关键词匹配
2) 内置人群档案关键词表（药典/指南通识，保守起见提示级别为 warn）
"""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "shiyang.db"

# 人群档案：code → {name, desc, block_kw(配料名精确/包含), warn_kw(功效或禁忌文本关键词)}
PROFILES = {
    "diabetes": {
        "name": "控糖期",
        "desc": "糖尿病/血糖偏高人群",
        # 蜂蜜冰糖升糖快；大枣含糖高提示
        "block_kw": ["蜂蜜", "冰糖", "红糖", "饴糖"],
        "warn_kw": ["大枣", "桂圆", "龙眼", "血糖", "糖尿"],
    },
    "hypertension": {
        "name": "高血压",
        "desc": "血压偏高/服降压药人群",
        # 甘草可致水钠潴留、血压升高（药典提示）；人参类与降压药相互作用
        "block_kw": [],
        "warn_kw": ["甘草", "人参", "血压", "高血压"],
    },
    "pregnant": {
        "name": "孕期",
        "desc": "怀孕期人群（最保守）",
        # 活血/峻下/通窍类：药典孕妇禁用慎用名单常见项
        "block_kw": ["番泻叶", "芦荟", "藏红花", "红花", "桃仁", "山楂", "薏苡仁", "薏米",
                     "麦芽", "决明子", "肉桂", "牡丹皮", "玫瑰花", "益母草", "枳椇子"],
        "warn_kw": ["孕妇", "妊娠", "活血", "滑胎"],
    },
    "lactation": {
        "name": "哺乳期",
        "desc": "母乳喂养人群",
        # 麦芽回乳；浓茶咖啡因；薄荷可能减少泌乳
        "block_kw": ["麦芽"],
        "warn_kw": ["哺乳", "回乳", "咖啡因", "茶叶", "薄荷"],
    },
    "children": {
        "name": "儿童",
        "desc": "12 岁以下（减量+部分药材不宜）",
        "block_kw": ["人参", "西洋参", "三七", "藏红花", "番泻叶"],
        "warn_kw": ["儿童", "婴幼儿", "小儿不宜"],
    },
}


def _db():
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def check_recipe(rid: int, profile: str) -> dict | None:
    """单方检查；方子不存在返回 None"""
    p = PROFILES.get(profile)
    if not p:
        return None
    conn = _db()
    try:
        r = conn.execute("SELECT id,name FROM recipe WHERE id=?", (rid,)).fetchone()
        if not r:
            return None
        mats = conn.execute(
            "SELECT m.name, m.note, h.functions, h.contraindication, f.functions AS f_functions, "
            "f.contraindication AS f_contra "
            "FROM rel_recipe_material m "
            "LEFT JOIN herb h ON h.id=m.herb_id "
            "LEFT JOIN food f ON f.id=m.food_id WHERE m.recipe_id=?", (rid,)).fetchall()
    finally:
        conn.close()

    blocks, warns = [], []
    for m in mats:
        name = m["name"] or ""
        text = " ".join(filter(None, [m["note"], m["functions"], m["f_functions"],
                                      m["contraindication"], m["f_contra"]]))
        hit_block = next((kw for kw in p["block_kw"] if kw in name), None)
        if hit_block:
            blocks.append({"material": name, "reason": f"{p['name']}人群不建议 {hit_block}"})
            continue
        hit_warn_kw = next((kw for kw in p["warn_kw"] if kw in name), None)
        hit_text = next((kw for kw in p["warn_kw"] if kw in text), None)
        if hit_warn_kw:
            warns.append({"material": name, "reason": f"含 {hit_warn_kw}，{p['name']}人群请咨询医生后使用"})
        elif hit_text:
            frag_idx = text.find(hit_text)
            frag = text[max(0, frag_idx - 18):frag_idx + 24].strip()
            warns.append({"material": name, "reason": f"资料提示「…{frag}…」，{p['name']}人群注意"})

    verdict = "block" if blocks else ("warn" if warns else "pass")
    return {"recipe_id": rid, "recipe_name": r["name"], "profile": profile,
            "profile_name": p["name"], "verdict": verdict, "blocks": blocks, "warns": warns}


def filter_recipes(profile: str, rids: list[int]) -> dict:
    """批量检查（方子库列表页用）"""
    out = {}
    for rid in rids:
        r = check_recipe(rid, profile)
        if r:
            out[rid] = r
    return {"profile": profile, "profile_name": PROFILES[profile]["name"], "results": out}


def _profile_summaries():
    return [{"code": k, "name": v["name"], "desc": v["desc"]} for k, v in PROFILES.items()]
