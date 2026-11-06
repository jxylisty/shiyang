# -*- coding: utf-8 -*-
"""
2026-11-05 药食同源目录扩容灌库脚本（herb.ac.cn → shiyang.db）

对应 docs/数据扩容方案_2026-11-05.md 的 D3/D4 交付物；落位规则严格执行
docs/数据库设计文档.md §6「2026-11-05 扩容 schema 增量」：
  - herb.id = HERB ID 原样（如 HERB003070），herb.name = 目录正名（如「枣」）
  - compound.id = HBIN ID，预测列（prob_cctcm/radar_*/ad_*/chembl_* 等）一律 NULL
  - target.gene = HBTAR gene name，target_type/species = '未知(herb.ac.cn)'
  - 新药材成分关联写 rel_herb_compound（v1）；v2/v3、recipe_*、compound_map、
    herb_compound_content、rel_recipe_material 一律不动
  - compound_count 灌库后按 v1 表全量重算；target_count 按 rel_compound_target 全量重算
    （与 scripts/check_consistency.py 的既有口径一致，2026-11-05 实测存量 0 不一致）

流程：
  1) 调 scripts/_migrate_20261105.migrate() 完成 schema 迁移（幂等，含时间戳备份）
  2) 采集：search_api 精确命中（候选行第3列==期望名，不猜不模糊匹配）→ detail_api
     （响应顶层 dict）→ 每个成分 detail_api(label=Ingredient) 取 SMILES/MW/
     ingredient_target（成分-靶点关联只存在于成分详情，无法用药材级数据替代，
     故全量采集不裁剪）。全部结果落 data/cache/herb_ingest_20261105.json
     （增量写盘，中断后重跑自动续传，不再打已完成的 API）
  3) 写库（单事务）：herb/compound/target 按主键先查后插；关联按唯一键先查后插；
     存量已覆盖行（目录项名/异名命中现库 34 味）只补标 added_batch/source/reference_url，
     不新插行、不挂新成分；结束时全量重算 compound_count/target_count 并打印行数对比

数据真实边界（最高优先级，违反即宁缺勿滥）：
  - 不编造任何 ID/名称/数值：search 无精确命中即跳过并记录（如「蝮蛇」HERB 无条目，
    2026-11-05 实测 search(蝮蛇)/search(蛇) 均无精确命中）；网络失败 ≠ 无条目，
    网络失败中止本轮（缓存已落盘），不落 skip
  - 模型预测列不填（新成分在模型输入域外，跑了就是编造）
  - rel_compound_target.activity_* 全 NULL：HBTAR 的 P-value/FDR 是富集统计量，
    不是 IC50/Ki 类活性值，塞进 activity_value 会伪造活性数据
  - reference 口径（实测：成分级 ingredient_target 无 P 列，P/FDR 仅存在于药材级
    herb_target）：gene 命中该药材 herb_target 时写 "P=<值>; FDR_BH=<值> (herb-level …)"；
    未命中时写 "P=NA; FDR_BH=NA (ingredient-level …)"，不挪用药材级统计量冒充成分级
  - 性味归经：SymMap 中文值（properties_cn/meridians_cn）优先；SymMap 未收录时把 HERB
    英文 Properties/Meridians 按「药典术语固定对照表」翻译（见 GLOSSARY_*，属术语对照
    非机翻自由文本）；未识别术语丢弃并计数；两者皆无则留空
  - 槐米与槐花在 HERB 共用同一条目（HERB002472，2026-11-05 实测 search「槐米」无结果）：
    归属规则 = 谁的目录名与 HERB 条目中文名一致谁占 HERB ID 行（槐花），
    另一方（槐米）按本库既有 imp: 惯例落 imp:槐米 行，数据镜像自 HERB002472，
    source 如实记录 herb.ac.cn HERB002472，alias 注明共用关系

用法：
  python -X utf8 scripts/import_herbs_20261105.py                 # 完整采集+灌库
  python -X utf8 scripts/import_herbs_20261105.py --db PATH       # 指定库（试跑用副本）
  python -X utf8 scripts/import_herbs_20261105.py --cache PATH    # 指定采集缓存
  python -X utf8 scripts/import_herbs_20261105.py --limit N       # 只采前 N 味新药材（调试）
  python -X utf8 scripts/import_herbs_20261105.py --max-ingredients M   # 每味成分详情上限（调试）
  调试参数仅供小规模验证流程；用了它们本轮计划不冻结、不会写库结论性变更之外的数据，
  完整灌库必须不带调试参数重跑（报告会写清实际口径）。
"""
import argparse
import json
import re
import sqlite3
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _cache_seed import ensure_cache  # noqa: E402

DEFAULT_DB = ROOT / "data" / "shiyang.db"
DEFAULT_CACHE = ensure_cache(ROOT, "herb_ingest_20261105")
CATALOG_PATH = ROOT / "data" / "food_homology_catalog.json"
SYMMAP_PATH = ROOT / "data" / "symmap_smhb_v2.json"

API_URL = "http://herb.ac.cn/chedi/api/"
BATCH = 20261105
REQUEST_TIMEOUT = 30      # 单请求超时（秒）
REQUEST_RETRIES = 2       # 失败重试次数
RETRY_BACKOFF = 2.0       # 重试退避（秒）
SLEEP_BETWEEN = 0.45      # 请求间隔下限（数据源要求 >=0.4s）
MAX_CONSECUTIVE_FAILS = 12  # 连续失败熔断，保护缓存与对方服务
TERMINAL_STATUS = ("existing", "existing_covered", "new", "skip")

