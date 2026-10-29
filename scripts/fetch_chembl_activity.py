# -*- coding: utf-8 -*-
"""
ChEMBL 实验活性补数据
-------------------------------------------------
背景：现有证据链（成分 → 入血概率 → 靶点 → 通路）全部是模型预测或数据库关联，
      没有一条「实验实测」证据。ChEMBL 收录化合物-靶点-活性的实测记录
      （IC50/Ki/EC50 等，含 pChEMBL 强度值），可补上这一环。

做法：对库内每个成分，用 InChIKey 精确匹配 ChEMBL 分子，取其活性记录，
      按靶点聚合，写入新表 compound_chembl_activity。

证据等级判据（写入前先想清楚，别越级）：
  pChEMBL >= 6（即 IC50/Ki <= 1 μM）才算「较强实验证据」，标 L1
  5 <= pChEMBL < 6 标 L2（中等活性）
  有记录但 pChEMBL < 5 不入库（弱活性噪音大）

重要边界：
  - 这是「体外/实验测定活性」，不等于「人体内有效」，更不等于食疗功效。
  - 展示时必须写明"体外实验测定"，不得写成疗效结论（AGENTS.md §2.3）。

用法：
  python -X utf8 scripts/fetch_chembl_activity.py --dry-run   # 抽样 5 个看效果
  python -X utf8 scripts/fetch_chembl_activity.py             # 全量 165 个
  python -X utf8 scripts/fetch_chembl_activity.py --refresh   # 忽略缓存重拉
"""
import argparse
import json
import math
import sqlite3
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import requests
from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "shiyang.db"
CACHE = ROOT / "data" / "cache" / "chembl"
CHEMBL_API = "https://www.ebi.ac.uk/chembl/api/data"

# 只收这些活性类型（与课件/资料包 config.yaml 口径一致）
ALLOWED_TYPES = {"IC50", "Ki", "Kd", "EC50", "AC50", "Potency"}
MIN_PCHEMBL = 5.0          # 低于此不入库
STRONG_PCHEMBL = 6.0       # 达到此标 L1

# ChEMBL 对大量中药成分的老文献记录缺 pchembl_value（未标准化），
# 实测人参皂苷 Re 的 IC50 记录 pChEMBL 全为 None。所以必须能从
# standard_value + standard_units 自行换算，否则大部分成分会被误判"无活性"。
_UNIT_TO_LOG_MOLAR = {
    "nm": 9.0, "nmol/l": 9.0,
    "um": 6.0, "µm": 6.0, "μm": 6.0, "micromolar": 6.0, "umol/l": 6.0,
    "mm": 3.0, "mmol/l": 3.0,
    "m": 0.0, "mol/l": 0.0,
}


def _pchembl(value, unit):
    """由标准值+单位换算 pChEMBL（-log10(摩尔浓度)）。无法换算（如 ug/mL）返回 None。"""
    if value is None or not unit:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    key = str(unit).strip().lower().replace(" ", "")
    base = _UNIT_TO_LOG_MOLAR.get(key)
    if base is None:
        return None
    return round(base - math.log10(v), 3)


def _cache_path(key: str) -> Path:
    CACHE.mkdir(parents=True, exist_ok=True)
    return CACHE / f"{key}.json"


def _get(url, params=None, cache_key=None, refresh=False, timeout=25):
    if cache_key and not refresh:
        p = _cache_path(cache_key)
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                pass
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    data = r.json()
    if cache_key:
        _cache_path(cache_key).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return data


def inchikey_for(smiles: str) -> str | None:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    try:
        return Chem.MolToInchiKey(mol)
    except Exception:
        return None


def find_molecule(inchikey: str, refresh=False) -> str | None:
    """按 InChIKey 精确找 ChEMBL 分子 ID。找不到返回 None（不瞎猜相似分子）。"""
    data = _get(f"{CHEMBL_API}/molecule.json",
                {"molecule_structures__standard_inchi_key": inchikey, "limit": 1},
                cache_key=f"mol_{inchikey}", refresh=refresh)
    mols = data.get("molecules") or []
    if not mols:
        return None
    return mols[0].get("molecule_chembl_id")


