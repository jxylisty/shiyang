# -*- coding: utf-8 -*-
"""
知识库重建驱动脚本（shiyang.db，从零到完整库）

完整链路与每一步的口径说明见 docs/知识库重建链路_2026-11-06.md。
本脚本在**隔离沙箱**里按序调用既有 scripts/*.py，每步校验关键表行数，
失败即停并打印可复制的续跑命令。默认绝不写 data/shiyang.db（生产库）。

为什么用沙箱镜像而不是「原地跑 + 备份还原」：
  现有重建脚本几乎都把 DB 路径写死为 `<repo>/data/shiyang.db`
  （只有 _migrate_20261105.py 收 argv、import_herbs_20261105.py 收 --db）。
  原地模式必然出现「build_db.py 已 unlink 生产库、后续步骤失败」的窗口。
  因此本脚本把仓库镜像到 `<target-dir>/root/`，并把仓库外资源放到
  `<target-dir>/` 下（root 的兄弟目录），脚本里的 `ROOT = __file__.parent.parent`
  自然解析到沙箱。生产库全程只读、零写入风险。

用法：
  # 1) 只看计划，不建任何文件
  python -X utf8 scripts/rebuild_all.py --dry-run

  # 2) 复刻 19 张业务表基线（5,643 成分 / 59,437 关联），跳过 AI
  python -X utf8 scripts/rebuild_all.py --target-dir data/_rebuild_test/run1 \
      --skip-ai --skip-legacy10

  # 3) 复刻当前生产库（含 2026-11-06 c99bdd3 的 10 味补录 → 6,098 成分）
  python -X utf8 scripts/rebuild_all.py --target-dir data/_rebuild_test/run2 --skip-ai

  # 4) 中断后续跑（脚本会打印现成命令）
  python -X utf8 scripts/rebuild_all.py --target-dir data/_rebuild_test/run1 \
      --skip-ai --skip-legacy10 --start-at 10-expand --force

  # 5) 研究类步骤覆盖全库（慢：应用域/交叉验证/ChEMBL 都要跑全部成分）
  python -X utf8 scripts/rebuild_all.py --target-dir data/_rebuild_test/full \
      --profile full --skip-ai --chembl-limit 50

退出码：0 完成；1 有步骤失败；2 参数/资源错误；130 用户中断。
"""
import argparse
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

REPO = Path(__file__).resolve().parent.parent
PROD_DB = (REPO / "data" / "shiyang.db").resolve()

# 仓库外资源（相对仓库父目录）
EXT_ASTHMA = Path("my-asthma-system/asthma-core/data/asthma_v2.db")
EXT_EXCEL = Path("数据库溯源/主要展示数据均为cctcm2.0/药材-化合物-含量-赵玉男.xlsx")
EXT_TRAIN = Path("入血预测/cctcm2.0/化合物理化性质和生物利用度属性-赵玉男.xlsx")
EXT_LABELS = Path("入血预测/cctcm2.0/中药复方血中移行成分数据集.xlsx")
EXT_BRIDGE = Path("入血预测/cctcm2.0/化合物血中移行成分标识-赵玉男.xlsx")

INPUT_FILES = [
    "data/recipes_v0.1.json",
    "data/food_homology_catalog.json",
    "data/recipe_plain_ai.json",
    "data/symmap_smhb_v2.json",
    "data/symmap_smhb_v2.xlsx",
]
INPUT_DIRS = ["data/recipes_raw"]
CACHE_FILES = [
    "data/cache/herb_ingest_20261105.json",
    "data/cache/herb_ingest_legacy10.json",
]
CACHE_DIRS = ["data/cache/chembl"]

# 已入库的历史快照（可作为 --seed-from 的种子库）
SEED_CANDIDATES = [
    "data/shiyang.db.bak-before-rebuild",          # 34 味/165 成分基线（已入 git）
    "data/shiyang.db.bak-sync-20261026195251",
    "data/shiyang.db.bak-sync-20261026163956",
]

# 19 张业务表（用户验收口径；不含 c99bdd3 新增的两张补录表）
CORE19 = [
    "compound", "compound_chembl_activity", "compound_map", "constitution",
    "constitution_food_ref", "food", "herb", "herb_compound_content", "meta",
    "recipe", "recipe_analysis", "recipe_pathway", "recipe_pregen_ai",
    "rel_compound_target", "rel_herb_compound", "rel_herb_compound_v2",
    "rel_herb_compound_v3", "rel_recipe_material", "target",
]
LEGACY10_TABLES = ["rel_herb_compound_herb", "rel_herb_target_herb"]

# 基线（build_db.py 产物）——两种源口径
BASE_LEGACY = {  # 默认：把大创库 rel_herb_compound 换成修复前 rel_herb_compound_old 快照
    "herb": 34, "compound": 165, "target": 2807, "rel_compound_target": 12168,
}
BASE_REPAIRED = {  # --from-source：当前 asthma_v2.db 的 rel_herb_compound（修复后）
    "herb": 34, "compound": 138, "target": 4119, "rel_compound_target": 15502,
}
# 扩容步的确定增量（仅随采集缓存变化）
EXPAND_DELTA = {"herb": 71, "compound": 5478, "target": None, "rel_herb_compound": 8905,
                "rel_compound_target": 47269}
EXPAND_TOTAL_LEGACY = {"herb": 105, "compound": 5643, "target": 10091,
                       "rel_herb_compound": 9106, "rel_compound_target": 59437}
EXPAND_TOTAL_REPAIRED = {"herb": 105, "compound": 5616, "target": None,
                         "rel_herb_compound": 9121, "rel_compound_target": 62771}
LEGACY10_TOTAL = {"compound": 6098, "target": 10151, "rel_compound_target": 62617,
                  "rel_herb_compound_herb": 824, "rel_herb_target_herb": 627}


