from flask import jsonify, request

from ..core import hash_password, json_error, login_required, require_user, verify_password
from ..db import get_db
from . import api_bp


@api_bp.get("/profile")
@login_required
def api_get_profile():
    user = require_user()
    return jsonify(
        {
            "success": True,
            "data": {
                "id": user["id"],
                "username": user["username"],
                "display_name": user["display_name"],
                "is_admin": user["is_admin"],
            },
        }
    )


@api_bp.put("/profile")
@login_required
def api_update_profile():
    user = require_user()
    db = get_db()
    data = request.get_json(silent=True) or {}
    display_name = data.get("display_name")
    new_password = data.get("password")
    old_password = data.get("old_password") or ""

    db_user = db.execute("SELECT password FROM users WHERE id = ?", (user["id"],)).fetchone()

    if new_password:
        if len(new_password) < 8:
            return json_error("新密碼至少 8 位")
        if not old_password or not verify_password(old_password, db_user["password"]):
            return json_error("舊密碼錯誤", 400)
        if verify_password(new_password, db_user["password"]):
            return json_error("新密碼不可與舊密碼相同", 400)
        db.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (hash_password(new_password), user["id"]),
        )

    if display_name is not None:
        db.execute("UPDATE users SET display_name = ? WHERE id = ?", (display_name.strip(), user["id"]))

    db.commit()
    return jsonify({"success": True, "data": {"message": "個人資料更新成功"}})