def _target_types(target_ids, refresh=False) -> dict:
    """批量查靶点类型。activity 端点不返回 target_type（实测全为 None），
    必须走 target.json，否则会把 SK-MEL-28 这类细胞系当成分子靶点收进来。"""
    ids = [t for t in target_ids if t]
    if not ids:
        return {}
    out = {}
    for i in range(0, len(ids), 50):
        chunk = ids[i:i + 50]
        try:
            data = _get(f"{CHEMBL_API}/target.json",
                        {"target_chembl_id__in": ",".join(chunk), "limit": 50},
                        cache_key="tt_" + str(abs(hash(",".join(sorted(chunk))))),
                        refresh=refresh)
            for t in data.get("targets") or []:
                out[t.get("target_chembl_id")] = (t.get("target_type") or "").upper()
        except Exception:
            continue
    return out


# 只收真正的分子靶点（库内 target 表口径是基因/蛋白）
_PROTEIN_TYPES = {"SINGLE PROTEIN", "PROTEIN COMPLEX", "PROTEIN FAMILY"}


def fetch_activities(chembl_id: str, refresh=False, max_records=1000) -> list[dict]:
    """拉取该分子的活性记录，只保留人类蛋白靶点 + 允许的活性类型。

    max_records 取 1000：ChEMBL 单分子记录数实测可到 278 条，取太小会漏。
    """
    data = _get(f"{CHEMBL_API}/activity.json",
                {"molecule_chembl_id": chembl_id, "limit": max_records},
                cache_key=f"act_{chembl_id}", refresh=refresh)
    acts = data.get("activities") or []

    ttypes = _target_types({a.get("target_chembl_id") for a in acts}, refresh=refresh)

    out = []
    for a in acts:
        atype = (a.get("standard_type") or "").strip()
        if atype not in ALLOWED_TYPES:
            continue
        # pChEMBL 优先用官方值，缺失则自行换算（中药成分大量缺失，见 _pchembl 注释）
        pchembl = a.get("pchembl_value")
        try:
            pchembl = float(pchembl) if pchembl is not None else None
        except (TypeError, ValueError):
            pchembl = None
        if pchembl is None:
            pchembl = _pchembl(a.get("standard_value"), a.get("standard_units"))
        if pchembl is None or pchembl < MIN_PCHEMBL:
            continue
        organism = a.get("target_organism")
        if organism and organism != "Homo sapiens":
            continue
        tid = a.get("target_chembl_id")
        # 靶点类型白名单：细胞系/组织/物种/未分类一律丢弃
        if ttypes.get(tid) not in _PROTEIN_TYPES:
            continue
        out.append({
            "target_chembl_id": tid,
            "target_name": a.get("target_pref_name"),
            "activity_type": atype,
            "activity_value": a.get("standard_value"),
            "activity_unit": a.get("standard_units"),
            "pchembl": pchembl,
            "assay_chembl_id": a.get("assay_chembl_id"),
            "document_chembl_id": a.get("document_chembl_id"),
        })
    return out


def aggregate_by_target(acts: list[dict]) -> list[dict]:
    """按靶点聚合：取该靶点上最强的 pChEMBL，并记录证据条数。"""
    by_target = {}
    for a in acts:
        key = a["target_chembl_id"] or a["target_name"]
        if not key:
            continue
        cur = by_target.get(key)
        if cur is None:
            by_target[key] = dict(a, n_records=1)
        else:
            cur["n_records"] += 1
            if a["pchembl"] > cur["pchembl"]:
                cur.update({k: a[k] for k in ("activity_type", "activity_value",
                                              "activity_unit", "pchembl")})
    out = sorted(by_target.values(), key=lambda x: -x["pchembl"])
    for x in out:
        x["evidence_level"] = "L1" if x["pchembl"] >= STRONG_PCHEMBL else "L2"
    return out


