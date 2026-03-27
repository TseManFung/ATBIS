import os

from flask import Flask, redirect, render_template, session, url_for

from .api import api_bp
from .core import BASE_PATH, can_access_add_bill_page, hash_password, login_required, require_user
from .db import get_db, init_app as init_db_app, init_db


def create_app(test_config=None):
    app = Flask(
        __name__,
        static_folder="static",
        template_folder="templates",
        static_url_path=f"{BASE_PATH}/static",
    )
    app.config.update(
        SECRET_KEY=os.getenv("SECRET_KEY") or os.urandom(24).hex(),
        DATABASE=os.path.join(app.instance_path, "atbis.sqlite3"),
        JSON_AS_ASCII=False,
    )
    if test_config:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)
    init_db_app(app)

    with app.app_context():
        init_db()
        ensure_admin_user()

    register_page_routes(app)
    app.register_blueprint(api_bp)
    return app


def ensure_admin_user():
    db = get_db()
    existing = db.execute("SELECT id FROM users WHERE is_admin = 1 LIMIT 1").fetchone()
    if existing:
        return

    username = os.getenv("ATBIS_ADMIN_USERNAME", "admin")
    password = os.getenv("ATBIS_ADMIN_PASSWORD", "Admin12345")
    db.execute(
        "INSERT INTO users(username, password, display_name, is_admin) VALUES (?, ?, ?, 1)",
        (username, hash_password(password), "系統管理員"),
    )
    db.commit()


def register_page_routes(app: Flask):
    @app.get("/")
    def root_redirect():
        return redirect(url_for("login_page"))

    @app.get(BASE_PATH)
    def login_page():
        if "user_id" in session:
            return redirect(url_for("bills_page"))
        return render_template("login.html", base_path=BASE_PATH)

    @app.get(f"{BASE_PATH}/logout")
    def logout():
        session.clear()
        return redirect(url_for("login_page"))

    @app.get(f"{BASE_PATH}/bills")
    @login_required
    def bills_page():
        return render_template("bills.html", base_path=BASE_PATH, user=require_user())

    @app.get(f"{BASE_PATH}/profile")
    @login_required
    def profile_page():
        return render_template("profile.html", base_path=BASE_PATH, user=require_user())

    @app.get(f"{BASE_PATH}/add-bill")
    @login_required
    def add_bill_page():
        user = require_user()
        if not can_access_add_bill_page(user):
            return redirect(url_for("bills_page"))
        return render_template("add_bill.html", base_path=BASE_PATH, user=user)

    @app.get(f"{BASE_PATH}/admin/add-user")
    @login_required
    def add_user_page():
        user = require_user()
        if user["is_admin"] != 1:
            return redirect(url_for("bills_page"))
        return render_template("add_user.html", base_path=BASE_PATH, user=user)

    @app.get(f"{BASE_PATH}/groups/new")
    @login_required
    def new_group_page():
        return render_template("new_group.html", base_path=BASE_PATH, user=require_user())

    @app.get(f"{BASE_PATH}/groups/manage")
    @login_required
    def manage_group_page():
        return render_template("manage_group.html", base_path=BASE_PATH, user=require_user())
