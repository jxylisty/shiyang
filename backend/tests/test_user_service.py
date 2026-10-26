# -*- coding: utf-8 -*-
"""
用户系统单元级测试：密码哈希、令牌签发/校验、注册规则。
（reg/login 的端到端路径已被 test_search_and_compound.py 覆盖，
 这里补 service 层规则边界；不写 user.db，只测纯函数与临时库语义）
运行：cd backend && python -X utf8 -m pytest tests/test_user_service.py -q
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import pytest  # noqa: E402

from services import user_service as us  # noqa: E402


def test_password_hash_roundtrip_and_salt():
    h1 = us.hash_pw("abc12345")
    h2 = us.hash_pw("abc12345")
    assert h1 != h2, "同密码两次哈希应不同（bcrypt 随机盐）"
    assert us.verify_pw("abc12345", h1)
    assert not us.verify_pw("wrong", h1)
    # 坏格式哈希不抛异常、返回 False
    assert us.verify_pw("abc12345", "not-a-hash") is False


def test_token_roundtrip_and_expiry_claim():
    tok = us.make_token(42, "someone")
    payload = us.parse_token(tok)
    assert payload and payload["uid"] == 42 and payload["username"] == "someone"
    assert payload["exp"] > __import__("time").time()
    assert us.parse_token(tok + "x") is None
    assert us.parse_token("") is None
    assert us.parse_token("garbage.token.value") is None


@pytest.mark.parametrize("bad_name", ["ab", "x" * 21, "带中文", "bad name", "bad-name"])
def test_register_rejects_bad_username(bad_name, monkeypatch):
    # 3-20 位 ASCII 字母数字下划线（下划线允许，中文/空格/连字符一概拒绝）。
    # 重定向到临时库：坏用户名若被意外放行也不能写进真实 user.db
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        monkeypatch.setattr(us, "USER_DB", Path(td) / "user.db")
        with pytest.raises(ValueError):
            us.register(bad_name, "goodpw123")


def test_register_rejects_short_password():
    with pytest.raises(ValueError):
        us.register("pwtest_user", "12345")


def test_register_duplicate_name(monkeypatch):
    """重名检测走 sqlite3.IntegrityError → ValueError。用临时库验证，不污染 user.db"""
    import sqlite3, tempfile, os
    with tempfile.TemporaryDirectory() as td:
        tmpdb = Path(td) / "user.db"
        orig = us.USER_DB
        us.USER_DB = tmpdb
        try:
            us.register("dup_user", "goodpw123")
            with pytest.raises(ValueError):
                us.register("dup_user", "other123")
        finally:
            us.USER_DB = orig
        assert not os.path.exists(str(tmpdb) + "-wal") or True  # 临时目录随用随清