def ensure_table(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS compound_chembl_activity (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        compound_id TEXT,
        compound_name TEXT,
        chembl_id TEXT,
        target_chembl_id TEXT,
        target_name TEXT,
        activity_type TEXT,
        activity_value REAL,
        activity_unit TEXT,
        pchembl REAL,
        evidence_level TEXT,
        n_records INTEGER,
        assay_chembl_id TEXT,
        document_chembl_id TEXT,
        fetched_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_cca_compound ON compound_chembl_activity(compound_id);
    """)
    # compound 表加三个汇总列（供列表页快速展示）
    for col, typ in (("chembl_id", "TEXT"),
                     ("chembl_target_count", "INTEGER"),
                     ("chembl_strong_count", "INTEGER")):
        if not any(r[1] == col for r in conn.execute("PRAGMA table_info(compound)")):
            conn.execute(f"ALTER TABLE compound ADD COLUMN {col} {typ}")


def run(limit=None, dry_run=False, refresh=False, sleep=0.3):
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=rw", uri=True)
    conn.row_factory = sqlite3.Row
    ensure_table(conn)

    rows = conn.execute(
        "SELECT id, name, smiles FROM compound WHERE smiles IS NOT NULL AND smiles != '' "
        "ORDER BY prob_cctcm DESC"
    ).fetchall()
    if limit:
        rows = rows[:limit]
    print(f"待查成分: {len(rows)} 个\n")

    hit = miss = err = 0
    total_targets = 0
    t0 = time.time()
    stamp = time.strftime("%Y-%m-%d")

    for i, r in enumerate(rows, 1):
        cid, name, smi = r["id"], r["name"], r["smiles"]
        ik = inchikey_for(smi)
        if not ik:
            err += 1
            continue
        try:
            chembl_id = find_molecule(ik, refresh=refresh)
            if not chembl_id:
                miss += 1
                if dry_run:
                    print(f"[{i}/{len(rows)}] {name}: 未命中")
                continue
            acts = fetch_activities(chembl_id, refresh=refresh)
            agg = aggregate_by_target(acts)
            hit += 1
            total_targets += len(agg)
            strong = sum(1 for x in agg if x["evidence_level"] == "L1")

            if dry_run:
                print(f"[{i}/{len(rows)}] {name}: {chembl_id} → {len(agg)} 个靶点"
                      f"（L1 强证据 {strong}）")
                for x in agg[:3]:
                    print(f"      {x['target_name']}  {x['activity_type']}={x['activity_value']}"
                          f"{x['activity_unit'] or ''}  pChEMBL={x['pchembl']:.2f} [{x['evidence_level']}]")
                continue

            conn.execute("DELETE FROM compound_chembl_activity WHERE compound_id=?", (cid,))
            for x in agg:
                conn.execute(
                    "INSERT INTO compound_chembl_activity "
                    "(compound_id,compound_name,chembl_id,target_chembl_id,target_name,"
                    "activity_type,activity_value,activity_unit,pchembl,evidence_level,"
                    "n_records,assay_chembl_id,document_chembl_id,fetched_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (cid, name, chembl_id, x["target_chembl_id"], x["target_name"],
                     x["activity_type"], x["activity_value"], x["activity_unit"],
                     round(x["pchembl"], 3), x["evidence_level"], x["n_records"],
                     x["assay_chembl_id"], x["document_chembl_id"], stamp))
            conn.execute(
                "UPDATE compound SET chembl_id=?, chembl_target_count=?, chembl_strong_count=? "
                "WHERE id=?", (chembl_id, len(agg), strong, cid))
            if i % 20 == 0:
                conn.commit()
                print(f"  进度 {i}/{len(rows)}  命中 {hit}  未命中 {miss}  错误 {err}")
        except Exception as e:
            err += 1
            print(f"  [警告] {name}: {type(e).__name__}: {e}")
        time.sleep(sleep)

    if not dry_run:
        conn.commit()
    conn.close()
    print(f"\n完成：命中 {hit} / 未命中 {miss} / 错误 {err}，"
          f"共 {total_targets} 条靶点活性，耗时 {time.time()-t0:.0f}s")
    if dry_run:
        print("[dry-run] 未写库。")
    return hit, miss, err


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    run(limit=a.limit, dry_run=a.dry_run, refresh=a.refresh)
