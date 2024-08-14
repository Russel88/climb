from flask import Flask, render_template, request, jsonify, Response
from functools import wraps
import sqlite3
import os


def create_app():
    app = Flask(__name__)

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
        selected_objects = data['selected_objects']

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
        return jsonify(entry)

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


    return app
