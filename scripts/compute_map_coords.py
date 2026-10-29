# -*- coding: utf-8 -*-
"""
成分化学空间地图（UMAP）坐标生成
-------------------------------------------------
把 165 个成分的 Morgan 指纹降到 2 维，前端渲染成散点图。一张图回答三个问题：
  1. 这些成分在化学空间里怎么分布（结构上谁跟谁是一族）
  2. 入血概率高的成分长什么样（按概率着色）
  3. 模型之间分歧的成分在哪（按一致性标注）——分歧点若聚成一团，
     直观说明分歧来自结构类别（皂苷/脂肪酸），而非随机噪声

字段（写入新表 compound_map）：
  compound_id / name / x / y / prob_cctcm / prob_indep / ad_level / cv_level

确定性：UMAP random_state=42，同数据重跑坐标不变。
用法：python -X utf8 scripts/compute_map_coords.py
"""
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem
import umap

RDLogger.DisableLog("rdApp.*")

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "shiyang.db"


def main():
    conn = sqlite3.connect(f"file:{DB.as_posix()}?mode=rw", uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT id, name, smiles, prob_cctcm, prob_indep, ad_level "
        "FROM compound WHERE smiles IS NOT NULL AND smiles != ''").fetchall()
    print(f"成分: {len(rows)}")

    gen = AllChem.GetMorganGenerator(radius=2, fpSize=1024)
    fps, keep_rows = [], []
    for r in rows:
        mol = Chem.MolFromSmiles(r["smiles"])
        if mol is None:
            continue
        fps.append(gen.GetFingerprint(mol))
        keep_rows.append(r)
    print(f"指纹: {len(fps)} 个有效")

    # 交叉验证一致性档（与 explain_service 同口径，用于着色）
    thr_row = conn.execute("SELECT value FROM meta WHERE key='indep_threshold'").fetchone()
    thr = float(thr_row[0]) if thr_row else 0.5

    reducer = umap.UMAP(n_components=2, random_state=42, n_neighbors=15, min_dist=0.3)
    coords = reducer.fit_transform(np.array([np.array(f) for f in fps], dtype=np.float32))
    print(f"UMAP 完成: {coords.shape}")

    conn.executescript("""
    CREATE TABLE IF NOT EXISTS compound_map (
        compound_id TEXT PRIMARY KEY,
        name TEXT, x REAL, y REAL,
        prob_cctcm REAL, prob_indep REAL,
        ad_level TEXT, cv_level TEXT
    );
    """)
    conn.execute("DELETE FROM compound_map")
    n = 0
    for r, (x, y) in zip(keep_rows, coords):
        p_main, p_ind = r["prob_cctcm"], r["prob_indep"]
        if p_main is None or p_ind is None:
            cv = None
        else:
            hi_main, hi_ind = p_main >= 0.7, p_ind >= thr
            cv = ("both_high" if hi_main and hi_ind else
                  "main_only" if hi_main else
                  "indep_only" if hi_ind else "both_low")
        conn.execute(
            "INSERT OR REPLACE INTO compound_map VALUES (?,?,?,?,?,?,?,?)",
            (r["id"], r["name"], round(float(x), 3), round(float(y), 3),
             p_main, p_ind, r["ad_level"], cv))
        n += 1
    conn.commit()
    conn.close()
    print(f"已写 compound_map {n} 行")


if __name__ == "__main__":
    main()
