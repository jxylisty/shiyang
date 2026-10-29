# -*- coding: utf-8 -*-
"""
入血模型「应用域（Applicability Domain）」标注
-------------------------------------------------
背景：入血概率是 PU-Learning 模型预测值。模型只在训练数据分布内可信，
      离训练集越远，预测越不可靠（课件「结构新颖性 = 与参考集最大 Tanimoto 相似度」）。

做法：对库内每个成分，计算它与「训练集」的最大 Morgan 指纹 Tanimoto 相似度，
      作为该成分在模型应用域内的程度指标。零重训，只补一列。

字段（写入 compound 表）：
  max_sim_to_train  与训练集的最大 Tanimoto 相似度 [0,1]
  ad_level          应用域档位：in（域内）/ edge（边缘）/ out（域外）
  ad_nearest        最相似的训练集成分名（便于人工核查）

判定阈值：取训练集内部相似度分布的 5% 分位作「域外」界，25% 分位作「边缘」界。
         用分位数而非拍脑袋定 0.3，是因为可辩护：低于 5% 分位 = 比训练集内部
         最不相似的 5% 还疏远。

用法：
  python -X utf8 scripts/compute_applicability.py            # 计算并写库
  python -X utf8 scripts/compute_applicability.py --dry-run  # 只打印不写库
"""
import argparse
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import AllChem

RDLogger.DisableLog("rdApp.*")

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "shiyang.db"
# 训练集原始特征表（含 smiles 列），与入血预测 V2 训练脚本同一份数据
TRAIN_XLSX = (ROOT.parent / "入血预测" / "cctcm2.0"
              / "化合物理化性质和生物利用度属性-赵玉男.xlsx")

FP_SIZE = 1024
RADIUS = 2


def _fp(mol):
    return AllChem.GetMorganGenerator(radius=RADIUS, fpSize=FP_SIZE).GetFingerprint(mol)


def load_train_set():
    """读训练集 SMILES，返回 [(name, fp)]。文件缺失则报错退出（不静默降级）。"""
    if not TRAIN_XLSX.exists():
        raise SystemExit(f"训练集文件不存在：{TRAIN_XLSX}\n"
                         f"该脚本依赖课题原始训练数据，请先确认路径。")
    import pandas as pd
    df = pd.read_excel(TRAIN_XLSX, header=1)
    out = []
    bad = 0
    for _, row in df.iterrows():
        smi = row.get("smiles")
        if not isinstance(smi, str) or not smi.strip():
            continue
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            bad += 1
            continue
        out.append((str(row.get("Compound") or ""), _fp(mol)))
    print(f"训练集: {len(out)} 个可用分子（解析失败 {bad} 个）")
    if not out:
        raise SystemExit("训练集解析后为空，终止。")
    return out


def train_loo_nearest(train):
    """留一法：每个训练分子对其余训练集的『最大相似度』分布。

    这才是应用域阈值的正确参照系——随机配对的相似度会被大量无关分子拉低
    （实测 5% 分位仅 0.028，会把所有查询分子都判成"域内"，失去区分度）。
    留一法问的是"训练集自身分子，离最近的同伴有多近"，用它作基准才可比。
    """
    fps = [fp for _, fp in train]
    sims = []
    for i, fp in enumerate(fps):
        others = fps[:i] + fps[i + 1:]
        if not others:
            continue
        sims.append(max(DataStructs.BulkTanimotoSimilarity(fp, others)))
    sims.sort()
    return sims


def compute(db_path=DB, dry_run=False):
    train = load_train_set()
    train_fps = [fp for _, fp in train]

    self_sims = train_loo_nearest(train)
    p05 = self_sims[int(len(self_sims) * 0.05)]
    p25 = self_sims[int(len(self_sims) * 0.25)]
    print(f"训练集留一法最近邻相似度: 5%分位={p05:.3f}  25%分位={p25:.3f} "
          f"中位={self_sims[len(self_sims)//2]:.3f}")
    print(f"  （查询分子 ≤5%分位视为域外，≤25%分位视为边缘）")

    conn = sqlite3.connect(f"file:{db_path.as_posix()}?mode=rw", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, name, smiles FROM compound WHERE smiles IS NOT NULL AND smiles != ''"
        ).fetchall()
        print(f"待标注成分: {len(rows)} 个")

        results = []
        for r in rows:
            mol = Chem.MolFromSmiles(r["smiles"])
            if mol is None:
                continue
            sims = DataStructs.BulkTanimotoSimilarity(_fp(mol), train_fps)
            best = max(sims)
            nearest = train[sims.index(best)][0]
            if best <= p05:
                level = "out"
            elif best <= p25:
                level = "edge"
            else:
                level = "in"
            results.append((round(best, 4), level, nearest, r["id"], r["name"]))

        from collections import Counter
        dist = Counter(x[1] for x in results)
        print(f"结果: 域内 in={dist['in']}  边缘 edge={dist['edge']}  域外 out={dist['out']}"
              f"  （共 {len(results)}）")

        if dry_run:
            print("\n--- 域外成分（最需谨慎展示）---")
            for best, level, nearest, cid, name in sorted(results)[:10]:
                print(f"  {name:20s} sim={best:.3f} 最近={nearest}")
            print("\n[dry-run] 未写库。")
            return results

        conn.execute("BEGIN")
        conn.execute("ALTER TABLE compound ADD COLUMN max_sim_to_train REAL") \
            if not _has_col(conn, "compound", "max_sim_to_train") else None
        if not _has_col(conn, "compound", "ad_level"):
            conn.execute("ALTER TABLE compound ADD COLUMN ad_level TEXT")
        if not _has_col(conn, "compound", "ad_nearest"):
            conn.execute("ALTER TABLE compound ADD COLUMN ad_nearest TEXT")
        for best, level, nearest, cid, _ in results:
            conn.execute(
                "UPDATE compound SET max_sim_to_train=?, ad_level=?, ad_nearest=? WHERE id=?",
                (best, level, nearest, cid))
        conn.commit()
        print(f"已写入 {len(results)} 行。")
        return results
    finally:
        conn.close()


def _has_col(conn, table, col):
    return any(r[1] == col for r in conn.execute(f"PRAGMA table_info({table})"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只打印不写库")
    args = ap.parse_args()
    compute(dry_run=args.dry_run)
