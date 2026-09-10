"""
Minimal Flask backend + auto-refreshing dashboard. For the review demo,
this stands in for the full Caregiver Companion App (Flutter/Firebase
version comes later) — it shows the same data a caregiver would see:
a live feed of visitor, fall, check-in, and panic-button events.
"""

from flask import Flask, request, jsonify, render_template
import sqlite3
import os
from alerts import init_db, DB_PATH

app = Flask(__name__)


@app.route("/api/alert", methods=["POST"])
def receive_alert():
    # main.py already writes to SQLite directly via alerts.log_event();
    # this endpoint exists so a future mobile app / cloud sync has a real
    # place to push to, and so the dashboard has a live "just happened"
    # signal it can poll. For the demo it just acknowledges.
    data = request.get_json(force=True)
    return jsonify({"status": "received", "data": data}), 200


@app.route("/api/logs", methods=["GET"])
def get_logs():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT type, message, severity, timestamp FROM alerts ORDER BY timestamp DESC LIMIT 50")
    rows = c.fetchall()
    conn.close()
    logs = [
        {"type": r[0], "message": r[1], "severity": r[2], "timestamp": r[3]}
        for r in rows
    ]
    return jsonify(logs)


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