# ---------------------------------------------------------------------------
# 正名映射（2026-11-05 实测：以下 11 味直查无精确命中，须按映射正名检索）
# 蝮蛇特殊：HERB 无条目，按 SKIP_PROBES 探测（仍要求精确命中）后跳过并如实记录
# ---------------------------------------------------------------------------
NAME_MAP = {
    "代代花": "玳玳花",
    "白扁豆花": "扁豆花",
    "枣": "大枣",
    "姜": "生姜",
    "黄芥子": "芥子",
    "紫苏籽": "紫苏子",
    "黑胡椒": "胡椒",
    "槐米": "槐花",
    "鲜白茅根": "白茅根",
    "鲜芦根": "芦根",
    "藿香": "广藿香",
}
SKIP_PROBES = {"蝮蛇": ["蛇"]}  # 兜底探测词；命中标准仍是「候选中文名==蝮蛇」，不许硬凑

# ---------------------------------------------------------------------------
# HERB 英文性味/归经 → 中国药典术语固定对照表（术语对照，非机翻自由文本）
# 用途：仅当 SymMap 未收录该药材时，把 HERB summary 的 Properties/Meridians 落库；
#       未识别的术语丢弃并计数（宁缺勿滥），不会把 unrecognized 词硬翻
# ---------------------------------------------------------------------------
NATURE_EN = {
    "cold": "寒", "minor cold": "微寒", "slightly cold": "微寒",
    "hot": "热", "great heat": "大热",
    "warm": "温", "slightly warm": "微温", "minor warm": "微温",
    "cool": "凉", "slightly cool": "微凉", "neutral": "平",
}
FLAVOR_EN = {
    "sweet": "甘", "bitter": "苦", "pungent": "辛", "acrid": "辛",
    "sour": "酸", "salty": "咸", "tasteless": "淡", "bland": "淡",
    "astringent": "涩",
}
MERIDIAN_EN = {
    "lung": "肺", "large intestine": "大肠", "stomach": "胃", "spleen": "脾",
    "heart": "心", "small intestine": "小肠", "bladder": "膀胱", "kidney": "肾",
    "pericardium": "心包", "liver": "肝", "gallbladder": "胆",
    "triple burner": "三焦", "triple energizer": "三焦", "sanjiao": "三焦",
}
NATURE_CHARS = set("寒热温凉平")
FLAVOR_CHARS = set("甘苦酸辛咸淡涩")

COUNTED_TABLES = ["herb", "compound", "target",
                  "rel_herb_compound", "rel_compound_target"]


class CircuitBreak(RuntimeError):
    """连续失败熔断（区别于单条失败：熔断必须中止整轮，不能被逐条 except 吞掉）。"""


def log(msg: str) -> None:
    print(msg, flush=True)


def cell_val(x):
    """HERB 单元格可能是 {'style':…,'title':…} 结构，取 title；否则原样返回。"""
    if isinstance(x, dict):
        return x.get("title")
    return x


def parse_properties_cn(prop: str):
    """SymMap properties_cn（如「辛,苦,温,有小毒」）拆成 (nature, flavor)。

    按字集分类：含寒热温凉平的 token 记 nature（保留 微/大 前缀，如「微寒」），
    含甘苦酸辛咸淡涩的记 flavor；其余 token（如「有小毒」）非性味，丢弃。
    输出格式与本库存量一致：nature='微温'，flavor='酸,甘'（半角逗号连接）。
    """
    nature, flavor = [], []
    for tok in re.split(r"[,，、;；/\s]+", prop or ""):
        if not tok:
            continue
        if any(ch in NATURE_CHARS for ch in tok):
            nature.append(tok)
        elif any(ch in FLAVOR_CHARS for ch in tok):
            flavor.append(tok)
    return ",".join(dict.fromkeys(nature)) or None, ",".join(dict.fromkeys(flavor)) or None


def _gloss_translate(raw: str, exact_map: dict, all_map: dict, stats: dict) -> list:
    """按固定对照表翻译英文术语串：精确匹配优先，其次最长术语包含匹配；识别不了丢弃。"""
    out = []
    for tok in re.split(r"[;；,，]", raw or ""):
        t = tok.strip().lower()
        if not t:
            continue
        if t in exact_map:
            out.append(exact_map[t])
            continue
        hit = next((k for k in sorted(all_map, key=len, reverse=True) if k in t), None)
        if hit is None:
            stats["en_unrecognized"] = stats.get("en_unrecognized", 0) + 1
            continue
        out.append(all_map[hit])
    return out


def parse_properties_en(prop: str, stats: dict):
    """HERB Properties（如 'Minor cold; Bitter'）→ (nature, flavor)，固定对照表翻译。"""
    all_map = {**FLAVOR_EN, **NATURE_EN}
    toks = _gloss_translate(prop, {**NATURE_EN, **FLAVOR_EN}, all_map, stats)
    nature = [t for t in toks if any(ch in NATURE_CHARS for ch in t)]
    flavor = [t for t in toks if any(ch in FLAVOR_CHARS for ch in t)]
    return ",".join(dict.fromkeys(nature)) or None, ",".join(dict.fromkeys(flavor)) or None


def parse_meridians_en(mer: str, stats: dict):
    """HERB Meridians（如 'Large Intestine; Liver'）→ '大肠,肝'，固定对照表翻译。"""
    return ",".join(dict.fromkeys(
        _gloss_translate(mer, MERIDIAN_EN, MERIDIAN_EN, stats))) or None


