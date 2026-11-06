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
import os
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

# SymMap v2 下载地址与本地缓存路径（用于补中文性味归经）
SYMMAP_URL = "http://www.symmap.org/static/download/V2.0/SymMap%20v2.0%2C%20SMHB%20file.xlsx"
_DATA_DIR = Path(__file__).resolve().parents[2].parent / "data"
SYMMAP_LOCAL = _DATA_DIR / "symmap_smhb_v2.json"
# 构建期预置的 xlsx（703 味药，含中文性味/归经/别名），存在则优先读它
SYMMAP_XLSX_LOCAL = _DATA_DIR / "symmap_smhb_v2.xlsx"


def _parse_symmap_xlsx(raw) -> dict:
    """把 SMHB xlsx（路径或 bytes）解析成 {中文名: {properties_cn, meridians_cn, alias, pinyin}}"""
    import io
    import openpyxl
    if isinstance(raw, (bytes, bytearray)):
        wb = openpyxl.load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
    else:
        wb = openpyxl.load_workbook(str(raw), read_only=True, data_only=True)
    ws = wb[wb.sheetnames[0]]
    rows = list(ws.iter_rows(values_only=True))
    col = {name: i for i, name in enumerate(rows[0])}
    out = {}
    for row in rows[1:]:
        name = row[col['Chinese_name']]
        if not name:
            continue
        out[name] = {
            "properties_cn": row[col['Properties_Chinese']] or None,
            "meridians_cn": row[col['Meridians_Chinese']] or None,
            "alias": (row[col['Alias']] or None) if 'Alias' in col else None,
            "pinyin": row[col['Pinyin_name']] or None,
        }
    wb.close()
    return out


