import secrets
from functools import wraps

import bcrypt
from flask import jsonify, redirect, request, session, url_for

from .db import get_db


BASE_PATH = "/atbis"
API_PREFIX = f"{BASE_PATH}/api"


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw: str, hashed: str) -> bool:
    return bcrypt.checkpw(raw.encode("utf-8"), hashed.encode("utf-8"))


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return get_db().execute(
        "SELECT id, username, display_name, is_admin FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()


def require_user():
    user = current_user()
    if user is None:
        raise RuntimeError("未登入使用者不可存取此函式")
    return user


def parse_int(value):
    if value is None:
        raise ValueError("值不可為空")
    return int(value)


def parse_float(value):
    if value is None:
        raise ValueError("值不可為空")
    return float(value)


def json_error(message, status=400):
    return jsonify({"success": False, "message": message}), status


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user():
            if request.path.startswith(API_PREFIX):
                return json_error("請先登入", 401)
            return redirect(url_for("login_page"))
        return view(*args, **kwargs)

    return wrapped


def is_group_manager(user, group_id: int) -> bool:
    if not user:
        return False
    if user["is_admin"] == 1:
        return True
    row = get_db().execute(
        "SELECT role FROM group_members WHERE group_id = ? AND user_id = ?",
        (group_id, user["id"]),
    ).fetchone()
    return bool(row and row["role"] == "group_admin")


def can_add_bill(user, group_id: int) -> bool:
    if not user:
        return False
    if user["is_admin"] == 1:
        return True
    row = get_db().execute(
        "SELECT role FROM group_members WHERE group_id = ? AND user_id = ?",
        (group_id, user["id"]),
    ).fetchone()
    return bool(row and row["role"] in ("group_admin", "treasurer"))


def can_access_add_bill_page(user) -> bool:
    if not user:
        return False
    if user["is_admin"] == 1:
        return True
    row = get_db().execute(
        """
        SELECT 1
        FROM group_members
        WHERE user_id = ? AND role IN ('group_admin', 'treasurer')
        LIMIT 1
        """,
        (user["id"],),
    ).fetchone()
    return bool(row)


def can_view_group_details(user, group_id: int) -> bool:
    if not user:
        return False
    if user["is_admin"] == 1:
        return True
    row = get_db().execute(
        "SELECT role FROM group_members WHERE group_id = ? AND user_id = ?",
        (group_id, user["id"]),
    ).fetchone()
    if not row:
        return False
    return row["role"] == "group_admin"


def get_visible_groups(user):
    db = get_db()
    if user["is_admin"] == 1:
        return db.execute("SELECT id, name FROM groups ORDER BY name").fetchall()
    return db.execute(
        """
        SELECT g.id, g.name
        FROM groups g
        JOIN group_members gm ON gm.group_id = g.id
        WHERE gm.user_id = ?
        ORDER BY g.name
        """,
        (user["id"],),
    ).fetchall()


def generate_password(length=12):
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
    return "".join(secrets.choice(alphabet) for _ in range(length))
