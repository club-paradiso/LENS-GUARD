"""Bounded metadata aggregation and a deliberately transparent baseline."""

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import hmac
import math
import secrets
import statistics

MODEL_VERSION = "rules-0.1"
THRESHOLD = 70
MAX_SECONDS = 3600
MAX_PACKETS = 200_000


@dataclass(frozen=True)
class Observation:
    timestamp: float
    source: str
    size: int
    rssi: int | None = None


def classify(features):
    if features["packets"] < 100 or features["duration_s"] < 10:
        return {"score": None, "status": "insufficient", "reasons": ["Need at least 100 packets and 10 seconds of observation."]}
    parts = {
        "Sustained activity": 35 * features["active_ratio"],
        "Large packets": 25 * features["large_ratio"],
        "Transmission rate": 25 * min(features["bytes_per_s"] / 20_000, 1),
        "Stable throughput": 15 / (1 + features["throughput_cv"]),
    }
    score = round(sum(parts.values()), 1)
    return {"score": score, "status": "candidate" if score >= THRESHOLD else "low_evidence",
            "reasons": [f"{key}: {value:.1f} score points" for key, value in parts.items()]}


def analyze(observations, provenance, *, salt=None, diagnostics=None):
    items = list(observations)
    if len(items) > MAX_PACKETS:
        raise ValueError("Capture exceeds the 200,000 packet limit; split it locally.")
    if any(not math.isfinite(p.timestamp) or p.size < 0 or p.size > 262144 for p in items):
        raise ValueError("Invalid packet metadata.")
    salt = salt or secrets.token_bytes(32)
    items.sort(key=lambda p: p.timestamp)
    start = items[0].timestamp if items else 0
    duration = items[-1].timestamp - start if items else 0
    if duration > MAX_SECONDS:
        raise ValueError("Capture spans over one hour; split it locally.")
    bins = max(1, math.floor(duration) + 1)
    totals = [0] * bins
    grouped = defaultdict(list)
    for p in items:
        grouped[p.source].append(p)
        totals[min(int(p.timestamp - start), bins - 1)] += p.size
    devices = []
    for source, packets in grouped.items():
        series = [0] * bins
        for p in packets:
            series[min(int(p.timestamp - start), bins - 1)] += p.size
        rate = sum(series) / bins
        features = {
            "packets": len(packets), "duration_s": round(duration, 3),
            "active_ratio": sum(n > 0 for n in series) / bins,
            "large_ratio": sum(p.size >= 1000 for p in packets) / len(packets),
            "bytes_per_s": rate,
            "throughput_cv": statistics.pstdev(series) / rate if rate else 0,
            "mean_packet_bytes": statistics.mean(p.size for p in packets),
        }
        rssi = [p.rssi for p in packets if p.rssi is not None]
        device_id = "device-" + hmac.new(salt, source.encode(), hashlib.sha256).hexdigest()[:10]
        devices.append({"id": device_id, "features": features, **classify(features),
                        "rssi_dbm": round(statistics.mean(rssi), 1) if rssi else None,
                        "series": series})
    devices.sort(key=lambda d: (-(d["score"] if d["score"] is not None else -1), d["id"]))
    return {"schema_version": 1, "model_version": MODEL_VERSION,
            "provenance": provenance, "ground_truth": "not_verified",
            "threshold": THRESHOLD, "duration_s": round(duration, 3),
            "packet_count": len(items), "devices": devices,
            "timeline": [{"second": i, "bytes": n} for i, n in enumerate(totals)],
            "diagnostics": diagnostics or {},
            "limitations": ["Scores are experimental pattern scores, not camera probabilities.",
                            "Video calls, live streams and backups can resemble cameras.",
                            "No candidate does not establish that a room is safe.",
                            "Silent, wired, cellular and off-channel devices are outside scope.",
                            "Device identifiers are pseudonymous and change between analyses."]}
