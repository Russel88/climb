from __future__ import annotations

from flask import Blueprint, render_template


personal_bp = Blueprint("personal", __name__, url_prefix="/personal")


@personal_bp.route("/")
def dashboard_page():
    return render_template("personal/dashboard.html", page_title="Dashboard", active_nav="dashboard")


@personal_bp.route("/exercises")
def exercises_page():
    return render_template("personal/exercises.html", page_title="Exercises", active_nav="exercises")


@personal_bp.route("/workouts/new")
def workout_planner_page():
    return render_template("personal/workout_planner.html", page_title="Workout Planner", active_nav="workout")


@personal_bp.route("/workouts/<int:session_id>/run")
def workout_run_page(session_id: int):
    return render_template(
        "personal/workout_run.html",
        page_title="Run Workout",
        active_nav="workout",
        session_id=session_id,
    )


@personal_bp.route("/history")
def history_page():
    return render_template("personal/history.html", page_title="History", active_nav="history")


@personal_bp.route("/settings")
def settings_page():
    return render_template("personal/settings.html", page_title="Settings", active_nav="settings")


@personal_bp.route("/templates")
def templates_page():
    return render_template("personal/templates.html", page_title="Templates", active_nav="templates")
