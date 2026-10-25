# -*- coding: utf-8 -*-
"""
用户系统服务：注册登录(JWT) + 体质档案历史 + 收藏
存储在独立的 data/user.db（与方子库 shiyang.db 分离，重建方子库不丢用户数据）
"""
import json
import os
import sqlite3
import time
from pathlib import Path

import bcrypt
import jose.jwt as jwt
from jose import JWTError

USER_DB = Path(__file__).resolve().parents[3] / "data" / "user.db"
# 生产环境用环境变量 SHIYANG_JWT_SECRET 覆盖；缺省值仅供本地开发
JWT_SECRET = os.environ.get("SHIYANG_JWT_SECRET") or "shiyang-dev-secret-change-in-prod"
JWT_EXP = 60 * 60 * 24 * 14  # 14 天

_SCHEMA = """
CREATE TABLE IF NOT EXISTS user (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    nickname TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE TABLE IF NOT EXISTS constitution_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES user(id),
    main_code TEXT, main_name TEXT,
    combined TEXT,           -- JSON 兼夹codes
    transformed TEXT,        -- JSON 全维度转化分
    answers TEXT,            -- JSON 原始作答（复现用）
    member_id INTEGER,       -- 家庭成员（T2-8；NULL=本人）
    created_at TEXT DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_cr_user ON constitution_record(user_id);
CREATE TABLE IF NOT EXISTS favorite (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES user(id),
    recipe_id INTEGER NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, recipe_id)
);
CREATE TABLE IF NOT EXISTS checkin (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES user(id),
    recipe_id INTEGER NOT NULL,
    day TEXT NOT NULL,           -- YYYY-MM-DD（本地日期，一天一方一条）
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, recipe_id, day)
);
CREATE INDEX IF NOT EXISTS idx_ck_user_day ON checkin(user_id, day);
CREATE TABLE IF NOT EXISTS family_member (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES user(id),
    name TEXT NOT NULL,
    relation TEXT,                -- 妈妈/爸爸/孩子/伴侣/自定义
    color TEXT,                   -- 头像底色
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(user_id, name)
);
CREATE INDEX IF NOT EXISTS idx_fm_user ON family_member(user_id);
"""


def db():
    conn = sqlite3.connect(USER_DB)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(_SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn):
    """存量库增量迁移：老 constitution_record 无 member_id 列（T2-8 家庭档案）"""
    cols = {r[1] for r in conn.execute("PRAGMA table_info(constitution_record)")}
    if "member_id" not in cols:
        conn.execute("ALTER TABLE constitution_record ADD COLUMN member_id INTEGER")
        conn.commit()


# ---------- 认证 ----------

def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()