def _load_symmap_dict() -> dict:
    """加载 SymMap SMHB 数据（药材中文名 → {properties_cn, meridians_cn, alias}）。
    顺序：本地 JSON 缓存 → 构建期预置 xlsx → 联网下载 xlsx。全失败返回 {}。
    返回 dict：{中文名: {properties_cn, meridians_cn, alias, pinyin}}
    """
    import json as _json
    if SYMMAP_LOCAL.exists():
        try:
            return _json.loads(SYMMAP_LOCAL.read_text(encoding="utf-8"))
        except Exception:
            pass  # 缓存损坏就继续往下走

    def _persist(out: dict) -> dict:
        try:
            SYMMAP_LOCAL.parent.mkdir(parents=True, exist_ok=True)
            SYMMAP_LOCAL.write_text(_json.dumps(out, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass  # 写不了缓存不影响本次使用
        return out

    # 构建期预置的 xlsx（离线可用，首选）
    if SYMMAP_XLSX_LOCAL.exists():
        try:
            return _persist(_parse_symmap_xlsx(SYMMAP_XLSX_LOCAL))
        except Exception:
            pass

    # 最后才联网下载
    try:
        r = requests.get(SYMMAP_URL, timeout=60)
        r.raise_for_status()
        return _persist(_parse_symmap_xlsx(r.content))
    except Exception:
        return {}  # 下载失败就返回空字典，不影响主流程


_symmap_cache = None

# 鲜品/炮制品与 SymMap 正名的对应（药典通识整理，非实验数据；仅用于补性味归经展示）
_SYMMAP_ALIAS_EXTRA = {
    "蜜枣": "大枣",
    "枣": "大枣",
    "乌梅干": "乌梅",
    "生甘草": "甘草",
    "炒麦芽": "麦芽",
    "炒谷芽": "谷芽",
}


def _symmap_dict() -> dict:
    """懒加载 SymMap 字典（只加载一次）"""
    global _symmap_cache
    if _symmap_cache is None:
        _symmap_cache = _load_symmap_dict()
    return _symmap_cache


def _lookup_symmap(name: str, smap: dict) -> dict | None:
    """在 SymMap 字典里找一味药。匹配顺序：
    1) 正名精确匹配
    2) 显式别名表（鲜干/炮制差异，如 鲜芦根→芦根、蜜枣→大枣）
    3) 别名匹配（Alias 字段逗号分隔）
    4) 前缀剥离：鲜/干/生/炒/炙 开头去掉再试
    5) 后缀兜底：枸杞→枸杞子、薏苡→薏苡仁（2-3 字短名才启用）
    找不到返回 None —— 不猜、不做模糊相似匹配，避免配到不相干的药。"""
    info = smap.get(name)
    if info:
        return info

    # 鲜/干/炮制差异的显式映射（药典通识，非推测）
    alt = _SYMMAP_ALIAS_EXTRA.get(name)
    if alt:
        info = smap.get(alt)
        if info:
            return info

    # 别名匹配
    for cn, data in smap.items():
        aliases = data.get("alias") or ""
        if name in [a.strip() for a in aliases.split(",")]:
            return data

    # 前缀剥离（鲜芦根 → 芦根）
    for pre in ("鲜", "干", "生", "炒", "炙", "制"):
        if name.startswith(pre) and len(name) > len(pre) + 1:
            stripped = name[len(pre):]
            info = smap.get(stripped)
            if not info:
                alt2 = _SYMMAP_ALIAS_EXTRA.get(stripped)
                info = smap.get(alt2) if alt2 else None
            if info:
                return info

    # 后缀兜底：只对短名（2-3 字）启用，避免误配
    if 2 <= len(name) <= 3:
        for suf in ("子", "仁", "花", "叶"):
            cand = smap.get(name + suf)
            if cand:
                return cand
    return None


_KB_DB = Path(__file__).resolve().parents[3] / "data" / "shiyang.db"
_kb_herb_cache = None


def _kb_herb_dict() -> dict:
    """本地知识库（shiyang.db）34 味策展药材的中文性味/归经/功效。
    这部分是人工整理+有出处的数据，质量高于 SymMap 与机器翻译，优先采用。
    返回 {药名或别名: {nature, flavor, meridians, functions, name}}"""
    global _kb_herb_cache
    if _kb_herb_cache is not None:
        return _kb_herb_cache
    out = {}
    try:
        conn = sqlite3.connect(f"file:{_KB_DB.as_posix()}?mode=ro", uri=True)
        try:
            rows = conn.execute(
                "SELECT name, alias, nature, flavor, meridians, functions FROM herb").fetchall()
        finally:
            conn.close()
        for name, alias, nature, flavor, meridians, functions in rows:
            rec = {"name": name, "nature": nature, "flavor": flavor,
                   "meridians": meridians, "functions": functions}
            out[name] = rec
            for a in (alias or "").replace("，", ",").split(","):
                a = a.strip()
                if a and a != name:
                    out.setdefault(a, rec)
    except Exception:
        pass  # 知识库不可用时不影响 HERB 主流程
    _kb_herb_cache = out
    return out


def _enrich_with_symmap(result: dict) -> dict:
    """补中文性味/归经/功效。优先本地知识库（有出处的人工整理数据），
    其次 SymMap（703 味药的药典性味归经）。都没有则字段为 None。"""
    name = result.get("name_cn") or result.get("herb_name")
    kb = _kb_herb_dict().get(name) if name else None
    info = _lookup_symmap(name, _symmap_dict()) if name else None

    if kb:
        # 本地库的性味是拆开的 nature/flavor，拼成「甘,寒」形式与 SymMap 对齐
        parts = [p for p in (kb.get("flavor"), kb.get("nature")) if p]
        result["properties_cn"] = ",".join(parts) if parts else None
        result["meridians_cn"] = kb.get("meridians")
        result["functions_cn"] = kb.get("functions")
        result["functions_cn_source"] = "curated"
    else:
        result["properties_cn"] = info.get("properties_cn") if info else None
        result["meridians_cn"] = info.get("meridians_cn") if info else None
        result["functions_cn"] = None
        result["functions_cn_source"] = None
    return result


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
        # AI 翻译缓存：HERB 只给英文功效，中文译文按原文哈希缓存，避免重复调模型
        conn.execute("""
            CREATE TABLE IF NOT EXISTS herb_translation (
                source_hash TEXT PRIMARY KEY,       -- sha1(原文)，同一段英文只翻一次
                text_en TEXT NOT NULL,              -- 英文原文（便于人工复核）
                text_cn TEXT NOT NULL,              -- 中文译文
                model TEXT,                         -- 产出译文的模型
                created_at REAL                     -- 缓存时间戳
            )
        """)
        # 联网搜索兜底缓存：HERB/SymMap 查不到的药材，用 web-search 查「有什么作用」
        # sources 必须来自网关返回的 web_search[]（真实搜索结果），不允许模型自由发挥
        conn.execute("""
            CREATE TABLE IF NOT EXISTS herb_web_lookup (
                herb_name TEXT PRIMARY KEY,         -- 查询的药名/食材名
                summary_cn TEXT NOT NULL,           -- 作用的白话总结（AI 生成，须标注）
                sources TEXT NOT NULL,              -- JSON: [{title, url, publish_date, site}]
                searched_at REAL                    -- 缓存时间戳
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
    """写入缓存（INSERT OR REPLACE）。
    HERB 返回的 summary 行里任何文本列都可能是 {link, title} dict（不同药材字段
    行为不一致），这里统一剥成字符串/None 兜底，避免逐个字段打地鼠。"""
    def _txt(v):
        if isinstance(v, dict):
            t = v.get("title")
            return t if isinstance(t, str) else None
        return v if isinstance(v, str) else None

    conn = _db()
    try:
        conn.execute("""
            INSERT OR REPLACE INTO herb_cache
            (herb_name, herb_id, pinyin, latin_name, properties, meridians,
             function_en, indication_en, ingredients, targets, diseases,
             ingredient_count, target_count, disease_count, cached_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            data["herb_name"],
            _txt(data["herb_id"]),
            _txt(data["pinyin"]),
            _txt(data["latin_name"]),
            _txt(data["properties"]),
            _txt(data["meridians"]),
            _txt(data["function_en"]),
            _txt(data["indication_en"]),
            json.dumps(data["ingredients"], ensure_ascii=False),
            json.dumps(data["targets"], ensure_ascii=False),
            json.dumps(data["diseases"], ensure_ascii=False),
            data["ingredient_count"], data["target_count"], data["disease_count"],
            time.time(),
        ))
        conn.commit()
    finally:
        conn.close()


# ---------- AI 中文白话翻译（HERB 只给英文，本地库/SymMap 不命中时兜底） ----------

AI_BASE_URL = os.environ.get("SHIYANG_AI_BASE_URL") or "http://127.0.0.1:7863/v1"
AI_MODEL = os.environ.get("SHIYANG_AI_MODEL") or "deepseek-v4-flash"
TRANSLATE_TIMEOUT = 25  # 秒；翻译是锦上添花，不能拖慢主请求

_TRANSLATE_PROMPT = (
    "你是中医药专业翻译。把用户给出的英文中药功效/主治描述译成简洁的中文白话，"
    "要求：保留专业术语（如 toxic heat→热毒、wind-heat→风热），不要添加原文没有的疗效，"
    "不要输出解释或前言，只输出译文本身。"
)


def _translation_get(text_en: str) -> str | None:
    """查翻译缓存（按原文哈希）"""
    import hashlib
    h = hashlib.sha1(text_en.encode("utf-8")).hexdigest()
    conn = _db()
    try:
        row = conn.execute(
            "SELECT text_cn FROM herb_translation WHERE source_hash = ?", (h,)).fetchone()
        return row["text_cn"] if row else None
    except Exception:
        return None
    finally:
        conn.close()


def _translation_put(text_en: str, text_cn: str, model: str) -> None:
    import hashlib
    h = hashlib.sha1(text_en.encode("utf-8")).hexdigest()
    conn = _db()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO herb_translation(source_hash,text_en,text_cn,model,created_at) "
            "VALUES (?,?,?,?,?)", (h, text_en, text_cn, model, time.time()))
        conn.commit()
    except Exception:
        pass  # 缓存写失败不影响返回译文
    finally:
        conn.close()


def translate_to_cn(text_en: str | None, api_key: str | None = None) -> dict:
    """把英文功效/主治译成中文。带缓存；模型不可用时返回 ok=False 由调用方降级显示英文。
    返回 {"text_cn": str|None, "ok": bool, "model": str|None}
    """
    if not text_en or not text_en.strip():
        return {"text_cn": None, "ok": False, "model": None}

    cached = _translation_get(text_en)
    if cached:
        return {"text_cn": cached, "ok": True, "model": "cache"}

    key = (api_key or "").strip() or os.environ.get("SHIYANG_AI_KEY") or "zerogate"
    try:
        r = requests.post(
            f"{AI_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": AI_MODEL,
                "messages": [
                    {"role": "system", "content": _TRANSLATE_PROMPT},
                    {"role": "user", "content": text_en},
                ],
                "temperature": 0.2,
                "stream": False,
            },
            timeout=TRANSLATE_TIMEOUT,
        )
        r.raise_for_status()
        text_cn = (r.json()["choices"][0]["message"]["content"] or "").strip()
        if not text_cn:
            return {"text_cn": None, "ok": False, "model": None}
        _translation_put(text_en, text_cn, AI_MODEL)
        return {"text_cn": text_cn, "ok": True, "model": AI_MODEL}
    except Exception:
        return {"text_cn": None, "ok": False, "model": None}  # 网关不可用 → 前端回落英文


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