class Fail(Exception):
    pass


class Skip(Exception):
    """环境不满足的可选步骤（例如 umap/sklearn 版本不兼容）——记录后继续。"""


def preflight_chem_map(python_exe: str) -> str | None:
    """预检 compute_map_coords 的 umap/sklearn 兼容性——**用目标解释器实测**。

    关键点：本脚本自己可能跑在 base 环境（sklearn 1.4.2），但步骤子进程可以用
    --python 指向专用环境（.venv-rebuild，sklearn>=1.6）。所以预检必须在目标
    解释器里跑，不能用父进程的 import 结果下结论——否则会出现「明明装了好环境，
    UMAP 步骤却被跳过」的假阴性。

    已知失败模式（base 环境）：umap-learn 0.5.12 调用 sklearn 的
    check_array(ensure_all_finite=...)，该形参自 sklearn 1.5 起才有，
    1.4.2 会抛 TypeError。这是环境问题不是数据问题——降级跳过并如实标注，不掩盖。
    """
    probe = "\n".join([
        "import numpy as np, umap, sklearn",
        "umap.UMAP(n_components=2, random_state=42, n_neighbors=5).fit_transform(",
        "    np.random.RandomState(0).rand(12, 8).astype('float32'))",
        "print('OK', sklearn.__version__)",
        "",
    ])
    try:
        r = subprocess.run([python_exe, "-X", "utf8", "-c", probe],
                           capture_output=True, text=True, timeout=180,
                           encoding="utf-8", errors="replace")
    except Exception as e:
        return f"预检无法执行（{type(e).__name__}: {e}）"
    if r.returncode == 0:
        return None
    err = (r.stderr or r.stdout or "").strip().splitlines()
    tail = err[-1] if err else f"退出码 {r.returncode}"
    return f"umap/sklearn 不兼容（{tail[:150]}）"


def log(msg=""):
    print(msg, flush=True)