class Ingestor:
    """herb.ac.cn 采集器：带重试/节流/熔断，结果增量写入缓存文件。"""

    def __init__(self, cache_path: Path):
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json"})
        self.cache_path = cache_path
        self.cache = {
            "meta": {"api": API_URL, "batch": BATCH, "stats": {}},
            "plan": None,       # 目录项解析结果（全部到达终态后才冻结复用）
            "herbs": {},        # HERB ID -> 药材级提取数据
            "ingredients": {},  # HBIN ID -> 成分级提取数据（仅成功项）
            "existing": {},     # 现库 herb id -> {item, herb_id, search_term}
            "failures": {"herbs": {}, "ingredients": {}},
        }
        if cache_path.exists():
            try:
                old = json.loads(cache_path.read_text(encoding="utf-8"))
                if isinstance(old, dict) and "herbs" in old:
                    self.cache.update(old)
                    log(f"[缓存] 已加载 {cache_path}（herbs={len(self.cache['herbs'])}, "
                        f"ingredients={len(self.cache['ingredients'])}），重跑只补缺口")
            except (json.JSONDecodeError, OSError) as e:
                log(f"[缓存] 旧缓存损坏（{e}），重建")
        self.consecutive_fails = 0
        self._dirty = False

    # ---------- 基础请求 ----------
    def post(self, payload: dict):
        r = self.session.post(API_URL, data=json.dumps(payload).encode("utf-8"),
                              timeout=REQUEST_TIMEOUT)
        r.raise_for_status()
        time.sleep(SLEEP_BETWEEN)  # 节流：请求间隔 >=0.4s
        return r.json()

    def post_retry(self, payload: dict, what: str):
        """带 2 次重试/2s 退避的请求；连续失败超限熔断（缓存已落盘，可续跑）。"""
        last_err = None
        for attempt in range(1 + REQUEST_RETRIES):
            try:
                res = self.post(payload)
                self.consecutive_fails = 0
                self.cache["meta"]["stats"]["requests"] = \
                    self.cache["meta"]["stats"].get("requests", 0) + 1
                return res
            except (requests.RequestException, ValueError) as e:
                last_err = e
                self.consecutive_fails += 1
                if attempt < REQUEST_RETRIES:
                    time.sleep(RETRY_BACKOFF)
        if self.consecutive_fails >= MAX_CONSECUTIVE_FAILS:
            raise CircuitBreak(
                f"连续 {self.consecutive_fails} 次请求失败（{what}: {last_err}），"
                f"熔断中止。已采集数据在 {self.cache_path}，排除网络/服务问题后重跑可续传。")
        raise RuntimeError(f"{what} 请求失败（重试 {REQUEST_RETRIES} 次后）: {last_err}")

    # ---------- 缓存 ----------
    def save(self):
        if not self._dirty:
            return
        self.cache["meta"]["updated_at"] = datetime.now().isoformat(timespec="seconds")
        self.cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.cache_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.cache, ensure_ascii=False, separators=(",", ":")),
                       encoding="utf-8")
        tmp.replace(self.cache_path)
        self._dirty = False

    def mark(self):
        self._dirty = True

    # ---------- API 封装 ----------
    def search_exact(self, term: str, expect: str):
        """search_api 精确命中：候选行（res_data[1:]，[0] 为表头）第 3 列中文名==expect。

        命中返回 {herb_id, pinyin, cn, en}；无命中返回 None（不猜、不模糊匹配）。
        网络失败抛 RuntimeError——网络失败 ≠ 无条目，由调用方中止本轮，绝不落成 skip。
        """
        res = self.post_retry({"func_name": "search_api", "keyword": term, "label": "Herb"},
                              f"search({term})")
        rows = (res or {}).get("res_data") or []
        for row in rows[1:]:
            if isinstance(row, list) and len(row) >= 3 and row[2] == expect:
                return {
                    "herb_id": cell_val(row[0]),
                    "pinyin": row[1] if len(row) > 1 else None,
                    "cn": row[2],
                    "en": row[3] if len(row) > 3 else None,
                }
        return None

    def herb_detail(self, herb_id: str) -> dict:
        """detail_api（Herb）。注意：响应是顶层 dict，无 res_data 包裹（2026-11-05 实测）。"""
        res = self.post_retry({"func_name": "detail_api", "key_id": herb_id,
                               "label": "Herb", "v": herb_id}, f"detail({herb_id})")
        if not isinstance(res, dict):
            raise RuntimeError(f"detail({herb_id}) 响应非 dict")
        return res

    def ingredient_detail(self, hbin: str) -> dict:
        res = self.post_retry({"func_name": "detail_api", "key_id": hbin,
                               "label": "Ingredient", "v": hbin}, f"ingredient({hbin})")
        if not isinstance(res, dict):
            raise RuntimeError(f"ingredient({hbin}) 响应非 dict")
        return res


# ---------------------------------------------------------------------------
# 解析：HERB 响应 → 缓存提取结构
# ---------------------------------------------------------------------------
HERB_SUMMARY_KEYS = {  # summary 表头 -> 缓存字段
    "Herb id": "herb_id", "Herb pinyin name": "pinyin", "Herb Chinese name": "cn",
    "Herb English name": "en", "Herb Latin name": "latin",
    "Properties": "properties_en", "Meridians": "meridians_en",
    "Function": "function_en", "Indication": "indication_en",
    "Therapeutic class": "class_en", "Therapeutic class (Chinese)": "class_cn",
    "Use part": "use_part", "Dosage": "dosage", "Toxicity": "toxicity",
    "Contraindication": "contraindication",
}


def parse_herb_detail(det: dict) -> dict:
    """从 herb 详情提取写库所需字段；herb_ingredient/herb_target 只留数据行（行首为 dict）。"""
    summ = det.get("summary") or []
    s = {}
    if len(summ) >= 2 and isinstance(summ[0], list) and isinstance(summ[1], list):
        for h, v in zip(summ[0], summ[1]):
            key = HERB_SUMMARY_KEYS.get(str(h))
            if key:
                s[key] = cell_val(v)

    ingredients, seen = [], set()
    dup_ing = 0
    for row in det.get("herb_ingredient") or []:
        if not (isinstance(row, list) and row and isinstance(row[0], dict) and row[0].get("title")):
            continue  # 表头行或异常行
        hbin = row[0]["title"]
        if hbin in seen:
            dup_ing += 1
            continue
        seen.add(hbin)
        ingredients.append([hbin, row[1] if len(row) > 1 else None])

    herb_targets, tseen = [], set()
    dup_tgt = 0
    for row in det.get("herb_target") or []:
        if not (isinstance(row, list) and len(row) >= 4 and isinstance(row[0], dict)):
            continue
        gene = row[1]
        if not gene:
            continue
        if gene in tseen:
            dup_tgt += 1
            continue
        tseen.add(gene)
        herb_targets.append([gene, row[2], row[3]])

    s["ingredients"] = ingredients
    s["herb_targets"] = herb_targets
    s["dup_ingredient_rows"] = dup_ing
    s["dup_target_rows"] = dup_tgt
    return s


