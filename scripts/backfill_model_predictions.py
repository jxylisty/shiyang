# -*- coding: utf-8 -*-
"""
把「官方预测表里已经算好的」入血概率回填进库（零重训）

## 为什么要这个脚本（2026-11-06 实测）

扩容后库里有 4,562 个带 SMILES 的成分，但只有 165 个（全是 `ccMon` 前缀的老成分）
有 `prob_cctcm`。看起来像「新成分没跑模型」，实测不是——

按 Morgan 指纹（radius=2, 1024 位）的 canonical SMILES 做结构匹配：
  - 库内 4,562 个可解析成分中，**956 行（595 个唯一结构）**能在
    `入血预测/cctcm2.0_v2/cctcm_v2_predictions_union.csv`（正式版并集标签预测，
    2169 行）里按结构精确命中。
  - 其余 3,602 行是训练集外的成分，官方预测表里**确实没有**它们的值。

也就是说：这 956 行是当初灌库时漏掉的，不是模型没跑。回填它们属于**取回已算好的
事实**，不是新增预测，风险为零。

## 口径与诚实标注（AGENTS.md §2 数据真实铁律）

1. **不改现有 165 个 `prob_cctcm`**。它们是旧管线产物（源库 asthma_v2.db 直接带过来的），
   已在界面/材料中引用；本脚本只填 `prob_cctcm_v2 IS NULL` 的行。两列并存，
   谁是谁分得清，不制造口径漂移。
2. **`prob_cctcm_v2` 的语义要说准**：`final_cctcm_union.py` 是「全量重训后对全量样本
   predict」（`prob_all = model_full.predict_proba(X_all_p)`），所以这些值是
   **训练集内（in-sample）预测**，通常比训练集外的预测**偏乐观**。因此另写
   `prob_source` 列如实标注，前端/接口不得把它当成「和训练集外同等可靠」的结论。
3. 匹配只认**精确结构相等**（canonical SMILES 逐字符相同），不做相似度近似匹配——
   近似匹配会把「结构相近但不同」的化合物概率张冠李戴，属于编造数据。

## 用法

  python -X utf8 scripts/backfill_model_predictions.py            # 预览
  python -X utf8 scripts/backfill_model_predictions.py --apply    # 写库（自动备份）

依赖仓库外的 `../入血预测/`（课题原始模型项目）。文件缺失则报错退出，不静默降级。
"""
import argparse
import difflib
import re
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

from rdkit import Chem, RDLogger

RDLogger.DisableLog("rdApp.*")

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "shiyang.db"
MODEL_DIR = ROOT.parent / "入血预测"
TRAIN_XLSX = MODEL_DIR / "cctcm2.0" / "化合物理化性质和生物利用度属性-赵玉男.xlsx"
PRED_CSV = MODEL_DIR / "cctcm2.0_v2" / "cctcm_v2_predictions_union.csv"

# 新列（全部可空；存量 165 个 ccMon 成分这三列保持 NULL）
NEW_COLUMNS = [
    ("prob_cctcm_v2", "REAL"),   # 官方正式版（并集标签）预测，训练集内 in-sample
    ("prob_source", "TEXT"),     # 来源说明，见 PROB_SOURCE_DOC
    ("prob_in_train", "INTEGER"),  # 1=该结构在模型训练集内（预测偏乐观）
]

PROB_SOURCE_DOC = "cctcm_v2_predictions_union.csv@20260816(in-sample)"

# 名称佐证：结构匹配成功但名称完全不同时，仍要有一个词能对上，否则很可能不是同物异名，
# 而是 **HERB 源数据本身名-结构错配**。实测抓到一例：库内 HBIN004827 名为
# 「2,6,10-trimethyl-dodecane」（C15 长链烷），SMILES 却是呋喃酮 `CC1=C(O)C(=O)C(O)CO1`。
# 这种行若按结构回填，会把这个呋喃酮的概率挂到长链烷的名字上——正是「数据张冠李戴」。
# 同物异名（Aceteugenol / eugenol acetate、Henicosane / heneicosane）会共享词干，能通过。
_NAME_STOP = {
    "acid", "methyl", "ethyl", "dimethyl", "trimethyl", "alpha", "beta", "gamma",
    "delta", "cis", "trans", "iso", "the", "and", "for", "propan", "propen",
}


def _name_tokens(s: str):
    out = set()
    for t in re.split(r"[^a-z0-9]+", s.lower()):
        if len(t) >= 4 and t not in _NAME_STOP:
            out.add(t)
    return out


