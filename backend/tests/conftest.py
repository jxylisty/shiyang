# -*- coding: utf-8 -*-
"""
测试兜底清理（AGENTS.md §2.7：测试数据测完即删）。
用例中途断言失败时，用例内的内联清理不会执行，测试账号会残留在 user.db。
本 fixture 在每个用例结束后，把本次用例期间新出现、且明显是测试模式的账号
连同其打卡/收藏/档案数据一起删除。只删 t_/uitest_/smoke_/tester 前缀的
测试模式用户名，绝不触碰真实用户数据。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import pytest  # noqa: E402

TEST_PREFIXES = ("t_", "uitest_", "smoke_", "tester")


@pytest.fixture(autouse=True)
def _cleanup_test_users():
    from services import user_service as us
    conn = us.db()
    before = {r[0] for r in conn.execute("SELECT username FROM user").fetchall()}
    conn.close()
    yield
    conn = us.db()
    try:
        after = [r[0] for r in conn.execute("SELECT username FROM user").fetchall()
                 if r[0] not in before and r[0].startswith(TEST_PREFIXES)]
        if not after:
            return
        conn.execute("PRAGMA foreign_keys=OFF")
        ph = ",".join("?" * len(after))
        uids = [r[0] for r in conn.execute(
            f"SELECT id FROM user WHERE username IN ({ph})", after).fetchall()]
        if not uids:
            return
        uph = ",".join("?" * len(uids))
        # §2.7 顺序：checkin→favorite→constitution_record→family_member→user
        for table in ("checkin", "favorite", "constitution_record", "family_member"):
            conn.execute(f"DELETE FROM {table} WHERE user_id IN ({uph})", uids)
        conn.execute(f"DELETE FROM user WHERE id IN ({uph})", uids)
        conn.commit()
    finally:
        conn.close()
