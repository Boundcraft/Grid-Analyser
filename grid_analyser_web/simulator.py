import random
import time
from datetime import datetime

# ── SAFE OPERATING RANGES ─────────────────────────────────────────────────────
VOLTAGE_NORMAL  = (220.0, 240.0)
VOLTAGE_WARNING = (200.0, 260.0)  # outside normal but not fault
CURRENT_NORMAL  = (0.0,   100.0)
CURRENT_WARNING = (100.0, 120.0)
FREQ_NORMAL     = (49.5,  50.5)
FREQ_WARNING    = (48.0,  49.5)

# Fault injection probability per tick (5% chance of fault per node per tick)
FAULT_PROBABILITY = 0.05


def _clamp(value, low, high):
    return max(low, min(high, value))


def _determine_status(voltage, current, frequency):
    """
    Returns (status, fault_type, severity) based on readings.
    status: 'normal' | 'warning' | 'fault'
    fault_type: None or description string
    severity: None | 'low' | 'medium' | 'high'
    """
    faults = []

    # Voltage checks
    if voltage < 200 or voltage > 260:
        severity = "high" if (voltage < 180 or voltage > 280) else "medium"
        faults.append(("Voltage Out of Range", severity))
    elif voltage < VOLTAGE_NORMAL[0] or voltage > VOLTAGE_NORMAL[1]:
        faults.append(("Voltage Warning", "low"))

    # Current checks
    if current > 120:
        faults.append(("Overcurrent", "high"))
    elif current > 100:
        faults.append(("Current Warning", "low"))

    # Frequency checks
    if frequency < 48 or frequency > 52:
        faults.append(("Frequency Deviation", "high"))
    elif frequency < FREQ_NORMAL[0] or frequency > FREQ_NORMAL[1]:
        faults.append(("Frequency Warning", "low"))

    if not faults:
        return "normal", None, None

    # Pick the most severe fault
    severity_order = {"high": 3, "medium": 2, "low": 1}
    faults.sort(key=lambda x: severity_order[x[1]], reverse=True)
    top_fault = faults[0]

    if top_fault[1] in ("high", "medium"):
        return "fault", top_fault[0], top_fault[1]
    else:
        return "warning", top_fault[0], top_fault[1]


class NodeSimulator:
    """
    Simulates a single grid node's readings over time.
    Each node maintains a state (voltage, current, frequency) that
    drifts realistically with occasional fault injections.
    """

    def __init__(self, node_id, node_name):
        self.node_id   = node_id
        self.node_name = node_name

        # Start within normal range
        self.voltage   = random.uniform(225, 235)
        self.current   = random.uniform(40, 80)
        self.frequency = random.uniform(49.8, 50.2)

        self._fault_active    = False
        self._fault_duration  = 0
        self._fault_countdown = 0

    def tick(self):
        """
        Advance simulation by one tick.
        Returns dict with reading values and status.
        """
        # Inject fault randomly
        if not self._fault_active and random.random() < FAULT_PROBABILITY:
            self._fault_active    = True
            self._fault_duration  = random.randint(3, 10)  # ticks
            self._fault_countdown = self._fault_duration

        if self._fault_active:
            self._apply_fault()
            self._fault_countdown -= 1
            if self._fault_countdown <= 0:
                self._fault_active = False
        else:
            self._drift_normal()

        # Clamp to realistic bounds
        self.voltage   = _clamp(self.voltage,   170, 290)
        self.current   = _clamp(self.current,   0,   150)
        self.frequency = _clamp(self.frequency, 46,  54)

        status, fault_type, severity = _determine_status(
            self.voltage, self.current, self.frequency
        )

        return {
            "node_id":    self.node_id,
            "node_name":  self.node_name,
            "timestamp":  datetime.now().isoformat(),
            "voltage":    round(self.voltage,   2),
            "current":    round(self.current,   2),
            "frequency":  round(self.frequency, 3),
            "status":     status,
            "fault_type": fault_type,
            "severity":   severity,
        }

    def _drift_normal(self):
        """Small random walk within normal range."""
        self.voltage   += random.uniform(-1.5, 1.5)
        self.current   += random.uniform(-2.0, 2.0)
        self.frequency += random.uniform(-0.05, 0.05)

        # Pull back toward normal centre
        self.voltage   += (230 - self.voltage)   * 0.05
        self.current   += (60  - self.current)   * 0.03
        self.frequency += (50  - self.frequency) * 0.1

    def _apply_fault(self):
        """Push readings toward fault territory."""
        fault_choice = random.choice(["undervoltage", "overvoltage", "overcurrent", "freq_drop"])

        if fault_choice == "undervoltage":
            self.voltage   -= random.uniform(5, 15)
            self.frequency -= random.uniform(0.1, 0.3)
        elif fault_choice == "overvoltage":
            self.voltage   += random.uniform(5, 20)
        elif fault_choice == "overcurrent":
            self.current   += random.uniform(5, 20)
            self.voltage   -= random.uniform(2, 8)
        elif fault_choice == "freq_drop":
            self.frequency -= random.uniform(0.3, 1.0)
            self.voltage   -= random.uniform(3, 10)

    def reset(self):
        """Reset node to normal operating conditions."""
        self.voltage        = random.uniform(225, 235)
        self.current        = random.uniform(40,  80)
        self.frequency      = random.uniform(49.8, 50.2)
        self._fault_active  = False
        self._fault_countdown = 0


class GridSimulator:
    """
    Manages all NodeSimulators and produces readings on demand.
    """

    def __init__(self, nodes):
        """
        nodes: list of dicts with keys node_id, node_name
        """
        self.simulators = {
            n["node_id"]: NodeSimulator(n["node_id"], n["node_name"])
            for n in nodes
        }
        self.running = False

    def tick_all(self):
        """Advance all nodes by one tick. Returns list of reading dicts."""
        return [sim.tick() for sim in self.simulators.values()]

    def tick_node(self, node_id):
        """Advance a single node by one tick."""
        return self.simulators[node_id].tick()

    def reset_node(self, node_id):
        self.simulators[node_id].reset()

    def reset_all(self):
        for sim in self.simulators.values():
            sim.reset()

    def get_node_ids(self):
        return list(self.simulators.keys())


if __name__ == "__main__":
    # Quick smoke test
    nodes = [
        {"node_id": 1, "node_name": "Accra Central"},
        {"node_id": 2, "node_name": "Kumasi"},
    ]
    grid = GridSimulator(nodes)
    for i in range(5):
        readings = grid.tick_all()
        for r in readings:
            print(f"[{r['node_name']}] V={r['voltage']}V  I={r['current']}A  "
                  f"f={r['frequency']}Hz  status={r['status']}")
        time.sleep(0.5)
