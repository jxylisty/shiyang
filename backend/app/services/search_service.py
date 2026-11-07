# -*- coding: utf-8 -*-
"""
全局搜索服务：一次关键词聚合查三类实体（方子/药材/成分），各取前 5 条
- 数据型产品基本功：顶栏统一入口，替代三页各自的局部搜索
- SQL 全部参数化 LIKE；q 为空或去空白后为空返回空分组
- 搜索域：方子=名称/一句话/场景/配料名；药材=名称/拼音/别名/功效；成分=名称
  命中来源以 matched_by 标注（如「配料含枸杞」「别名」），让用户知道为什么出这条
"""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "shiyang.db"

LIMIT = 5  # 顶栏下拉默认每类条数；端点可传 limit 覆盖（独立搜索页用大值）

# 疾病/症状口语 → 库内可命中的检索词（多角色试用实测：搜「高血压」「糖尿病」「降压」
# 全部零结果，而这是慢病人群最自然的输入）。映射遵循「只做检索扩展，不做医学判断」：
# 命中的方子由既有 safety_service / scenes 标签决定是否提示禁忌，不因本表放宽任何安全口径。
# 依据：药食同源安全通识与常见中医证型用语，属编辑性检索规则，非实验数据。
QUERY_EXPANSION = {
    # 心血管
    "高血压": ["血压", "平肝", "决明子", "菊花", "山楂", "芹菜"],
    "降压": ["血压", "平肝", "决明子", "菊花"],
    "血压高": ["血压", "平肝", "决明子", "菊花"],
    "血脂": ["降脂", "山楂", "决明子", "荷叶", "消脂", "轻身"],
    "高血脂": ["降脂", "山楂", "决明子", "荷叶", "消脂", "轻身"],
    "降脂": ["降脂", "山楂", "决明子", "荷叶", "轻身"],
    # 代谢
    "糖尿病": ["控糖", "血糖", "低糖", "桑叶", "玉竹", "麦冬"],
    "血糖高": ["控糖", "血糖", "低糖", "桑叶"],
    "控糖": ["控糖", "血糖", "桑叶", "玉竹"],
    # 睡眠
    "睡不着": ["助眠", "安神", "失眠", "酸枣仁", "百合", "莲子"],
    "失眠": ["助眠", "安神", "失眠", "酸枣仁", "百合", "莲子"],
    "睡不好": ["助眠", "安神", "失眠", "酸枣仁"],
    "多梦": ["助眠", "安神", "失眠", "酸枣仁"],
    # 消化
    "胃不好": ["健脾", "养胃", "消化", "陈皮", "茯苓", "山药"],
    "胃胀": ["健脾", "消化", "行气", "陈皮", "山楂"],
    "消化不良": ["健脾", "消化", "山楂", "陈皮"],
    "便秘": ["通便", "决明子", "火麻仁", "润肠"],
    # 咽喉/呼吸
    "嗓子疼": ["护嗓", "利咽", "咽干", "金银花", "菊花", "薄荷"],
    "咽炎": ["护嗓", "利咽", "咽干", "金银花", "麦冬"],
    "咳嗽": ["润肺", "止咳", "百合", "麦冬", "川贝"],
    # 其他常见
    "上火": ["清热", "降火", "菊花", "金银花", "绿豆"],
    "湿气": ["祛湿", "健脾", "薏苡仁", "茯苓", "赤小豆"],
    "怕冷": ["温阳", "暖身", "生姜", "桂圆", "红枣"],
    "痛经": ["经期", "温养", "红糖", "生姜", "玫瑰花"],
    "眼干": ["护眼", "明目", "枸杞", "菊花", "决明子"],
    "熬夜": ["护眼", "养阴", "枸杞", "菊花"],
}


def expand_queries(q: str) -> list:
    """把用户口语词扩展成若干检索词（原词优先，最多 4 个）。"""
    q = (q or "").strip()
    if not q:
        return []
    extra = []
    for key, syns in QUERY_EXPANSION.items():
        if key in q or q in key:
            extra.extend(syns)
    seen = {q}
    out = [q]
    for s in extra:
        if s not in seen:
            seen.add(s)
            out.append(s)
        if len(out) >= 4:
            break
    return out


