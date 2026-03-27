from flask import jsonify, request, session

from ..core import json_error, login_required, verify_password
from ..db import get_db
from . import api_bp


@api_bp.post("/login")
def api_login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return json_error("請輸入帳號與密碼")

    user = get_db().execute(
        "SELECT id, username, display_name, password, is_admin FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    if not user or not verify_password(password, user["password"]):
        return json_error("帳號或密碼錯誤", 401)

    session["user_id"] = user["id"]
    return jsonify(
        {
            "success": True,
            "data": {
                "token": None,
                "user_info": {
                    "id": user["id"],
                    "username": user["username"],
                    "display_name": user["display_name"],
                    "is_admin": user["is_admin"],
                },
            },
        }
    )


@api_bp.post("/logout")
@login_required
def api_logout():
    session.clear()
    return jsonify({"success": True, "data": {"message": "已登出"}})
