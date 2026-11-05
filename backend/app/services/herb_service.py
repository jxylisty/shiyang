# -*- coding: utf-8 -*-
"""
HERB 数据库封装（herb.ac.cn）
用于「自定义茶罐」功能：用户输入任意药材，从 HERB 拉取成分/靶点/功效数据。

设计要点：
- 搜索走精确匹配优先（中文名 == 用户输入），否则取搜索结果第一条
- 详情只缓存关键字段，不存完整 600KB+ 返回
- 缓存存在 user.db 的 herb_cache 表，TTL 30 天（HERB 数据几乎不变）
- 失败兜底：返回 not_found 状态，不抛异常，前端展示"未找到"
- 所有网络请求都有超时（15s），避免卡住

数据许可：HERB 为 CC BY-NC 4.0，非商业用途可用（大创项目符合）。
若未来商业化须换源或取得授权。
"""
import json
import sqlite3
import time
from pathlib import Path

import requests

from services import user_service as us

HERB_API = "http://herb.ac.cn/chedi/api/"
HTTP_TIMEOUT = 15  # 秒
CACHE_TTL_DAYS = 30  # 缓存有效期：30 天
MAX_INGREDIENTS = 50  # 详情返回前 N 个成分（按相关性排序，HERB 返回本身就是按相关性的）
MAX_TARGETS = 30  # 详情返回前 N 个靶点
MAX_DISEASES = 30  # 详情返回前 N 个疾病


def _db():
    """拿 user.db 连接（缓存表放这，shiyang.db 是只读的）"""
    return us.db()