def _db():
    conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _search_recipes(conn, q: str, kw: str, limit: int = LIMIT) -> list:
    """方子按 名称/一句话/场景/配料名 匹配，标注 matched_by"""
    rows = conn.execute(
        "SELECT id,name,type,oneliner,scenes,constitutions_suitable FROM recipe "
        "WHERE status != '弃用' AND (name LIKE ? OR oneliner LIKE ? OR scenes LIKE ? "
        "OR id IN (SELECT recipe_id FROM rel_recipe_material WHERE name LIKE ?)) "
        "ORDER BY analysis_ready DESC, id LIMIT ?",
        (kw, kw, kw, kw, limit)).fetchall()
    out = []
    for r in rows:
        matched = []
        if q in (r["name"] or ""):
            matched.append("名称")
        if q in (r["oneliner"] or ""):
            matched.append("简介")
        if q in (r["scenes"] or ""):
            scenes = r["scenes"] or ""
            hit = [s for s in scenes.replace("[", ",").replace("]", ",").replace('"', ",").split(",") if s.strip() and q in s]
            if hit:
                matched.append(f"场景·{hit[0]}")
        if not matched:
            mat = conn.execute(
                "SELECT name FROM rel_recipe_material WHERE recipe_id=? AND name LIKE ? "
                "ORDER BY id LIMIT 1", (r["id"], kw)).fetchone()
            if mat:
                matched.append(f"配料含{mat['name']}")
        out.append({**dict(r), "matched_by": "、".join(matched) if matched else ""})
    return out


def _search_herbs(conn, q: str, kw: str, limit: int = LIMIT) -> list:
    """药材按 名称/拼音/别名/功效 匹配，标注 matched_by"""
    rows = conn.execute(
        "SELECT id,name,category,nature,flavor,functions,compound_count,alias "
        "FROM herb WHERE name LIKE ? OR pinyin LIKE ? OR alias LIKE ? OR functions LIKE ? "
        "ORDER BY compound_count DESC LIMIT ?",
        (kw, f"{q}%", kw, kw, limit)).fetchall()
    out = []
    for r in rows:
        matched = []
        if q in (r["name"] or ""):
            matched.append("名称")
        else:
            # 别名/功效是「、」或「，」分隔的词串，按词命中才标注具体词
            fields = (r["alias"] or "") + "、" + (r["functions"] or "")
            parts = [p.strip() for p in fields.replace("，", "、").split("、") if p.strip()]
            hit = next((p for p in parts if q in p), None)
            if hit and hit in (r["alias"] or ""):
                matched.append(f"别名·{hit}")
            elif hit:
                matched.append(f"功效·{hit}")
        out.append({**dict(r), "matched_by": "、".join(matched)})
    return out


def global_search(q: str, limit: int = LIMIT) -> dict:
    q = (q or "").strip()
    empty = {"query": q, "recipes": [], "herbs": [], "compounds": []}
    if not q:
        return empty
    # 原词命中优先；原词零结果时用同义/口语扩展词再检索一次（扩展命中会在 expanded_from 标注）
    terms = expand_queries(q)
    conn = _db()
    try:
        recipes, herbs, compounds = [], [], []
        used_term = None
        for term in terms:
            kw = f"%{term}%"
            r_ = _search_recipes(conn, term, kw, limit)
            h_ = _search_herbs(conn, term, kw, limit)
            c_ = conn.execute(
                "SELECT id,name,mw,logp,prob_cctcm,target_count "
                "FROM compound WHERE name LIKE ? AND prob_cctcm IS NOT NULL "
                "ORDER BY prob_cctcm DESC LIMIT ?",
                (kw, limit)).fetchall()
            if term == q or r_ or h_ or c_:
                recipes, herbs, compounds = r_, h_, c_
                used_term = term
            if recipes or herbs or compounds:
                break
    finally:
        conn.close()
    out = {
        "query": q,
        "recipes": recipes,
        "herbs": herbs,
        "compounds": [dict(c) for c in compounds],
    }
    # 命中来自扩展词时如实告知，避免用户以为库里直接有「高血压」这个方子
    if used_term and used_term != q:
        out["expanded_from"] = used_term
        out["note"] = f"未找到「{q}」的直接结果，以下为按「{used_term}」等食养场景词检索到的参考"
    return out
