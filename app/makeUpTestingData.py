from app import create_app
from app.core import hash_password
from app.db import get_db


SEED_USERS = [
	("seed_admin", "Admin12345", "測試全局管理員", 1),
	("ga_amy", "Pass1234", "Amy 群組管理員", 0),
	("tr_bob", "Pass1234", "Bob 金錢保管人", 0),
	("member_cathy", "Pass1234", "Cathy 一般成員", 0),
	("member_dan", "Pass1234", "Dan 一般成員", 0),
	("ga_eric", "Pass1234", "Eric 群組管理員", 0),
	("member_fiona", "Pass1234", "Fiona 一般成員", 0),
	("member_gary", "Pass1234", "Gary 一般成員", 0),
]


def get_or_create_user(db, username, password, display_name, is_admin):
	row = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
	if row:
		return row["id"]

	cur = db.execute(
		"""
		INSERT INTO users(username, password, display_name, is_admin)
		VALUES (?, ?, ?, ?)
		""",
		(username, hash_password(password), display_name, is_admin),
	)
	return cur.lastrowid


def get_or_create_group(db, name, created_by):
	row = db.execute("SELECT id FROM groups WHERE name = ?", (name,)).fetchone()
	if row:
		return row["id"]

	cur = db.execute(
		"INSERT INTO groups(name, created_by) VALUES (?, ?)",
		(name, created_by),
	)
	return cur.lastrowid


def upsert_group_member(db, group_id, user_id, role):
	row = db.execute(
		"SELECT id FROM group_members WHERE group_id = ? AND user_id = ?",
		(group_id, user_id),
	).fetchone()
	if row:
		db.execute(
			"UPDATE group_members SET role = ? WHERE group_id = ? AND user_id = ?",
			(role, group_id, user_id),
		)
		return

	db.execute(
		"""
		INSERT INTO group_members(group_id, user_id, role, balance)
		VALUES (?, ?, ?, 0)
		""",
		(group_id, user_id, role),
	)


def seed_bill_if_missing(
	db,
	group_id,
	bill_type,
	total_amount,
	is_equal_split,
	remark,
	created_by,
	amount_by_user,
):
	existing = db.execute(
		"SELECT id FROM bills WHERE group_id = ? AND remark = ? LIMIT 1",
		(group_id, remark),
	).fetchone()
	if existing:
		return

	cur = db.execute(
		"""
		INSERT INTO bills(group_id, bill_type, total_amount, is_equal_split, remark, created_by)
		VALUES (?, ?, ?, ?, ?, ?)
		""",
		(group_id, bill_type, total_amount, is_equal_split, remark, created_by),
	)
	bill_id = cur.lastrowid

	sign = 1.0 if bill_type == "income" else -1.0
	for user_id, amount in amount_by_user.items():
		signed_amount = round(sign * float(amount), 2)
		db.execute(
			"INSERT INTO bill_splits(bill_id, user_id, amount) VALUES (?, ?, ?)",
			(bill_id, user_id, signed_amount),
		)
		db.execute(
			"""
			UPDATE group_members
			SET balance = balance + ?
			WHERE group_id = ? AND user_id = ?
			""",
			(signed_amount, group_id, user_id),
		)


def main():
	app = create_app()
	with app.app_context():
		db = get_db()

		try:
			db.execute("BEGIN")

			user_ids = {}
			for username, password, display_name, is_admin in SEED_USERS:
				user_ids[username] = get_or_create_user(
					db,
					username,
					password,
					display_name,
					is_admin,
				)

			group_trip = get_or_create_group(db, "旅行基金 2026", user_ids["seed_admin"])
			group_family = get_or_create_group(db, "家庭共用金", user_ids["seed_admin"])

			# 群組一：有保管人
			upsert_group_member(db, group_trip, user_ids["ga_amy"], "group_admin")
			upsert_group_member(db, group_trip, user_ids["tr_bob"], "treasurer")
			upsert_group_member(db, group_trip, user_ids["member_cathy"], "member")
			upsert_group_member(db, group_trip, user_ids["member_dan"], "member")

			# 群組二：沒有保管人（用於測試由 group_admin 代替顯示）
			upsert_group_member(db, group_family, user_ids["ga_eric"], "group_admin")
			upsert_group_member(db, group_family, user_ids["member_fiona"], "member")
			upsert_group_member(db, group_family, user_ids["member_gary"], "member")

			# 測試帳單（remark 用唯一字串，避免重跑重複寫入）
			seed_bill_if_missing(
				db,
				group_id=group_trip,
				bill_type="expense",
				total_amount=120.0,
				is_equal_split=1,
				remark="[SEED] 旅行基金-餐費平分",
				created_by=user_ids["ga_amy"],
				amount_by_user={
					user_ids["ga_amy"]: 30,
					user_ids["tr_bob"]: 30,
					user_ids["member_cathy"]: 30,
					user_ids["member_dan"]: 30,
				},
			)
			seed_bill_if_missing(
				db,
				group_id=group_trip,
				bill_type="income",
				total_amount=90.0,
				is_equal_split=0,
				remark="[SEED] 旅行基金-退款自訂",
				created_by=user_ids["tr_bob"],
				amount_by_user={
					user_ids["ga_amy"]: 30,
					user_ids["member_cathy"]: 20,
					user_ids["member_dan"]: 40,
				},
			)
			seed_bill_if_missing(
				db,
				group_id=group_family,
				bill_type="expense",
				total_amount=60.0,
				is_equal_split=1,
				remark="[SEED] 家庭共用金-生活支出",
				created_by=user_ids["ga_eric"],
				amount_by_user={
					user_ids["ga_eric"]: 20,
					user_ids["member_fiona"]: 20,
					user_ids["member_gary"]: 20,
				},
			)

			db.commit()
		except Exception:
			db.rollback()
			raise

	print("Seed data ready.")
	print("Test users and passwords:")
	print("- seed_admin / Admin12345")
	print("- ga_amy / Pass1234")
	print("- tr_bob / Pass1234")
	print("- member_cathy / Pass1234")
	print("- member_dan / Pass1234")
	print("- ga_eric / Pass1234")
	print("- member_fiona / Pass1234")
	print("- member_gary / Pass1234")


if __name__ == "__main__":
	main()
