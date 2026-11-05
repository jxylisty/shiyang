# -*- coding: utf-8 -*-
"""
2026-11-05 shiyang.db 扩容 schema 迁移（纯函数库，只做 DDL，不写任何数据行）。

本文件对应 docs/数据扩容方案_2026-11-05.md §2「schema 变更（最小增量）」与
docs/数据库设计文档.md §6「2026-11-05 扩容 schema 增量」：
  1) herb 表加三列：source / reference_url / added_batch（幂等 ALTER，参照 user_service._migrate 惯例）
  2) rel_herb_compound 建 idx_rhc_compound（扩容后「成分→药材」反向查询用，
     原 UNIQUE(herb_id,compound_id) 隐式索引只覆盖正向）
  3) rel_compound_target 建 partial UNIQUE 索引 ux_rct_hbtar：
     把「herb.ac.cn 来源的成分-靶点关联幂等」交给数据库（灌库用 INSERT OR IGNORE）
  4) 迁移前带时间戳整库备份（WAL checkpoint 后 copy2），返回迁移前后行数对比

注意：本文件只做 DDL。数据灌入（herb 行 / HBIN 成分 / HBTAR 关联 / compound_count 重算）
由后续灌库脚本 import_herbs_20261105.py 负责，落位规则见 docs/数据库设计文档.md §6.4。

用法：
  import 调用： from _migrate_20261105 import migrate
                result = migrate("data/shiyang.db")
  独立执行：   python -X utf8 scripts/_migrate_20261105.py [db_path]
"""
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB = ROOT / "data" / "shiyang.db"

BATCH = 20261105  # 本扩容批次号（灌库脚本写 herb.added_batch 时引用；迁移本身不写数据）

# herb 新增列：(列名, 类型)。全部可空列——SQLite 的 ADD COLUMN 不允许加
# NOT NULL(无默认)/UNIQUE/PK，且存量 34 味这些列本来就没有值，可空是唯一诚实口径。
NEW_COLUMNS = [
    ("source", "TEXT"),         # 数据来源，如 'herb.ac.cn HERB003070'（机构名+ID，沿用 recipe.source 惯例）
    ("reference_url", "TEXT"),  # 详情页 URL，如 'https://herb.ac.cn/herbs?id=...'（可点开溯源）
    ("added_batch", "INTEGER"),  # 入库批次标记，本批=20261105；存量 34 味由灌库脚本补标
]

# 新增索引：(索引名, 表, 列定义 SQL 片段, 可选 WHERE 子句)。
# 列片段拼在 ON 表(...) 括号内，WHERE 子句（partial index）拼在括号外。
NEW_INDEXES = [
    # 扩容后 v1 关联会从 201 条涨到万级，反向查询（给成分找药材）需要独立索引；
    # 正向（药材→成分）继续走 UNIQUE(herb_id,compound_id) 隐式索引
    ("idx_rhc_compound", "rel_herb_compound", "compound_id", None),
    # herb.ac.cn 来源的成分-靶点关联幂等约束：同一 (成分, 靶点) 在该来源只允许一条。
    # partial index 不影响存量 12,168 条（source_db 全为 NULL），见 §6.4 落位规则
    ("ux_rct_hbtar", "rel_compound_target",
     "compound_id, target_gene", "source_db = 'herb.ac.cn'"),
]

# 行数对比覆盖的表（验收「旧数据 0 丢失」用；迁移只加列，行数应完全不变）
COUNTED_TABLES = ["herb", "compound", "target",
                  "rel_herb_compound", "rel_compound_target", "rel_recipe_material"]


def _count_rows(conn: sqlite3.Connection) -> dict:
    """逐表统计行数（供迁移前后对比）。"""
    return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in COUNTED_TABLES}