def _name_agrees(db_name: str, train_name: str) -> bool:
    """名称是否对得上（只用于分级报告，不作为回填门槛，见 plan()）。"""
    a, b = _name_tokens(db_name), _name_tokens(train_name)
    if not a or not b:
        return True
    best = 0.0
    for x in a:
        for y in b:
            if x in y or y in x:
                return True
            best = max(best, difflib.SequenceMatcher(None, x, y).ratio())
    return best >= 0.75


def _formula(smiles: str):
    """分子式；解析失败返回 None。用于挡「名字和结构明显不同物」的错配行。"""
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None
    from rdkit.Chem import rdMolDescriptors
    return rdMolDescriptors.CalcMolFormula(mol)


# 名称关键词 → 该名称必然蕴含的分子特征。用于识别 HERB 源数据里的「名-结构错配」：
# 同一个 canonical SMILES 一定指向同一分子，但如果**库里的名字**说的是长链烷烃而
# **结构**是个含氧小分子，那说明源数据本身把名字和结构配错了，此时按结构回填就会
# 把错的概率挂到对的分子上（或反之）。实测典型：HBIN004827「2,6,10-trimethyl-dodecane」
# 的 SMILES 是呋喃酮 C6H8O4，而名字蕴含的是 C15 烷烃。
_NAME_CONSTRAINTS = [
    # (名字里的关键词, 结构必须满足的判定, 说明)
    (r"dodecane|undecane|decane|nonane|octadecane|heptadecane|hexadecane|pentadecane|"
     r"tetradecane|tridecane|heneicosane|henicosane|eicosane|icosane|heptadekan|oktadekan",
     lambda m: all(a.GetSymbol() in ("C", "H") for a in m.GetAtoms()),
     "长链烷烃名字 → 结构只能是碳氢"),
]


def _structure_matches_name(name: str, mol) -> bool:
    """名称蕴含的结构约束是否成立。只挡「名字和结构必然不同物」的硬冲突。"""
    low = name.lower()
    for pattern, check, _why in _NAME_CONSTRAINTS:
        if re.search(pattern, low) and not check(mol):
            return False
    return True


def migrate(conn):
    """幂等加列：先 pragma 查现有列，缺什么补什么。"""
    have = {r[1] for r in conn.execute("PRAGMA table_info(compound)")}
    added = []
    for col, typ in NEW_COLUMNS:
        if col not in have:
            conn.execute(f"ALTER TABLE compound ADD COLUMN {col} {typ}")
            added.append(col)
    conn.commit()
    return added


def load_predictions():
    """读训练表（拿 名称→canonical SMILES）与官方预测表，返回 {canonical: (prob, name)}。"""
    if not TRAIN_XLSX.exists():
        raise SystemExit(f"训练特征表不存在：{TRAIN_XLSX}")
    if not PRED_CSV.exists():
        raise SystemExit(f"官方预测表不存在：{PRED_CSV}")

    import pandas as pd

    train = pd.read_excel(TRAIN_XLSX, header=1)
    name2can = {}
    for _, r in train.iterrows():
        name = str(r.get("Compound") or "").strip()
        smi = r.get("smiles")
        if not name or not isinstance(smi, str) or not smi.strip():
            continue
        mol = Chem.MolFromSmiles(smi.strip())
        if mol is not None:
            name2can.setdefault(name, Chem.MolToSmiles(mol))

    pred = pd.read_csv(PRED_CSV)
    can2prob = {}
    for _, r in pred.iterrows():
        can = name2can.get(str(r.get("Compound") or "").strip())
        if can:
            can2prob.setdefault(can, (float(r["预测入血概率"]), str(r["Compound"]).strip()))
    print(f"训练表可映射结构 {len(name2can)}；官方预测经结构映射后 {len(can2prob)} 个唯一结构")
    return can2prob


