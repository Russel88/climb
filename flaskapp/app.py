from flask import Flask, render_template, request, jsonify, Response
from functools import wraps
import sqlite3
import os
import json  # ✅ added to handle JSON encoding/decoding

def create_app():
    app = Flask(__name__)
    
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    TRAINING_FILE = os.path.join(BASE_DIR, "training.json")
    LOG_FILE = os.path.join(BASE_DIR, "log.json")    
    WEIGHTS_FILE = os.path.join(BASE_DIR, "weights.json")


    # Initialize the database
    def init_db():
        db_path = os.path.join(app.instance_path, 'database.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                selected_objects TEXT NOT NULL
            )
        ''')
        conn.commit()
        conn.close()

    try:
        os.makedirs(app.instance_path)
    except OSError:
        pass

    init_db()

    @app.route('/')
    def index():
        return render_template('index.html')

    @app.route('/save_entry', methods=['POST'])
    def save_entry():
        data = request.get_json()
        name = data['name']
        selected_objects = json.dumps(data['selected_objects'])  # ✅ changed to store as JSON string

        db_path = os.path.join(app.instance_path, 'database.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('INSERT INTO entries (name, selected_objects) VALUES (?, ?)', (name, selected_objects))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success'})

    @app.route('/get_entries')
    def get_entries():
        db_path = os.path.join(app.instance_path, 'database.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM entries')
        entries = cursor.fetchall()
        conn.close()
        return jsonify(entries)

    @app.route('/entry/<int:entry_id>')
    def get_entry(entry_id):
        db_path = os.path.join(app.instance_path, 'database.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM entries WHERE id = ?', (entry_id,))
        entry = cursor.fetchone()
        conn.close()

        if entry:
            id, name, selected_objects = entry
            return jsonify([id, name, json.loads(selected_objects)])  # ✅ parse JSON string back into dict
        else:
            return jsonify({'error': 'not found'}), 404

    @app.route('/create_climb')
    def create_entry():
        return render_template('edit.html')

    @app.route('/update_entry/<int:entry_id>', methods=['POST'])
    def update_entry(entry_id):
        data = request.get_json()
        new_name = data['name']

        db_path = os.path.join(app.instance_path, 'database.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('UPDATE entries SET name = ? WHERE id = ?', (new_name, entry_id))
        conn.commit()
        conn.close()

        return jsonify({'status': 'success'})

    @app.route('/delete_entry/<int:entry_id>', methods=['POST'])
    def delete_entry(entry_id):
        db_path = os.path.join(app.instance_path, 'database.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM entries WHERE id = ?', (entry_id,))
        conn.commit()
        conn.close()

        return jsonify({'status': 'success'})
    
    
    def load_json(filename):
        if os.path.exists(filename):
            with open(filename) as f:
                return json.load(f)
        return {}

    def save_json(filename, data):
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)

    @app.route("/personal")
    def personal():
        return render_template("personal.html")

    @app.route("/api/program", methods=["GET", "POST"])
    def program_api():
        if request.method == "POST":
            new_program = request.json
            save_json(TRAINING_FILE, new_program)
            return jsonify({"status": "program updated"})
        else:
            program = load_json(TRAINING_FILE)
            return jsonify(program)

    @app.route("/api/log", methods=["GET", "POST"])
    def log_api():
        if request.method == "POST":
            new_entry = request.json
            week = str(new_entry.get("week"))
            day = str(new_entry.get("day"))
            exercises = new_entry.get("exercises", [])

            log = load_json(LOG_FILE)
            if not log or "entries" not in log:
                log = {"entries": {}}

            if week not in log["entries"]:
                log["entries"][week] = {}
            if day not in log["entries"][week]:
                log["entries"][week][day] = []

            # Replace exercises for this day with the new log
            log["entries"][week][day] = exercises

            save_json(LOG_FILE, log)
            return jsonify({"status": "saved", "log": log})

        else:
            log = load_json(LOG_FILE)
            if not log:
                log = {"entries": {}}
            return jsonify(log)

    @app.route("/api/reset_cycle", methods=["POST"])
    def reset_cycle():
        save_json(LOG_FILE, {"entries": {}})
        return jsonify({"status": "cycle reset"})

    @app.route("/personal/log_summary")
    def log_summary_page():
        return render_template("log_summary.html")

    @app.route("/api/log_summary")
    def get_log_summary():
        logs = load_json(LOG_FILE)
        program = load_json(TRAINING_FILE)
        return jsonify({"program": program, "logs": logs})

    @app.route("/personal/edit_program")
    def edit_program_page():
        return render_template("edit_program.html")

    @app.route("/api/program", methods=["POST"])
    def update_program():
        new_program = request.json
        save_json(TRAINING_FILE, new_program)
        return jsonify({"status": "program updated"})

    @app.route("/api/weights", methods=["GET", "POST"])
    def weights_api():
        if request.method == "POST":
            new_weights = request.json  # Expecting a dict: { "Squat": 105, "Bench Press": 60 }
            if not isinstance(new_weights, dict):
                return jsonify({"status": "error", "message": "Invalid data format"}), 400

            # Save to weights.json
            save_json(WEIGHTS_FILE, new_weights)
            return jsonify({"status": "saved"})

        else:  # GET request
            weights = load_json(WEIGHTS_FILE)
            if not weights:
                weights = {}
            return jsonify(weights)

    return app



