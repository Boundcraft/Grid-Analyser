import threading
import time
from datetime import datetime


# Severity colours for GUI use
SEVERITY_COLOURS = {
    "low":    "#FFD700",   # gold
    "medium": "#FF8C00",   # dark orange
    "high":   "#FF2222",   # red
}

STATUS_COLOURS = {
    "normal":  "#00CC44",
    "warning": "#FFD700",
    "fault":   "#FF2222",
}


class AlarmManager:
    """
    Manages active alarms in memory and triggers callbacks.
    Works alongside the database — DB is source of truth,
    this class handles real-time GUI notifications.
    """

    def __init__(self, on_alarm_callback=None):
        """
        on_alarm_callback: callable(alarm_dict) called whenever a new alarm fires.
        """
        self._active_alarms  = []   # list of alarm dicts
        self._lock           = threading.Lock()
        self._callback       = on_alarm_callback
        self._alarm_id_counter = 0

    def raise_alarm(self, node_name, fault_type, severity, node_id=None, fault_id=None):
        """
        Create and store a new alarm. Fires callback if set.
        Returns alarm dict.
        """
        self._alarm_id_counter += 1
        alarm = {
            "alarm_id":     self._alarm_id_counter,
            "node_id":      node_id,
            "node_name":    node_name,
            "fault_type":   fault_type,
            "severity":     severity,
            "fault_id":     fault_id,
            "timestamp":    datetime.now().strftime("%H:%M:%S"),
            "acknowledged": False,
            "colour":       SEVERITY_COLOURS.get(severity, "#FFFFFF"),
        }

        with self._lock:
            self._active_alarms.append(alarm)

        if self._callback:
            self._callback(alarm)

        return alarm

    def acknowledge(self, alarm_id):
        with self._lock:
            for alarm in self._active_alarms:
                if alarm["alarm_id"] == alarm_id:
                    alarm["acknowledged"] = True
                    break

    def acknowledge_all(self):
        with self._lock:
            for alarm in self._active_alarms:
                alarm["acknowledged"] = True

    def get_active(self):
        """Returns unacknowledged alarms, most recent first."""
        with self._lock:
            return [a for a in reversed(self._active_alarms) if not a["acknowledged"]]

    def get_all(self):
        with self._lock:
            return list(reversed(self._active_alarms))

    def clear_all(self):
        with self._lock:
            self._active_alarms.clear()

    def active_count(self):
        with self._lock:
            return sum(1 for a in self._active_alarms if not a["acknowledged"])


class BeepAlarm:
    """
    Optional audible alarm using system beep.
    Runs in a background thread so it doesn't block the GUI.
    """

    def __init__(self):
        self._beeping = False
        self._thread  = None

    def beep(self, severity="low"):
        """Trigger a non-blocking beep based on severity."""
        if self._beeping:
            return
        self._beeping = True
        self._thread  = threading.Thread(target=self._beep_worker,
                                         args=(severity,), daemon=True)
        self._thread.start()

    def _beep_worker(self, severity):
        try:
            import winsound
            freqs    = {"low": 800, "medium": 1200, "high": 1600}
            durations = {"low": 200, "medium": 300, "high": 500}
            repeats   = {"low": 1,   "medium": 2,   "high": 3}
            freq     = freqs.get(severity, 800)
            duration = durations.get(severity, 200)
            count    = repeats.get(severity, 1)
            for _ in range(count):
                winsound.Beep(freq, duration)
                time.sleep(0.1)
        except ImportError:
            # Non-Windows fallback — print bell character
            print("\a", end="", flush=True)
        finally:
            self._beeping = False

    def stop(self):
        self._beeping = False


if __name__ == "__main__":
    def my_callback(alarm):
        print(f"[ALARM] {alarm['timestamp']} | {alarm['node_name']} | "
              f"{alarm['fault_type']} | Severity: {alarm['severity']}")

    manager = AlarmManager(on_alarm_callback=my_callback)
    manager.raise_alarm("Accra Central", "Voltage Out of Range", "high", node_id=1)
    manager.raise_alarm("Kumasi",        "Overcurrent",           "medium", node_id=2)
    manager.raise_alarm("Tamale",        "Frequency Warning",     "low",    node_id=4)

    print("\nActive alarms:", len(manager.get_active()))
    manager.acknowledge_all()
    print("After ack:", len(manager.get_active()))
