import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "grid_analyser.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialise_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Nodes table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS nodes (
            node_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            node_name TEXT NOT NULL UNIQUE,
            region    TEXT NOT NULL
        )
    """)

    # Readings table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id    INTEGER NOT NULL,
            timestamp  TEXT NOT NULL,
            voltage    REAL NOT NULL,
            current    REAL NOT NULL,
            frequency  REAL NOT NULL,
            status     TEXT NOT NULL DEFAULT 'normal',
            FOREIGN KEY (node_id) REFERENCES nodes(node_id)
        )
    """)

    # Faults table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS faults (
            fault_id   INTEGER PRIMARY KEY AUTOINCREMENT,
            node_id    INTEGER NOT NULL,
            timestamp  TEXT NOT NULL,
            fault_type TEXT NOT NULL,
            severity   TEXT NOT NULL,
            resolved   INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (node_id) REFERENCES nodes(node_id)
        )
    """)

    # Alarms table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alarms (
            alarm_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            fault_id     INTEGER NOT NULL,
            timestamp    TEXT NOT NULL,
            acknowledged INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (fault_id) REFERENCES faults(fault_id)
        )
    """)

    # Seed nodes if not already present
    nodes = [
        ("Accra Central",   "Greater Accra"),
        ("Kumasi",          "Ashanti"),
        ("Takoradi",        "Western"),
        ("Tamale",          "Northern"),
        ("Tema Industrial", "Greater Accra"),
    ]
    cursor.executemany("""
        INSERT OR IGNORE INTO nodes (node_name, region) VALUES (?, ?)
    """, nodes)

    conn.commit()
    conn.close()
    print("[DB] Database initialised successfully.")


# ── READINGS ──────────────────────────────────────────────────────────────────

def insert_reading(node_id, voltage, current, frequency, status):
    conn = get_connection()
    conn.execute("""
        INSERT INTO readings (node_id, timestamp, voltage, current, frequency, status)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (node_id, datetime.now().isoformat(), voltage, current, frequency, status))
    conn.commit()
    conn.close()


def get_recent_readings(node_id, limit=60):
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM readings
        WHERE node_id = ?
        ORDER BY reading_id DESC
        LIMIT ?
    """, (node_id, limit)).fetchall()
    conn.close()
    return list(reversed(rows))


def get_all_readings(node_id):
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM readings
        WHERE node_id = ?
        ORDER BY reading_id ASC
    """, (node_id,)).fetchall()
    conn.close()
    return rows


# ── FAULTS ────────────────────────────────────────────────────────────────────

def insert_fault(node_id, fault_type, severity):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO faults (node_id, timestamp, fault_type, severity, resolved)
        VALUES (?, ?, ?, ?, 0)
    """, (node_id, datetime.now().isoformat(), fault_type, severity))
    fault_id = cursor.lastrowid

    # Auto-create alarm for this fault
    cursor.execute("""
        INSERT INTO alarms (fault_id, timestamp, acknowledged)
        VALUES (?, ?, 0)
    """, (fault_id, datetime.now().isoformat()))

    conn.commit()
    conn.close()
    return fault_id


def get_recent_faults(limit=50):
    conn = get_connection()
    rows = conn.execute("""
        SELECT f.*, n.node_name FROM faults f
        JOIN nodes n ON f.node_id = n.node_id
        ORDER BY f.fault_id DESC
        LIMIT ?
    """, (limit,)).fetchall()
    conn.close()
    return rows


def resolve_fault(fault_id):
    conn = get_connection()
    conn.execute("UPDATE faults SET resolved = 1 WHERE fault_id = ?", (fault_id,))
    conn.commit()
    conn.close()


def get_fault_count():
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM faults").fetchone()[0]
    conn.close()
    return count


# ── ALARMS ────────────────────────────────────────────────────────────────────

def get_unacknowledged_alarms():
    conn = get_connection()
    rows = conn.execute("""
        SELECT a.*, f.fault_type, f.severity, n.node_name
        FROM alarms a
        JOIN faults f ON a.fault_id = f.fault_id
        JOIN nodes n ON f.node_id = n.node_id
        WHERE a.acknowledged = 0
        ORDER BY a.alarm_id DESC
    """).fetchall()
    conn.close()
    return rows


def acknowledge_alarm(alarm_id):
    conn = get_connection()
    conn.execute("UPDATE alarms SET acknowledged = 1 WHERE alarm_id = ?", (alarm_id,))
    conn.commit()
    conn.close()


def acknowledge_all_alarms():
    conn = get_connection()
    conn.execute("UPDATE alarms SET acknowledged = 1")
    conn.commit()
    conn.close()


# ── NODES ─────────────────────────────────────────────────────────────────────

def get_all_nodes():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM nodes ORDER BY node_id").fetchall()
    conn.close()
    return rows


def get_node_by_name(name):
    conn = get_connection()
    row = conn.execute("SELECT * FROM nodes WHERE node_name = ?", (name,)).fetchone()
    conn.close()
    return row


# ── REPORTING ─────────────────────────────────────────────────────────────────

def get_fault_summary():
    """Returns fault counts grouped by node and severity."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT n.node_name, f.severity, COUNT(*) as count
        FROM faults f
        JOIN nodes n ON f.node_id = n.node_id
        GROUP BY n.node_name, f.severity
        ORDER BY n.node_name, f.severity
    """).fetchall()
    conn.close()
    return rows


if __name__ == "__main__":
    initialise_db()
    print("[DB] Nodes:", [dict(n) for n in get_all_nodes()])