def parse_ingredient_detail(det: dict) -> dict:
    """成分详情 → {name, smiles, mw, targets: [[gene, sources_str]]}。

    实测 ingredient_target 列 = ['Target id','Target name','Database sources']，
    无 P/FDR 列（P/FDR 仅在药材级 herb_target）——见模块 docstring 的 reference 口径。
    """
    summ = det.get("summary") or []
    d = {}
    if len(summ) >= 2 and isinstance(summ[0], list) and isinstance(summ[1], list):
        d = {str(h): v for h, v in zip(summ[0], summ[1])}
    mw = None
    raw_mw = cell_val(d.get("Molecule weight"))
    if raw_mw not in (None, ""):
        try:
            mw = float(raw_mw)
        except (TypeError, ValueError):
            mw = None
    targets = []
    for row in det.get("ingredient_target") or []:
        if not (isinstance(row, list) and len(row) >= 2 and isinstance(row[0], dict)):
            continue
        gene = row[1]
        if not gene:
            continue
        srcs = row[2] if len(row) > 2 else None
        if isinstance(srcs, list):
            src_str = "; ".join(filter(None, (cell_val(c) for c in srcs)))
        elif srcs:
            src_str = str(srcs)
        else:
            src_str = ""
        targets.append([gene, src_str or None])
    smile_raw = cell_val(d.get("Molecule smile"))
    smile = str(smile_raw).strip() if smile_raw not in (None, "") else None
    # "Not Available" 等占位符不算 SMILES；再做字符白名单校验（宁缺勿滥，不把脏值入库）
    if smile and (smile.lower() in ("not available", "n/a", "na", "none", "null")
                  or not re.fullmatch(r"[A-Za-z0-9@+\-\[\]\(\)=#$%/.\\]+", smile)):
        smile = None
    return {
        "name": cell_val(d.get("Ingredient name")),
        "smiles": smile,
        "mw": mw,
        "targets": targets,
    }


# ---------------------------------------------------------------------------
# SymMap 查找（惯例对齐 backend/app/services/herb_service.py：精确→前缀剥离→别名）
# ---------------------------------------------------------------------------
def symmap_lookup(sm: dict, candidates) -> dict | None:
    cands = [c for c in candidates if c]
    for n in cands:
        if n in sm:
            return sm[n]
    for n in cands:  # 前缀剥离：鲜/干/生/炒/炙/制（鲜芦根→芦根）
        for pre in ("鲜", "干", "生", "炒", "炙", "制"):
            if n.startswith(pre) and len(n) > len(pre) + 1 and n[len(pre):] in sm:
                return sm[n[len(pre):]]
    for n in cands:  # SymMap alias 字段反查
        for data in sm.values():
            aliases = (data.get("alias") or "")
            if n in [a.strip() for a in aliases.split(",") if a.strip()]:
                return data
    return None


# ---------------------------------------------------------------------------
# 计划：目录项 → 现库判定（existing / new）
# ---------------------------------------------------------------------------
def build_plan(conn: sqlite3.Connection, items: list) -> list:
    db_names = {r[0]: r[1] for r in conn.execute("SELECT name, id FROM herb")}
    plan = []
    for item in items:
        name = item["name"]
        if name in db_names:
            plan.append({**item, "status": "existing", "db_id": db_names[name],
                         "match_name": name})
            continue
        alias_hit = next(((a, db_names[a]) for a in item.get("aliases") or [] if a in db_names),
                         None)
        if alias_hit:
            plan.append({**item, "status": "existing", "db_id": alias_hit[1],
                         "match_name": alias_hit[0]})
            continue
        plan.append({**item, "status": "new", "match_name": name})
    return plan


def search_terms_for(item: dict) -> list:
    """检索词级联：库内命中名 → 原名 → 正名映射 → 目录异名 → 蝮蛇类兜底探测词。"""
    terms, seen = [], set()
    for t in ([item.get("match_name"), item["name"], NAME_MAP.get(item["name"]),
               *(item.get("aliases") or []), *SKIP_PROBES.get(item["name"], [])]):
        if t and t not in seen:
            seen.add(t)
            terms.append(t)
    return terms


