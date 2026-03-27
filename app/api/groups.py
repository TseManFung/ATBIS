from flask import jsonify, request

from ..core import can_add_bill, get_visible_groups, is_group_manager, json_error, login_required, parse_int, require_user
from ..db import get_db
from . import api_bp


@api_bp.get("/groups")
@login_required
def api_groups():
    user = require_user()
    scope = (request.args.get("scope") or "").strip().lower()
    groups = [dict(g) for g in get_visible_groups(user)]

    if scope == "add-bill":
        groups = [g for g in groups if can_add_bill(user, g["id"])]
    elif scope == "manage":
        groups = [g for g in groups if is_group_manager(user, g["id"])]

    return jsonify({"success": True, "data": groups})


@api_bp.get("/groups/bill-members")
@login_required
def api_bill_members():
    user = require_user()
    group_id_raw = request.args.get("group_id")
    try:
        group_id = parse_int(group_id_raw)
    except (TypeError, ValueError):
        return json_error("group_id 格式錯誤")

    if not can_add_bill(user, group_id):
        return json_error("權限不足", 403)

    db = get_db()
    members = db.execute(
        """
        SELECT gm.user_id, u.username, u.display_name, gm.role
        FROM group_members gm
        JOIN users u ON u.id = gm.user_id
        WHERE gm.group_id = ?
        ORDER BY u.username
        """,
        (group_id,),
    ).fetchall()
    return jsonify({"success": True, "data": {"members": [dict(m) for m in members]}})


@api_bp.post("/groups")
@login_required
def api_create_group():
    user = require_user()
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return json_error("群組名稱不可為空")
    if len(name) > 100:
        return json_error("群組名稱不可超過 100 字")

    db = get_db()
    exists = db.execute("SELECT id FROM groups WHERE name = ?", (name,)).fetchone()
    if exists:
        return json_error("群組名稱已存在")

    try:
        db.execute("BEGIN")
        cur = db.execute("INSERT INTO groups(name, created_by) VALUES (?, ?)", (name, user["id"]))
        gid = cur.lastrowid
        db.execute(
            "INSERT INTO group_members(group_id, user_id, role, balance) VALUES (?, ?, 'group_admin', 0)",
            (gid, user["id"]),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return jsonify({"success": True, "data": {"group_id": gid, "name": name}})


@api_bp.get("/groups/manage")
@login_required
def api_group_manage_info():
    user = require_user()
    group_id_raw = request.args.get("group_id")
    try:
        group_id = parse_int(group_id_raw)
    except (TypeError, ValueError):
        return json_error("group_id 格式錯誤")

    if not is_group_manager(user, group_id):
        return json_error("權限不足", 403)

    db = get_db()
    members = db.execute(
        """
        SELECT gm.user_id, u.username, u.display_name, gm.role, gm.balance
        FROM group_members gm
        JOIN users u ON u.id = gm.user_id
        WHERE gm.group_id = ?
        ORDER BY u.username
        """,
        (group_id,),
    ).fetchall()
    return jsonify({"success": True, "data": {"members": [dict(m) for m in members]}})


@api_bp.put("/groups/members")
@login_required
def api_add_group_member():
    user = require_user()
    data = request.get_json(silent=True) or {}
    try:
        group_id = parse_int(data.get("group_id"))
    except (TypeError, ValueError):
        return json_error("group_id 格式錯誤")

    if not is_group_manager(user, group_id):
        return json_error("權限不足", 403)

    username = (data.get("username") or "").strip()
    if not username:
        return json_error("username 不可為空")

    db = get_db()
    target_user = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if not target_user:
        return json_error("使用者不存在", 404)

    exists = db.execute(
        "SELECT id FROM group_members WHERE group_id = ? AND user_id = ?",
        (group_id, target_user["id"]),
    ).fetchone()
    if exists:
        return json_error("該使用者已在群組內")

    db.execute(
        "INSERT INTO group_members(group_id, user_id, role, balance) VALUES (?, ?, 'member', 0)",
        (group_id, target_user["id"]),
    )
    db.commit()
    return jsonify({"success": True, "data": {"message": "新增成員成功"}})


@api_bp.put("/groups/treasurer")
@login_required
def api_change_treasurer():
    user = require_user()
    data = request.get_json(silent=True) or {}
    try:
        group_id = parse_int(data.get("group_id"))
        user_id = parse_int(data.get("user_id"))
    except (TypeError, ValueError):
        return json_error("group_id 或 user_id 格式錯誤")

    if not is_group_manager(user, group_id):
        return json_error("權限不足", 403)

    db = get_db()
    member_exists = db.execute(
        "SELECT role FROM group_members WHERE group_id = ? AND user_id = ?",
        (group_id, user_id),
    ).fetchone()
    if not member_exists:
        return json_error("指定成員不在群組內", 404)
    if member_exists["role"] == "group_admin":
        return json_error("不可將群組管理員改為金錢保管人")

    try:
        db.execute("BEGIN")
        db.execute(
            "UPDATE group_members SET role = 'member' WHERE group_id = ? AND role = 'treasurer'",
            (group_id,),
        )
        db.execute(
            "UPDATE group_members SET role = 'treasurer' WHERE group_id = ? AND user_id = ?",
            (group_id, user_id),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return jsonify({"success": True, "data": {"message": "已更新金錢保管人"}})
