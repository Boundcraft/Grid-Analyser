import csv
import os
from datetime import datetime
from database import get_recent_faults, get_fault_summary, get_all_readings, get_all_nodes


REPORTS_DIR = os.path.join(os.path.dirname(__file__), "reports")


def _ensure_reports_dir():
    os.makedirs(REPORTS_DIR, exist_ok=True)


def export_fault_log_csv(filename=None):
    """
    Exports all recent faults to a CSV file.
    Returns the path to the saved file.
    """
    _ensure_reports_dir()
    if not filename:
        filename = f"fault_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    path = os.path.join(REPORTS_DIR, filename)

    faults = get_recent_faults(limit=1000)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Fault ID", "Node", "Timestamp", "Fault Type", "Severity", "Resolved"])
        for fault in faults:
            writer.writerow([
                fault["fault_id"],
                fault["node_name"],
                fault["timestamp"],
                fault["fault_type"],
                fault["severity"],
                "Yes" if fault["resolved"] else "No",
            ])

    print(f"[Reporter] Fault log exported to: {path}")
    return path


def export_readings_csv(node_id, node_name, filename=None):
    """
    Exports all readings for a node to CSV.
    Returns the path to the saved file.
    """
    _ensure_reports_dir()
    if not filename:
        safe_name = node_name.replace(" ", "_")
        filename  = f"readings_{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    path = os.path.join(REPORTS_DIR, filename)

    readings = get_all_readings(node_id)

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Reading ID", "Timestamp", "Voltage (V)",
                          "Current (A)", "Frequency (Hz)", "Status"])
        for r in readings:
            writer.writerow([
                r["reading_id"],
                r["timestamp"],
                r["voltage"],
                r["current"],
                r["frequency"],
                r["status"],
            ])

    print(f"[Reporter] Readings exported to: {path}")
    return path


def generate_summary_report(filename=None):
    """
    Generates a plain-text summary report of the entire grid session.
    Returns the path to the saved file.
    """
    _ensure_reports_dir()
    if not filename:
        filename = f"grid_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    path = os.path.join(REPORTS_DIR, filename)

    nodes        = get_all_nodes()
    fault_summary = get_fault_summary()
    recent_faults = get_recent_faults(limit=20)

    lines = [
        "=" * 60,
        "       GRID ANALYSER — SESSION SUMMARY REPORT",
        f"       Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "=" * 60,
        "",
        "MONITORED NODES:",
    ]

    for node in nodes:
        lines.append(f"  • {node['node_name']} ({node['region']})")

    lines += ["", "FAULT SUMMARY BY NODE AND SEVERITY:", "-" * 40]

    if fault_summary:
        for row in fault_summary:
            lines.append(f"  {row['node_name']:<20} | {row['severity']:<8} | {row['count']} fault(s)")
    else:
        lines.append("  No faults recorded this session.")

    lines += ["", "RECENT FAULTS (last 20):", "-" * 40]

    if recent_faults:
        for f in recent_faults:
            resolved = "✓" if f["resolved"] else "✗"
            lines.append(
                f"  [{resolved}] {f['timestamp'][:19]}  |  {f['node_name']:<18}  |  "
                f"{f['fault_type']:<28}  |  {f['severity'].upper()}"
            )
    else:
        lines.append("  No faults recorded.")

    lines += ["", "=" * 60, "END OF REPORT", "=" * 60]

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"[Reporter] Summary report saved to: {path}")
    return path


if __name__ == "__main__":
    print(generate_summary_report())