# ---------------------------------------------------------------------------
# 采集阶段
# ---------------------------------------------------------------------------
def resolve_plan(ing: Ingestor, plan: list, limit: int | None):
    """检索解析：existing 两遍走（先存量后新增，避免占位竞态），全终态才冻结计划。

    冻结前任何一轮失败/中断，下次重跑整个检索阶段（约 140 次轻量请求，成本低），
    已抓到的 herb/ingredient 详情缓存不受影响。
    """
    # ---- 第一遍：存量行检索（拿 HERB ID 供补标 source 用）----
    for it in plan:
        if it["status"] != "existing":
            continue
        hit, term = None, None
        for t in search_terms_for(it):  # match_name（库内命中的名字）优先
            hit = ing.search_exact(t, t)
            if hit:
                term = t
                break
        ing.cache["existing"][it["db_id"]] = {
            "item": it["name"], "herb_id": hit["herb_id"] if hit else None,
            "search_term": term}
        it["herb_id"] = hit["herb_id"] if hit else None
        it["search_term"] = term
        if hit:
            log(f"[存量] {it['name']}（库内 {it['db_id']}）→ HERB {hit['herb_id']}（{term}）")
        else:
            log(f"[存量] {it['name']}（库内 {it['db_id']}）→ HERB 无精确命中，仅补标批次")
        ing.mark()

    existing_hids = {v["herb_id"] for v in ing.cache["existing"].values() if v["herb_id"]}

    # ---- 第二遍：新增药材检索（先全部拿到 hit，再按 HERB 条目分组定归属）----
    new_items = [it for it in plan if it["status"] == "new"]
    new_seen = 0
    for it in new_items:
        if limit is not None and new_seen >= limit:
            it["status"] = "deferred"  # 调试参数：超出部分本轮不采
            continue
        hit, term = None, None
        for t in search_terms_for(it):
            expect = it["name"] if t in SKIP_PROBES.get(it["name"], []) else t
            hit = ing.search_exact(t, expect)
            if hit:
                term = t
                break
        if hit is None:
            it["status"] = "skip"
            probes = "；".join(f"search({t}) 无精确命中" for t in search_terms_for(it))
            it["reason"] = f"HERB 无条目：{probes}（精确命中口径，不许硬凑）"
            log(f"[跳过] {it['name']}: {it['reason']}")
            ing.mark()
            continue
        new_seen += 1
        it["hit"] = hit
        it["search_term"] = term
        ing.mark()

    # 分组归属：同一 HERB 条目被多个目录项命中时（如槐米/槐花共用 HERB002472），
    # 目录名与条目中文名一致者占 HERB ID 行，其余按 imp: 惯例镜像落行
    groups = {}
    for it in new_items:
        hit = it.get("hit")
        if not hit:
            continue
        groups.setdefault(hit["herb_id"], []).append(it)
    for hid, members in groups.items():
        hit = members[0]["hit"]
        if hid in existing_hids:
            for it in members:
                it["status"] = "existing_covered"
                it["reason"] = f"检索命中 {hid}，与现库存量行同条目（不新插行）"
                log(f"[覆盖] {it['name']}: {it['reason']}")
            continue
        owner = next((m for m in members if m["name"] == hit["cn"]), members[0])
        for it in members:
            it["herb_id"] = hid
            if it is owner:
                claimed_note = ""
                if len(members) > 1:
                    others = "、".join(m["name"] for m in members if m is not owner)
                    claimed_note = f"（目录项 {others} 共用本条目，按 imp: 惯例镜像落行）"
                log(f"[新增] {it['name']} → {hid}（{it['search_term']}，条目名「{hit['cn']}」）"
                    f"{claimed_note}")
            else:
                it["imp"] = True
                it["mirror_of"] = owner["name"]
                it["reason"] = (f"与目录项「{owner['name']}」共用 HERB 条目 {hid}"
                                f"（条目中文名「{hit['cn']}」），按 imp: 惯例落行并注明共用关系")
                log(f"[共用] {it['name']}: {it['reason']}")


def collect(ing: Ingestor, plan: list, limit: int | None, max_ingredients: int | None):
    # ---- 1. 检索解析（计划冻结后复用，不重复检索）----
    if ing.cache.get("plan") is None:
        resolve_plan(ing, plan, limit)
        complete = all(it["status"] in TERMINAL_STATUS for it in plan)
        if complete:
            ing.cache["plan"] = plan
            ing.mark()
            log("[计划] 全部目录项到达终态，计划已冻结")
        else:
            log("[计划] 存在未完结节（--limit 调试或检索未完成），本轮计划不冻结，"
                "下次完整重跑会重新解析")
    else:
        plan = ing.cache["plan"]
        log("[计划] 复用缓存中的冻结计划（" + "；".join(
            f"{s}={sum(1 for p in plan if p['status']==s)}"
            for s in ("existing", "existing_covered", "new", "skip")) + "）")
        assert all(it["status"] in TERMINAL_STATUS for it in plan)
    ing.save()

    # ---- 2. 新药材详情采集 ----
    to_fetch = [it for it in plan if it["status"] == "new" and it.get("herb_id")]
    n_total = len(to_fetch)
    log(f"[采集] 需拉取药材详情 {n_total} 味")
    t0 = time.time()
    for i, it in enumerate(to_fetch, 1):
        hid = it["herb_id"]
        if hid in ing.cache["herbs"]:
            continue
        ing.cache["failures"]["herbs"].pop(hid, None)  # 上轮失败的本轮重试
        try:
            det = ing.herb_detail(hid)
            parsed = parse_herb_detail(det)
            parsed["search_term"] = it.get("search_term")
            parsed["item"] = it["name"]
            ing.cache["herbs"][hid] = parsed
            ing.mark()
        except CircuitBreak:
            ing.save()
            raise
        except RuntimeError as e:
            ing.cache["failures"]["herbs"][hid] = str(e)
            ing.mark()
            log(f"  [失败] {it['name']} {hid}: {e}")
            continue
        log(f"  [{i}/{n_total}] {it['name']} {hid}: 成分 {len(parsed['ingredients'])}, "
            f"药材级靶点 {len(parsed['herb_targets'])}, 累计 {time.time()-t0:.0f}s")
        if i % 5 == 0:
            ing.save()
    ing.save()

    # ---- 3. 成分详情采集（SMILES / MW / ingredient_target，全量不裁剪）----
    hbin_owner = {}
    for it in plan:
        if it["status"] == "new" and it.get("herb_id") in ing.cache["herbs"]:
            for hbin, _ in ing.cache["herbs"][it["herb_id"]]["ingredients"]:
                hbin_owner.setdefault(hbin, it["name"])
    todo = [h for h in hbin_owner if h not in ing.cache["ingredients"]]
    log(f"[采集] 需拉取成分详情 {len(todo)} 条（新药材唯一成分 {len(hbin_owner)}，"
        f"缓存已有 {len(ing.cache['ingredients'])}）")
    t0 = time.time()
    per_herb_count = {}
    for i, hbin in enumerate(todo, 1):
        owner = hbin_owner[hbin]
        if max_ingredients is not None and per_herb_count.get(owner, 0) >= max_ingredients:
            continue  # 调试上限：超限成分本轮不拉详情（compound 行仍入，SMILES/靶点为空）
        per_herb_count[owner] = per_herb_count.get(owner, 0) + 1
        try:
            ing.cache["ingredients"][hbin] = parse_ingredient_detail(ing.ingredient_detail(hbin))
            ing.mark()
        except CircuitBreak:
            ing.save()
            raise
        except RuntimeError as e:
            ing.cache["failures"]["ingredients"][hbin] = str(e)
            ing.mark()
        if i % 20 == 0:
            rate = i / max(time.time() - t0, 1)
            remain = (len(todo) - i) / max(rate, 0.01)
            log(f"  [成分 {i}/{len(todo)}] {rate:.1f} 条/s，预计剩余 {remain/60:.0f} 分钟")
            ing.save()
    ing.save()
    fails = len(ing.cache["failures"]["ingredients"])
    log(f"[采集] 成分详情完成：缓存成功 {len(ing.cache['ingredients'])}，失败累计 {fails}")