def _ensure_cache_table():
    """保证 herb_cache 表存在（幂等，每次调用检查）"""
    conn = _db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS herb_cache (
                herb_name TEXT PRIMARY KEY,         -- 用户输入的中文名
                herb_id TEXT,                       -- HERB ID，如 HERB002962
                pinyin TEXT,                        -- 拼音
                latin_name TEXT,                    -- 拉丁名
                properties TEXT,                    -- 性味（英文）
                meridians TEXT,                     -- 归经（英文）
                function_en TEXT,                   -- 功效（英文直译）
                indication_en TEXT,                 -- 主治（英文直译）
                ingredients TEXT,                   -- JSON: [{id, name, alias}] 前 N 个
                targets TEXT,                       -- JSON: [{id, name, p_value, fdr}] 前 N 个
                diseases TEXT,                      -- JSON: [{id, name, p_value, fdr}] 前 N 个
                ingredient_count INTEGER,           -- 总成分数
                target_count INTEGER,               -- 总靶点数
                disease_count INTEGER,              -- 总疾病数
                cached_at REAL                      -- 缓存时间戳
            )
        """)
        conn.commit()
    finally:
        conn.close()


# 启动时建表（幂等）
_ensure_cache_table()


def _cache_get(herb_name: str) -> dict | None:
    """从缓存读，过期返回 None"""
    conn = _db()
    try:
        row = conn.execute(
            "SELECT * FROM herb_cache WHERE herb_name = ?", (herb_name,)).fetchone()
        if not row:
            return None
        age_days = (time.time() - row["cached_at"]) / 86400
        if age_days > CACHE_TTL_DAYS:
            return None
        d = dict(row)
        # JSON 字段解析
        for k in ("ingredients", "targets", "diseases"):
            d[k] = json.loads(d[k] or "[]")
        return d
    finally:
        conn.close()


def _cache_put(data: dict) -> None:
    """写入缓存（INSERT OR REPLACE）"""
    conn = _db()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO herb_cache
            (herb_name, herb_id, pinyin, latin_name, properties, meridians,
             function_en, indication_en, ingredients, targets, diseases,
             ingredient_count, target_count, disease_count, cached_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            data["herb_name"], data["herb_id"], data["pinyin"], data["latin_name"],
            data["properties"], data["meridians"],
            data["function_en"], data["indication_en"],
            json.dumps(data["ingredients"], ensure_ascii=False),
            json.dumps(data["targets"], ensure_ascii=False),
            json.dumps(data["diseases"], ensure_ascii=False),
            data["ingredient_count"], data["target_count"], data["disease_count"],
            time.time(),
        ))
        conn.commit()
    finally:
        conn.close()


def _herb_id_from_search(keyword: str) -> str | None:
    """调用 HERB search_api，返回最合适的 HERB ID。
    精确匹配（中文名 == 关键词）优先，否则取第一条。
    找不到返回 None。"""
    try:
        r = requests.post(HERB_API, json={
            "func_name": "search_api",
            "keyword": keyword,
            "label": "Herb",
        }, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return None

    rows = data.get("res_data", [])
    if not rows or len(rows) < 2:  # 只有表头
        return None

    results = rows[1:]  # 跳过表头行
    if not results:
        return None

    # 优先精确匹配中文名
    for row in results:
        if row[2] == keyword:
            cell = row[0]
            if isinstance(cell, dict):
                return cell.get("title")
            return cell

    # 否则取第一条
    cell = results[0][0]
    if isinstance(cell, dict):
        return cell.get("title")
    return cell


def _parse_link_cell(cell):
    """HERB 返回的第一列经常是 {"link":..., "title":...} 格式，也可能是纯字符串"""
    if isinstance(cell, dict):
        return cell.get("title", ""), cell.get("link", "")
    return str(cell), ""


def search_herb(keyword: str) -> dict:
    """搜索药材，返回结构化结果（优先读缓存，缓存 miss 才打 API）。

    返回：
    {
      "status": "ok" | "not_found" | "error",
      "herb_name": str,        # 用户输入名
      "herb_id": str | None,   # HERB ID
      "name_cn": str | None,   # 中文名（实际匹配到的）
      "pinyin": str | None,
      "latin_name": str | None,
      "from_cache": bool,
    }
    """
    keyword = (keyword or "").strip()
    if not keyword:
        return {"status": "error", "herb_name": keyword, "error": "关键词为空",
                "herb_id": None, "name_cn": None, "pinyin": None, "latin_name": None,
                "from_cache": False}

    # 先看缓存里有没有（有详情就算有，搜不到的也会缓存 not_found 结果）
    cached = _cache_get(keyword)
    if cached:
        return {
            "status": "ok" if cached.get("herb_id") else "not_found",
            "herb_name": keyword,
            "herb_id": cached.get("herb_id"),
            "name_cn": keyword,
            "pinyin": cached.get("pinyin"),
            "latin_name": cached.get("latin_name"),
            "from_cache": True,
        }

    # 调用搜索 API
    herb_id = _herb_id_from_search(keyword)
    if not herb_id:
        # 缓存 not_found 结果，避免每次都打请求
        _cache_put({
            "herb_name": keyword, "herb_id": None, "pinyin": None, "latin_name": None,
            "properties": None, "meridians": None,
            "function_en": None, "indication_en": None,
            "ingredients": [], "targets": [], "diseases": [],
            "ingredient_count": 0, "target_count": 0, "disease_count": 0,
        })
        return {
            "status": "not_found", "herb_name": keyword,
            "herb_id": None, "name_cn": None, "pinyin": None, "latin_name": None,
            "from_cache": False,
        }

    # 拿到 id 就可以，详情让 get_herb_detail 去拉
    # 这里再发一次请求拿中文名/拼音/拉丁名（搜索结果里有）
    s = None
    try:
        r = requests.post(HERB_API, json={
            "func_name": "search_api",
            "keyword": keyword,
            "label": "Herb",
        }, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        rows = r.json().get("res_data", [])[1:]
        for row in rows:
            _, _ = _parse_link_cell(row[0])
            if row[2] == keyword:
                s = row
                break
        if s is None and rows:
            s = rows[0]
    except Exception:
        s = None

    name_cn = keyword
    pinyin = None
    latin_name = None
    if s:
        pinyin = s[1]
        name_cn = s[2]
        # latin 是 dict 形式
        if isinstance(s[4], dict):
            latin_name = s[4].get("title")
        else:
            latin_name = s[4]

    return {
        "status": "ok",
        "herb_name": keyword,
        "herb_id": herb_id,
        "name_cn": name_cn,
        "pinyin": pinyin,
        "latin_name": latin_name,
        "from_cache": False,
    }


def get_herb_detail(keyword: str) -> dict:
    """获取药材详情（成分/靶点/疾病/功效）。
    优先读缓存，miss 则拉 API 并写缓存。

    返回：
    {
      "status": "ok" | "not_found" | "error",
      "herb_name": str,
      "herb_id": str | None,
      "name_cn": str | None,
      "pinyin": str | None,
      "latin_name": str | None,
      "properties": str | None,      # 性味（英文）
      "meridians": str | None,       # 归经（英文）
      "function_en": str | None,     # 功效（英文）
      "indication_en": str | None,   # 主治（英文）
      "ingredients": [...],          # 前 MAX_INGREDIENTS 个
      "targets": [...],              # 前 MAX_TARGETS 个
      "diseases": [...],             # 前 MAX_DISEASES 个
      "ingredient_count": int,
      "target_count": int,
      "disease_count": int,
      "from_cache": bool,
    }
    """
    keyword = (keyword or "").strip()
    if not keyword:
        return {"status": "error", "herb_name": keyword, "error": "关键词为空",
                "herb_id": None, "name_cn": None, "pinyin": None, "latin_name": None,
                "properties": None, "meridians": None,
                "function_en": None, "indication_en": None,
                "ingredients": [], "targets": [], "diseases": [],
                "ingredient_count": 0, "target_count": 0, "disease_count": 0,
                "from_cache": False}

    # 先查缓存
    cached = _cache_get(keyword)
    if cached:
        return {
            "status": "ok" if cached.get("herb_id") else "not_found",
            "herb_name": keyword,
            "herb_id": cached.get("herb_id"),
            "name_cn": keyword,
            "pinyin": cached.get("pinyin"),
            "latin_name": cached.get("latin_name"),
            "properties": cached.get("properties"),
            "meridians": cached.get("meridians"),
            "function_en": cached.get("function_en"),
            "indication_en": cached.get("indication_en"),
            "ingredients": cached.get("ingredients", []),
            "targets": cached.get("targets", []),
            "diseases": cached.get("diseases", []),
            "ingredient_count": cached.get("ingredient_count", 0),
            "target_count": cached.get("target_count", 0),
            "disease_count": cached.get("disease_count", 0),
            "from_cache": True,
        }

    # 1. 搜索拿 herb_id
    herb_id = _herb_id_from_search(keyword)
    if not herb_id:
        _cache_put({
            "herb_name": keyword, "herb_id": None, "pinyin": None, "latin_name": None,
            "properties": None, "meridians": None,
            "function_en": None, "indication_en": None,
            "ingredients": [], "targets": [], "diseases": [],
            "ingredient_count": 0, "target_count": 0, "disease_count": 0,
        })
        return {
            "status": "not_found", "herb_name": keyword,
            "herb_id": None, "name_cn": None, "pinyin": None, "latin_name": None,
            "properties": None, "meridians": None,
            "function_en": None, "indication_en": None,
            "ingredients": [], "targets": [], "diseases": [],
            "ingredient_count": 0, "target_count": 0, "disease_count": 0,
            "from_cache": False,
        }

    # 2. 拉详情
    try:
        r = requests.post(HERB_API, json={
            "func_name": "detail_api",
            "key_id": herb_id,
            "label": "Herb",
            "v": herb_id,
        }, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        d = r.json()
    except Exception as e:
        return {
            "status": "error", "herb_name": keyword, "error": str(e),
            "herb_id": herb_id, "name_cn": keyword,
            "pinyin": None, "latin_name": None,
            "properties": None, "meridians": None,
            "function_en": None, "indication_en": None,
            "ingredients": [], "targets": [], "diseases": [],
            "ingredient_count": 0, "target_count": 0, "disease_count": 0,
            "from_cache": False,
        }

    # 3. 解析
    summary_rows = d.get("summary", [])
    props = merid = func_en = indic_en = pinyin = latin = None
    name_cn = keyword
    if len(summary_rows) > 1:
        row = summary_rows[1]
        # 索引: 0=id, 1=pinyin, 2=cn name, 3=en name, 4=latin, 5=properties, 6=meridians,
        #       7=use part, 8=function, 9=indication, 10=clinical, 11=therapeutic, 12=therapeutic_cn, ...
        pinyin = row[1] if len(row) > 1 else None
        name_cn = row[2] if len(row) > 2 else keyword
        if isinstance(row[4], dict):
            latin = row[4].get("title")
        else:
            latin = row[4] if len(row) > 4 else None
        props = row[5] if len(row) > 5 else None
        merid = row[6] if len(row) > 6 else None
        func_en = row[8] if len(row) > 8 else None
        indic_en = row[9] if len(row) > 9 else None

    # 成分表
    ing_rows = d.get("herb_ingredient", [])[1:]  # 跳表头
    ingredients = []
    for row in ing_rows[:MAX_INGREDIENTS]:
        ing_id, _ = _parse_link_cell(row[0])
        ingredients.append({
            "id": ing_id,
            "name": row[1],
            "alias": row[2] if len(row) > 2 else "",
        })

    # 靶点表（P-value 已按显著性排序）
    tgt_rows = d.get("herb_target", [])[1:]
    targets = []
    for row in tgt_rows[:MAX_TARGETS]:
        tgt_id, _ = _parse_link_cell(row[0])
        targets.append({
            "id": tgt_id,
            "name": row[1],
            "p_value": row[2] if len(row) > 2 else None,
            "fdr": row[3] if len(row) > 3 else None,
        })

    # 疾病表
    dis_rows = d.get("herb_disease", [])[1:]
    diseases = []
    for row in dis_rows[:MAX_DISEASES]:
        dis_id, _ = _parse_link_cell(row[0])
        diseases.append({
            "id": dis_id,
            "name": row[1],
            "p_value": row[2] if len(row) > 2 else None,
            "fdr": row[3] if len(row) > 3 else None,
        })

    result = {
        "herb_name": keyword,
        "herb_id": herb_id,
        "name_cn": name_cn,
        "pinyin": pinyin,
        "latin_name": latin,
        "properties": props,
        "meridians": merid,
        "function_en": func_en,
        "indication_en": indic_en,
        "ingredients": ingredients,
        "targets": targets,
        "diseases": diseases,
        "ingredient_count": len(ing_rows),
        "target_count": len(tgt_rows),
        "disease_count": len(dis_rows),
    }

    # 写缓存
    _cache_put(result)

    return {"status": "ok", **result, "from_cache": False}


def analyze_recipe(herbs: list[dict]) -> dict:
    """分析一个自定义方子：多味药材合并统计。

    输入：[{"name": "金银花", "grams": 10}, ...]
    输出：{
      "status": "ok",
      "herbs": [...],               # 每味药材的详情（同 get_herb_detail）
      "all_ingredients": [...],     # 合并去重后的成分列表 [{name, herb_count, top_targets}]
      "all_targets": [...],         # 合并去重后的靶点列表 [{name, herb_count, p_value_min}]
      "all_diseases": [...],        # 合并去重后的疾病列表
      "matched_count": int,         # 成功匹配到 HERB 的药材数
      "not_found": [str],           # 没找到的药材名
    }
    """
    herbs = [h for h in herbs if h.get("name")]
    if not herbs:
        return {"status": "error", "error": "没有药材",
                "herbs": [], "all_ingredients": [], "all_targets": [], "all_diseases": [],
                "matched_count": 0, "not_found": []}

    herb_details = []
    not_found = []

    for h in herbs:
        name = h["name"].strip()
        detail = get_herb_detail(name)
        if detail["status"] == "ok":
            detail["grams"] = h.get("grams")
            herb_details.append(detail)
        else:
            not_found.append(name)

    # 合并成分（按名字去重，统计出现在多少味药里）
    ing_map = {}  # name -> {herb_count, first_id, alias}
    for hd in herb_details:
        for ing in hd.get("ingredients", []):
            key = ing["name"].lower()
            if key not in ing_map:
                ing_map[key] = {
                    "name": ing["name"],
                    "id": ing.get("id"),
                    "alias": ing.get("alias", ""),
                    "herb_count": 0,
                    "from_herbs": [],
                }
            ing_map[key]["herb_count"] += 1
            ing_map[key]["from_herbs"].append(hd["name_cn"])

    all_ingredients = sorted(
        ing_map.values(), key=lambda x: (-x["herb_count"], x["name"]))

    # 合并靶点
    tgt_map = {}
    for hd in herb_details:
        for t in hd.get("targets", []):
            key = t["name"]
            if key not in tgt_map:
                tgt_map[key] = {
                    "name": t["name"],
                    "id": t.get("id"),
                    "herb_count": 0,
                    "p_value_min": None,
                    "from_herbs": [],
                }
            tgt_map[key]["herb_count"] += 1
            tgt_map[key]["from_herbs"].append(hd["name_cn"])
            pv = t.get("p_value")
            if pv is not None:
                try:
                    pvf = float(pv)
                    if tgt_map[key]["p_value_min"] is None or pvf < tgt_map[key]["p_value_min"]:
                        tgt_map[key]["p_value_min"] = pvf
                except (ValueError, TypeError):
                    pass

    all_targets = sorted(
        tgt_map.values(), key=lambda x: (-x["herb_count"], x["p_value_min"] or 1))

    # 合并疾病
    dis_map = {}
    for hd in herb_details:
        for dis in hd.get("diseases", []):
            key = dis["name"]
            if key not in dis_map:
                dis_map[key] = {
                    "name": dis["name"],
                    "id": dis.get("id"),
                    "herb_count": 0,
                    "p_value_min": None,
                    "from_herbs": [],
                }
            dis_map[key]["herb_count"] += 1
            dis_map[key]["from_herbs"].append(hd["name_cn"])
            pv = dis.get("p_value")
            if pv is not None:
                try:
                    pvf = float(pv)
                    if dis_map[key]["p_value_min"] is None or pvf < dis_map[key]["p_value_min"]:
                        dis_map[key]["p_value_min"] = pvf
                except (ValueError, TypeError):
                    pass

    all_diseases = sorted(
        dis_map.values(), key=lambda x: (-x["herb_count"], x["p_value_min"] or 1))

    return {
        "status": "ok",
        "herbs": herb_details,
        "all_ingredients": all_ingredients,
        "all_targets": all_targets,
        "all_diseases": all_diseases,
        "matched_count": len(herb_details),
        "not_found": not_found,
    }
