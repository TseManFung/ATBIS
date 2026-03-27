from flask import jsonify, request

from ..core import generate_password, hash_password, json_error, login_required, require_user
from ..db import get_db
from . import api_bp


@api_bp.post("/admin/users")
@login_required
def api_add_user():
    user = require_user()
    if user["is_admin"] != 1:
        return json_error("權限不足", 403)

    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    display_name = (data.get("display_name") or "").strip() or username
    if not username:
        return json_error("username 不可為空")

    db = get_db()
    exist = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if exist:
        return json_error("username 已存在")

    raw_password = generate_password()
    db.execute(
        "INSERT INTO users(username, password, display_name, is_admin) VALUES (?, ?, ?, 0)",
        (username, hash_password(raw_password), display_name),
    )
    db.commit()
    return jsonify(
        {
            "success": True,
            "data": {
                "username": username,
                "display_name": display_name,
                "password": raw_password,
            },
        }
    )