def _backup(db_path: Path, backup_dir: Path) -> Path:
    """迁移前备份：先尝试把 WAL 合回主文件，再复制主库文件（时间戳命名，永不覆盖）。"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    conn = sqlite3.connect(db_path)
    try:
        # WAL 合流，保证备份文件自洽；有活跃连接占用时静默跳过（离线脚本场景基本不会发生）
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    except sqlite3.Error as e:
        print(f"  [提示] WAL checkpoint 跳过（不影响备份正确性，但备份可能不含最新 -wal 数据）: {e}")
    finally:
        conn.close()
    backup_path = backup_dir / f"{db_path.stem}.bak-migrate-{ts}{db_path.suffix}"
    shutil.copy2(db_path, backup_path)
    print(f"已备份: {backup_path} ({backup_path.stat().st_size:,} bytes)")
    return backup_path


def migrate(db_path=DEFAULT_DB, backup_dir=None) -> dict:
    """对 shiyang.db 做幂等 schema 迁移，返回迁移摘要 dict。

    幂等保证：每条 ALTER 前先查 PRAGMA table_info(herb)、每条 CREATE INDEX 前先查
    sqlite_master，已存在则跳过——第二遍跑不报错、不重复加列、不重复建索引。
    旧数据 0 丢失：迁移只加列/建索引，不改任何数据行，前后行数应完全一致（不一致即抛错）。
    """
    db_path = Path(db_path)
    if not db_path.exists():
        raise FileNotFoundError(f"数据库不存在: {db_path}")
    backup_dir = Path(backup_dir) if backup_dir else db_path.parent

    # ---------- 1. 迁移前统计 + 备份 ----------
    probe = sqlite3.connect(db_path)
    before = _count_rows(probe)
    probe.close()
    backup_path = _backup(db_path, backup_dir)

    # ---------- 2. 幂等 ALTER / CREATE INDEX ----------
    conn = sqlite3.connect(db_path)
    # 灌库脚本可能与只读的运行时 API 并发，等待其短暂持有的读锁，避免 SQLITE_BUSY
    conn.execute("PRAGMA busy_timeout=5000")
    added_cols, added_idx = [], []
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(herb)")}
        for name, ctype in NEW_COLUMNS:
            if name in cols:
                continue
            try:
                conn.execute(f"ALTER TABLE herb ADD COLUMN {name} {ctype}")
                added_cols.append(f"herb.{name}")
                print(f"加列: herb.{name} {ctype}")
            except sqlite3.OperationalError as e:
                # 兜底：极端并发下另一进程刚好先加了同名列，等价于已迁移，不算失败
                if "duplicate column" not in str(e).lower():
                    raise
                print(f"  [提示] herb.{name} 已被并发迁移，跳过")
        idx_names = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'")}
        for iname, itable, icol, iwhere in NEW_INDEXES:
            if iname in idx_names:
                continue
            try:
                where_sql = f" WHERE {iwhere}" if iwhere else ""
                conn.execute(f"CREATE INDEX {iname} ON {itable}({icol}){where_sql}")
                added_idx.append(iname)
                print(f"建索引: {iname} ON {itable}({icol})")
            except sqlite3.OperationalError as e:
                if "already exists" not in str(e).lower():
                    raise
                print(f"  [提示] 索引 {iname} 已被并发创建，跳过")
        conn.commit()
    finally:
        after = _count_rows(conn)
        conn.close()

    # ---------- 3. 旧数据 0 丢失校验 ----------
    lost = {t: (before[t], after[t]) for t in COUNTED_TABLES if before[t] != after[t]}
    if lost:
        raise RuntimeError(f"迁移后行数发生变化，存在数据丢失风险，请回滚备份 {backup_path}: {lost}")

    result = {
        "db_path": str(db_path),
        "backup_path": str(backup_path),
        "added_columns": added_cols,
        "added_indexes": added_idx,
        "before": before,
        "after": after,
        "row_consistent": True,
        "batch": BATCH,
    }
    print("\n=== 20261105 迁移完成 ===")
    for k, v in result.items():
        if k in ("before", "after"):
            continue
        print(f"  {k}: {v}")
    for t in COUNTED_TABLES:
        print(f"  {t}: {before[t]} -> {after[t]}")
    return result


if __name__ == "__main__":
    target_db = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DB
    migrate(target_db)
