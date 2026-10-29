# -*- coding: utf-8 -*-
"""
入血预测「独立算法族交叉验证」
-------------------------------------------------
目的：主模型是 PU Bagging(RandomForest, 30轮)。本脚本用三个**不同算法族**的模型
      —— 逻辑回归(线性) / XGBoost(提升树) / MLP(神经网络) ——
      在同一份 ccTCM 标签数据上独立训练，回答一个问题：
      「换一套完全不同的算法，结论还成立吗？」

与主模型的协议差异（这是有意的，正是"独立"的含义）：
  - 主模型：PU Learning，每轮 全部正样本 + 等量未标注样本，30 轮平均
  - 本脚本：标准二分类，未标注一律当负例（更保守的协议）
  - 特征相同：19 维描述符(中位数填补) + Morgan 指纹 1024 位

产出：
  1. 三个模型 × 3 随机种子的测试集 ROC-AUC / PR-AUC（稳定性）
  2. 全量重训后对 shiyang 165 成分的预测 prob_indep（三模型均值）
  3. 与主模型 prob_cctcm 的一致性：Spearman/Pearson 相关 + 阈值下分类一致率
  4. docs/独立交叉验证_预测明细.csv + 汇总打印（报告由人工核对后写 docs/）

用法：
  python -X utf8 scripts/cross_validate_independent.py            # 全流程
  python -X utf8 scripts/cross_validate_independent.py --dry-run  # 不写库
"""
import argparse
import math
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd

from rdkit import Chem, RDLogger
from rdkit.Chem import rdMolDescriptors

RDLogger.DisableLog("rdApp.*")

from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.metrics import roc_auc_score, average_precision_score, roc_curve
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "shiyang.db"
OLD_DIR = ROOT.parent / "入血预测" / "cctcm2.0"
OUT_CSV = ROOT / "docs" / "独立交叉验证_预测明细.csv"

ORIG_COLS = ['LogS', 'LogD', 'LogP', 'Pgp-inhibitor', 'Pgp-substrate',
             'F(20%)', 'Caco-2 Permeability', 'MDCK Permeability (cm/s)',
             'Num. H-bond acceptors', 'Num. H-bond donors', 'TPSA',
             'Num. Rotatable bonds', 'Num. Rings', 'MaxRing', 'nHet',
             'fChar', 'nRig', 'Flex', 'nStereo']
FP_BITS = 1024
SEEDS = [42, 7, 2026]


# ---------- 数据组装（复刻主训练脚本的融合/去重/标签逻辑） ----------

def load_training_data():
    bridge = pd.read_excel(OLD_DIR / '化合物血中移行成分标识-赵玉男.xlsx')
    bridge['name_en'] = bridge['name_en'].astype(str).str.strip()
    bridge['pubchem_cid'] = bridge['pubchem_cid'].apply(
        lambda x: str(int(x)) if pd.notna(x) and str(x).strip() != '' else '')
    bridge_dict = {}
    for _, row in bridge.iterrows():
        if row['name_en'] and row['pubchem_cid'] and row['name_en'] not in bridge_dict:
            bridge_dict[row['name_en']] = row['pubchem_cid']

    feats = pd.read_excel(OLD_DIR / '化合物理化性质和生物利用度属性-赵玉男.xlsx', header=1)
    feats['Compound'] = feats['Compound'].astype(str).str.strip()
    feats['pubchem_cid'] = feats['Compound'].map(bridge_dict)
    feats = feats.dropna(subset=['pubchem_cid']).reset_index(drop=True)

    for col in ORIG_COLS:
        feats[col] = pd.to_numeric(feats[col], errors='coerce')
    feats['_n_missing'] = feats[ORIG_COLS].isna().sum(axis=1)
    feats = (feats.sort_values('_n_missing')
             .drop_duplicates(subset='pubchem_cid', keep='first')
             .drop(columns='_n_missing')
             .reset_index(drop=True))

    presc = pd.read_excel(OLD_DIR / '中药复方血中移行成分数据集.xlsx')
    presc = presc.dropna(subset=['复方']).reset_index(drop=True)
    cids = presc['PubChem CID'].dropna().apply(lambda x: str(int(x)) if pd.notna(x) else '')
    positive = set(cids[cids != ''].unique())
    y = feats['pubchem_cid'].apply(lambda c: 1 if c in positive else 0).values
    print(f"训练数据: {len(feats)} 行（正样本 {int(y.sum())}，未标注 {int((y == 0).sum())}）")
    return feats, y


def morgan_fp(smiles):
    if not isinstance(smiles, str) or not smiles.strip():
        return None
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    fp = rdMolDescriptors.GetMorganFingerprintAsBitVect(mol, 2, nBits=FP_BITS)
    return np.array(fp, dtype=np.int8)


