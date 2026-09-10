import sqlite3
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "sahay.db"

DATA_DIR.mkdir(exist_ok=True)

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():

    conn = get_connection()
    cursor = conn.cursor()

    # --------------------------------
    # Known faces
    # --------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS known_faces (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            relation TEXT,
            embedding BLOB NOT NULL,
            model TEXT DEFAULT 'buffalo_l',
            created_at TEXT NOT NULL
        )
    """)

    # --------------------------------
    # Alerts
    # --------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            message TEXT NOT NULL,
            severity TEXT DEFAULT 'LOW',
            timestamp TEXT NOT NULL,
            snapshot TEXT,
            status TEXT DEFAULT 'ACTIVE'
        )
    """)

    # --------------------------------
    # Activity logs
    # --------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            camera_zone TEXT,
            details TEXT
        )
    """)

    # --------------------------------
    # Medicine logs
    # --------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS medicine_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            medicine_name TEXT NOT NULL,
            scheduled_time TEXT NOT NULL,
            taken INTEGER DEFAULT 0,
            timestamp TEXT
        )
    """)

    # --------------------------------
    # System events
    # --------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS system_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event_type TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            details TEXT
        )
    """)

    conn.commit()
    conn.close()


def log_activity(event_type, camera_zone="", details=""):

    conn = get_connection()

    conn.execute("""
        INSERT INTO activity_logs
        (event_type, timestamp, camera_zone, details)
        VALUES (?, ?, ?, ?)
    """, (
        event_type,
        datetime.now().isoformat(),
        camera_zone,
        details
    ))

    conn.commit()
    conn.close()


def create_alert(
    alert_type,
    message,
    severity="LOW",
    snapshot=None
):

    conn = get_connection()

    conn.execute("""
        INSERT INTO alerts
        (type, message, severity, timestamp, snapshot)
        VALUES (?, ?, ?, ?, ?)
    """, (
        alert_type,
        message,
        severity,
        datetime.now().isoformat(),
        snapshot
    ))

    conn.commit()
    conn.close()