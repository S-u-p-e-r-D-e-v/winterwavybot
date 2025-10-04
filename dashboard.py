import os
from functools import wraps
from typing import Dict, List, Any

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash

from utils import get_queues, clear_queue, get_live_stats


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = os.getenv("FLASK_SECRET", "dev-secret-change-me")

    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "changeme")

    def is_admin() -> bool:
        return session.get("admin_logged_in", False) is True

    def admin_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not is_admin():
                flash("Admin login required", "warning")
                return redirect(url_for("login", next=request.path))
            return f(*args, **kwargs)
        return decorated_function

    @app.route("/")
    def index():
        queues: Dict[str, List[str]] = get_queues()
        live_stats: Dict[str, Any] = get_live_stats()
        return render_template(
            "index.html",
            queues=queues,
            live_stats=live_stats,
            is_admin=is_admin(),
            tiktok_username=live_stats.get("tiktok_username", "")
        )

    @app.route("/api/live_stats")
    def api_live_stats():
        return jsonify(get_live_stats())

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if request.method == "POST":
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
                session["admin_logged_in"] = True
                flash("Logged in as admin", "success")
                next_url = request.args.get("next") or url_for("index")
                return redirect(next_url)
            flash("Invalid credentials", "danger")
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        session.pop("admin_logged_in", None)
        flash("Logged out", "info")
        return redirect(url_for("index"))

    @app.route("/admin/clear/<game>", methods=["POST"])  # admin-only
    @admin_required
    def admin_clear_queue(game: str):
        clear_queue(game)
        flash(f"Cleared queue for {game}", "success")
        return redirect(url_for("index"))

    return app


app = create_app()


if __name__ == "__main__":
    port = int(os.getenv("DASHBOARD_PORT", "2800"))
    host = os.getenv("DASHBOARD_HOST", "0.0.0.0")
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    # Run Flask development server
    app.run(host=host, port=port, debug=debug)
