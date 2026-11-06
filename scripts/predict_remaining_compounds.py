# -*- coding: utf-8 -*-
"""
对「官方预测表里没有」的成分跑兜底模型，并给全库补应用域标注

## 背景与为什么只跑 HERB 模型（2026-11-06 实测数据支撑）

库内 4,562 个可解析成分分成三类：

| 类别 | 行数 | 处理方式 |
|---|---|---|
| A 老成分（ccMon，旧管线 prob_cctcm） | 165 | **不动**，已由 `backfill_model_predictions.py` 之外的历史管线产出 |
| B 训练集内、官方预测表已有 | 795 | **零重训回填**（`backfill_model_predictions.py`），本次不涉及 |
| C 训练集外、官方无预测 | 3,602 | 本脚本：跑兜底模型 + 应用域标注 |

C 类只能用「仅 SMILES」模式推理，两个模型的实测差距：

| 模型 | 不可算特征 | 在 165 个已知值上的偏差 | 阈值一致率 | 结论 |
|---|---|---|---|---|
| ccTCM（主力） | 7 个 ADME（LogS/LogD/Pgp×2/F20%/Caco-2/MDCK） | 平均绝对偏差 **0.29**，最大 0.68 | 阈值翻转 **44.4%** | **不适合外推**，跑出来的数与原口径不是一回事 |
| HERB（兜底） | 2 个（Drug_likeness/OB_score，HERB 库字段） | 平均绝对偏差 **0.135**，中位 0.024 | 79.4% | 可用，但须标为「外推估计」 |

因此 C 类**只写 HERB 模型结果**（`prob_herb_v2`），且：
  - `prob_source` 明确写 `herb_model_union@20260816(extrapolated)`
  - `prob_in_train = 0`
  - 不写 `prob_cctcm` / `prob_cctcm_v2`——C 级证据不得冒充主力模型结论

## 应用域（全库）

`max_sim_to_train` / `ad_level` / `ad_nearest` 用与 `compute_applicability.py`
完全相同的口径（训练集留一法 5%/25% 分位作域外/边缘界）计算并写入**全部**
4,558 个可解析成分，让用户能判断「这个预测离训练数据有多远」。

实测（2026-11-06）：域内 in=2,775 / 边缘 edge=1,193 / 域外 out=590。

## 证据分级

按 `services/evidence_service.py` 定义：`prob_herb_v2` 是模型预测 → **C 级**，
外推成分尤其不得表述为疗效或实验结论（AGENTS.md §2.3）。

## 用法

  python -X utf8 scripts/predict_remaining_compounds.py            # 预览
  python -X utf8 scripts/predict_remaining_compounds.py --apply    # 写库（自动备份）
  python -X utf8 scripts/predict_remaining_compounds.py --apply --skip-ad   # 只跑模型

依赖仓库外的 `../入血预测/`（课题原始模型项目），缺失则报错退出。
"""
import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "shiyang.db"
MODEL_DIR = ROOT.parent / "入血预测"
TRAIN_XLSX = MODEL_DIR / "cctcm2.0" / "化合物理化性质和生物利用度属性-赵玉男.xlsx"

PROB_SOURCE_HERB = "herb_model_union@20260816(extrapolated)"

from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem

RDLogger.DisableLog("rdApp.*")

FP_SIZE, RADIUS = 1024, 2
_gen = AllChem.GetMorganGenerator(radius=RADIUS, fpSize=FP_SIZE)


def _fp(mol):
    return _gen.GetFingerprint(mol)


def migrate(conn):
    """幂等补列（prob_cctcm_v2/prob_source/prob_in_train 由回填脚本先建，这里兜底）。"""
    have = {r[1] for r in conn.execute("PRAGMA table_info(compound)")}
    want = [
        ("prob_herb_v2", "REAL"),
        ("prob_cctcm_v2", "REAL"),
        ("prob_source", "TEXT"),
        ("prob_in_train", "INTEGER"),
        ("max_sim_to_train", "REAL"),
        ("ad_level", "TEXT"),
        ("ad_nearest", "TEXT"),
    ]
    added = []
    for col, typ in want:
        if col not in have:
            conn.execute(f"ALTER TABLE compound ADD COLUMN {col} {typ}")
            added.append(col)
    conn.commit()
    return added


