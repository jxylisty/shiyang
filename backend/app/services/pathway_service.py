# -*- coding: utf-8 -*-
"""
通路富集服务（KEGG）——用 Enrichr 公开 API 给方子做通路富集。

数据流：recipe → top 成分(prob_cctcm>=0.7) → 人类蛋白靶点基因 → Enrichr KEGG_2021_Human → 通路

设计约束（写死防回归）：
- 只用人类蛋白靶点（target_type='Protein' AND species='Homo sapiens'）
- 基因数 < 3 不做富集（统计上无意义，直接返回 insufficient）
- 结果缓存进 recipe_pathway 表，运行时只读缓存；缓存缺失时才实时调 API
- API 不可达时返回 offline 状态 + 空结果，绝不抛 500（对外是健康参考站，不能因第三方挂掉而崩）
- 展示层必须标注"生物信息学推断"，与 A/B/C 证据分级中的 C 级一致
"""
import json
import sqlite3
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[3] / "data" / "shiyang.db"
ENRICHR = "https://maayanlab.cloud/Enrichr"
# 双库并行：GO BP 是主展示（词条贴合"炎症/氧化应激/代谢"等食养语境），
# KEGG 作辅助但要过滤疾病/癌症类词条（避免暗示疗效、触碰医疗红线）
LIBRARY_GO = "GO_Biological_Process_2023"
LIBRARY_KEGG = "KEGG_2021_Human"
MIN_PROB = 0.7
MIN_GENES = 3
MAX_PATHWAYS = 8
UA = "shiyang-research/0.2 (+https://github.com/; academic use)"

# KEGG 词条黑名单：疾病/癌症/感染类不做健康参考展示（红线：不暗示治疗）
_KEGG_BLOCKLIST = (
    "cancer", "carcinoma", "carcinogenesis", "leukemia", "lymphoma", "sarcoma",
    "melanoma", "hepatitis", "herpesvirus", "measles", "influenza", "tuberculosis",
    "malaria", "toxoplasmosis", "infection", "disease", "diabetic", "viral",
    "addiction", "cocaine", "alcoholism", "amyloid", "parkinson",
    "alzheimer", "huntington", "cardiomyopathy", "atherosclerosis",
)

# GO BP 术语 → 中文（按关键词映射，命中即译；未命中保留英文原文）
_GO_ZH = (
    ("inflammatory response", "炎症反应"),
    ("response to oxidative stress", "氧化应激反应"),
    ("response to reactive oxygen species", "活性氧反应"),
    ("response to cytokine", "细胞因子反应"),
    ("cytokine production", "细胞因子生成"),
    ("immune response", "免疫反应"),
    ("immune system process", "免疫系统过程"),
    ("apoptotic process", "凋亡过程"),
    ("apoptosis", "凋亡"),
    ("cell death", "细胞死亡"),
    ("response to hypoxia", "缺氧反应"),
    ("response to nutrient", "营养应答"),
    ("lipid metabolic process", "脂质代谢"),
    ("carbohydrate metabolic process", "糖代谢"),
    ("glucose", "葡萄糖代谢"),
    ("lipid transport", "脂质转运"),
    ("steroid", "类固醇代谢"),
    ("response to hormone", "激素应答"),
    ("signal transduction", "信号转导"),
    ("cell proliferation", "细胞增殖"),
    ("cell migration", "细胞迁移"),
    ("angiogenesis", "血管生成"),
    ("blood circulation", "血液循环"),
    ("vasodilation", "血管舒张"),
    ("wound healing", "创伤愈合"),
    ("response to wounding", "损伤应答"),
    ("response to bacterium", "细菌应答"),
    ("antimicrobial", "抗菌"),
    ("response to virus", "病毒应答"),
    ("response to stress", "应激反应"),
    ("response to toxic", "毒性物质应答"),
    ("xenobiotic", "外源物代谢"),
    ("drug", "药物代谢"),
    ("catabolic process", "分解代谢"),
    ("biosynthetic process", "合成代谢"),
    ("metabolic process", "代谢过程"),
    ("homeostasis", "稳态维持"),
    ("secretion", "分泌"),
    ("digestion", "消化"),
    ("response to food", "食物应答"),
    ("response to amino acid", "氨基酸应答"),
    ("muscle", "肌肉功能"),
    ("neuron", "神经功能"),
    ("synaptic", "突触传递"),
    ("sleep", "睡眠调节"),
    ("circadian", "昼夜节律"),
    ("behavior", "行为调节"),
    ("memory", "记忆"),
    ("response to pain", "疼痛应答"),
)