def _local_kb_detail(keyword: str) -> dict | None:
    """从本地知识库 shiyang.db 取药材详情（2026-11-05 扩容后 105 味）。

    背景：HERB search_api 对部分药材无精确命中（槐米/灵芝/天麻等约 71 味），
    但这些药的成分/靶点数据已在灌库时写入本地库——先查本地再判 not_found，
    避免把库内有的数据报成「未找到」。

    靶点取自成分级 rel_compound_target（source_db='herb.ac.cn'），P/FDR 从
    reference 列解析；药材级统计只对旧 34 味可用，新药材如实为 None。
    返回与 get_herb_detail 同构的 dict；本地没有该药返回 None。
    """
    try:
        conn = sqlite3.connect(f"file:{_KB_DB.as_posix()}?mode=ro", uri=True)
        try:
            row = conn.execute(
                "SELECT id, name, pinyin, latin_name, nature, flavor, meridians, functions, "
                "contraindication FROM herb WHERE name=? OR alias LIKE ? ORDER BY "
                "CASE WHEN name=? THEN 0 ELSE 1 END LIMIT 1",
                (keyword, f"%{keyword}%", keyword)).fetchone()
            if not row:
                return None
            herb_id, name, pinyin, latin, nature, flavor, meridians, functions, contra = row

            # 性味拆列 → 拼成 HERB 风格的英文口径列位（前端只读 properties/meridians 展示中文，
            # 这两列主要供 _enrich_with_symmap/白话层兜底，填中文原值）
            props = "、".join(x for x in (flavor, nature) if x) or None
            func_en = functions

            ing_rows = conn.execute(
                "SELECT c.id, c.name FROM rel_herb_compound r JOIN compound c ON c.id=r.compound_id "
                "WHERE r.herb_id=? ORDER BY c.name LIMIT ?", (herb_id, MAX_INGREDIENTS)).fetchall()
            ing_total = conn.execute(
                "SELECT COUNT(*) FROM rel_herb_compound WHERE herb_id=?", (herb_id,)).fetchone()[0]

            tgt_rows = conn.execute(
                "SELECT rt.target_gene, rt.reference FROM rel_compound_target rt "
                "JOIN rel_herb_compound r ON r.compound_id=rt.compound_id "
                "WHERE r.herb_id=? AND rt.source_db='herb.ac.cn' "
                "GROUP BY rt.target_gene ORDER BY MIN(rt.id) LIMIT ?",
                (herb_id, MAX_TARGETS)).fetchall()
            tgt_total = conn.execute(
                "SELECT COUNT(DISTINCT rt.target_gene) FROM rel_compound_target rt "
                "JOIN rel_herb_compound r ON r.compound_id=rt.compound_id "
                "WHERE r.herb_id=? AND rt.source_db='herb.ac.cn'", (herb_id,)).fetchone()[0]
        finally:
            conn.close()
    except Exception:
        return None  # 知识库不可用时不影响 HERB 主流程

    targets = []
    for gene, ref in tgt_rows:
        p_val = fdr = None
        if ref:
            # reference 格式：'P=<值>; FDR_BH=<值> (...)' 或 'P=NA; FDR_BH=NA (...)'
            for seg in ref.split(";"):
                seg = seg.strip()
                if seg.startswith("P=") and seg[2:] not in ("NA", "", None):
                    p_val = seg[2:]
                elif seg.startswith("FDR_BH=") and seg[7:] not in ("NA", "", None):
                    fdr = seg[7:]
        targets.append({"id": None, "name": gene, "p_value": p_val, "fdr": fdr})

    return {
        "status": "ok",
        "herb_name": keyword,
        "herb_id": herb_id,
        "name_cn": name,
        "pinyin": pinyin,
        "latin_name": latin,
        "properties": props,
        "meridians": meridians,
        "function_en": func_en,
        "indication_en": contra,
        "ingredients": [{"id": i, "name": n, "alias": ""} for i, n in ing_rows],
        "targets": targets,
        "diseases": [],
        "ingredient_count": ing_total,
        "target_count": tgt_total,
        "disease_count": 0,
    }