def link_or_copy(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def copy_tree_links(src: Path, dst: Path):
    for p in src.rglob("*"):
        rel = p.relative_to(src)
        if p.is_dir():
            (dst / rel).mkdir(parents=True, exist_ok=True)
        else:
            link_or_copy(p, dst / rel)


def ext(rel: Path) -> Path:
    return REPO.parent / rel


def resource_rows():
    return [
        ("大创修复库 asthma_v2.db", ext(EXT_ASTHMA), "缺：无法建基础库，链路中止"),
        ("溯源 Excel（归属/含量）", ext(EXT_EXCEL), "缺：v2 归属与含量表无法建，v2≡v3 校验失败"),
        ("入血训练特征 Excel", ext(EXT_TRAIN), "缺：应用域/交叉验证跳过"),
        ("入血标签 Excel", ext(EXT_LABELS), "缺：交叉验证跳过"),
        ("成分-PubChem 桥 Excel", ext(EXT_BRIDGE), "缺：交叉验证跳过"),
        ("扩容采集缓存 2.75MB", REPO / CACHE_FILES[0], "缺：import_herbs 联网全量采集（约 5,665 请求）"),
        ("legacy10 采集缓存 9MB", REPO / CACHE_FILES[1], "缺：import_herbs_legacy10 联网采集 10 味"),
        ("ChEMBL 缓存 84MB", REPO / CACHE_DIRS[0], "缺：fetch_chembl 联网（生产实测约 1600s）"),
    ]


def ai_gateway_open() -> bool:
    try:
        s = socket.socket()
        s.settimeout(0.6)
        s.connect(("127.0.0.1", 7863))
        s.close()
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# 校验断言：exact / min / pct / sql-exact
# ---------------------------------------------------------------------------
def exact(label, sql, n):
    return dict(label=label, sql=sql, kind="exact", n=n)


def at_least(label, sql, n):
    return dict(label=label, sql=sql, kind="min", n=n)


def same_as(label, sql, ref_sql):
    return dict(label=label, sql=sql, kind="sql", ref=ref_sql)


def describe(exp):
    if exp["kind"] == "exact":
        return str(exp["n"])
    if exp["kind"] == "min":
        return f">={exp['n']}"
    return "==动态参考查询"


def evaluate(conn, exp):
    got = conn.execute(exp["sql"]).fetchone()[0]
    if exp["kind"] == "exact":
        return got, got == exp["n"]
    if exp["kind"] == "min":
        return got, got >= exp["n"]
    ref = conn.execute(exp["ref"]).fetchone()[0]
    return got, got == ref


# ---------------------------------------------------------------------------
# 步骤定义
# ---------------------------------------------------------------------------
def build_steps(args):
    legacy = not args.from_source
    base = BASE_LEGACY if legacy else BASE_REPAIRED
    expand_totals = EXPAND_TOTAL_LEGACY if legacy else EXPAND_TOTAL_REPAIRED
    S = []

    def add(**kw):
        S.append(kw)

    # 1) 基础库：从零（build_db.py）或从历史快照播种（--seed-from）
    if args.seed_from:
        add(id="01-seed", title="从历史快照播种基础库（--seed-from）",
            script=None, argv=[], hard=True,
            checks=[
                exact("herb", "SELECT COUNT(*) FROM herb", 34),
                exact("compound", "SELECT COUNT(*) FROM compound", 165),
                exact("rel_compound_target", "SELECT COUNT(*) FROM rel_compound_target", 12168),
                exact("recipe_analysis", "SELECT COUNT(*) FROM recipe_analysis", 69),
                exact("recipe_pregen_ai", "SELECT COUNT(*) FROM recipe_pregen_ai", 69),
            ],
            note=f"种子库：{args.seed_from}（已入 git 的历史快照，含修复前概率与分析行）")
    else:
        add(id="01-base", title="基础库 11 表（药材/成分/靶点/方子/体质）",
            script="build_db.py", argv=[], hard=True,
            pre="use_legacy_source" if legacy else None,
            checks=[
                exact("herb", "SELECT COUNT(*) FROM herb", base["herb"]),
                exact("compound", "SELECT COUNT(*) FROM compound", base["compound"]),
                exact("target", "SELECT COUNT(*) FROM target", base["target"]),
                exact("rel_compound_target", "SELECT COUNT(*) FROM rel_compound_target",
                      base["rel_compound_target"]),
                exact("recipe", "SELECT COUNT(*) FROM recipe", 73),
                exact("rel_recipe_material", "SELECT COUNT(*) FROM rel_recipe_material", 270),
                exact("food", "SELECT COUNT(*) FROM food", 39),
                exact("constitution", "SELECT COUNT(*) FROM constitution", 9),
                exact("constitution_food_ref", "SELECT COUNT(*) FROM constitution_food_ref", 246),
            ],
            note="build_db.py 开头会 unlink 目标库再重建：沙箱内执行，生产库安全")

    # 2) 归属 v2（Excel 真源）
    add(id="02-rel-v2", title="归属 v2（Excel 真源，63 条）",
        script="rebuild_herb_compound.py", argv=[], hard=True,
        checks=[exact("rel_herb_compound_v2",
                      "SELECT COUNT(*) FROM rel_herb_compound_v2", 63)],
        note="依赖仓库外「药材-化合物-含量-赵玉男.xlsx」")

    # 3) 分析 v1：只为建表 + 历史口径的 17 行
    if not args.seed_from:
        add(id="03-analysis-v1", title="方子分析 v1（建表 + 69 行兜底）",
            script="pregen_analysis.py", argv=[], hard=True,
            checks=[exact("recipe_analysis", "SELECT COUNT(*) FROM recipe_analysis", 69)],
            note="必须在扩容前跑：v1 读 rel_herb_compound(v1)，扩容后会引入新增药材口径；"
                 "v3 随后只覆盖能连到 v3 归属的 52 方")

    # 4) 同步大创修复库
    add(id="04-sync-v3", title="同步大创修复库（v3 63 条 + GSEA 列）",
        script="sync_from_repaired_db.py", argv=["--apply"], hard=True,
        pre="restore_repaired_source",
        checks=[
            exact("rel_herb_compound_v3",
                  "SELECT COUNT(*) FROM rel_herb_compound_v3", 63),
            exact("source_db 置空",
                  "SELECT COUNT(*) FROM rel_compound_target WHERE source_db IS NULL",
                  base["rel_compound_target"]),
            at_least("GSEA 非空成分",
                     "SELECT COUNT(*) FROM compound "
                     "WHERE radar_anti_inflammatory_gsea IS NOT NULL", 119),
        ],
        note="把 compound 概率/理化值更新为修复版；清空 source_db 随机标签；"
             "只保留库里存在的 herb/compound 关联")

    # 5) 含量表
    add(id="05-content", title="药材-成分含量表（3,970 行）",
        script="import_content.py", argv=[], hard=True,
        checks=[exact("herb_compound_content",
                      "SELECT COUNT(*) FROM herb_compound_content", 3970)],
        note="脚本内 DELETE+INSERT（幂等）；依赖溯源 Excel 第 10 列含量")

    # 6) 研究类（current 口径：扩容前、只覆盖旧 165 成分）
    if args.profile == "current":
        research = [
            dict(id="06-applicability", title="模型应用域标注（旧 165 成分）",
                 script="compute_applicability.py", argv=[], optional=True,
                 checks=[at_least("ad_level 非空",
                                  "SELECT COUNT(*) FROM compound WHERE ad_level IS NOT NULL", 160)],
                 note="全量写 165 中可解析 SMILES 的行；依赖入血训练特征 Excel"),
            dict(id="07-cross-validate", title="独立算法族交叉验证（prob_indep）",
                 script="cross_validate_independent.py", argv=[], optional=True,
                 checks=[at_least("prob_indep 非空",
                                  "SELECT COUNT(*) FROM compound "
                                  "WHERE prob_indep IS NOT NULL", 160),
                         exact("meta.indep_threshold",
                               "SELECT COUNT(*) FROM meta WHERE key='indep_threshold'", 1)],
                 note="LR/XGB/MLP × 3 种子，约 2-3 分钟"),
            dict(id="08-chem-map", title="化学空间 UMAP 坐标（compound_map）",
                 script="compute_map_coords.py", argv=[], optional=True,
                 checks=[at_least("compound_map",
                                  "SELECT COUNT(*) FROM compound_map", 160)],
                 note="已知环境坑：umap 0.5.12 需 sklearn>=1.5；当前 sklearn 1.4.2 会抛 "
                      "TypeError: check_array() got an unexpected keyword argument "
                      "'ensure_all_finite'（现库 compound_map 为旧环境产物）"),
            dict(id="09-chembl", title="ChEMBL 实验活性（465 条）",
                 script="fetch_chembl_activity.py",
                 argv=(["--limit", str(args.chembl_limit)] if args.chembl_limit else []),
                 optional=True, network=True,
                 checks=[at_least("compound_chembl_activity",
                                  "SELECT COUNT(*) FROM compound_chembl_activity", 1)],
                 note="有 data/cache/chembl 时离线可跑；无缓存需网络，生产实测约 1600s"),
        ]
        S.extend(research)

    # 7) 扩容
    add(id="10-expand", title="2026-11-05 扩容（105 味 / +5,478 成分）",
        script="import_herbs_20261105.py", argv=[], hard=True,
        network=True,
        checks=([
            exact(k, f"SELECT COUNT(*) FROM {k}", v)
            for k, v in expand_totals.items() if v is not None
        ] if legacy else [
            exact("herb", "SELECT COUNT(*) FROM herb", 105),
            at_least("compound", "SELECT COUNT(*) FROM compound", 5616),
            at_least("rel_herb_compound", "SELECT COUNT(*) FROM rel_herb_compound", 9121),
            at_least("rel_compound_target", "SELECT COUNT(*) FROM rel_compound_target", 62771),
        ]),
        note="内部调 _migrate_20261105（herb 3 列 + 2 索引，幂等、带备份）；"
             "缓存命中时不联网，缺失则联网采集、可断点续传")

    # 8) 10 味补录（c99bdd3）
    if not args.skip_legacy10:
        add(id="11-legacy10", title="补 10 味旧药材归属（+455 成分 / 2 张新表）",
            script="import_herbs_legacy10.py", argv=["--apply"], hard=True,
            network=True,
            checks=[
                exact(k, f"SELECT COUNT(*) FROM {k}", v)
                for k, v in LEGACY10_TOTAL.items()
            ] if legacy else [
                at_least("compound", "SELECT COUNT(*) FROM compound", 6071),
                at_least("rel_herb_compound_herb",
                         "SELECT COUNT(*) FROM rel_herb_compound_herb", 824),
                at_least("rel_herb_target_herb",
                         "SELECT COUNT(*) FROM rel_herb_target_herb", 627),
            ],
            note="2026-11-06 c99bdd3 新增；--skip-legacy10 可停在 19 表基线")

    # 9) 回填配料 herb_id（必须在证据链/分析之前）
    add(id="12-backfill", title="回填方子配料 herb_id（53 条）",
        script="backfill_material_herb_id.py", argv=["--apply"], hard=True,
        checks=[exact("药材料子 herb_id 空值",
                      "SELECT COUNT(*) FROM rel_recipe_material "
                      "WHERE material_type='herb' AND herb_id IS NULL", 0)],
        note="扩容前 53 条 NULL 是 21 方空链根因；匹配顺序 正名→别名→药典异名，不猜")

    # 9b) 计数归一：import_herbs 会按 v1 全量重算 compound_count，
    #     把旧药（ccTCM）的三口径计数覆盖成 v1 值（生产实测 31 行偏差）。
    #     生产库靠 check_consistency --apply 修过，链路必须显式补这一步。
    if not args.skip_legacy10:
        add(id="12b-recount", title="计数归一（修复 31 行 compound_count 三口径）",
            script="check_consistency.py", argv=["--apply"], hard=True,
            checks=[exact("compound_count 偏差行",
                          "SELECT COUNT(*) FROM herb h WHERE COALESCE(h.compound_count,0) != "
                          "CASE WHEN h.id LIKE 'ccTCM%' THEN "
                          "(SELECT COUNT(*) FROM rel_herb_compound_v3 v WHERE v.herb_id=h.id) "
                          "+ (SELECT COUNT(*) FROM rel_herb_compound_herb x WHERE x.herb_id=h.id) "
                          "ELSE (SELECT COUNT(*) FROM rel_herb_compound v WHERE v.herb_id=h.id) END",
                          0)],
            expect_exit=0,
            note="必须在 import_herbs_20261105 之后、任何计数校验之前；"
                 "漏掉这步 check_consistency 会以退出码 1 拒绝收敛")
    else:
        add(id="12b-recount", title="计数归一（修复 31 行 compound_count 三口径，无补录表口径）",
            script="check_consistency.py", argv=["--apply"], hard=True,
            checks=[exact("compound_count 偏差行",
                          "SELECT COUNT(*) FROM herb h WHERE COALESCE(h.compound_count,0) != "
                          "CASE WHEN h.id LIKE 'ccTCM%' THEN "
                          "(SELECT COUNT(*) FROM rel_herb_compound_v3 v WHERE v.herb_id=h.id) "
                          "ELSE (SELECT COUNT(*) FROM rel_herb_compound v WHERE v.herb_id=h.id) END",
                          0)],
            expect_exit=0,
            note="import_herbs 按 v1 重算会覆盖旧药计数；此处按当前 schema 口径归一并校验")

    # 10) 研究类（full 口径：扩容后、覆盖全库）
    if args.profile == "full":
        S.extend([
            dict(id="13-applicability", title="模型应用域标注（全库成分）",
                 script="compute_applicability.py", argv=[], optional=True,
                 checks=[same_as("ad_level 非空",
                                 "SELECT COUNT(*) FROM compound WHERE ad_level IS NOT NULL",
                                 "SELECT COUNT(*) FROM compound "
                                 "WHERE smiles IS NOT NULL AND smiles != ''")],
                 note="对全部可解析 SMILES 的成分计算（含 HBIN 新成分）"),
            dict(id="14-cross-validate", title="独立算法族交叉验证（全库）",
                 script="cross_validate_independent.py", argv=[], optional=True,
                 checks=[same_as("prob_indep 非空",
                                 "SELECT COUNT(*) FROM compound WHERE prob_indep IS NOT NULL",
                                 "SELECT COUNT(*) FROM compound "
                                 "WHERE smiles IS NOT NULL AND smiles != ''")],
                 note="对全部可解析 SMILES 成分预测，耗时随成分数增长"),
            dict(id="15-chem-map", title="化学空间 UMAP 坐标（全库）",
                 script="compute_map_coords.py", argv=[], optional=True,
                 checks=[same_as("compound_map", "SELECT COUNT(*) FROM compound_map",
                                 "SELECT COUNT(*) FROM compound "
                                 "WHERE smiles IS NOT NULL AND smiles != ''")],
                 note="同 08 的 umap/sklearn 版本坑"),
            dict(id="16-chembl", title="ChEMBL 实验活性（全库，建议 --chembl-limit）",
                 script="fetch_chembl_activity.py",
                 argv=(["--limit", str(args.chembl_limit)] if args.chembl_limit else []),
                 optional=True, network=True,
                 checks=[at_least("compound_chembl_activity",
                                  "SELECT COUNT(*) FROM compound_chembl_activity", 1)],
                 note="全库 4,500+ 成分逐条查，无 --chembl-limit 时耗时极长"),
        ])

    # 11) 分析 v3
    add(id="17-analysis-v3", title="方子分析 v3（GSEA 三维评分）",
        script="pregen_analysis_v3.py", argv=[], hard=True,
        checks=[
            exact("recipe_analysis", "SELECT COUNT(*) FROM recipe_analysis", 69),
            at_least("GSEA 版分析行",
                     "SELECT COUNT(*) FROM recipe_analysis "
                     "WHERE radar_summary LIKE '%gsea_covered%'", 50),
        ],
        note="只覆盖 v3 归属能连到的方子（现库 52/69），其余保留 v1 行")

    # 12) 通路富集
    add(id="18-pathways", title="方子通路富集（Enrichr）",
        script="pregen_pathways.py", argv=[], optional=True, network=True,
        checks=[at_least("recipe_pathway", "SELECT COUNT(*) FROM recipe_pathway", 1)],
        note="第三方 API 不稳定：重跑时 ok/insufficient 分布会变（实测 58 vs 61），"
             "只校验「有行」，不校验具体条数")

    # 13) AI 解读
    add(id="19-ai-reports", title="AI 解读预生成（recipe_pregen_ai）",
        script="pregen_ai_reports.py", argv=[], optional=True, ai=True,
        checks=[exact("recipe_pregen_ai",
                      "SELECT COUNT(*) FROM recipe_pregen_ai", 69)],
        note="默认走本机 ZeroGate 网关 127.0.0.1:7863；--skip-ai 时整步跳过（表不创建）")
    add(id="20-plain", title="白话解读预生成（data/recipe_plain_ai.json）",
        script="pregen_plain.py", argv=[], optional=True, ai=True,
        check_json="data/recipe_plain_ai.json",
        checks=[],
        note="写 JSON 不写库；仓库已带 73 条时本步只补缺失")

    # 14) 营养
    add(id="21-nutrients", title="食物营养成分（39/39）",
        script="fill_nutrients.py", argv=[], hard=True,
        checks=[exact("food.nutrient_json",
                      "SELECT COUNT(*) FROM food WHERE nutrient_json IS NOT NULL "
                      "AND nutrient_json != ''", 39)])

    # 15) 自检
    add(id="22-check", title="一致性自检（必须退出码 0）",
        script="check_consistency.py", argv=[], hard=True, checks=[],
        expect_exit=0,
        note="v2≡v3、herb.compound_count 三口径（ccTCM→v3+补录 / HERB·imp→v1）、"
             "compound.target_count")
    return S


# ---------------------------------------------------------------------------
# 沙箱
# ---------------------------------------------------------------------------
def prepare_stage(target: Path, args):
    root = target / "root"
    fresh = not root.exists() or not args.force
    if root.exists() and not args.force:
        raise Fail(f"目标已存在：{root}\n续跑请加 --force（保留已建库），或换 --target-dir")
    root.mkdir(parents=True, exist_ok=True)
    if fresh:
        (target / "stage.json").write_text(json.dumps({
            "created": datetime.now().isoformat(timespec="seconds"),
            "profile": args.profile, "from_source": args.from_source,
            "skip_legacy10": args.skip_legacy10,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    (root / "scripts").mkdir(exist_ok=True)
    for p in (REPO / "scripts").glob("*.py"):
        link_or_copy(p, root / "scripts" / p.name)
    for p in (REPO / "backend" / "app").rglob("*.py"):
        rel = p.relative_to(REPO / "backend" / "app")
        link_or_copy(p, root / "backend" / "app" / rel)
    for d in ("data", "docs"):
        (root / d).mkdir(exist_ok=True)

    for rel in INPUT_FILES:
        src = REPO / rel
        if not src.exists():
            continue
        dst = root / rel
        if dst.exists() and not fresh:
            continue  # 续跑时保留已生成的 recipe_plain_ai.json
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)  # 必复制：pregen_plain 会原地重写
    for rel in INPUT_DIRS:
        src = REPO / rel
        if src.exists():
            (root / rel).mkdir(parents=True, exist_ok=True)
            shutil.copytree(src, root / rel, dirs_exist_ok=True)
    for rel in CACHE_FILES:
        src = REPO / rel
        if src.exists():
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, root / rel)
    for rel in CACHE_DIRS:
        src = REPO / rel
        if src.exists():
            copy_tree_links(src, root / rel)

    for rel in (EXT_ASTHMA, EXT_EXCEL, EXT_TRAIN, EXT_LABELS, EXT_BRIDGE):
        src = ext(rel)
        if not src.exists():
            raise Fail(f"缺少外部资源：{src}\n取得方式见 "
                       f"docs/知识库重建链路_2026-11-06.md §3")
        dst = target / rel
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    # 保存未被改动的修复版源库（sync 前还原用）
    pristine = target / "_src" / "asthma_v2_repaired.db"
    pristine.parent.mkdir(parents=True, exist_ok=True)
    if not pristine.exists():
        shutil.copy2(target / EXT_ASTHMA, pristine)

    if fresh:
        for suf in ("", "-wal", "-shm"):
            p = root / "data" / f"shiyang.db{suf}"
            if p.exists():
                p.unlink()

    if args.seed_from:
        seed_src = Path(args.seed_from)
        if not seed_src.is_absolute():
            seed_src = (REPO / seed_src).resolve()
        if not seed_src.exists():
            raise Fail(f"种子库不存在：{seed_src}")
        seed_dst = target / "_seed" / "seed.db"
        seed_dst.parent.mkdir(parents=True, exist_ok=True)
        if not seed_dst.exists():
            shutil.copy2(seed_src, seed_dst)
            log(f"  [seed] 已复制种子库：{seed_src} → {seed_dst}")
    return root


def use_legacy_source(target: Path):
    """把沙箱里大创库的 rel_herb_compound 换成修复前 rel_herb_compound_old 快照。

    只改沙箱副本。目的：复刻现库 165 成分基线——当前修复版表只含 138 个成分，
    直接建库会少 27 个成分、25,800 条靶点关联，与现库不可比。
    """
    db = target / EXT_ASTHMA
    conn = sqlite3.connect(db)
    try:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")}
        if "rel_herb_compound_old" not in tables:
            raise Fail("外部大创库缺少 rel_herb_compound_old，无法复刻 165 成分基线；"
                       "请改用 --from-source（138 成分，非现库口径）")
        conn.execute("BEGIN")
        conn.execute("DROP TABLE IF EXISTS rel_herb_compound")
        conn.execute("CREATE TABLE rel_herb_compound ("
                     "id INTEGER PRIMARY KEY AUTOINCREMENT, herb_id TEXT, compound_id TEXT,"
                     "UNIQUE(herb_id,compound_id))")
        conn.execute("INSERT INTO rel_herb_compound(herb_id,compound_id) "
                     "SELECT herb_id,compound_id FROM rel_herb_compound_old")
        conn.commit()
        n = conn.execute("SELECT COUNT(*) FROM rel_herb_compound").fetchone()[0]
        log(f"  [沙箱] 大创库基线切到修复前快照（rel_herb_compound={n} 条）")
    finally:
        conn.close()


def restore_repaired_source(target: Path):
    shutil.copy2(target / "_src" / "asthma_v2_repaired.db", target / EXT_ASTHMA)
    log("  [沙箱] 大创库还原为修复版（供 v3 同步）")


# ---------------------------------------------------------------------------
# 执行
# ---------------------------------------------------------------------------
def check_step(root: Path, step: dict):
    db = root / "data" / "shiyang.db"
    out = []
    if step.get("check_json"):
        p = root / step["check_json"]
        if not p.exists():
            raise Fail(f"校验失败：{step['check_json']} 不存在")
        items = json.loads(p.read_text(encoding="utf-8")).get("items", {})
        if len(items) < 69:
            raise Fail(f"校验失败：白话解读条目 {len(items)} < 69")
        out.append((step["check_json"] + " items", len(items), ">=69"))
        return out
    if not step.get("checks"):
        return out
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        for c in step["checks"]:
            got, ok = evaluate(conn, c)
            out.append((c["label"], got, describe(c)))
            if not ok:
                raise Fail(f"校验失败：{c['label']} = {got}，期望 {describe(c)}")
    finally:
        conn.close()
    return out


def step_runnable(step, args):
    if args.skip_ai and step.get("ai"):
        return False, "--skip-ai"
    if args.skip_network and step.get("network"):
        cached = {
            "10-expand": (REPO / CACHE_FILES[0]).exists(),
            "11-legacy10": (REPO / CACHE_FILES[1]).exists(),
            "09-chembl": (REPO / CACHE_DIRS[0]).exists(),
            "16-chembl": (REPO / CACHE_DIRS[0]).exists(),
            "18-pathways": False,  # Enrichr 无本地缓存
        }.get(step["id"], False)
        if not cached:
            return False, "--skip-network 且无本地缓存"
    return True, ""


def run_step(root: Path, target: Path, step: dict, log_path: Path, python_exe: str):
    if step.get("script") is None:  # 播种步骤
        seed = (target / "_seed" / "seed.db")
        db = root / "data" / "shiyang.db"
        for suf in ("", "-wal", "-shm"):
            p = root / "data" / f"shiyang.db{suf}"
            if p.exists():
                p.unlink()
        shutil.copy2(seed, db)
        log(f"\n[{step['id']}] {step['title']}")
        log(f"  [seed] {seed} → {db}（{db.stat().st_size:,} bytes）")
        checks = check_step(root, step)
        for label, got, exp in checks:
            log(f"  [check] {label}: {got}（期望 {exp}）")
        log(f"  [ok] {step['id']}")
        return 0.0, checks

    script = root / "scripts" / step["script"]
    if not script.exists():
        raise Fail(f"脚本不存在：{script}")
    if step.get("pre") == "use_legacy_source":
        use_legacy_source(target)
    elif step.get("pre") == "restore_repaired_source":
        restore_repaired_source(target)

    cmd = [python_exe, "-X", "utf8", str(script), *step.get("argv", [])]
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    log(f"\n[{step['id']}] {step['title']}")
    log(f"  $ {Path(python_exe).name} -X utf8 scripts/{step['script']} "
        f"{' '.join(step.get('argv', []))}".rstrip())
    t0 = time.time()
    tail = []
    with open(log_path, "a", encoding="utf-8") as lf:
        lf.write(f"\n===== [{step['id']}] {step['title']} =====\n")
        lf.write("$ " + " ".join(cmd) + "\n")
        lf.flush()
        p = subprocess.Popen(cmd, cwd=str(root), env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, encoding="utf-8", errors="replace", bufsize=1)
        for line in p.stdout:
            line = line.rstrip("\n")
            print("  " + line, flush=True)
            lf.write(line + "\n")
            lf.flush()
            tail.append(line)
            if len(tail) > 60:
                tail.pop(0)
        rc = p.wait()
    dur = time.time() - t0
    want = step.get("expect_exit", 0)
    if rc != want:
        raise Fail(f"{step['id']} 退出码 {rc}（期望 {want}）。最后输出：\n"
                   + "\n".join(tail[-20:]))
    checks = check_step(root, step)
    for label, got, exp in checks:
        log(f"  [check] {label}: {got}（期望 {exp}）")
    log(f"  [ok] {step['id']} 用时 {dur:.1f}s")
    return dur, checks


def cmdline(args, start_at=None):
    p = ["python", "-X", "utf8", "scripts/rebuild_all.py",
         "--target-dir", str(args.target_dir), "--profile", args.profile]
    for flag, on in [("--from-source", args.from_source), ("--skip-ai", args.skip_ai),
                     ("--skip-network", args.skip_network),
                     ("--skip-legacy10", args.skip_legacy10),
                     ("--continue-on-optional", args.continue_on_optional)]:
        if on:
            p.append(flag)
    if args.seed_from:
        p += ["--seed-from", str(args.seed_from)]
    if args.chembl_limit:
        p += ["--chembl-limit", str(args.chembl_limit)]
    if start_at:
        p += ["--start-at", start_at]
    p.append("--force")
    return " ".join(p)


def main():
    ap = argparse.ArgumentParser(
        description="在隔离沙箱中按序重建 shiyang.db（默认不碰生产库）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="完整链路说明：docs/知识库重建链路_2026-11-06.md")
    ap.add_argument("--target-dir", default=str(REPO / "data" / "_rebuild_run"),
                    help="沙箱目录；最终库在 <dir>/root/data/shiyang.db")
    ap.add_argument("--dry-run", action="store_true", help="只打印计划与资源检查，不建文件")
    ap.add_argument("--skip-ai", action="store_true", help="跳过需要 AI 网关/Key 的步骤")
    ap.add_argument("--skip-network", action="store_true",
                    help="跳过需要联网且无本地缓存的步骤")
    ap.add_argument("--skip-legacy10", action="store_true",
                    help="跳过 2026-11-06 的 10 味补录 → 停在 19 张业务表基线")
    ap.add_argument("--profile", choices=["current", "full"], default="current",
                    help="current=复刻现库口径（研究类只覆盖旧 165 成分）；"
                         "full=研究类覆盖全库（慢）")
    ap.add_argument("--from-source", action="store_true",
                    help="直接用当前修复版大创库（138 成分），不复刻现库 165 基线")
    ap.add_argument("--seed-from", default=None,
                    help="用历史快照库作种子（复刻现库分析行；默认候选见 "
                         + "、".join(SEED_CANDIDATES) + "）")
    ap.add_argument("--start-at", default=None, help="从指定步骤 id 开始（续跑）")
    ap.add_argument("--force", action="store_true", help="目标已存在时保留并续跑")
    ap.add_argument("--continue-on-optional", action="store_true",
                    help="可选步骤失败时记录并继续（默认任何失败都停）")
    ap.add_argument("--chembl-limit", type=int, default=None,
                    help="传给 fetch_chembl_activity.py 的 --limit")
    ap.add_argument("--python", default=None,
                    help="跑各步骤子进程用的解释器路径。默认用当前解释器。"
                         "建议指向专用环境 .venv-rebuild（见 docs/知识库重建链路_2026-11-06.md §6.3），"
                         "否则 UMAP 步骤会因 base 环境 sklearn 版本过低被跳过")
    args = ap.parse_args()
    args.target_dir = Path(args.target_dir).resolve()

    try:
        # 解释器：默认用仓库内专用环境 .venv-rebuild（若存在），否则当前解释器；
        # --python 可显式覆盖。显式传了就要求真实存在，避免「写错路径 → 每步都
        # FileNotFoundError」这种难查的失败。放在 try 内，让 Fail 走统一的退出码 2。
        if args.python:
            py = Path(args.python).expanduser()
            if not py.exists():
                raise Fail(f"--python 不存在：{py}")
            python_exe = str(py.resolve())
        else:
            default_venv = REPO / ".venv-rebuild" / "Scripts" / "python.exe"
            python_exe = str(default_venv) if default_venv.exists() else sys.executable

        chem_map_bad = preflight_chem_map(python_exe)

        if args.target_dir == (REPO / "data").resolve():
            raise Fail("--target-dir 不能是 data/ 本身（生产库所在地）")
        if (args.target_dir / "root" / "data" / "shiyang.db").resolve() == PROD_DB:
            raise Fail("目标库路径等于生产库，拒绝执行")

        steps = build_steps(args)
        ids = [s["id"] for s in steps]
        if args.start_at and args.start_at not in ids:
            raise Fail(f"--start-at 无效：{args.start_at}；可选：{', '.join(ids)}")

        log("=" * 78)
        log("shiyang.db 重建计划（隔离沙箱）")
        log(f"  仓库    : {REPO}")
        log(f"  沙箱    : {args.target_dir}")
        log(f"  最终库  : {args.target_dir / 'root' / 'data' / 'shiyang.db'}")
        log(f"  生产库  : {PROD_DB}（本脚本不会写入）")
        log(f"  解释器  : {python_exe}")
        log(f"  口径    : profile={args.profile}  from_source={args.from_source}  "
            f"legacy10={'off' if args.skip_legacy10 else 'on'}  "
            f"seed={'yes' if args.seed_from else 'no'}")
        log(f"  预期表  : {'19 张业务表（CORE19）' if args.skip_legacy10 else '21 张（CORE19 + 补录 2 表）'}"
            f"{'，跳过 AI 时无 recipe_pregen_ai' if args.skip_ai else ''}")
        log("=" * 78)

        log("\n[资源检查]")
        hard_missing = []
        for name, path, impact in resource_rows():
            ok = path.exists()
            log(f"  {'OK  ' if ok else 'MISS'} {name}: {path}")
            if not ok:
                log(f"       → {impact}")
                if name.startswith(("大创修复库", "溯源 Excel")):
                    hard_missing.append(name)
        log(f"  AI 网关 127.0.0.1:7863: {'OPEN' if ai_gateway_open() else 'CLOSED'}"
            f"；SHIYANG_AI_KEY={'SET' if os.environ.get('SHIYANG_AI_KEY') else 'unset'}")
        log(f"  UMAP 预检: {'OK' if not chem_map_bad else 'WARN ' + chem_map_bad}")
        if hard_missing and not args.dry_run:
            raise Fail(f"缺少硬前置资源：{'、'.join(hard_missing)}")

        log("\n[步骤计划]")
        for i, s in enumerate(steps, 1):
            run_ok, why = step_runnable(s, args)
            if run_ok and s["id"] in ("08-chem-map", "15-chem-map") and chem_map_bad:
                run_ok, why = False, "UMAP 环境不兼容（见预检）"
            if args.start_at and ids.index(s["id"]) < ids.index(args.start_at):
                state = "SKIP(--start-at 之前)"
            elif not run_ok:
                state = f"SKIP({why})"
            else:
                state = "RUN(可选)" if s.get("optional") else "RUN"
            tag = " [network]" if s.get("network") else ""
            log(f"  {i:02d}. {s['id']:<20} {state:<26}{tag} {s['title']}")
            for c in s.get("checks", []):
                log(f"        - 校验 {c['label']} → {describe(c)}")
            if s.get("note"):
                log(f"        注：{s['note']}")

        if args.dry_run:
            log("\n[dry-run] 只打印计划，未创建文件、未执行脚本。")
            log(f"实跑命令：{cmdline(args)}")
            return 0

        target = args.target_dir
        root = prepare_stage(target, args)
        log_path = target / "rebuild.log"
        report = {"started": datetime.now().isoformat(timespec="seconds"),
                  "target": str(target), "profile": args.profile,
                  "from_source": args.from_source,
                  "skip_legacy10": args.skip_legacy10, "steps": []}

        started = args.start_at is None
        t_all = time.time()
        for s in steps:
            if not started:
                if s["id"] != args.start_at:
                    continue
                started = True
            run_ok, why = step_runnable(s, args)
            if run_ok and s["id"] in ("08-chem-map", "15-chem-map") and chem_map_bad:
                run_ok, why = False, "UMAP 环境不兼容（见预检）"
            if not run_ok:
                log(f"\n[{s['id']}] SKIP：{why}")
                report["steps"].append({"id": s["id"], "status": "skipped", "reason": why})
                continue
            try:
                dur, checks = run_step(root, target, s, log_path, python_exe)
                report["steps"].append({
                    "id": s["id"], "status": "ok", "seconds": round(dur, 1),
                    "checks": [{"label": a, "got": b, "expect": c} for a, b, c in checks]})
            except Fail as e:
                if s.get("optional") and args.continue_on_optional:
                    log(f"\n[{s['id']}] 可选步骤失败（--continue-on-optional 继续）：{e}")
                    report["steps"].append({"id": s["id"], "status": "failed_optional",
                                            "error": str(e)})
                    continue
                log(f"\n[FAIL] {s['id']}：{e}")
                report["steps"].append({"id": s["id"], "status": "failed", "error": str(e)})
                report["resume_command"] = cmdline(args, start_at=s["id"])
                (target / "rebuild_report.json").write_text(
                    json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
                log("\n续跑命令（可复制）：")
                log("  " + report["resume_command"])
                log(f"日志：{log_path}")
                return 1

        db = root / "data" / "shiyang.db"
        conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
        try:
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name")]
            counts = {t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]
                      for t in tables}
        finally:
            conn.close()

        expected = list(CORE19) + ([] if args.skip_legacy10 else LEGACY10_TABLES)
        if args.skip_ai:
            expected = [t for t in expected if t != "recipe_pregen_ai"]
        # 被主动跳过的步骤（环境/参数原因）不产生表，属于"已知缺失"，不算失败
        skipped_ids = {s["id"] for s in report["steps"] if s["status"] == "skipped"}
        skipped_tables = set()
        if "19-ai-reports" in skipped_ids:
            skipped_tables.add("recipe_pregen_ai")
        if "18-pathways" in skipped_ids:
            skipped_tables.add("recipe_pathway")
        if "08-chem-map" in skipped_ids or "15-chem-map" in skipped_ids:
            skipped_tables.add("compound_map")
        if "09-chembl" in skipped_ids or "16-chembl" in skipped_ids:
            skipped_tables.add("compound_chembl_activity")
        missing = [t for t in expected if t not in tables and t not in skipped_tables]
        known_absent = [t for t in expected if t not in tables and t in skipped_tables]

        report["finished"] = datetime.now().isoformat(timespec="seconds")
        report["seconds"] = round(time.time() - t_all, 1)
        report["tables"] = counts
        report["missing_tables"] = missing
        report["known_absent_tables"] = sorted(known_absent)
        (target / "rebuild_report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        log("\n" + "=" * 78)
        log(f"重建完成：{len(tables)} 张业务表，用时 {report['seconds']:.0f}s")
        for t in tables:
            log(f"  {t:<28} {counts[t]:>7}")
        if known_absent:
            log(f"\n[已知缺失] 因步骤被跳过而未创建：{sorted(known_absent)}")
            log("           （用 --skip-ai / --skip-network / UMAP 预检 控制，详见链路文档 §4）")
        if missing:
            log(f"\n[警告] 期望但缺失的表：{missing}")
        log(f"\n库文件：{db}")
        log(f"报告  ：{target / 'rebuild_report.json'}")
        log(f"日志  ：{log_path}")
        log("=" * 78)
        return 0 if not missing else 1
    except Fail as e:
        log(f"\n[ERROR] {e}")
        return 2
    except KeyboardInterrupt:
        log("\n[中断] 沙箱已保留，用 --force --start-at <步骤> 续跑。")
        return 130


if __name__ == "__main__":
    sys.exit(main())
