import tempfile
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from app.core import hash_password
from app.db import get_db


def expect(name: str, condition: bool):
    if not condition:
        raise AssertionError(f"[FAIL] {name}")
    print(f"[PASS] {name}")


def login(client, username: str, password: str):
    return client.post(
        "/atbis/api/login",
        json={"username": username, "password": password},
    )


def seed_data(app):
    with app.app_context():
        db = get_db()

        db.execute(
            "INSERT INTO users(username, password, display_name, is_admin) VALUES (?, ?, ?, 0)",
            ("group_admin", hash_password("Pass1234"), "群組管理員"),
        )
        db.execute(
            "INSERT INTO users(username, password, display_name, is_admin) VALUES (?, ?, ?, 0)",
            ("treasurer", hash_password("Pass1234"), "保管人"),
        )
        db.execute(
            "INSERT INTO users(username, password, display_name, is_admin) VALUES (?, ?, ?, 0)",
            ("member", hash_password("Pass1234"), "一般成員"),
        )

        admin = db.execute("SELECT id FROM users WHERE username = 'admin'").fetchone()["id"]
        group_admin = db.execute("SELECT id FROM users WHERE username = 'group_admin'").fetchone()["id"]
        treasurer = db.execute("SELECT id FROM users WHERE username = 'treasurer'").fetchone()["id"]
        member = db.execute("SELECT id FROM users WHERE username = 'member'").fetchone()["id"]

        db.execute("INSERT INTO groups(name, created_by) VALUES (?, ?)", ("測試群組A", admin))
        group_id = db.execute("SELECT id FROM groups WHERE name = '測試群組A'").fetchone()["id"]

        db.execute(
            "INSERT INTO group_members(group_id, user_id, role, balance) VALUES (?, ?, 'group_admin', 0)",
            (group_id, group_admin),
        )
        db.execute(
            "INSERT INTO group_members(group_id, user_id, role, balance) VALUES (?, ?, 'treasurer', 0)",
            (group_id, treasurer),
        )
        db.execute(
            "INSERT INTO group_members(group_id, user_id, role, balance) VALUES (?, ?, 'member', 0)",
            (group_id, member),
        )
        db.commit()

        return {
            "group_id": group_id,
            "group_admin": group_admin,
            "treasurer": treasurer,
            "member": member,
        }


def run_regression():
    with tempfile.TemporaryDirectory() as td:
        db_path = str(Path(td) / "atbis_test.sqlite3")
        app = create_app(
            {
                "TESTING": True,
                "DATABASE": db_path,
                "ATBIS_ADMIN_USERNAME": "admin",
                "ATBIS_ADMIN_PASSWORD": "Admin12345",
            }
        )

        ctx = seed_data(app)

        admin_client = app.test_client()
        ga_client = app.test_client()
        tr_client = app.test_client()
        mem_client = app.test_client()

        expect("admin 登入成功", login(admin_client, "admin", "Admin12345").status_code == 200)
        expect("group_admin 登入成功", login(ga_client, "group_admin", "Pass1234").status_code == 200)
        expect("treasurer 登入成功", login(tr_client, "treasurer", "Pass1234").status_code == 200)
        expect("member 登入成功", login(mem_client, "member", "Pass1234").status_code == 200)

        logout_res = mem_client.post("/atbis/api/logout")
        expect("member 可呼叫 logout API", logout_res.status_code == 200)
        expect(
            "logout 後 profile 需重新登入",
            mem_client.get("/atbis/api/profile").status_code == 401,
        )
        expect("member 重新登入成功", login(mem_client, "member", "Pass1234").status_code == 200)

        add_bill_admin = admin_client.get("/atbis/add-bill", follow_redirects=False)
        add_bill_ga = ga_client.get("/atbis/add-bill", follow_redirects=False)
        add_bill_tr = tr_client.get("/atbis/add-bill", follow_redirects=False)
        add_bill_mem = mem_client.get("/atbis/add-bill", follow_redirects=False)

        expect("admin 可進入 add-bill", add_bill_admin.status_code == 200)
        expect("group_admin 可進入 add-bill", add_bill_ga.status_code == 200)
        expect("treasurer 可進入 add-bill", add_bill_tr.status_code == 200)
        expect("member 不可進入 add-bill", add_bill_mem.status_code in (301, 302))

        payload = {
            "group_id": ctx["group_id"],
            "bill_type": "expense",
            "total_amount": 90,
            "is_equal_split": True,
            "remark": "回歸測試",
            "selected_members": [ctx["group_admin"], ctx["treasurer"], ctx["member"]],
        }

        res_admin = admin_client.post("/atbis/api/bills", json=payload)
        res_ga = ga_client.post("/atbis/api/bills", json=payload)
        res_tr = tr_client.post("/atbis/api/bills", json=payload)
        res_mem = mem_client.post("/atbis/api/bills", json=payload)

        expect("admin 可新增帳單", res_admin.status_code == 200)
        expect("group_admin 可新增帳單", res_ga.status_code == 200)
        expect("treasurer 可新增帳單", res_tr.status_code == 200)
        expect("member 新增帳單被拒絕", res_mem.status_code == 403)

        manage_admin = admin_client.get(f"/atbis/api/groups/manage?group_id={ctx['group_id']}")
        manage_ga = ga_client.get(f"/atbis/api/groups/manage?group_id={ctx['group_id']}")
        manage_tr = tr_client.get(f"/atbis/api/groups/manage?group_id={ctx['group_id']}")

        expect("admin 可查看群組管理資訊", manage_admin.status_code == 200)
        expect("group_admin 可查看群組管理資訊", manage_ga.status_code == 200)
        expect("treasurer 不可查看群組管理資訊", manage_tr.status_code == 403)

        add_member_payload = {"group_id": ctx["group_id"], "username": "admin"}
        change_treasurer_payload = {"group_id": ctx["group_id"], "user_id": ctx["member"]}

        expect(
            "treasurer 不可新增群組成員",
            tr_client.put("/atbis/api/groups/members", json=add_member_payload).status_code == 403,
        )
        expect(
            "treasurer 不可修改保管人",
            tr_client.put("/atbis/api/groups/treasurer", json=change_treasurer_payload).status_code == 403,
        )

        with app.app_context():
            db = get_db()
            bill_count = db.execute("SELECT COUNT(*) AS c FROM bills").fetchone()["c"]
            split_count = db.execute("SELECT COUNT(*) AS c FROM bill_splits").fetchone()["c"]
            balances = db.execute(
                "SELECT user_id, balance FROM group_members WHERE group_id = ? ORDER BY user_id",
                (ctx["group_id"],),
            ).fetchall()

        expect("bills 寫入 3 筆", bill_count == 3)
        expect("bill_splits 寫入 9 筆", split_count == 9)
        expect(
            "每位成員餘額為 -90",
            all(abs(row["balance"] + 90.0) < 0.01 for row in balances),
        )

        print("\n回歸測試完成：四角色權限與帳單交易檢查通過")


if __name__ == "__main__":
    run_regression()