def get_herb_detail(keyword: str) -> dict:
    """获取药材详情（成分/靶点/疾病/功效）。
    优先读缓存 → HERB search_api → 本地知识库兜底（105 味灌库数据），并写缓存。

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
        return _enrich_with_symmap({
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
        })

    # 1. 搜索拿 herb_id
    herb_id = _herb_id_from_search(keyword)
    if not herb_id:
        # HERB 搜不到 → 本地知识库兜底（105 味灌库数据，含槐米/灵芝等 search_api 无命中的药材）
        local = _local_kb_detail(keyword)
        if local:
            _cache_put(local)
            return _enrich_with_symmap({**local, "from_cache": False})
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
        # summary 行的文本列（拼音/拉丁/性味/归经/功效/主治）都可能是 {link, title}
        # dict，不同药材行为不一致，统一剥成字符串/None
        def _cell(v):
            if isinstance(v, dict):
                t = v.get("title")
                return t if isinstance(t, str) else None
            return v if isinstance(v, str) else None

        latin = _cell(row[4] if len(row) > 4 else None)
        props = _cell(row[5] if len(row) > 5 else None)
        merid = _cell(row[6] if len(row) > 6 else None)
        func_en = _cell(row[8] if len(row) > 8 else None)
        indic_en = _cell(row[9] if len(row) > 9 else None)
        if not isinstance(name_cn, str):
            name_cn = _cell(name_cn) or keyword

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

    return _enrich_with_symmap({"status": "ok", **result, "from_cache": False})


_BATCH_TRANSLATE_PROMPT = (
    "你是中医药专业翻译。用户会给你一个 JSON 数组，每个元素是一条英文中药功效/主治描述。"
    "请把它译成简洁的中文白话，保留专业术语（如 toxic heat→热毒、wind-heat→风热），"
    "不要添加原文没有的疗效。严格输出一个与输入等长的 JSON 数组，元素为对应中文译文，"
    "不要输出任何其他文字。"
)


def _batch_translate(texts: list[str], api_key: str | None = None) -> list[str | None]:
    """一次请求翻译多条英文。返回等长列表，失败位置为 None。
    空串/None 位置直接返回 None，不浪费 token。"""
    results: list[str | None] = []
    pending: list[tuple[int, str]] = []
    for i, t in enumerate(texts):
        if not t or not t.strip():
            results.append(None)
            continue
        cached = _translation_get(t)
        if cached:
            results.append(cached)
        else:
            results.append(None)
            pending.append((i, t))

    if not pending:
        return results

    key = (api_key or "").strip() or os.environ.get("SHIYANG_AI_KEY") or "zerogate"
    try:
        r = requests.post(
            f"{AI_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": AI_MODEL,
                "messages": [
                    {"role": "system", "content": _BATCH_TRANSLATE_PROMPT},
                    {"role": "user", "content": json.dumps([t for _, t in pending], ensure_ascii=False)},
                ],
                "temperature": 0.2,
                "stream": False,
            },
            timeout=TRANSLATE_TIMEOUT,
        )
        r.raise_for_status()
        content = (r.json()["choices"][0]["message"]["content"] or "").strip()
        # 模型常带 ```json 包裹，剥掉
        if content.startswith("```"):
            content = content.strip("`")
            content = content[content.find("["):] if "[" in content else content
        arr = json.loads(content)
        if not isinstance(arr, list) or len(arr) != len(pending):
            return results  # 数量对不上就整体放弃，不猜对应关系
        for (idx, src), cn in zip(pending, arr):
            if isinstance(cn, str) and cn.strip():
                results[idx] = cn.strip()
                _translation_put(src, cn.strip(), AI_MODEL)
    except Exception:
        pass  # 网关不可用/解析失败 → 保留 None，前端回落英文
    return results


def _fill_ai_translations(herb_details: list[dict], api_key: str | None = None) -> None:
    """给缺中文功效的药材批量补 AI 译文（原地修改）。
    只翻「功效」(`function_en`，短句、价值高）；「主治」(`indication_en`) 是一长串
    疾病名，机器翻译容易失真，保持英文原文由前端标注「英译」。
    翻译失败保持 None，前端回落英文。"""
    targets: list[dict] = []
    texts: list[str] = []
    for hd in herb_details:
        if hd.get("functions_cn"):
            continue  # 本地策展库已有，不翻
        src = hd.get("function_en")
        if src:
            targets.append(hd)
            texts.append(src)

    if not texts:
        return

    translated = _batch_translate(texts, api_key)
    for hd, cn in zip(targets, translated):
        hd["functions_cn"] = cn
        hd["functions_cn_source"] = "ai" if cn else None


def analyze_recipe(herbs: list[dict], api_key: str | None = None) -> dict:
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

    _fill_ai_translations(herb_details, api_key)

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


# ---------- P2：从粘贴的方子文案里提取药材+克重 ----------

_PARSE_PROMPT = (
    "你是中药方剂信息抽取器。用户会给一段可能来自小红书/公众号的方子文案，"
    "请只抽取「药材名 + 克重」两部分，规则：\n"
    "1. 只输出文案里**明确出现**的药材名，不要补充、不要推荐、不要联想同类药\n"
    "2. 克重只取文案明确写出的数字（含 g/克/钱），没写就填 null，不要估算\n"
    "3. 剔除剂量单位之外的修饰语（如「特级」「野生」「古法炮制」）\n"
    "4. 如果同一味药出现多次，只保留一条\n"
    "5. 文案里没有药材，返回空数组\n"
    "严格输出 JSON 数组，形如 [{\"name\":\"金银花\",\"grams\":10}]，不要输出其他文字。"
)


def _call_parse_model(text: str, api_key: str) -> str:
    """调模型抽取药材，返回模型原始输出字符串（已剥掉 ``` 包裹）。
    单独成函数便于测试注入假输出，不必依赖真实网关。"""
    r = requests.post(
        f"{AI_BASE_URL.rstrip('/')}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": AI_MODEL,
            "messages": [
                {"role": "system", "content": _PARSE_PROMPT},
                {"role": "user", "content": text[:2000]},  # 截断超长文案，防刷
            ],
            "temperature": 0.0,
            "stream": False,
        },
        timeout=TRANSLATE_TIMEOUT,
    )
    r.raise_for_status()
    content = (r.json()["choices"][0]["message"]["content"] or "").strip()
    if content.startswith("```"):
        content = content.strip("`")
        if "[" in content:
            content = content[content.find("["):]
    return content


def parse_formula_text(text: str, api_key: str | None = None) -> dict:
    """用 AI 从一段自由文本里抽取药材名与克重。

    安全设计：模型输出**必须**经本地校验才算数——名字要在知识库/SymMap/HERB 里
    真能对上（用 search_herb 复核），克重必须在合理区间（0.5–200g）。
    模型编出来的药名会被标进 rejected，不会静默进入分析流程。

    返回：
      {"ok": bool, "herbs": [{name, grams, verified}], "rejected": [{name, reason}],
       "model": str|None, "error": str|None}
    """
    if not text or not text.strip():
        return {"ok": False, "herbs": [], "rejected": [], "model": None,
                "error": "文本为空"}

    key = (api_key or "").strip() or os.environ.get("SHIYANG_AI_KEY") or "zerogate"
    try:
        raw = json.loads(_call_parse_model(text, key))
    except Exception as e:
        return {"ok": False, "herbs": [], "rejected": [], "model": None,
                "error": f"解析失败：{e}"}

    if not isinstance(raw, list):
        return {"ok": False, "herbs": [], "rejected": [], "model": AI_MODEL,
                "error": "模型输出不是数组"}

    herbs, rejected = [], []
    for item in raw[:25]:  # 上限 25 味，超过大概率是模型发散
        if not isinstance(item, dict):
            continue
        name = (item.get("name") or "").strip()
        if not name:
            continue
        grams = item.get("grams")
        if grams is not None:
            try:
                grams = float(grams)
            except (TypeError, ValueError):
                grams = None
        if grams is not None and not (0.5 <= grams <= 200):
            rejected.append({"name": name, "reason": f"克重 {grams}g 超出合理范围（0.5–200g）"})
            continue
        # 复核药名真实性：先查本地（知识库 / SymMap，零网络开销），
        # 都未命中才走 HERB 联网确认——避免 25 味药串行打 25 次外部请求
        if _name_exists_locally(name):
            canon = name
        else:
            detail = get_herb_detail(name)
            if detail.get("status") != "ok":
                rejected.append({"name": name, "reason": "在 HERB/本地知识库中查不到这味药"})
                continue
            canon = detail.get("name_cn") or name
        herbs.append({"name": canon, "grams": grams, "verified": True})

    return {"ok": True, "herbs": herbs, "rejected": rejected,
            "model": AI_MODEL, "error": None}


def _name_exists_locally(name: str) -> bool:
    """药名是否在本地知识库或 SymMap 里能对上（不联网）"""
    return bool(_kb_herb_dict().get(name)) or _lookup_symmap(name, _symmap_dict()) is not None


# ---------- 联网搜索兜底（导师要求：HERB 查不到的药材/奇怪输入，给出「有什么作用 + 真实来源」） ----------
# 数据通路：ZeroGate 网关 web-search 模型（智谱搜索后端）。
# 来源真实性约定：引用列表只取网关响应里的 web_search[]（搜索引擎返回的真实结果），
# AI 正文仅作白话总结；web_search[] 为空 = 没搜到，直接放弃，不产出无来源的结果。

WEB_LOOKUP_TTL_DAYS = 30   # 药材常识性信息变化慢，30 天内不重复搜
WEB_SEARCH_TIMEOUT = 90    # 秒；web-search 实测 ~17s，留足余量

_WEB_LOOKUP_PROMPT = (
    "你是中医药科普编辑。用户会给你一个药材/食材名（可能来自民间偏方或网络文案，"
    "未必是规范中药名）。请基于给出的搜索结果回答：\n"
    "1. 这个东西传统上/民间被认为有什么作用（3-5 句白话，别夸大疗效）\n"
    "2. 如有安全性问题（毒性、禁忌、误认风险）必须提到\n"
    "3. 只依据搜索结果，不要补充你自己的知识；搜索结果没提到的不要写\n"
    "4. 不要输出前言、问候、总结句，直接输出正文"
)


def _web_lookup_get(name: str) -> dict | None:
    """读缓存（30 天 TTL）"""
    conn = _db()
    try:
        row = conn.execute(
            "SELECT summary_cn, sources, searched_at FROM herb_web_lookup WHERE herb_name=?",
            (name,)).fetchone()
        if not row:
            return None
        if (time.time() - row["searched_at"]) / 86400 > WEB_LOOKUP_TTL_DAYS:
            return None
        return {"summary_cn": row["summary_cn"], "sources": json.loads(row["sources"])}
    except Exception:
        return None
    finally:
        conn.close()


def _web_lookup_put(name: str, summary_cn: str, sources: list) -> None:
    conn = _db()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO herb_web_lookup(herb_name,summary_cn,sources,searched_at) "
            "VALUES (?,?,?,?)", (name, summary_cn, json.dumps(sources, ensure_ascii=False), time.time()))
        conn.commit()
    except Exception:
        pass  # 缓存写失败不影响返回
    finally:
        conn.close()