def load_train(tmpl):
    """训练集指纹 + 留一法阈值（与 compute_applicability.py 同口径）。"""
    if not TRAIN_XLSX.exists():
        raise SystemExit(f"训练特征表不存在：{TRAIN_XLSX}")
    import pandas as pd
    from rdkit import DataStructs

    df = pd.read_excel(TRAIN_XLSX, header=1)
    names, fps = [], []
    for _, r in df.iterrows():
        smi = r.get("smiles")
        if not isinstance(smi, str) or not smi.strip():
            continue
        mol = Chem.MolFromSmiles(smi.strip())
        if mol is None:
            continue
        names.append(str(r.get("Compound") or ""))
        fps.append(_fp(mol))
    print(f"训练集可用分子 {len(fps)}")

    sims = []
    for i, fp in enumerate(fps):
        others = fps[:i] + fps[i + 1:]
        if others:
            sims.append(max(DataStructs.BulkTanimotoSimilarity(fp, others)))
    sims.sort()
    p05 = sims[int(len(sims) * 0.05)]
    p25 = sims[int(len(sims) * 0.25)]
    print(f"留一法阈值：5%分位={p05:.3f}（域外界） 25%分位={p25:.3f}（边缘界）")
    return names, fps, p05, p25


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正写库（默认只预览）")
    ap.add_argument("--skip-ad", action="store_true", help="跳过应用域计算（省时间）")
    args = ap.parse_args()

    if not DB.exists():
        raise SystemExit(f"数据库不存在：{DB}")
    if not MODEL_DIR.exists():
        raise SystemExit(f"模型项目不存在：{MODEL_DIR}（本脚本依赖课题原始模型）")

    sys.path.insert(0, str(MODEL_DIR))
    import model_inference as mi
    import pandas as pd
    from rdkit import DataStructs

    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    added = migrate(conn)
    if added:
        print(f"[schema] 新增列：{', '.join(added)}")

    # ---- C 类：训练集外、两列都空 ----
    rows = conn.execute(
        "SELECT id, name, smiles FROM compound "
        "WHERE smiles IS NOT NULL AND smiles != '' "
        "AND prob_cctcm IS NULL AND prob_cctcm_v2 IS NULL AND prob_herb_v2 IS NULL"
    ).fetchall()
    print(f"\nC 类待预测成分：{len(rows)}")

    preds = []
    if rows:
        df = pd.DataFrame({"smiles": [r["smiles"] for r in rows]})
        ph = mi.predict_herb(df)["herb_prob"].values
        preds = [(float(p), r["id"], r["name"]) for p, r in zip(ph, rows)]
        above = sum(1 for p, _, _ in preds if p >= 0.62)
        print(f"HERB 模型跑完：均值 {sum(p for p,_,_ in preds)/len(preds):.3f}，"
              f"达阈值 0.62 的 {above} 个")
        print("⚠ 这些是「仅 SMILES」外推估计（缺 Drug_likeness/OB_score），"
              "按 C 级证据使用，不得与主力模型结论等同")

    # ---- 应用域：全库 ----
    ad_rows = []
    if not args.skip_ad:
        names, train_fps, p05, p25 = load_train(None)
        allc = conn.execute(
            "SELECT id, name, smiles FROM compound "
            "WHERE smiles IS NOT NULL AND smiles != ''").fetchall()
        print(f"应用域：待标注 {len(allc)} 个")
        for r in allc:
            mol = Chem.MolFromSmiles(r["smiles"])
            if mol is None:
                continue
            sims = DataStructs.BulkTanimotoSimilarity(_fp(mol), train_fps)
            best = max(sims)
            nearest = names[sims.index(best)] if sims else ""
            level = "out" if best <= p05 else ("edge" if best <= p25 else "in")
            ad_rows.append((round(best, 4), level, nearest, r["id"]))
        from collections import Counter
        dist = Counter(x[1] for x in ad_rows)
        print(f"  结果：域内 {dist['in']} / 边缘 {dist['edge']} / 域外 {dist['out']}")

    if not args.apply:
        print("\n未加 --apply，未写库。")
        conn.close()
        return 0

    backup = DB.with_name(f"{DB.name}.bak-model-{datetime.now():%Y%m%d%H%M%S}")
    shutil.copy2(DB, backup)
    print(f"\n[备份] {backup.name}（{backup.stat().st_size:,} bytes）")

    if preds:
        conn.executemany(
            "UPDATE compound SET prob_herb_v2=?, prob_source=?, prob_in_train=0 WHERE id=?",
            [(p, PROB_SOURCE_HERB, cid) for p, cid, _n in preds])
    if ad_rows:
        conn.executemany(
            "UPDATE compound SET max_sim_to_train=?, ad_level=?, ad_nearest=? WHERE id=?",
            ad_rows)
    conn.commit()

    q = lambda s: conn.execute(s).fetchone()[0]
    print(f"\n[完成]")
    print(f"  官方预测回填 prob_cctcm_v2：{q('SELECT COUNT(*) FROM compound WHERE prob_cctcm_v2 IS NOT NULL')}")
    print(f"  旧管线 prob_cctcm（未动）：{q('SELECT COUNT(*) FROM compound WHERE prob_cctcm IS NOT NULL')}")
    print(f"  HERB 外推 prob_herb_v2：{q('SELECT COUNT(*) FROM compound WHERE prob_herb_v2 IS NOT NULL')}")
    print(f"  有任一概率：{q('SELECT COUNT(*) FROM compound WHERE prob_cctcm IS NOT NULL OR prob_cctcm_v2 IS NOT NULL OR prob_herb_v2 IS NOT NULL')}")
    print(f"  应用域已标注：{q('SELECT COUNT(*) FROM compound WHERE ad_level IS NOT NULL')}")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