def build_matrix(feats):
    """19 描述符(中位数填补) + Morgan1024。返回 X, 有效行掩码。"""
    X_desc = feats[ORIG_COLS].apply(pd.to_numeric, errors='coerce').to_numpy(dtype=np.float64)
    # 原表存在 inf 哨兵值（如 1E99 量级占位），一并置 NaN 走中位数填补
    X_desc[~np.isfinite(X_desc)] = np.nan
    X_desc = SimpleImputer(strategy='median').fit_transform(X_desc)
    fp_rows, keep = [], []
    for i, smi in enumerate(feats['smiles']):
        fp = morgan_fp(smi)
        fp_rows.append(fp if fp is not None else np.zeros(FP_BITS, dtype=np.int8))
        keep.append(fp is not None)
    X = np.hstack([X_desc, np.array(fp_rows, dtype=np.int8)])
    return X, np.array(keep)


def make_models(seed):
    spw = None  # 训练时按折内比例设置
    return {
        "LR": LogisticRegression(max_iter=2000, class_weight='balanced', random_state=seed),
        "XGB": None,  # 需要动态 scale_pos_weight，见 train_one
        "MLP": MLPClassifier(hidden_layer_sizes=(256, 128), max_iter=300,
                             early_stopping=True, random_state=seed),
    }


def train_one(name, Xtr, ytr, Xte, seed):
    if name == "LR":
        sc = StandardScaler().fit(Xtr)
        m = LogisticRegression(max_iter=2000, class_weight='balanced', random_state=seed)
        m.fit(sc.transform(Xtr), ytr)
        return m, sc.transform(Xte), sc
    if name == "XGB":
        spw = float((ytr == 0).sum()) / max(1, int((ytr == 1).sum()))
        m = XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.1,
                          scale_pos_weight=spw, eval_metric='logloss',
                          tree_method='hist', n_jobs=-1, random_state=seed)
        m.fit(Xtr, ytr)
        return m, Xte, None
    if name == "MLP":
        sc = StandardScaler().fit(Xtr)
        m = MLPClassifier(hidden_layer_sizes=(256, 128), max_iter=300,
                          early_stopping=True, random_state=seed)
        m.fit(sc.transform(Xtr), ytr)
        return m, sc.transform(Xte), sc
    raise ValueError(name)