def web_lookup_herb(name: str, api_key: str | None = None) -> dict:
    """联网搜索一味药材/食材的作用，带真实来源。

    返回 {
      "status": "ok" | "no_result" | "error",
      "name": str,
      "summary_cn": str | None,      # AI 白话总结（调用方必须标注 AI 生成）
      "sources": [{title, url, publish_date, site}],  # 真实搜索结果，可能为空
    }
    """
    name = (name or "").strip()
    if not name:
        return {"status": "error", "name": name, "summary_cn": None, "sources": []}

    cached = _web_lookup_get(name)
    if cached:
        return {"status": "ok", "name": name, **cached, "from_cache": True}

    key = (api_key or "").strip() or os.environ.get("SHIYANG_AI_KEY") or "zerogate"
    try:
        r = requests.post(
            f"{AI_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": "web-search",
                "messages": [
                    {"role": "system", "content": _WEB_LOOKUP_PROMPT},
                    {"role": "user", "content": f"药材/食材名：{name}"},
                ],
                "temperature": 0.3,
                "stream": False,
            },
            timeout=WEB_SEARCH_TIMEOUT,
        )
        r.raise_for_status()
        d = r.json()
    except Exception:
        return {"status": "error", "name": name, "summary_cn": None, "sources": []}

    # 来源只取网关的 web_search[]（真实搜索结果）；没有 = 没搜到，不产出无来源结果
    raw_sources = d.get("web_search") or []
    sources = []
    for w in raw_sources[:6]:
        url = (w.get("link") or "").strip()
        if not url:
            continue
        sources.append({
            "title": (w.get("title") or "").strip()[:120],
            "url": url,
            "publish_date": w.get("publish_date"),
            "site": w.get("media") or w.get("site") or None,
        })

    summary = (d.get("choices", [{}])[0].get("message", {}).get("content") or "").strip()
    if not sources or not summary:
        # 没搜到可靠来源 → 如实报 no_result，不编
        return {"status": "no_result", "name": name, "summary_cn": None, "sources": []}

    _web_lookup_put(name, summary, sources)
    return {"status": "ok", "name": name, "summary_cn": summary, "sources": sources}


