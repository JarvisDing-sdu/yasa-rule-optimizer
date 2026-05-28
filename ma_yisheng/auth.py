# -*- coding: utf-8 -*-
"""用户认证模块：注册、登录、JWT"""

import sqlite3
import time
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict

try:
    import bcrypt
    HAS_BCRYPT = True
except ImportError:
    import hashlib
    import os as _os
    HAS_BCRYPT = False

try:
    import jwt
except ImportError:
    jwt = None




def get_db_path() -> Path:
    """获取数据库路径"""
    from config import get_project_root
    return get_project_root() / "users.db"


def _connect():
    """获取数据库连接（WAL 模式，多线程安全）"""
    conn = sqlite3.connect(str(get_db_path()), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """初始化数据库表"""
    conn = _connect()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS verification_codes (
            email TEXT NOT NULL,
            code TEXT NOT NULL,
            expire_at REAL NOT NULL,
            last_sent_at REAL NOT NULL DEFAULT 0,
            PRIMARY KEY (email)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS login_attempts (
            key TEXT PRIMARY KEY,
            fail_count INTEGER NOT NULL DEFAULT 0,
            locked_until REAL NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scan_tasks (
            task_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            scan_path TEXT,
            lang TEXT,
            progress TEXT,
            result TEXT,
            created_at TEXT,
            finished_at REAL
        )
    """)
    conn.commit()
    conn.close()


def check_login_allowed(key: str, max_fails: int = 5, lockout_seconds: int = 900) -> bool:
    """检查该 key（ip:email）是否被锁定，返回 True 表示允许登录"""
    db_path = get_db_path()
    conn = _connect()
    row = conn.execute("SELECT fail_count, locked_until FROM login_attempts WHERE key=?", (key,)).fetchone()
    conn.close()
    if not row:
        return True
    fail_count, locked_until = row
    if time.time() < locked_until:
        return False
    return fail_count < max_fails


def record_login_fail(key: str, max_fails: int = 5, lockout_seconds: int = 900):
    """记录一次登录失败，达到上限后锁定"""
    db_path = get_db_path()
    conn = _connect()
    row = conn.execute("SELECT fail_count FROM login_attempts WHERE key=?", (key,)).fetchone()
    fail_count = (row[0] if row else 0) + 1
    locked_until = time.time() + lockout_seconds if fail_count >= max_fails else 0
    conn.execute(
        "INSERT INTO login_attempts (key, fail_count, locked_until) VALUES (?,?,?) ON CONFLICT(key) DO UPDATE SET fail_count=excluded.fail_count, locked_until=excluded.locked_until",
        (key, fail_count, locked_until)
    )
    conn.commit()
    conn.close()


def record_login_success(key: str):
    """登录成功后清除失败记录"""
    db_path = get_db_path()
    conn = _connect()
    conn.execute("DELETE FROM login_attempts WHERE key=?", (key,))
    conn.commit()
    conn.close()


def hash_password(password: str) -> str:
    """密码哈希"""
    if HAS_BCRYPT:
        return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    else:
        # bcrypt 不可用时用 PBKDF2-HMAC-SHA256 加盐，格式：pbkdf2$<hex_salt>$<hex_hash>
        salt = _os.urandom(32)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260000)
        return f"pbkdf2${salt.hex()}${dk.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    """验证密码"""
    if HAS_BCRYPT and not password_hash.startswith("pbkdf2$"):
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    if password_hash.startswith("pbkdf2$"):
        try:
            _, salt_hex, dk_hex = password_hash.split("$")
            salt = bytes.fromhex(salt_hex)
            dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 260000)
            return dk.hex() == dk_hex
        except Exception:
            return False
    # 兼容旧的无盐 SHA256 记录（只读，不再写入）
    return hashlib.sha256(password.encode()).hexdigest() == password_hash


def generate_verification_code() -> str:
    """生成 6 位验证码"""
    return str(secrets.randbelow(1000000)).zfill(6)


def save_verification_code(email: str, code: str, ttl: int = 300):
    """保存验证码到数据库，ttl 秒后过期"""
    expire_at = time.time() + ttl
    db_path = get_db_path()
    conn = _connect()
    conn.execute(
        "INSERT OR REPLACE INTO verification_codes (email, code, expire_at, last_sent_at) VALUES (?, ?, ?, COALESCE((SELECT last_sent_at FROM verification_codes WHERE email=?), 0))",
        (email, code, expire_at, email)
    )
    conn.commit()
    conn.close()


def verify_code(email: str, code: str) -> bool:
    """验证验证码，验证成功后删除"""
    db_path = get_db_path()
    conn = _connect()
    row = conn.execute(
        "SELECT code, expire_at FROM verification_codes WHERE email = ?", (email,)
    ).fetchone()
    if not row:
        conn.close()
        return False
    saved_code, expire_at = row
    if time.time() > expire_at or saved_code != code:
        conn.close()
        return False
    conn.execute("DELETE FROM verification_codes WHERE email = ?", (email,))
    conn.commit()
    conn.close()
    return True


def try_acquire_send_slot(email: str, interval: int = 60) -> bool:
    """原子检查并获取发送槽位。返回 True 表示可以发送，同时已更新时间戳。"""
    now = time.time()
    conn = _connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        row = conn.execute(
            "SELECT last_sent_at FROM verification_codes WHERE email = ?", (email,)
        ).fetchone()
        if row and now - row[0] < interval:
            conn.commit()
            return False
        conn.execute(
            "INSERT INTO verification_codes (email, code, expire_at, last_sent_at) VALUES (?, '', 0, ?) "
            "ON CONFLICT(email) DO UPDATE SET last_sent_at=excluded.last_sent_at",
            (email, now)
        )
        conn.commit()
        return True
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()


def create_user(email: str, password: str) -> Optional[int]:
    """创建用户，返回 user_id，失败返回 None"""
    try:
        init_db()
        db_path = get_db_path()
        conn = _connect()
        password_hash = hash_password(password)
        created_at = datetime.now().isoformat()
        cursor = conn.execute(
            "INSERT INTO users (email, password_hash, created_at) VALUES (?, ?, ?)",
            (email, password_hash, created_at)
        )
        user_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return user_id
    except sqlite3.IntegrityError:
        return None
    except Exception:
        return None


def get_user_by_email(email: str) -> Optional[Dict]:
    """根据邮箱获取用户，返回 {id, email, password_hash}"""
    try:
        init_db()
        db_path = get_db_path()
        conn = _connect()
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT id, email, password_hash FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)
        return None
    except Exception:
        return None


def create_jwt_token(user_id: int, email: str, secret: str, expire_days: int = 30) -> Optional[str]:
    """生成 JWT token"""
    if not jwt:
        return None
    try:
        payload = {
            "user_id": user_id,
            "email": email,
            "exp": datetime.utcnow() + timedelta(days=expire_days)
        }
        return jwt.encode(payload, secret, algorithm="HS256")
    except Exception:
        return None


def reset_password(email: str, new_password: str) -> bool:
    """重置用户密码，返回是否成功"""
    try:
        init_db()
        db_path = get_db_path()
        conn = _connect()
        password_hash = hash_password(new_password)
        cursor = conn.execute(
            "UPDATE users SET password_hash = ? WHERE email = ?",
            (password_hash, email)
        )
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return affected > 0
    except Exception:
        return False


def verify_jwt_token(token: str, secret: str) -> Optional[Dict]:
    """验证 JWT token，返回 {user_id, email}"""
    if not jwt:
        return None
    try:
        payload = jwt.decode(token, secret, algorithms=["HS256"])
        return {"user_id": payload["user_id"], "email": payload["email"]}
    except Exception:
        return None