def plan(conn, can2prob):
    """返回待回填 [(id, name, prob, matched_name)]。

    只挑 **`prob_cctcm IS NULL` 且 `prob_cctcm_v2 IS NULL`** 的行——即扩容后新入库、
    从来没有过任何概率的成分。已有 `prob_cctcm` 的老 165 个（ccMon）**一律不碰**：
    它们的旧管线值和正式版口径实测差得不少（柚皮素 0.537 vs 0.951，160 个里 14 个
    会跨过阈值），若两套值同时出现在界面上，用户看到的就是两个数打架。
    要保持「旧成分只有旧值、新成分只有新值」，界面才不会精神分裂。
    """
    rows = conn.execute(
        "SELECT id, name, smiles FROM compound "
        "WHERE smiles IS NOT NULL AND smiles != '' "
        "AND prob_cctcm IS NULL AND prob_cctcm_v2 IS NULL").fetchall()
    todo, dup_struct, renamed, mismatched = [], {}, [], []
    for cid, name, smi in rows:
        mol = Chem.MolFromSmiles(smi)
        if mol is None:
            continue
        can = Chem.MolToSmiles(mol)
        hit = can2prob.get(can)
        if not hit:
            continue
        prob, train_name = hit
        # ① 硬冲突拦截：名字蕴含的结构约束与结构本身矛盾（如名字说长链烷、结构含氧）
        if not _structure_matches_name(name, mol):
            mismatched.append((cid, name, train_name, prob))
            continue
        # ② 名称文本对不上只记录、照常回填：canonical SMILES 完全相同即同一分子，
        #    实测这类里绝大多数是合法同物异名（linolenic acid =
        #    9,12,15-octadecatrienoic acid、eugeniin = Tellimagrandin II、Furol = Furfural）。
        if not _name_agrees(name, train_name):
            renamed.append((cid, name, train_name, prob))
        todo.append((cid, name, prob, train_name))
        dup_struct[can] = dup_struct.get(can, 0) + 1
    skipped_old = conn.execute(
        "SELECT COUNT(*) FROM compound WHERE prob_cctcm IS NOT NULL").fetchone()[0]
    print(f"待回填 {len(todo)} 行（对应 {len(dup_struct)} 个唯一结构；"
          f"同结构多名称最多 {max(dup_struct.values()) if dup_struct else 0} 行）；"
          f"老成分 {skipped_old} 个保持原值不动")
    if mismatched:
        print(f"⛔ 名称与结构硬冲突、已跳过 {len(mismatched)} 行"
              f"（HERB 源数据把名字和结构配错了，回填会张冠李戴）：")
        for cid, name, tn, prob in mismatched[:8]:
            print(f"    {cid:16s} 库内名「{name[:26]}」 / 训练表名「{tn[:26]}」")
    if renamed:
        print(f"ℹ 名称与训练表不常见但结构相同 {len(renamed)} 行（同物异名，照常回填）")
    return todo


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="真正写库（默认只预览）")
    args = ap.parse_args()

    if not DB.exists():
        raise SystemExit(f"数据库不存在：{DB}")

    can2prob = load_predictions()
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row

    added = migrate(conn)
    if added:
        print(f"[schema] 新增列：{', '.join(added)}")
    else:
        print("[schema] 三列已存在，跳过")

    todo = plan(conn, can2prob)
    if not todo:
        print("没有需要回填的行。")
        conn.close()
        return 0

    print("\n样例（前 8 条）：")
    for cid, name, prob, mname in todo[:8]:
        tag = "" if name.strip().lower() == mname.lower() else f"  ← 训练表名 {mname}"
        print(f"  {cid:16s} {name[:22]:24s} prob={prob:.4f}{tag}")

    if not args.apply:
        print("\n未加 --apply，未写库。")
        conn.close()
        return 0

    backup = DB.with_name(f"{DB.name}.bak-prob-{datetime.now():%Y%m%d%H%M%S}")
    shutil.copy2(DB, backup)
    print(f"\n[备份] {backup.name}（{backup.stat().st_size:,} bytes）")

    conn.executemany(
        "UPDATE compound SET prob_cctcm_v2=?, prob_source=?, prob_in_train=1 WHERE id=?",
        [(prob, PROB_SOURCE_DOC, cid) for cid, _n, prob, _m in todo])
    conn.commit()

    n_v2 = conn.execute(
        "SELECT COUNT(*) FROM compound WHERE prob_cctcm_v2 IS NOT NULL").fetchone()[0]
    n_old = conn.execute(
        "SELECT COUNT(*) FROM compound WHERE prob_cctcm IS NOT NULL").fetchone()[0]
    n_any = conn.execute(
        "SELECT COUNT(*) FROM compound WHERE prob_cctcm IS NOT NULL "
        "OR prob_cctcm_v2 IS NOT NULL").fetchone()[0]
    low = conn.execute(
        "SELECT COUNT(*) FROM compound WHERE prob_cctcm_v2 >= 0.56").fetchone()[0]
    conn.close()
    print(f"\n[完成] 回填 {len(todo)} 行")
    print(f"  prob_cctcm（旧管线，未改动）：{n_old}")
    print(f"  prob_cctcm_v2（本次回填）：{n_v2}")
    print(f"  两者合计有概率的成分：{n_any}（其中 v2 >= 阈值 0.56 的 {low} 个）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
