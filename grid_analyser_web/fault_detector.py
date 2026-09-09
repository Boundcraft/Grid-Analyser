import numpy as np
from sklearn.ensemble import IsolationForest
from collections import defaultdict

# ── RULE-BASED THRESHOLDS ────────────────────────────────────────────────────
THRESHOLDS = {
    "voltage": {
        "normal":  (220.0, 240.0),
        "warning": (200.0, 260.0),
        "fault":   (180.0, 280.0),   # outside this = high severity fault
    },
    "current": {
        "normal":  (0.0,  100.0),
        "warning": (100.0, 120.0),
        "fault":   (120.0, float("inf")),
    },
    "frequency": {
        "normal":  (49.5, 50.5),
        "warning": (48.0, 52.0),
        "fault":   (46.0, 54.0),
    },
}

SEVERITY_MAP = {
    "normal":  None,
    "warning": "low",
    "fault":   "high",
}


def rule_based_check(voltage, current, frequency):
    """
    Apply rule-based threshold checks.
    Returns list of (fault_type, severity) tuples. Empty list = all normal.
    """
    issues = []

    def check_param(name, value):
        t = THRESHOLDS[name]
        lo_n, hi_n = t["normal"]
        lo_w, hi_w = t["warning"]
        lo_f, hi_f = t["fault"]

        if value < lo_n or value > hi_n:
            if value < lo_w or value > hi_w:
                # Outside warning range
                if value < lo_f or value > hi_f:
                    issues.append((f"{name.capitalize()} Critical Fault", "high"))
                else:
                    issues.append((f"{name.capitalize()} Out of Range", "medium"))
            else:
                issues.append((f"{name.capitalize()} Warning", "low"))

    check_param("voltage",   voltage)
    check_param("current",   current)
    check_param("frequency", frequency)

    return issues


class AnomalyDetector:
    """
    ML-based anomaly detector using IsolationForest.
    Trains on historical readings for each node separately.
    Requires at least MIN_SAMPLES readings before activating.
    """

    MIN_SAMPLES = 30

    def __init__(self):
        self._models  = {}   # node_id -> trained IsolationForest
        self._buffers = defaultdict(list)  # node_id -> list of feature vectors

    def add_reading(self, node_id, voltage, current, frequency):
        """Feed a new reading into the node's buffer."""
        self._buffers[node_id].append([voltage, current, frequency])

        # Retrain every 20 new samples once past MIN_SAMPLES
        buf = self._buffers[node_id]
        if len(buf) >= self.MIN_SAMPLES and len(buf) % 20 == 0:
            self._train(node_id)

    def _train(self, node_id):
        buf = self._buffers[node_id]
        X   = np.array(buf)
        model = IsolationForest(
            n_estimators=100,
            contamination=0.05,   # expect ~5% anomalies
            random_state=42
        )
        model.fit(X)
        self._models[node_id] = model

    def predict(self, node_id, voltage, current, frequency):
        """
        Returns (is_anomaly: bool, score: float).
        score < 0 = anomaly territory in IsolationForest.
        Returns (False, 0.0) if model not yet trained.
        """
        if node_id not in self._models:
            return False, 0.0

        model  = self._models[node_id]
        X      = np.array([[voltage, current, frequency]])
        pred   = model.predict(X)[0]    # 1 = normal, -1 = anomaly
        score  = model.score_samples(X)[0]

        is_anomaly = pred == -1
        return is_anomaly, round(float(score), 4)

    def is_ready(self, node_id):
        return node_id in self._models


class FaultDetector:
    """
    Combines rule-based and ML anomaly detection.
    Maintains one AnomalyDetector shared across all nodes.
    """

    def __init__(self):
        self.anomaly_detector = AnomalyDetector()
        self._fault_counts    = defaultdict(int)   # node_id -> total faults

    def analyse(self, node_id, voltage, current, frequency):
        """
        Analyse a reading. Returns:
        {
            'status':      'normal' | 'warning' | 'fault',
            'issues':      [(fault_type, severity), ...],
            'is_anomaly':  bool,
            'anomaly_score': float,
            'ml_ready':    bool,
        }
        """
        # Feed into anomaly detector
        self.anomaly_detector.add_reading(node_id, voltage, current, frequency)

        # Rule-based check
        issues = rule_based_check(voltage, current, frequency)

        # ML anomaly check
        is_anomaly, score = self.anomaly_detector.predict(node_id, voltage, current, frequency)
        ml_ready          = self.anomaly_detector.is_ready(node_id)

        # If ML flags anomaly but rules didn't, add as low severity issue
        if is_anomaly and not issues:
            issues.append(("ML Anomaly Detected", "low"))

        # Determine overall status
        if not issues:
            status = "normal"
        else:
            severities = [s for _, s in issues]
            if "high" in severities:
                status = "fault"
            elif "medium" in severities:
                status = "fault"
            else:
                status = "warning"

        if status in ("fault", "warning"):
            self._fault_counts[node_id] += 1

        return {
            "status":        status,
            "issues":        issues,
            "is_anomaly":    is_anomaly,
            "anomaly_score": score,
            "ml_ready":      ml_ready,
        }

    def get_fault_count(self, node_id):
        return self._fault_counts[node_id]

    def reset_counts(self):
        self._fault_counts.clear()


if __name__ == "__main__":
    detector = FaultDetector()

    # Simulate some normal readings to train ML
    import random
    for _ in range(50):
        detector.analyse(1, random.uniform(225, 235),
                            random.uniform(40, 80),
                            random.uniform(49.8, 50.2))

    # Now test a fault reading
    result = detector.analyse(1, 185.0, 130.0, 47.5)
    print("Fault reading result:", result)

    # Normal reading
    result = detector.analyse(1, 230.0, 60.0, 50.0)
    print("Normal reading result:", result)
