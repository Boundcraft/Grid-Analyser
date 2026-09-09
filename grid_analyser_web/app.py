"""
Grid Analyser Web — Flask Backend
Ghana Power Grid Fault Detection System
Boundcraft / Cami 2026
"""

from flask import Flask, jsonify, render_template, request
import threading
import time
from datetime import datetime
from collections import defaultdict, deque

import database as db
import simulator as sim
import fault_detector as fd
import alarm as alm

app = Flask(__name__)

# ── GLOBAL STATE ─────────────────────────────────────────────────────────────
_lock         = threading.Lock()
_running      = False
_elapsed_s    = 0
_tick_thread  = None

_grid_sim     = None
_detector     = None
_alarm_mgr    = None

# Rolling cache — last 60 readings per node for charting
_readings_cache = defaultdict(lambda: deque(maxlen=60))

# Latest reading per node
_latest = {}

# Recent faults list (in memory, max 100)
_recent_faults = deque(maxlen=100)

# ── PLAIN ENGLISH EXPLANATIONS ────────────────────────────────────────────────
FAULT_EXPLANATIONS = {
    "Voltage Out of Range":      "The electricity supply voltage has dropped or risen beyond safe levels. This can cause appliances to malfunction or stop working.",
    "Voltage Critical Fault":    "The voltage has reached a dangerous level. Immediate action is needed — appliances and equipment in this area are at serious risk.",
    "Voltage Warning":           "The voltage is slightly outside the normal range. If this continues, it could affect the quality of electricity supply in this area.",
    "Current Out of Range":      "Too much electrical current is flowing through this node. This can overheat cables and cause equipment damage or fire risk.",
    "Overcurrent":               "A dangerous level of current has been detected. This is similar to an electrical overload in a home — circuits may trip or fail.",
    "Current Warning":           "The electrical current is approaching unsafe levels. Engineers should monitor this node closely.",
    "Frequency Out of Range":    "The stability of the power supply has been disrupted. Frequency deviation means the grid is struggling to maintain balance, which can affect sensitive equipment.",
    "Frequency Critical Fault":  "The power supply frequency has deviated critically. This is a serious grid instability event that can cause widespread outages.",
    "Frequency Warning":         "Minor instability detected in the power supply frequency. This is an early warning sign of grid stress.",
    "ML Anomaly Detected":       "Our system has detected an unusual pattern in this node's readings that does not match normal behaviour. Further monitoring is recommended.",
}

STATUS_EXPLANATIONS = {
    "normal":  "All systems are operating within safe limits. No action required.",
    "warning": "This node is showing early signs of stress. Engineers should monitor it closely.",
    "fault":   "A fault has been detected at this node. Immediate investigation is recommended.",
}

SEVERITY_LABELS = {
    "low":    "Minor Issue",
    "medium": "Moderate Fault",
    "high":   "Critical Fault",
}


def _explain_fault(fault_type):
    return FAULT_EXPLANATIONS.get(fault_type,
        "An abnormal reading has been detected at this node. Technical review is advised.")


def _explain_status(status):
    return STATUS_EXPLANATIONS.get(status, "Status unknown.")


# ── SIMULATION ENGINE ─────────────────────────────────────────────────────────

def _init_engine():
    global _grid_sim, _detector, _alarm_mgr
    db.initialise_db()
    nodes      = [dict(n) for n in db.get_all_nodes()]
    _grid_sim  = sim.GridSimulator(nodes)
    _detector  = fd.FaultDetector()
    _alarm_mgr = alm.AlarmManager()


def _simulation_loop():
    global _running, _elapsed_s
    while _running:
        _elapsed_s += 1
        readings = _grid_sim.tick_all()

        for reading in readings:
            node_id   = reading["node_id"]
            voltage   = reading["voltage"]
            current   = reading["current"]
            frequency = reading["frequency"]

            result = _detector.analyse(node_id, voltage, current, frequency)
            status = result["status"]

            db.insert_reading(node_id, voltage, current, frequency, status)

            with _lock:
                _readings_cache[node_id].append({
                    "t":         _elapsed_s,
                    "voltage":   voltage,
                    "current":   current,
                    "frequency": frequency,
                    "status":    status,
                })
                _latest[node_id] = {
                    "node_id":    node_id,
                    "node_name":  reading["node_name"],
                    "voltage":    voltage,
                    "current":    current,
                    "frequency":  frequency,
                    "status":     status,
                    "status_explanation": _explain_status(status),
                    "issues":     result["issues"],
                    "ml_ready":   result["ml_ready"],
                    "anomaly":    result["is_anomaly"],
                }

            if status in ("fault", "warning"):
                for fault_type, severity in result["issues"]:
                    db.insert_fault(node_id, fault_type, severity)
                    with _lock:
                        _recent_faults.appendleft({
                            "time":        datetime.now().strftime("%H:%M:%S"),
                            "node_name":   reading["node_name"],
                            "fault_type":  fault_type,
                            "severity":    severity,
                            "severity_label": SEVERITY_LABELS.get(severity, severity),
                            "explanation": _explain_fault(fault_type),
                        })

        time.sleep(1)


# ── FLASK ROUTES ──────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("monitor.html")


@app.route("/report")
def report():
    return render_template("report.html")


