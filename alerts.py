"""
Shared helper for logging events to SQLite and pushing them to the local
Flask server, which the dashboard reads from. This is the single place
every module (visitor recognition, fall detection, panic button, wellbeing
check-in) calls into when something needs to be recorded or escalated.
"""

import sqlite3
import time
import os
import requests

DB_PATH = os.path.join(os.path.dirname(__file__), "data", "sahay.db")
SERVER_URL = "http://localhost:5000/api/alert"


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT,
            message TEXT,
            severity TEXT,
            timestamp REAL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS known_faces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            relation TEXT,
            encoding BLOB
        )
    """)
    conn.commit()
    conn.close()


def log_event(event_type: str, message: str, severity: str = "info"):
    """
    event_type: 'visitor' | 'fall' | 'checkin' | 'panic'
    severity:   'info' | 'soft' | 'emergency'
    Writes to local SQLite (works offline) and tries to notify the local
    Flask server for the live dashboard. If the server/network call fails,
    the event is still safely logged locally — nothing is lost.
    """
    ts = time.time()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO alerts (type, message, severity, timestamp) VALUES (?, ?, ?, ?)",
        (event_type, message, severity, ts),
    )
    conn.commit()
    conn.close()

    try:
        requests.post(
            SERVER_URL,
            json={"type": event_type, "message": message, "severity": severity, "timestamp": ts},
            timeout=1,
        )
    except requests.exceptions.RequestException:
        # Server not running / offline — event is still safely in SQLite.
        # In the real deployment this is where a retry queue would kick in.
        pass


def escalate_emergency(message: str):
    from notifications import send_telegram_alert  # your new helper

    log_event(
        "emergency",
        message,
        severity="emergency"
    )

    print(f"[ESCALATION] {message}")

    # Send caregiver Telegram alert
    send_telegram_alert(
        f"SAHAY EMERGENCY ALERT\n\n{message}",
        chat_id=os.getenv("CAREGIVER_CHAT_ID")
    )

    # Send emergency contact Telegram alert
    send_telegram_alert(
        f"SAHAY EMERGENCY ALERT\n\n{message}",
        chat_id=os.getenv("EMERGENCY_CHAT_ID")
    )