# ---------------------------------------------------------------------------
# 写库阶段（单事务）
# ---------------------------------------------------------------------------
def write_db(conn: sqlite3.Connection, ing: Ingestor, symmap: dict | None):
    cache = ing.cache
    plan = cache["plan"] or []
    res = {k: 0 for k in ("herb_new", "herb_updated", "herb_existing", "backfill",
                          "backfill_nohit", "compound_new", "compound_updated",
                          "target_new", "rhc_new", "rct_new", "rct_p", "rct_na")}

    def row_eq(row, vals) -> bool:
        return all(a == b for a, b in zip(row, vals))

    conn.execute("BEGIN")
    try:
        # ---- 1. 新药材行（含 imp: 共用条目行）----
        for it in plan:
            if it["status"] != "new":
                continue
            hid = it["herb_id"]
            base = cache["herbs"].get(hid) or {}
            row_id = f"imp:{it['name']}" if it.get("imp") else hid
            # SymMap 中文值优先，缺则按固定对照表翻译 HERB 英文（宁缺勿滥）
            sm = symmap_lookup(symmap, [it["name"], it.get("search_term"), base.get("cn"),
                                        *(it.get("aliases") or [])]) if symmap else None
            if sm and (sm.get("properties_cn") or sm.get("meridians_cn")):
                nature, flavor = parse_properties_cn(sm.get("properties_cn"))
                meridians = sm.get("meridians_cn")
                pinyin_col = sm.get("pinyin")
            else:
                stats = cache["meta"]["stats"]
                nature, flavor = parse_properties_en(base.get("properties_en"), stats)
                meridians = parse_meridians_en(base.get("meridians_en"), stats)
                pinyin_col = base.get("pinyin")
            fn_parts = []
            if base.get("function_en"):
                fn_parts.append(base["function_en"])
            if base.get("indication_en"):
                fn_parts.append(f"Indication: {base['indication_en']}")
            functions = " | ".join(fn_parts) or None
            alias_parts = [base.get("pinyin"), base.get("en")]
            if base.get("cn") and base.get("cn") != it["name"]:
                alias_parts.append(base["cn"])
            if it.get("imp"):
                mirror_name = it.get("mirror_of") \
                    or (cache["herbs"].get(hid) or {}).get("item") or hid
                alias_parts.append(f"与「{mirror_name}」同植物共用 HERB 条目 {hid}")
            alias = ", ".join([str(a) for a in alias_parts if a]) or None
            vals = (it["name"], pinyin_col, alias, cell_val(base.get("latin")),
                    cell_val(base.get("class_cn")), functions, nature, flavor, meridians,
                    cell_val(base.get("use_part")), cell_val(base.get("dosage")),
                    cell_val(base.get("toxicity")), cell_val(base.get("contraindication")),
                    it["batch"], f"herb.ac.cn {hid}",
                    f"http://herb.ac.cn/Detail/?v={hid}&label=Herb", BATCH)
            old = conn.execute(
                "SELECT name, pinyin, alias, latin_name, category, functions, nature, flavor,"
                " meridians, medicinal_part, dosage, toxicity, contraindication,"
                " food_catalog_batch, source, reference_url, added_batch FROM herb WHERE id=?",
                (row_id,)).fetchone()
            if old is None:
                conn.execute(
                    "INSERT INTO herb (id, name, pinyin, alias, latin_name, category, functions,"
                    " nature, flavor, meridians, medicinal_part, dosage, toxicity,"
                    " contraindication, compound_count, is_food_homology, food_catalog_batch,"
                    " source, reference_url, added_batch)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,1,?,?,?,?)", (row_id, *vals))
                res["herb_new"] += 1
            elif not row_eq(old, vals):
                conn.execute(
                    "UPDATE herb SET name=?, pinyin=?, alias=?, latin_name=?, category=?,"
                    " functions=?, nature=?, flavor=?, meridians=?, medicinal_part=?, dosage=?,"
                    " toxicity=?, contraindication=?, food_catalog_batch=?, source=?,"
                    " reference_url=?, added_batch=? WHERE id=?", (*vals, row_id))
                res["herb_updated"] += 1
            else:
                res["herb_existing"] += 1

        # ---- 2. 存量行补标（§6.3：只补 added_batch/source/reference_url，不新插行、不挂新成分）----
        for db_id, info in cache["existing"].items():
            hid = info.get("herb_id")
            vals = (f"herb.ac.cn {hid}", f"http://herb.ac.cn/Detail/?v={hid}&label=Herb", BATCH) \
                if hid else (None, None, BATCH)
            old = conn.execute("SELECT source, reference_url, added_batch FROM herb WHERE id=?",
                               (db_id,)).fetchone()
            if old is None:
                continue
            if not row_eq(old, vals):
                conn.execute("UPDATE herb SET source=?, reference_url=?, added_batch=? WHERE id=?",
                             (*vals, db_id))
                res["backfill" if hid else "backfill_nohit"] += 1

        # ---- 3. 成分行（id=HBIN，预测列不写即 NULL）----
        all_hbins = {}
        for it in plan:
            if it["status"] != "new" or not it.get("herb_id"):
                continue
            for hbin, iname in (cache["herbs"].get(it["herb_id"]) or {}).get("ingredients") or []:
                all_hbins.setdefault(hbin, iname)
        for hbin, list_name in all_hbins.items():
            det = cache["ingredients"].get(hbin)
            name = (det or {}).get("name") or list_name
            smiles = (det or {}).get("smiles")
            mw = (det or {}).get("mw")
            # target_count 不在此写：步骤 7 会按 rel_compound_target 全量重算（幂等关键，
            # 否则第二遍 None vs 重算值会误判 changed）
            old = conn.execute("SELECT name, smiles, mw FROM compound WHERE id=?",
                               (hbin,)).fetchone()
            vals = (name, smiles, mw)
            if old is None:
                conn.execute(
                    "INSERT INTO compound (id, name, smiles, mw, logp, target_count)"
                    " VALUES (?,?,?,?,NULL,NULL)", (hbin, *vals))
                res["compound_new"] += 1
            elif not row_eq(old, vals):
                conn.execute("UPDATE compound SET name=?, smiles=?, mw=? WHERE id=?",
                             (*vals, hbin))
                res["compound_updated"] += 1

        # ---- 4. 靶点行（gene 为主键；只插成分关联引用到的 gene，不造孤儿行）----
        all_genes = set()
        for det in cache["ingredients"].values():
            for gene, _ in det.get("targets") or []:
                all_genes.add(gene)
        known = {r[0] for r in conn.execute("SELECT gene FROM target")}
        for gene in sorted(all_genes):
            if gene in known:
                continue
            conn.execute("INSERT INTO target (gene, target_type, species) VALUES (?,?,?)",
                         (gene, "未知(herb.ac.cn)", "未知(herb.ac.cn)"))
            res["target_new"] += 1

        # ---- 5. 药材-成分关联（v1 表，UNIQUE(herb_id,compound_id)）----
        for it in plan:
            if it["status"] != "new" or not it.get("herb_id"):
                continue
            herb_row_id = f"imp:{it['name']}" if it.get("imp") else it["herb_id"]
            for hbin, _ in (cache["herbs"].get(it["herb_id"]) or {}).get("ingredients") or []:
                dup = conn.execute(
                    "SELECT 1 FROM rel_herb_compound WHERE herb_id=? AND compound_id=?",
                    (herb_row_id, hbin)).fetchone()
                if dup:
                    continue
                conn.execute("INSERT INTO rel_herb_compound (herb_id, compound_id) VALUES (?,?)",
                             (herb_row_id, hbin))
                res["rhc_new"] += 1

        # ---- 6. 成分-靶点关联（source_db='herb.ac.cn'，partial UNIQUE 幂等）----
        # P/FDR 口径：成分级 ingredient_target 无 P 列；gene 命中来源药材的 herb_target
        # 时记录该药材级富集统计量，未命中如实标 NA（见模块 docstring）
        for it in plan:
            if it["status"] != "new" or not it.get("herb_id"):
                continue
            pmap = {g: (p, f) for g, p, f in
                    (cache["herbs"].get(it["herb_id"]) or {}).get("herb_targets") or []}
            for hbin, _ in (cache["herbs"].get(it["herb_id"]) or {}).get("ingredients") or []:
                det = cache["ingredients"].get(hbin)
                if not det:
                    continue  # 无详情（失败/调试上限）→ 无成分级靶点可写
                for gene, src in det.get("targets") or []:
                    dup = conn.execute(
                        "SELECT 1 FROM rel_compound_target WHERE compound_id=? AND target_gene=?"
                        " AND source_db='herb.ac.cn'", (hbin, gene)).fetchone()
                    if dup:
                        continue
                    if gene in pmap:
                        p, f = pmap[gene]
                        ref = f"P={p}; FDR_BH={f} (herb-level stats of {it['herb_id']})"
                        res["rct_p"] += 1
                    else:
                        extra = f"; sources: {src}" if src else ""
                        ref = (f"P=NA; FDR_BH=NA (ingredient-level association; herb-level "
                               f"stats unavailable for {it['herb_id']}{extra})")
                        res["rct_na"] += 1
                    conn.execute(
                        "INSERT INTO rel_compound_target (compound_id, target_gene, activity_type,"
                        " activity_value, activity_unit, reference, source_db)"
                        " VALUES (?,?,NULL,NULL,NULL,?,'herb.ac.cn')", (hbin, gene, ref))
                    res["rct_new"] += 1

        # ---- 7. 计数全量重算（docs/数据库设计文档.md §6.3 口径）----
        conn.execute("""UPDATE herb SET compound_count =
            (SELECT COUNT(*) FROM rel_herb_compound WHERE herb_id = herb.id)""")
        conn.execute("""UPDATE compound SET target_count =
            (SELECT COUNT(*) FROM rel_compound_target WHERE compound_id = compound.id)""")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return res