@app.route("/api/start", methods=["POST"])
def api_start():
    global _running, _tick_thread, _elapsed_s
    if _running:
        return jsonify({"status": "already_running"})
    _running   = True
    _elapsed_s = 0
    _tick_thread = threading.Thread(target=_simulation_loop, daemon=True)
    _tick_thread.start()
    return jsonify({"status": "started"})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    global _running
    _running = False
    return jsonify({"status": "stopped"})


@app.route("/api/status")
def api_status():
    """Returns simulation running state and elapsed time."""
    h = _elapsed_s // 3600
    m = (_elapsed_s % 3600) // 60
    s = _elapsed_s % 60
    return jsonify({
        "running": _running,
        "elapsed": f"{h:02d}:{m:02d}:{s:02d}",
        "total_faults": db.get_fault_count(),
    })


@app.route("/api/nodes")
def api_nodes():
    """Returns latest reading for all nodes."""
    with _lock:
        nodes = list(_latest.values())

    # Enrich with plain English
    for node in nodes:
        node["issues_explained"] = [
            {
                "fault_type":     ft,
                "severity":       sv,
                "severity_label": SEVERITY_LABELS.get(sv, sv),
                "explanation":    _explain_fault(ft),
            }
            for ft, sv in node.get("issues", [])
        ]

    return jsonify(nodes)


@app.route("/api/faults")
def api_faults():
    """Returns recent faults list."""
    with _lock:
        faults = list(_recent_faults)
    return jsonify(faults[:50])


@app.route("/api/chart/<int:node_id>")
def api_chart(node_id):
    """Returns rolling chart data for a specific node."""
    with _lock:
        data = list(_readings_cache[node_id])
    return jsonify(data)


@app.route("/api/report")
def api_report():
    """Generates and returns a structured report with plain English."""
    fault_summary = db.get_fault_summary()
    recent_faults = db.get_recent_faults(limit=20)
    nodes         = db.get_all_nodes()

    # Build per-node summary
    node_summaries = {}
    for node in nodes:
        node_summaries[node["node_name"]] = {
            "node_name": node["node_name"],
            "region":    node["region"],
            "faults":    {"low": 0, "medium": 0, "high": 0},
            "total":     0,
        }

    for row in fault_summary:
        name = row["node_name"]
        sev  = row["severity"]
        cnt  = row["count"]
        if name in node_summaries:
            node_summaries[name]["faults"][sev] = cnt
            node_summaries[name]["total"]       += cnt

    # Plain English per node
    for name, summary in node_summaries.items():
        total  = summary["total"]
        high   = summary["faults"]["high"]
        medium = summary["faults"]["medium"]
        low    = summary["faults"]["low"]

        if total == 0:
            summary["plain_english"] = (
                f"{name} operated normally throughout this session. "
                "No faults or warnings were recorded. Electricity supply in this area was stable."
            )
        else:
            parts = []
            if high:
                parts.append(f"{high} critical fault{'s' if high > 1 else ''}")
            if medium:
                parts.append(f"{medium} moderate fault{'s' if medium > 1 else ''}")
            if low:
                parts.append(f"{low} minor warning{'s' if low > 1 else ''}")

            fault_str = ", ".join(parts)
            summary["plain_english"] = (
                f"{name} recorded {fault_str} during this session. "
                f"This means the electricity supply in this area experienced "
                f"{'serious disruptions' if high > 0 else 'some instability'} "
                f"that {'required' if high > 0 else 'may have required'} attention from engineers. "
                f"{'Residents in this area likely experienced outages or power quality issues.' if high > 2 else ''}"
            )

    recent = []
    for f in recent_faults:
        recent.append({
            "time":        f["timestamp"][:19],
            "node_name":   f["node_name"],
            "fault_type":  f["fault_type"],
            "severity":    f["severity"],
            "severity_label": SEVERITY_LABELS.get(f["severity"], f["severity"]),
            "explanation": _explain_fault(f["fault_type"]),
            "resolved":    bool(f["resolved"]),
        })

    h = _elapsed_s // 3600
    m = (_elapsed_s % 3600) // 60
    s = _elapsed_s % 60

    return jsonify({
        "generated_at":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "session_elapsed": f"{h:02d}:{m:02d}:{s:02d}",
        "total_faults":   db.get_fault_count(),
        "node_summaries": list(node_summaries.values()),
        "recent_faults":  recent,
    })


@app.route("/api/export/csv")
def api_export_csv():
    """Export fault log as CSV download."""
    import csv
    import io
    from flask import Response

    faults = db.get_recent_faults(limit=1000)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Fault ID", "Node", "Timestamp", "Fault Type",
                     "Severity", "Plain English", "Resolved"])
    for f in faults:
        writer.writerow([
            f["fault_id"],
            f["node_name"],
            f["timestamp"],
            f["fault_type"],
            f["severity"],
            _explain_fault(f["fault_type"]),
            "Yes" if f["resolved"] else "No",
        ])

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=grid_fault_log.csv"}
    )


# ── STARTUP ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    _init_engine()
    print("\n⚡ Grid Analyser Web starting...")
    print("   Open http://127.0.0.1:5000 in your browser\n")
    app.run(debug=False, threaded=True)