def verify_pw(pw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except ValueError:
        return False


def make_token(uid: int, username: str) -> str:
    payload = {"uid": uid, "username": username, "exp": int(time.time()) + JWT_EXP}
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")


def parse_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except JWTError:
        return None


def register(username: str, password: str, nickname: str | None = None) -> dict:
    if not (3 <= len(username) <= 20) or not username.replace("_", "").isalnum():
        raise ValueError("用户名需3-20位字母数字下划线")
    if len(password) < 6:
        raise ValueError("密码至少6位")
    conn = db()
    try:
        cur = conn.execute("INSERT INTO user(username,password_hash,nickname) VALUES (?,?,?)",
                           (username, hash_pw(password), nickname or username))
        conn.commit()
        uid = cur.lastrowid
        return {"id": uid, "username": username, "nickname": nickname or username,
                "token": make_token(uid, username)}
    except sqlite3.IntegrityError:
        raise ValueError("用户名已被注册")
    finally:
        conn.close()


def login(username: str, password: str) -> dict:
    conn = db()
    try:
        row = conn.execute("SELECT * FROM user WHERE username=?", (username,)).fetchone()
        if not row or not verify_pw(password, row["password_hash"]):
            raise ValueError("用户名或密码错误")
        return {"id": row["id"], "username": row["username"], "nickname": row["nickname"],
                "token": make_token(row["id"], row["username"])}
    finally:
        conn.close()


# ---------- 体质档案 ----------

def save_record(uid: int, judged: dict, transformed: dict, answers: dict,
                member_id: int | None = None) -> int:
    conn = db()
    try:
        cur = conn.execute(
            "INSERT INTO constitution_record(user_id,main_code,main_name,combined,transformed,answers,member_id) "
            "VALUES (?,?,?,?,?,?,?)",
            (uid, judged.get("main"), judged.get("main_name"),
             json.dumps(judged.get("combined", []), ensure_ascii=False),
             json.dumps(transformed, ensure_ascii=False),
             json.dumps(answers, ensure_ascii=False), member_id))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_records(uid: int, limit: int = 20) -> list[dict]:
    conn = db()
    try:
        rows = conn.execute(
            "SELECT r.id, r.main_code, r.combined, r.transformed, r.created_at, r.member_id, m.name AS member_name "
            "FROM constitution_record r LEFT JOIN family_member m ON m.id=r.member_id "
            "WHERE r.user_id=? ORDER BY r.id DESC LIMIT ?",
            (uid, limit)).fetchall()
        out = []
        for r in rows:
            out.append({"id": r["id"], "main_code": r["main_code"],
                        "main_name": NAME_BY_CODE.get(r["main_code"], r["main_code"]),
                        "combined": [NAME_BY_CODE.get(c, c) for c in json.loads(r["combined"] or "[]")],
                        "transformed": json.loads(r["transformed"] or "{}"),
                        "created_at": r["created_at"],
                        "member_id": r["member_id"], "member_name": r["member_name"]})
        return out
    finally:
        conn.close()


# ---------- 家庭成员（T2-8） ----------

def add_member(uid: int, name: str, relation: str | None = None, color: str | None = None) -> dict:
    name = (name or "").strip()
    if not (1 <= len(name) <= 12):
        raise ValueError("成员名需1-12字")
    conn = db()
    try:
        cur = conn.execute(
            "INSERT INTO family_member(user_id,name,relation,color) VALUES (?,?,?,?)",
            (uid, name, relation, color))
        conn.commit()
        return {"id": cur.lastrowid, "name": name, "relation": relation, "color": color}
    except sqlite3.IntegrityError:
        raise ValueError("同名成员已存在")
    finally:
        conn.close()


def list_members(uid: int) -> list[dict]:
    conn = db()
    try:
        rows = conn.execute(
            "SELECT id,name,relation,color,created_at FROM family_member WHERE user_id=? ORDER BY id",
            (uid,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def remove_member(uid: int, member_id: int) -> bool:
    conn = db()
    try:
        # 成员的历史测评保留（member_id 悬挂引用时 member_name 显示为空），不级联删除
        cur = conn.execute("DELETE FROM family_member WHERE id=? AND user_id=?", (member_id, uid))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


NAME_BY_CODE = {"pinghe": "平和质", "qixu": "气虚质", "yangxu": "阳虚质", "yinxu": "阴虚质",
                "tanshi": "痰湿质", "shire": "湿热质", "xueyu": "血瘀质", "qiyu": "气郁质", "tebing": "特禀质"}


# ---------- 收藏 ----------

def add_favorite(uid: int, recipe_id: int):
    conn = db()
    try:
        conn.execute("INSERT OR IGNORE INTO favorite(user_id,recipe_id) VALUES (?,?)", (uid, recipe_id))
        conn.commit()
    finally:
        conn.close()


def remove_favorite(uid: int, recipe_id: int):
    conn = db()
    try:
        conn.execute("DELETE FROM favorite WHERE user_id=? AND recipe_id=?", (uid, recipe_id))
        conn.commit()
    finally:
        conn.close()


def list_favorites(uid: int) -> list[int]:
    conn = db()
    try:
        return [r[0] for r in conn.execute(
            "SELECT recipe_id FROM favorite WHERE user_id=? ORDER BY id DESC", (uid,)).fetchall()]
    finally:
        conn.close()


# ---------- 饮用打卡（P2） ----------

def add_checkin(uid: int, recipe_id: int) -> dict:
    """当日打卡（一天一方一条，重复打卡幂等返回 already=True）"""
    day = time.strftime("%Y-%m-%d")
    conn = db()
    try:
        cur = conn.execute("INSERT OR IGNORE INTO checkin(user_id,recipe_id,day) VALUES (?,?,?)",
                           (uid, recipe_id, day))
        conn.commit()
        return {"recipe_id": recipe_id, "day": day,
                "already": cur.rowcount == 0}
    finally:
        conn.close()


def remove_checkin(uid: int, recipe_id: int) -> dict:
    day = time.strftime("%Y-%m-%d")
    conn = db()
    try:
        conn.execute("DELETE FROM checkin WHERE user_id=? AND recipe_id=? AND day=?",
                     (uid, recipe_id, day))
        conn.commit()
        return {"recipe_id": recipe_id, "day": day, "removed": True}
    finally:
        conn.close()


def _streak(days: set[str]) -> int:
    """连续打卡天数：从今天（或昨天）往前数"""
    from datetime import date, timedelta
    d = date.today()
    if d.isoformat() not in days:
        d -= timedelta(days=1)
        if d.isoformat() not in days:
            return 0
    n = 0
    while d.isoformat() in days:
        n += 1
        d -= timedelta(days=1)
    return n


def list_checkins(uid: int, days: int = 30) -> dict:
    """近 N 天打卡记录 + 连续天数 + 今日打卡的方子 id 列表"""
    from datetime import date, timedelta
    since = (date.today() - timedelta(days=days - 1)).isoformat()
    conn = db()
    try:
        rows = conn.execute(
            "SELECT recipe_id, day FROM checkin WHERE user_id=? AND day>=? ORDER BY day DESC",
            (uid, since)).fetchall()
    finally:
        conn.close()
    records = [{"recipe_id": r["recipe_id"], "day": r["day"]} for r in rows]
    day_set = {r["day"] for r in rows}
    today = date.today().isoformat()
    return {
        "records": records,
        "streak": _streak(day_set),
        "total": len(day_set),
        "today": sorted({r["recipe_id"] for r in rows if r["day"] == today}),
    }
