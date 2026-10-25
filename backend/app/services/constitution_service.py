# -*- coding: utf-8 -*-
"""
CCMQ 体质测评服务模块：
- 58 题量表（按维度分组，平和质逆向计分标记）
- 转化分计算与判定（ZYYXH/T157-2009 规则）
- 体质 → 方子推荐（适宜体质匹配 + 忌口排除）
被 routers/constitution.py 和 routers/recipes.py 复用
"""
import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "shiyang.db"
CONSTITUTION_JSON = Path(__file__).resolve().parents[3] / "data" / "recipes_raw" / "constitution.json"

_data = None

def _load():
    global _data
    if _data is None:
        _data = json.loads(CONSTITUTION_JSON.read_text(encoding="utf-8"))
    return _data

# 平和质需逆向计分的反向表述题（题干含这些关键词的反向题）
# 采录版平和质全部为正向题外的反向题，标准版中平和质部分条目逆向计分。
# 本版按采录页 scoring 说明："平和质带*条目逆向计分"，问卷网版未标星号，
# 故默认全正向计分，逆向条目留待标准原文核对时补。
REVERSE_ITEMS = set()


def get_questionnaire():
    """返回 {code: [题目...]} 与提示"""
    d = _load()
    items = d["questionnaire"]["items"]
    return items, d.get("questionnaire_note", "")


def calc_transformed(answers: dict) -> dict:
    """
    answers: {维度code: [每题1-5分...]}，顺序与 get_questionnaire() 的题目一致
    返回 {code: 转化分(0-100)}
    """
    items, _ = get_questionnaire()
    result = {}
    for code, qs in items.items():
        scores = answers.get(code)
        if not scores or len(scores) != len(qs):
            raise ValueError(f"维度 {code} 需要 {len(qs)} 题的答案")
        raw = sum(scores)
        n = len(qs)
        transformed = (raw - n) / (n * 4) * 100
        result[code] = round(max(0.0, min(100.0, transformed)), 1)
    return result


def judge(transformed: dict) -> dict:
    """
    判定规则（ZYYXH/T157-2009）：
    偏颇体质：转化分≥40 '是'，30-39 '倾向是'，<30 '否'
    平和质：≥60 且其余8种均<30 → '是'；≥60 且其余均<40 → '基本是'；否则 '否'
    返回 {code: {score, result}}，附兼夹列表
    """
    results = {}
    for code, score in transformed.items():
        if code == "pinghe":
            others = [s for c, s in transformed.items() if c != "pinghe"]
            if score >= 60 and all(s < 30 for s in others):
                r = "是"
            elif score >= 60 and all(s < 40 for s in others):
                r = "基本是"
            else:
                r = "否"
        else:
            if score >= 40:
                r = "是"
            elif score >= 30:
                r = "倾向是"
            else:
                r = "否"
        results[code] = {"score": score, "result": r}
    combined = [c for c, v in results.items() if c != "pinghe" and v["result"] == "是"]
    return {"results": results, "main": combined[0] if len(combined) == 1 else None,
            "combined": combined}


NAME_BY_CODE = {"pinghe": "平和质", "qixu": "气虚质", "yangxu": "阳虚质", "yinxu": "阴虚质",
                "tanshi": "痰湿质", "shire": "湿热质", "xueyu": "血瘀质", "qiyu": "气郁质", "tebing": "特禀质"}
SHORT_NAME = {c: n.replace("质", "") for c, n in NAME_BY_CODE.items()}


def recommend_recipes(judged: dict, limit: int = 6) -> list:
    """按判定结果推荐方子：主+兼夹体质的适宜方，排除不宜方"""
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    try:
        codes = set(judged["combined"]) | ({judged["main"]} if judged["main"] else set())
        # 倾向体质也纳入弱推荐
        for c, v in judged["results"].items():
            if v["result"] == "倾向是":
                codes.add(c)
        codes_short = json.dumps(list(codes), ensure_ascii=False)  # 不用于SQL，下面用参数
        rows = conn.execute(
            "SELECT id, name, type, oneliner, scenes, constitutions_suitable, constitutions_unsuitable "
            "FROM recipe WHERE status != '弃用'").fetchall()
        scored = []
        for rid, name, rtype, oneliner, scenes, suit, unsuit in rows:
            try:
                suit_l = json.loads(suit or "[]")
                unsuit_l = json.loads(unsuit or "[]")
                scenes_l = json.loads(scenes or "[]")
            except json.JSONDecodeError:
                continue
            # 命中不宜 → 排除
            if any(SHORT_NAME.get(c) in unsuit_l for c in codes):
                continue
            hit = [SHORT_NAME[c] for c in codes if SHORT_NAME.get(c) in suit_l]
            if hit:
                scored.append({"score": len(hit), "id": rid, "name": name, "type": rtype,
                               "oneliner": oneliner, "scenes": scenes_l,
                               "matched_constitutions": hit})
        scored.sort(key=lambda x: -x["score"])
        return scored[:limit]
    finally:
        conn.close()


def constitution_detail(code: str) -> dict | None:
    """体质详情（典型表现/宜忌/茶饮思路/生活建议）"""
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    try:
        row = conn.execute(
            "SELECT name, typical_signs, principle, foods_suitable, foods_avoid, tea_ideas, lifestyle, reference_url "
            "FROM constitution WHERE code=?", (code,)).fetchone()
        if not row:
            return None
        keys = ["typical_signs", "foods_suitable", "foods_avoid", "tea_ideas", "lifestyle"]
        out = {"code": code, "name": row[0], "typical_signs": json.loads(row[1] or "[]"),
               "principle": row[2], "reference_url": row[7]}
        for k, v in zip(keys[1:], row[3:8]):
            try:
                out[k] = json.loads(v or "[]")
            except json.JSONDecodeError:
                out[k] = []
        return out
    finally:
        conn.close()