# ---------------------------------------------------------------------------
# 报告
# ---------------------------------------------------------------------------
def report(conn: sqlite3.Connection, ing: Ingestor, before: dict, wres: dict):
    plan = ing.cache.get("plan") or []
    after = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in COUNTED_TABLES}
    log("\n=== 20261105 药食同源扩容灌库报告 ===")
    log("[计划] " + "；".join(
        f"{s}={sum(1 for p in plan if p['status']==s)}"
        for s in ("existing", "existing_covered", "new", "skip", "deferred")))
    for name, reason in [(p["name"], p.get("reason")) for p in plan if p["status"] == "skip"]:
        log(f"[跳过] {name}: {reason}")
    for name, reason in [(p["name"], p.get("reason")) for p in plan if p.get("imp")]:
        log(f"[共用条目] {name}: {reason}")

    new_herbs = [p for p in plan if p["status"] == "new"]
    with_source = conn.execute(
        "SELECT COUNT(*) FROM herb WHERE added_batch=? AND source IS NOT NULL"
        " AND reference_url IS NOT NULL", (BATCH,)).fetchone()[0]
    no_source = [r[0] for r in conn.execute(
        "SELECT name FROM herb WHERE added_batch=? AND (source IS NULL OR reference_url IS NULL)",
        (BATCH,))]
    log(f"[药材] 本轮新插 {wres['herb_new']}（更新 {wres['herb_updated']}，已一致 "
        f"{wres['herb_existing']}）；批次={BATCH} 且 source/reference_url 齐全 {with_source} 行"
        + (f"；缺 source: {no_source}" if no_source else ""))

    n_ing = len(ing.cache["ingredients"])
    with_smiles = sum(1 for d in ing.cache["ingredients"].values() if d.get("smiles"))
    ing_fails = len(ing.cache["failures"]["ingredients"])
    all_hbins = {h for p in new_herbs if p.get("herb_id")
                 for h, _ in (ing.cache["herbs"].get(p["herb_id"]) or {}).get("ingredients") or []}
    no_detail = max(len(all_hbins) - n_ing - ing_fails, 0)
    log(f"[成分] 本轮新插 {wres['compound_new']}（更新 {wres['compound_updated']}）；"
        f"SMILES 口径：新药材唯一成分 {len(all_hbins)} = 已取详情 {n_ing}（含 SMILES "
        f"{with_smiles}，详情缺 SMILES {n_ing - with_smiles}）+ 详情失败 {ing_fails} + "
        f"未取详情 {no_detail}" + ("（调试上限所致）" if no_detail else "（全量采集，无裁剪）"))
    log(f"[靶点] 本轮新插 {wres['target_new']}（target_type/species='未知(herb.ac.cn)'，"
        f"存量同名 gene 不覆盖）")
    log(f"[关联] rel_herb_compound +{wres['rhc_new']}（v1 表）；rel_compound_target "
        f"+{wres['rct_new']}（reference 含药材级 P 值 {wres['rct_p']} 条 / P=NA 如实标注 "
        f"{wres['rct_na']} 条；activity_* 全 NULL，source_db='herb.ac.cn'）")
    log(f"[存量补标] 拉到 HERB 条目 {wres['backfill']} 行（补 added_batch/source/reference_url），"
        f"未命中 {wres['backfill_nohit']} 行（仅补 added_batch）")
    log("[行数对比]")
    for t in COUNTED_TABLES:
        log(f"  {t}: {before[t]} -> {after[t]}（+{after[t]-before[t]}）")
    en_un = ing.cache["meta"]["stats"].get("en_unrecognized", 0)
    if en_un:
        log(f"[提示] HERB 英文性味/归经未识别术语 {en_un} 处已丢弃（宁缺勿滥）")


