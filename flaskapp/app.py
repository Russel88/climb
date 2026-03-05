from __future__ import annotations

import os
import sqlite3

from flask import Flask, jsonify, render_template, request

from flaskapp.extensions import db
from flaskapp.personal import personal_api_bp, personal_bp


def _default_personal_db_url() -> str:
    return "postgresql+psycopg://postgres:postgres@localhost:5432/climb_personal"


def create_app() -> Flask:
    app = Flask(__name__)

    app.config.setdefault("SQLALCHEMY_DATABASE_URI", os.getenv("PERSONAL_DATABASE_URL", _default_personal_db_url()))
    app.config.setdefault("SQLALCHEMY_TRACK_MODIFICATIONS", False)

    db.init_app(app)

    def init_climb_db() -> None:
        db_path = os.path.join(app.instance_path, "database.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                selected_objects TEXT NOT NULL
            )
            """
        )
        conn.commit()
        conn.close()

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    init_climb_db()

    app.register_blueprint(personal_bp)
    app.register_blueprint(personal_api_bp)

    @app.route("/")
    def index():
        return render_template("index.html")

    @app.route("/save_entry", methods=["POST"])
    def save_entry():
        data = request.get_json(silent=True) or {}
        name = data["name"]
        selected_objects = data["selected_objects"]

        db_path = os.path.join(app.instance_path, "database.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO entries (name, selected_objects) VALUES (?, ?)", (name, selected_objects))
        conn.commit()
        conn.close()
        return jsonify({"status": "success"})

    @app.route("/get_entries")
    def get_entries():
        db_path = os.path.join(app.instance_path, "database.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM entries")
        entries = cursor.fetchall()
        conn.close()
        return jsonify(entries)

    @app.route("/entry/<int:entry_id>")
    def get_entry(entry_id: int):
        db_path = os.path.join(app.instance_path, "database.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM entries WHERE id = ?", (entry_id,))
        entry = cursor.fetchone()
        conn.close()
        return jsonify(entry)

    @app.route("/create_climb")
    def create_entry():
        return render_template("edit.html")

    @app.route("/update_entry/<int:entry_id>", methods=["POST"])
    def update_entry(entry_id: int):
        data = request.get_json(silent=True) or {}
        new_name = data["name"]

        db_path = os.path.join(app.instance_path, "database.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("UPDATE entries SET name = ? WHERE id = ?", (new_name, entry_id))
        conn.commit()
        conn.close()

        return jsonify({"status": "success"})

    @app.route("/delete_entry/<int:entry_id>", methods=["POST"])
    def delete_entry(entry_id: int):
        db_path = os.path.join(app.instance_path, "database.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM entries WHERE id = ?", (entry_id,))
        conn.commit()
        conn.close()

        return jsonify({"status": "success"})

    @app.cli.command("personal-db-create")
    def personal_db_create():
        """Create personal training tables (for local bootstrap only)."""
        from flaskapp.personal import models as _personal_models  # noqa: F401

        db.create_all()
        print("Personal training tables created.")

    return app