def _zh_term(term: str) -> str | None:
    low = term.lower()
    for key, zh in _GO_ZH:
        if key in low:
            return zh
    return None


NOTE = ("通路富集为生物信息学推断（Enrichr：GO 生物学过程 + KEGG），"
        "反映本方成分靶点集合的统计学富集趋势，不等同于体内疗效证据；"
        "疾病/癌症类 KEGG 通路已按健康参考口径过滤")


def _db(readonly=True):
    if readonly:
        conn = sqlite3.connect(f"file:{DB_PATH.as_posix()}?mode=ro", uri=True)
    else:
        conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def recipe_genes(rid: int) -> list[str]:
    """方子 Top 成分（入血概率>=0.7，取前 10 个）关联的人类蛋白靶点基因（去重）

    口径与 recipe_analysis.top_compounds 一致：只用 Top 成分而非全库成分，
    否则基因集过大（上百个）会让富集结果被"转录调控"这类泛化词条主导。
    """
    conn = _db()
    try:
        row = conn.execute("SELECT top_compounds FROM recipe_analysis WHERE recipe_id=?",
                           (rid,)).fetchone()
        names = []
        if row:
            names = [c["name"] for c in json.loads(row["top_compounds"] or "[]")][:10]
        if not names:
            return []
        ph = ",".join("?" * len(names))
        rows = conn.execute(
            f"SELECT DISTINCT rt.target_gene FROM rel_compound_target rt "
            f"JOIN target t ON t.gene=rt.target_gene "
            f"AND t.target_type='Protein' AND t.species='Homo sapiens' "
            f"JOIN compound c ON c.id=rt.compound_id "
            f"WHERE c.name IN ({ph})", names).fetchall()
        return [r["target_gene"] for r in rows if r["target_gene"]]
    finally:
        conn.close()


def _post_multipart(url: str, fields: dict) -> bytes:
    boundary = "----shiyangBoundary7MA4YWxk"
    body = ""
    for k, v in fields.items():
        body += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n"
                 f"{v}\r\n")
    body += f"--{boundary}--\r\n"
    req = urllib.request.Request(
        url, data=body.encode("utf-8"),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}",
                 "User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def _get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def enrich(genes: list[str]) -> dict:
    """调 Enrichr 做双库富集（GO BP 主 + KEGG 辅助）。返回 {status, pathways, n_genes}"""
    genes = list(dict.fromkeys(genes))
    if len(genes) < MIN_GENES:
        return {"status": "insufficient", "n_genes": len(genes), "pathways": [],
                "note": f"靶点基因少于 {MIN_GENES} 个，不做富集"}
    try:
        listed = json.loads(_post_multipart(
            f"{ENRICHR}/addList",
            {"list": "\n".join(genes), "description": "shiyang recipe enrichment"}))
        uid = listed["userListId"]

        def fetch(lib):
            res = _get_json(f"{ENRICHR}/enrich?"
                            + urllib.parse.urlencode({"userListId": uid,
                                                      "backgroundType": lib}))
            return res.get(lib) or []

        go_terms = fetch(LIBRARY_GO)
        kegg_terms = fetch(LIBRARY_KEGG)
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError,
            json.JSONDecodeError, TimeoutError, OSError):
        return {"status": "offline", "n_genes": len(genes), "pathways": [],
                "note": "通路富集服务暂时不可达，稍后重试"}

    def parse(t, source):
        # Enrichr 行格式: [rank, term, pvalue, zscore, combined, overlapping_genes, adjusted_p, ...]
        # JSON 接口里 overlapping_genes 是 list（网页版是逗号串），两种都兼容
        try:
            genes_cell = t[5]
            if isinstance(genes_cell, str):
                overlap = [g.strip() for g in genes_cell.split(",") if g.strip()]
            else:
                overlap = [str(g).strip() for g in (genes_cell or []) if str(g).strip()]
            term = t[1]
            zh = _zh_term(term)
            return {
                "term": term,
                "term_zh": zh,
                "source": source,
                "p_value": float(f"{t[6]:.3g}") if t[6] is not None else None,
                "combined_score": round(float(t[4]), 1) if t[4] is not None else None,
                "overlap": overlap[:8],
                "overlap_count": len(overlap),
            }
        except (IndexError, TypeError, ValueError):
            return None

    # GO BP：只保留能映射为中文的生理过程词条——用户看不懂的技术性词条
    # （转录调控/DNA模板化/蛋白磷酸化）对"这杯茶凭什么有用"没有解释力，直接丢弃
    go_out = []
    for t in go_terms[:MAX_PATHWAYS * 6]:
        p = parse(t, "GO_BP")
        if not p or not p["term_zh"]:
            continue
        go_out.append(p)
    # 同中文译名只留 p 值最优的一条（不同 GO ID 常有近似表述）
    seen, go_dedup = set(), []
    for p in go_out:
        key = p["term_zh"]
        if key in seen:
            continue
        seen.add(key)
        go_dedup.append(p)
    go_out = go_dedup[:MAX_PATHWAYS]

    # KEGG：过滤疾病/癌症/感染类，只留代谢与信号类
    kegg_out = []
    for t in kegg_terms[:MAX_PATHWAYS * 6]:
        p = parse(t, "KEGG")
        if not p:
            continue
        low = p["term"].lower()
        if any(bad in low for bad in _KEGG_BLOCKLIST):
            continue
        kegg_out.append(p)
        if len(kegg_out) >= MAX_PATHWAYS // 2:
            break

    return {"status": "ok", "n_genes": len(genes),
            "pathways": go_out, "pathways_kegg": kegg_out,
            "note": NOTE}