def main():
    ap = argparse.ArgumentParser(description="20261105 药食同源目录扩容灌库")
    ap.add_argument("--db", default=str(DEFAULT_DB))
    ap.add_argument("--cache", default=str(DEFAULT_CACHE))
    ap.add_argument("--limit", type=int, default=None,
                    help="只采集前 N 味新药材（调试用，正式灌库勿用）")
    ap.add_argument("--max-ingredients", type=int, default=None,
                    help="每味药材成分详情上限（调试用，正式灌库勿用）")
    args = ap.parse_args()
    db_path = Path(args.db)
    cache_path = Path(args.cache)

    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    items = catalog["items"]
    symmap = json.loads(SYMMAP_PATH.read_text(encoding="utf-8")) \
        if SYMMAP_PATH.exists() else None
    if symmap is None:
        log("[提示] SymMap 本地数据缺失，性味归经仅按 HERB 英文术语对照翻译")

    conn = sqlite3.connect(db_path, timeout=10)
    conn.execute("PRAGMA busy_timeout=5000")
    before = {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in COUNTED_TABLES}
    log(f"[现状] {db_path}：" + "，".join(f"{t}={before[t]}" for t in COUNTED_TABLES))

    # 1. schema 迁移（幂等，含时间戳备份）
    sys.path.insert(0, str(ROOT / "scripts"))
    from _migrate_20261105 import migrate
    mig = migrate(db_path)
    assert mig["row_consistent"]

    # 2. 采集（缓存增量，重跑不打已完成的 API；异常时也把已采数据落盘）
    ing = Ingestor(cache_path)
    try:
        if ing.cache.get("plan") is not None:
            plan = ing.cache["plan"]
        else:
            plan = build_plan(conn, items)
            log("[计划] " + "；".join(
                f"{s}={sum(1 for p in plan if p['status']==s)}"
                for s in ("existing", "new")))
        collect(ing, plan, args.limit, args.max_ingredients)
    except CircuitBreak as e:
        ing.save()
        log(f"\n[中止] {e}")
        conn.close()
        sys.exit(1)
    finally:
        ing.save()

    # 3. 写库（单事务）+ 计数重算
    if ing.cache.get("plan") is None:
        log("[中止] 计划未冻结（--limit 调试或检索未完成），不执行写库")
        conn.close()
        return
    wres = write_db(conn, ing, symmap)

    # 4. 报告
    report(conn, ing, before, wres)
    conn.close()
    log(f"\n[缓存] {cache_path}（{cache_path.stat().st_size:,} bytes）")


if __name__ == "__main__":
    main()
