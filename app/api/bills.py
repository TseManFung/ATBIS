from flask import jsonify, request

from ..core import (
    can_add_bill,
    can_view_group_details,
    get_visible_groups,
    is_group_manager,
    json_error,
    login_required,
    parse_float,
    parse_int,
    require_user,
)
from ..db import get_db
from . import api_bp


@api_bp.get("/bills")
@login_required
def api_bills():
    user = require_user()
    db = get_db()
    group_id_raw = request.args.get("group_id")

    if group_id_raw:
        try:
            group_ids = [parse_int(group_id_raw)]
        except ValueError:
            return json_error("group_id 格式錯誤")
    else:
        group_ids = [g["id"] for g in get_visible_groups(user)]

    if not group_ids:
        return jsonify({"success": True, "data": {"balances": [], "bills": []}})

    balances = []
    bills = []

    for gid in group_ids:
        members_for_keeper = db.execute(
            """
            SELECT u.username, u.display_name, gm.role
            FROM group_members gm
            JOIN users u ON u.id = gm.user_id
            WHERE gm.group_id = ?
            """,
            (gid,),
        ).fetchall()

        treasurer_names = [
            (row["display_name"] or row["username"])
            for row in members_for_keeper
            if row["role"] == "treasurer"
        ]
        if treasurer_names:
            keeper_display = "、".join(treasurer_names)
        else:
            group_admin_names = [
                (row["display_name"] or row["username"])
                for row in members_for_keeper
                if row["role"] == "group_admin"
            ]
            keeper_display = "、".join(group_admin_names)

        can_view_all = can_view_group_details(user, gid)
        if user["is_admin"] != 1 and not can_view_all:
            member_row = db.execute(
                "SELECT id FROM group_members WHERE group_id = ? AND user_id = ?",
                (gid, user["id"]),
            ).fetchone()
            if not member_row:
                continue

        if user["is_admin"] == 1 or can_view_all:
            balance_rows = db.execute(
                """
                SELECT gm.group_id, g.name AS group_name, u.username, u.display_name, gm.balance
                FROM group_members gm
                JOIN users u ON u.id = gm.user_id
                JOIN groups g ON g.id = gm.group_id
                WHERE gm.group_id = ?
                ORDER BY u.username
                """,
                (gid,),
            ).fetchall()
        else:
            balance_rows = db.execute(
                """
                SELECT gm.group_id, g.name AS group_name, u.username, u.display_name, gm.balance
                FROM group_members gm
                JOIN users u ON u.id = gm.user_id
                JOIN groups g ON g.id = gm.group_id
                WHERE gm.group_id = ? AND gm.user_id = ?
                """,
                (gid, user["id"]),
            ).fetchall()

        for row in balance_rows:
            item = dict(row)
            item["keeper"] = keeper_display
            balances.append(item)

        if user["is_admin"] == 1 or can_view_all:
            bill_rows = db.execute(
                """
                SELECT b.id, b.group_id, g.name AS group_name, b.bill_type, b.total_amount,
                       b.is_equal_split, b.remark, b.created_at, u.username AS created_by
                FROM bills b
                JOIN groups g ON g.id = b.group_id
                JOIN users u ON u.id = b.created_by
                WHERE b.group_id = ?
                ORDER BY b.created_at DESC, b.id DESC
                """,
                (gid,),
            ).fetchall()
        else:
            bill_rows = db.execute(
                """
                SELECT DISTINCT b.id, b.group_id, g.name AS group_name, b.bill_type, b.total_amount,
                       b.is_equal_split, b.remark, b.created_at, u.username AS created_by
                FROM bills b
                JOIN groups g ON g.id = b.group_id
                JOIN users u ON u.id = b.created_by
                JOIN bill_splits bs ON bs.bill_id = b.id
                WHERE b.group_id = ? AND bs.user_id = ?
                ORDER BY b.created_at DESC, b.id DESC
                """,
                (gid, user["id"]),
            ).fetchall()

        bills.extend([dict(row) for row in bill_rows])

    return jsonify({"success": True, "data": {"balances": balances, "bills": bills}})


@api_bp.post("/bills")
@login_required
def api_add_bill():
    user = require_user()
    db = get_db()
    data = request.get_json(silent=True) or {}

    try:
        group_id = parse_int(data.get("group_id"))
        total_amount = parse_float(data.get("total_amount"))
    except (TypeError, ValueError):
        return json_error("group_id 或 total_amount 格式錯誤")

    if not can_add_bill(user, group_id):
        return json_error("權限不足", 403)

    bill_type = data.get("bill_type")
    if bill_type not in ("income", "expense"):
        return json_error("bill_type 僅可為 income 或 expense")

    if total_amount <= 0:
        return json_error("total_amount 必須大於 0")

    selected_members = data.get("selected_members") or []
    if not isinstance(selected_members, list) or not selected_members:
        return json_error("請選擇至少一名成員")

    try:
        selected_members = [int(mid) for mid in selected_members]
    except ValueError:
        return json_error("selected_members 格式錯誤")

    existing_members = db.execute(
        f"SELECT user_id FROM group_members WHERE group_id = ? AND user_id IN ({','.join('?' * len(selected_members))})",
        (group_id, *selected_members),
    ).fetchall()
    if len(existing_members) != len(set(selected_members)):
        return json_error("所選成員包含不屬於該群組者")

    is_equal_split = 1 if bool(data.get("is_equal_split", True)) else 0
    remark = (data.get("remark") or "").strip() or None

    amounts = {}
    if is_equal_split == 1:
        per = round(total_amount / len(selected_members), 2)
        remain = round(total_amount - per * len(selected_members), 2)
        for idx, uid in enumerate(selected_members):
            adj = per + (remain if idx == 0 else 0)
            amounts[uid] = adj
    else:
        member_amounts = data.get("member_amounts") or {}
        if not isinstance(member_amounts, dict):
            return json_error("member_amounts 格式錯誤")

        running = 0.0
        for uid in selected_members:
            raw = member_amounts.get(str(uid), member_amounts.get(uid))
            try:
                val = parse_float(raw)
            except (TypeError, ValueError):
                return json_error("member_amounts 金額格式錯誤")
            if val < 0:
                return json_error("member_amounts 不能為負數")
            amounts[uid] = val
            running += val
        if abs(running - total_amount) > 0.01:
            return json_error("自訂分攤總和必須等於 total_amount")

    sign = 1.0 if bill_type == "income" else -1.0

    try:
        db.execute("BEGIN")
        cursor = db.execute(
            """
            INSERT INTO bills(group_id, bill_type, total_amount, is_equal_split, remark, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (group_id, bill_type, total_amount, is_equal_split, remark, user["id"]),
        )
        bill_id = cursor.lastrowid

        for uid, amt in amounts.items():
            signed_amount = round(sign * amt, 2)
            db.execute(
                "INSERT INTO bill_splits(bill_id, user_id, amount) VALUES (?, ?, ?)",
                (bill_id, uid, signed_amount),
            )
            db.execute(
                "UPDATE group_members SET balance = balance + ? WHERE group_id = ? AND user_id = ?",
                (signed_amount, group_id, uid),
            )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return jsonify({"success": True, "data": {"bill_id": bill_id}})