# ---------- 拍照/截图 → 抽取方子文字（OCR 路线，非识药） ----------
# 场景（用户原话）：在外面看到一个方子，拍下来；本质就是「上传截图」。
# 因此这里只做一件事：把图片里的文字抠出来，然后**复用 parse_formula_text**
# 做药材+克重抽取（那套已有防幻觉复核）。不做药材实物识别。
#
# 引擎选择（2026-11-06 实测，见 docs/拍照识药_方案调研.md）：
#   1) RapidOCR（ONNX，本地 CPU）—— 清晰图 1.5s / 极端劣化图 1.2-5.4s，
#      合成测试 3 张全部 100% 正确，且给出每行置信度、零 API 成本、断网可用
#   2) 视觉模型（网关 glm-5v-turbo）—— 兜底，适合手写体/竖排/图文混排
# RapidOCR 为主，失败或结果为空才退到视觉模型。
#
# 关键补充：correct_herb_name() 对 OCR 结果做形近字纠错。理由很实在——
# 「金银花」被认成「金银化」时，后面会去联网搜「金银化」，整条链路全错。

VISION_MODEL = "glm-5v-turbo"     # 兜底视觉模型（2-4s）
VISION_TIMEOUT = 60               # 秒
MAX_IMAGE_BYTES = 8 * 1024 * 1024  # 8MB
ALLOWED_IMAGE_MIME = {"image/jpeg", "image/png", "image/webp", "image/jpg"}

# RapidOCR 置信度低于此值的行丢弃（实测清晰图 0.94-1.00，劣化图 0.98+）
OCR_MIN_SCORE = 0.5

_rapidocr_engine = None


def _rapidocr():
    """懒加载 RapidOCR（首次约 0.8s，之后常驻内存）"""
    global _rapidocr_engine
    if _rapidocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _rapidocr_engine = RapidOCR()
    return _rapidocr_engine


def _ocr_with_rapidocr(image_bytes: bytes) -> dict | None:
    """用本地 RapidOCR 识别。失败/未安装返回 None，由调用方退到视觉模型。"""
    try:
        import numpy as np
        from PIL import Image
        import io

        engine = _rapidocr()
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        res, _ = engine(np.array(img))
        if not res:
            return {"text": "", "lines": 0, "engine": "rapidocr"}
        kept, dropped = [], 0
        for _box, txt, score in res:
            if float(score) >= OCR_MIN_SCORE and txt.strip():
                kept.append(txt.strip())
            else:
                dropped += 1
        return {"text": "\n".join(kept), "lines": len(kept),
                "dropped_low_conf": dropped, "engine": "rapidocr"}
    except Exception:
        return None

_OCR_PROMPT = (
    "你是文字识别器。把图片里所有可见文字**原样**抄出来（OCR），规则：\n"
    "1. 逐行抄，保留换行；数字与单位（g/克/钱/两）照抄，不要换算\n"
    "2. 处方里的药名、克重、用法一个都不要漏\n"
    "3. 手写体认不准的字用「?」占位，不要猜、不要编\n"
    "4. 只输出识别到的文字本身，不要任何解释、标题、标点补充或总结\n"
    "5. 图片里没有文字就输出空字符串"
)


def extract_text_from_image(image_bytes: bytes, mime: str = "image/jpeg",
                            api_key: str | None = None) -> dict:
    """把图片里的文字抽出来（OCR）。本地 RapidOCR 优先，视觉模型兜底。

    返回 {
      "status": "ok" | "no_text" | "error",
      "text": str | None,       # 识别到的原文
      "model": str,             # 实际使用的引擎
      "error": str | None,
    }
    """
    if not image_bytes:
        return {"status": "error", "text": None, "model": None, "error": "图片为空"}

    # ① 本地 RapidOCR（零成本、断网可用、实测准确率高）
    local = _ocr_with_rapidocr(image_bytes)
    if local is not None and local["text"].strip():
        return {"status": "ok", "text": local["text"][:3000],
                "model": local["engine"], "error": None}
    # RapidOCR 跑通但没认出字 → 直接判 no_text，不必再花一次 API 调用
    if local is not None and not local["text"].strip():
        return {"status": "no_text", "text": None, "model": local["engine"], "error": None}

    # ② 视觉模型兜底（RapidOCR 未安装/异常时；手写体、竖排也能救）
    return _ocr_with_vision(image_bytes, mime, api_key)


def _ocr_with_vision(image_bytes: bytes, mime: str, api_key: str | None) -> dict:
    """视觉模型 OCR（兜底路径）"""
    import base64

    b64 = base64.b64encode(image_bytes).decode("ascii")
    key = (api_key or "").strip() or os.environ.get("SHIYANG_AI_KEY") or "zerogate"
    try:
        r = requests.post(
            f"{AI_BASE_URL.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": VISION_MODEL,
                "messages": [{"role": "user", "content": [
                    {"type": "text", "text": _OCR_PROMPT},
                    {"type": "image_url",
                     "image_url": {"url": f"data:{mime};base64,{b64}"}},
                ]}],
                "temperature": 0,
                "stream": False,
            },
            timeout=VISION_TIMEOUT,
        )
        r.raise_for_status()
        text = (r.json()["choices"][0]["message"].get("content") or "").strip()
    except Exception as e:
        # 不把底层服务地址与原始 HTTP 错误抛给用户，但区分限流与其它故障
        if "429" in str(e):
            return {"status": "error", "text": None, "model": VISION_MODEL,
                    "error": "识别请求太多了，请等十几秒再试"}
        return {"status": "error", "text": None, "model": VISION_MODEL,
                "error": "图片识别服务暂时不可用，请稍后重试，或直接手动输入"}

    # 模型偶尔会用 ``` 包裹
    if text.startswith("```"):
        text = text.strip("`").strip()

    if not text:
        return {"status": "no_text", "text": None, "model": VISION_MODEL, "error": None}
    return {"status": "ok", "text": text[:3000], "model": VISION_MODEL, "error": None}