def main(dry_run=False):
    feats, y = load_training_data()
    X, keep = build_matrix(feats)
    feats, y, X = feats[keep].reset_index(drop=True), y[keep], X[keep]
    print(f"特征矩阵: {X.shape}（SMILES 解析失败剔除 {int((~keep).sum())} 行）\n")

    # ---------- 1) 3 模型 × 3 种子 稳定性 ----------
    print("=" * 62)
    print("测试集指标（分层 80/20，3 种子）")
    print("=" * 62)
    names = ["LR", "XGB", "MLP"]
    auc = {n: [] for n in names}
    pr = {n: [] for n in names}
    j_thresholds = {n: [] for n in names}
    for seed in SEEDS:
        itr, ite = train_test_split(np.arange(len(y)), test_size=0.2,
                                    stratify=y, random_state=seed)
        for n in names:
            m, Xte, _ = train_one(n, X[itr], y[itr], X[ite], seed)
            p = m.predict_proba(Xte)[:, 1]
            auc[n].append(roc_auc_score(y[ite], p))
            pr[n].append(average_precision_score(y[ite], p))
            fpr, tpr, thr = roc_curve(y[ite], p)
            j = int(np.argmax(tpr - fpr))
            j_thresholds[n].append(thr[j])
    for n in names:
        print(f"  {n:4s} ROC-AUC {np.mean(auc[n]):.4f} ± {np.std(auc[n]):.4f}   "
              f"PR-AUC {np.mean(pr[n]):.4f} ± {np.std(pr[n]):.4f}   "
              f"Youden阈值 {np.mean(j_thresholds[n]):.3f}")
    indep_threshold = float(np.mean(j_thresholds["XGB"]))  # 用提升树的 Youden 阈值做一致性判定
    print(f"\n独立模型工作阈值（XGB Youden J 均值）: {indep_threshold:.3f}")

    # ---------- 2) 全量重训 → 预测 165 成分 ----------
    print("\n全量重训（seed=42）→ 预测 shiyang 165 成分 ...")
    models, scalers = {}, {}
    for n in names:
        models[n], _, scalers[n] = train_one(n, X, y, X, 42)

    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, name, smiles, prob_cctcm, prob_herb FROM compound "
        "WHERE smiles IS NOT NULL AND smiles != ''").fetchall()
    conn.close()
    print(f"待预测成分: {len(rows)}")

    recs = []
    # 预测段沿用训练段的填补器（fit 于训练集，transform 查询分子）
    imputer = SimpleImputer(strategy='median').fit(
        feats[ORIG_COLS].apply(pd.to_numeric, errors='coerce')
        .replace([np.inf, -np.inf], np.nan).to_numpy(dtype=np.float64))
    from rdkit.Chem import Crippen
    for r in rows:
        fp = morgan_fp(r["smiles"])
        if fp is None:
            continue
        mol = Chem.MolFromSmiles(r["smiles"])
        rings = mol.GetRingInfo().AtomRings()
        n_bonds = mol.GetNumBonds()
        n_rot = rdMolDescriptors.CalcNumRotatableBonds(mol)
        desc = {
            'LogS': np.nan, 'LogD': np.nan,
            'LogP': Crippen.MolLogP(mol), 'Pgp-inhibitor': np.nan, 'Pgp-substrate': np.nan,
            'F(20%)': np.nan, 'Caco-2 Permeability': np.nan, 'MDCK Permeability (cm/s)': np.nan,
            'Num. H-bond acceptors': rdMolDescriptors.CalcNumHBA(mol),
            'Num. H-bond donors': rdMolDescriptors.CalcNumHBD(mol),
            'TPSA': rdMolDescriptors.CalcTPSA(mol),
            'Num. Rotatable bonds': n_rot,
            'Num. Rings': rdMolDescriptors.CalcNumRings(mol),
            'MaxRing': max((len(g) for g in rings), default=0),
            'nHet': rdMolDescriptors.CalcNumHeteroatoms(mol),
            'fChar': Chem.GetFormalCharge(mol),
            'nRig': n_bonds - n_rot,
            'Flex': (n_rot / n_bonds) if n_bonds > 0 else 0.0,
            'nStereo': rdMolDescriptors.CalcNumAtomStereoCenters(mol),
        }
        x_desc = imputer.transform(
            pd.DataFrame([desc], columns=ORIG_COLS).to_numpy(dtype=np.float64))
        xv = np.hstack([x_desc, fp.reshape(1, -1).astype(np.float64)])

        ps = {}
        for n in names:
            xin = scalers[n].transform(xv) if scalers[n] is not None else xv
            ps[n] = float(models[n].predict_proba(xin)[0, 1])
        prob_indep = float(np.mean(list(ps.values())))
        recs.append({
            "compound_id": r["id"], "name": r["name"],
            "prob_cctcm": r["prob_cctcm"], "prob_herb": r["prob_herb"],
            "prob_lr": round(ps["LR"], 4), "prob_xgb": round(ps["XGB"], 4),
            "prob_mlp": round(ps["MLP"], 4), "prob_indep": round(prob_indep, 4),
        })

    df = pd.DataFrame(recs)

    # ---------- 3) 与主模型一致性 ----------
    both = df.dropna(subset=["prob_cctcm", "prob_indep"])
    sp = both["prob_cctcm"].corr(both["prob_indep"], method="spearman")
    pe = both["prob_cctcm"].corr(both["prob_indep"], method="pearson")
    hi_main = both["prob_cctcm"] >= 0.7
    hi_indep = both["prob_indep"] >= indep_threshold
    agree = (hi_main == hi_indep)
    print("\n" + "=" * 62)
    print(f"与主模型一致性（{len(both)} 个成分）")
    print(f"  Spearman 相关: {sp:.3f}   Pearson: {pe:.3f}")
    print(f"  阈值下分类一致率: {agree.mean() * 100:.1f}%"
          f"（主模型≥0.7 vs 独立≥{indep_threshold:.2f}）")
    dis = both[~agree].sort_values("prob_cctcm", ascending=False)
    print(f"  分歧成分 {len(dis)} 个（前 8）:")
    for _, r in dis.head(8).iterrows():
        tag = "主高独低" if r["prob_cctcm"] >= 0.7 else "主低独高"
        print(f"    {r['name'][:18]:18s} cctcm={r['prob_cctcm']:.3f} indep={r['prob_indep']:.3f} [{tag}]")

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"\n明细已写: {OUT_CSV}")

    # ---------- 4) 写库 ----------
    if dry_run:
        print("[dry-run] 未写库。")
        return
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=rw", uri=True)
    try:
        if not any(r[1] == "prob_indep" for r in conn.execute("PRAGMA table_info(compound)")):
            conn.execute("ALTER TABLE compound ADD COLUMN prob_indep REAL")
        for _, r in df.iterrows():
            conn.execute("UPDATE compound SET prob_indep=? WHERE id=?",
                         (r["prob_indep"], r["compound_id"]))
        conn.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('indep_threshold', ?)",
                     (f"{indep_threshold:.4f}",))
        conn.commit()
        print(f"已写库 {len(df)} 行 prob_indep；meta.indep_threshold={indep_threshold:.4f}")
    finally:
        conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    main(dry_run=ap.parse_args().dry_run)
