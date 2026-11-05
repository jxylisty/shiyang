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