def parse_recipe_image(image_bytes: bytes, mime: str = "image/jpeg",
                       api_key: str | None = None) -> dict:
    """拍照/截图识别方子：OCR 取文字 → 复用 parse_formula_text 抽药材+克重。

    返回 {
      "status": "ok" | "no_text" | "no_herbs" | "error",
      "text": str | None,                        # 识别出的原文（供用户核对）
      "herbs": [{name, grams, verified}],        # 已核对数据源的药材
      "rejected": [{name, reason}],
      "model": str,
      "error": str | None,
    }
    """
    ocr = extract_text_from_image(image_bytes, mime, api_key)
    if ocr["status"] != "ok":
        return {"status": ocr["status"], "text": None, "herbs": [], "rejected": [],
                "model": ocr["model"], "error": ocr["error"]}

    text = ocr["text"]
    parsed = parse_formula_text(text, api_key)
    if not parsed["ok"]:
        return {"status": "error", "text": text, "herbs": [], "rejected": [],
                "model": ocr["model"], "error": parsed.get("error")}

    # 对抽出的药名做形近字纠错（模型若已自行纠正则这步不触发，属双保险）
    herbs, corrections = [], []
    for h in parsed["herbs"]:
        fix = correct_herb_name(h["name"])
        if fix["corrected"]:
            corrections.append({"from": h["name"], "to": fix["name"]})
            h = {**h, "name": fix["name"]}
        herbs.append(h)

    # rejected 里的名字也试一次纠错，能救回来的就收进 herbs
    rejected = list(parsed["rejected"])
    for r in list(rejected):
        fix = correct_herb_name(r["name"])
        if fix["corrected"] and _name_exists_locally(fix["name"]):
            corrections.append({"from": r["name"], "to": fix["name"]})
            herbs.append({"name": fix["name"], "grams": None, "verified": True})
            rejected.remove(r)

    # 原文对照：OCR 原文里出现、但和最终药名不一致的片段，也要告诉用户
    # （抽取模型常常自己就把「金银化」认成「金银花」，这些隐含纠正同样要透明）
    final_names = {h["name"] for h in herbs} | {h["name"][:-1] for h in herbs if len(h["name"]) > 2}
    known_froms = {c["from"] for c in corrections}
    for h in herbs:
        target = h["name"]
        # 在原文里找与目标名长度相同、只差一个字的片段
        for i in range(len(text) - len(target) + 1):
            frag = text[i:i + len(target)]
            if not all('\u4e00' <= ch <= '\u9fff' for ch in frag):
                continue
            if frag == target or frag in final_names or frag in known_froms:
                continue
            if correct_herb_name(frag)["name"] in (target, target[:-1]):
                corrections.append({"from": frag, "to": target})
                known_froms.add(frag)
                break

    # 抽到文字但一味药都没验证通过 → 明确区分「没认到字」和「有字但没药」
    if not herbs:
        return {"status": "no_herbs", "text": text, "herbs": [],
                "rejected": rejected, "corrections": corrections,
                "model": ocr["model"], "error": None}

    return {"status": "ok", "text": text, "herbs": herbs,
            "rejected": rejected, "corrections": corrections,
            "model": ocr["model"], "error": None}


# ---------- OCR 错字纠正（解决「认错一个字，后面全错」） ----------
# 动机：OCR 把「金银花」认成「金银化」时，后续流程会把它当成一个不存在的药材，
# 进而去联网搜「金银化」，整条链路结果全是错的。
# 做法：用本地词表（105 味正名/别名 + SymMap 703 味）做**受限编辑距离**纠错，
# 只在距离足够近且候选唯一时才纠正，并把原文与纠正结果一并返回给用户核对。
#
# 安全性：
#  - 距离阈值 1（2 字名）或 2（3 字及以上），避免把不相干的药纠到一起
#  - 多个候选距离相同时**不纠正**（歧义），交给人判断
#  - 只纠正「词表里没有」的名字；已在词表里的原样保留
#  - 纠正结果标注出来，前端必须显示「原文 → 纠正」让用户确认

# OCR 形近字映射（只收录实测确认的错字对）
#
# 为什么需要：编辑距离分不出「甘革 → 甘草/甘松/甘遂」（距离都是 1）。加入形近字
# 权重后，只有「字形确实接近」的候选才能胜出，消除歧义。
#
# 收录原则（严格遵守 AGENTS.md §2.5）：
#   - 每条都必须来自**真实 OCR 错误样本**，实测记录在案
#   - 不凭主观想象添加「看起来像」的字对
#   - 新增条目要在注释里写明来源与日期
#
# 当前来源：2026-11-06 本机 RapidOCR/视觉模型对手写与模糊图的实际错例。