def cached(rid: int) -> dict | None:
    conn = _db()
    try:
        row = conn.execute(
            "SELECT gene_count, pathways, pathways_kegg, status, generated_at "
            "FROM recipe_pathway WHERE recipe_id=?", (rid,)).fetchone()
        if not row:
            return None
        return {"status": row["status"], "n_genes": row["gene_count"],
                "pathways": json.loads(row["pathways"] or "[]"),
                "pathways_kegg": json.loads(row["pathways_kegg"] or "[]"),
                "cached_at": row["generated_at"], "note": NOTE}
    except sqlite3.OperationalError:
        return None  # 表还没建（未跑预生成）
    finally:
        conn.close()


def save(rid: int, result: dict) -> None:
    conn = _db(readonly=False)
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recipe_pathway (
                recipe_id INTEGER PRIMARY KEY REFERENCES recipe(id),
                gene_count INTEGER,
                pathways TEXT,
                pathways_kegg TEXT,
                status TEXT,
                library TEXT,
                generated_at TEXT
            )""")
        # 兼容旧表结构（只有 pathways 列）
        cols = {r[1] for r in conn.execute("PRAGMA table_info(recipe_pathway)")}
        if "pathways_kegg" not in cols:
            conn.execute("ALTER TABLE recipe_pathway ADD COLUMN pathways_kegg TEXT")
        conn.execute(
            "INSERT OR REPLACE INTO recipe_pathway "
            "(recipe_id,gene_count,pathways,pathways_kegg,status,library,generated_at) "
            "VALUES (?,?,?,?,?,?,datetime('now'))",
            (rid, result.get("n_genes"),
             json.dumps(result.get("pathways", []), ensure_ascii=False),
             json.dumps(result.get("pathways_kegg", []), ensure_ascii=False),
             result.get("status"), f"{LIBRARY_GO}+{LIBRARY_KEGG}"))
        conn.commit()
    finally:
        conn.close()


def for_recipe(rid: int, refresh: bool = False) -> dict:
    """对外入口：优先读缓存；缓存无或 refresh 时实时富集并落库"""
    if not refresh:
        c = cached(rid)
        if c and c["status"] in ("ok", "insufficient"):
            return c
    genes = recipe_genes(rid)
    if not genes:
        return {"status": "insufficient", "n_genes": 0, "pathways": [],
                "note": "该方无人类蛋白靶点（或未做成分分析），无法富集"}
    result = enrich(genes)
    if result["status"] == "ok":
        try:
            save(rid, result)
        except sqlite3.Error:
            pass  # 落库失败不影响返回（如库文件只读）
    return result