CONFUSABLE_PAIRS = [
    # (错字, 正字)  —— 2026-11-06 实测：合成劣化图 OCR 错例 + 中药材常识混淆
    ("化", "花"),   # 金银化 → 金银花
    ("札", "杞"),   # 枸札 → 枸杞
    ("簿", "薄"),   # 簿荷 → 薄荷
    ("革", "草"),   # 甘革 → 甘草
    ("各", "冬"),   # 麦各 → 麦冬
    ("茂", "芪"),   # 黄茂 → 黄芪
    ("获", "茯"),   # 获苓 → 茯苓
    ("名", "明"),   # 决名子 → 决明子
    ("查", "楂"),   # 山查 → 山楂
    ("氏", "芪"),   # 黄氏 → 黄芪
    ("令", "苓"),   # 茯令 → 茯苓
    ("己", "杞"),   # 枸己 → 枸杞
    ("构", "枸"),   # 构杞 → 枸杞
    ("鞠", "菊"),   # 鞠花 → 菊花
    ("阵", "陈"),   # 阵皮 → 陈皮
    ("曷", "葛"),   # 曷根 → 葛根
    ("跟", "根"),   # 葛跟 → 葛根
    ("只", "枳"),   # 只壳 → 枳壳
    ("勺", "芍"),   # 勺药 → 芍药
    ("漆", "膝"),   # 牛漆 → 牛膝
    ("午", "牛"),   # 午膝 → 牛膝
    ("羌", "姜"),   # 羌活/生姜混淆（双向都可能，按常见写反处理）
    ("付", "附"),   # 香付 → 香附
    ("朮", "术"),   # 白朮 → 白术（繁体/异体）
]

# 单字 → 可接受的形近替换集合（双向、对称）
def build_confusable_map() -> dict:
    graph: dict[str, set[str]] = {}
    for wrong, right in CONFUSABLE_PAIRS:
        graph.setdefault(wrong, set()).add(right)
        graph.setdefault(right, set()).add(wrong)
    return {k: frozenset(v) for k, v in graph.items()}

_correction_vocab_cache = None


def _correction_vocab() -> list[str]:
    """构建纠错词表：本地库正名+别名 + SymMap 正名（懒加载一次）"""
    global _correction_vocab_cache
    if _correction_vocab_cache is not None:
        return _correction_vocab_cache
    vocab = set()
    try:
        for name, rec in _kb_herb_dict().items():
            vocab.add(name)
    except Exception:
        pass
    try:
        vocab |= set(_symmap_dict().keys())
    except Exception:
        pass
    # 只保留 2-6 个汉字的词条，过滤掉长串别名
    _correction_vocab_cache = sorted(
        n for n in vocab if 2 <= len(n) <= 6 and all('\u4e00' <= ch <= '\u9fff' for ch in n))
    return _correction_vocab_cache


def _weighted_distance(a: str, b: str, confusable: dict) -> int:
    """形近字加权的编辑距离。
    完全不同的字记 1；若两字互为形近字（如 革/草、札/杞），记 0.5 而不是 1。
    这样「甘革→甘草」的距离(0.5) 会小于「甘革→甘松」(1)，从而在歧义中胜出。
    返回值 ×2 取整以保持整数比较（0.5 的粒度）。"""
    if a == b:
        return 0
    if abs(len(a) - len(b)) > 2:
        return 999

    def sub_cost(ca, cb):
        if ca == cb:
            return 0
        return 1 if cb in confusable.get(ca, ()) else 2   # 形近=1, 不同=2（即 0.5/1.0 的两倍）

    prev = [2 * i for i in range(len(b) + 1)]
    for i, ca in enumerate(a, 1):
        cur = [2 * i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 2,        # 删除
                           cur[j - 1] + 2,     # 插入
                           prev[j - 1] + sub_cost(ca, cb)))  # 替换
        prev = cur
    return prev[-1]


def correct_herb_name(name: str) -> dict:
    """纠正 OCR 认错的药材名。

    返回 {
      "name": str,          # 纠正后的名字（无纠正时等于原名）
      "original": str,      # 原始识别结果
      "corrected": bool,
      "reason": str | None, # 纠正依据
    }
    只在「词表里没有」且「有唯一最优候选」时纠正；有歧义一律不猜。
    """
    name = (name or "").strip()
    if not name:
        return {"name": name, "original": name, "corrected": False, "reason": None}

    vocab = _correction_vocab()
    if name in set(vocab):
        return {"name": name, "original": name, "corrected": False, "reason": None}

    confusable = build_confusable_map()

    # 第一优先：同长度匹配（形近字纠正）。「获苓」→「茯苓」、「甘革」→「甘草」
    # 必须在这里先判定，否则会被「茯苓皮」「山楂叶」这类多一个字的词条抢走。
    best, best_cost, ties = None, 999, 0
    for cand in vocab:
        if len(cand) != len(name):
            continue
        c = _weighted_distance(name, cand, confusable)
        if c < best_cost:
            best, best_cost, ties = cand, c, 1
        elif c == best_cost:
            ties += 1
    # 只接受「形近字替换」造成的差异（cost 恰好 1）。cost 为 2 说明是毫不相干的
    # 两个字被硬换掉（如 桂圆→桂枝，圆与枝毫无字形关系），属瞎猜，拒绝。
    if best and best_cost == 1 and ties == 1:
        return {"name": best, "original": name, "corrected": True,
                "reason": f"疑似识别错误，已纠正为「{best}」"}

    # 第二优先：省字匹配。「枸札」→「枸杞子」这类口语省字，
    # 按长度升序取第一个命中，确保短词优先。
    for cand in sorted((v for v in vocab if len(v) == len(name) + 1), key=len):
        head = cand[:-1]
        if _weighted_distance(name, head, confusable) <= 1:
            return {"name": cand, "original": name, "corrected": True,
                    "reason": f"疑似识别错误，已纠正为「{cand}」"}

    # 第三优先：长度差 1-2 的通用匹配。
    # 只接受「每处差异都是形近字替换或多/少一个字」的情况：
    # 用纯编辑距离会算出 cost 2/4 的瞎猜（桂圆→桂枝），一律拒绝。
    best, best_cost, ties = None, 999, 0
    for cand in vocab:
        len_gap = abs(len(cand) - len(name))
        if len_gap > 2:
            continue
        c = _weighted_distance(name, cand, confusable)
        # 允许的代价上限 = 每处形近替换(1) + 每处增删(2)
        if c > len_gap * 2 + 1:
            continue
        if c < best_cost:
            best, best_cost, ties = cand, c, 1
        elif c == best_cost:
            ties += 1

    if best and ties == 1:
        return {"name": best, "original": name, "corrected": True,
                "reason": f"疑似识别错误，已纠正为「{best}」"}
    return {"name": name, "original": name, "corrected": False, "reason": None}
