"""Bounded metadata aggregation and deliberately transparent baselines.

rules-0.2 is the primary score. rules-0.1 is recomputed unchanged on the
transmit-side observations so that both versions can be compared on one input.
"""

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import hmac
import json
import math
import secrets
import statistics

MODEL_VERSION = "rules-0.2"
LEGACY_VERSION = "rules-0.1"
LEGACY_THRESHOLD = 70
MAX_SECONDS = 3600
MAX_PACKETS = 200_000
DIRECTIONS = (None, "tx", "rx")

# Every number that changes a rules-0.2 decision lives here, so that the
# preregistered fingerprint changes whenever a rule or threshold changes.
RULES = {
    "version": MODEL_VERSION,
    "threshold": 55,
    "min_packets": 100,
    "min_duration_s": 10,
    "bin_s": 0.1,
    "baseline_half_window_bins": 10,
    "burst_mad_factor": 4.0,
    "burst_min_excess_ratio": 0.5,
    "period_lag_s": [0.5, 8.0],
    "min_burst_intervals": 3,
    "small_bytes": 600,
    "large_bytes": 1000,
    "gap_merge_s": 2,
    "continuous_active_ratio": 0.9,
    "parts": {
        "uplink": {"max": 30, "ramp": [0.55, 0.85]},
        "periodicity": {"max": 25, "ramp": [0.15, 0.5]},
        "regularity": {"max": 15, "ramp": [0.8, 0.2]},
        "size_mix": {"max": 10, "ramp": [0.05, 0.4]},
        "presence": {"max": 10},
        "shape": {"max": 10, "points": {"continuous": 1.0, "intermittent": 0.5, "single_block": 0.0}},
    },
}
THRESHOLD = RULES["threshold"]
RULE_FINGERPRINT = hashlib.sha256(json.dumps(RULES, sort_keys=True).encode()).hexdigest()[:16]

PROVENANCE_NOTICE = {
    "synthetic_demo": "Simulated data. Generator behavior only; not a detection result.",
    "synthetic_file": "Synthetic file. No physical measurement.",
    "synthetic_evaluation": "Synthetic evaluation. Generator behavior only; not real-world detection accuracy.",
    "user_declared_authorized_capture": "Origin and labels declared by the user; not verified by this program.",
    "unverified_file": "Unverified file. Data origin is unknown.",
}


@dataclass(frozen=True)
class Observation:
    timestamp: float
    source: str
    size: int
    rssi: int | None = None
    # "tx": sent by the allowlisted source; "rx": addressed to it; None: unknown.
    direction: str | None = None


def classify(features):
    """rules-0.1, unchanged. Kept for comparison only."""
    if features["packets"] < 100 or features["duration_s"] < 10:
        return {"score": None, "status": "insufficient", "reasons": ["Need at least 100 packets and 10 seconds of observation."]}
    parts = {
        "Sustained activity": 35 * features["active_ratio"],
        "Large packets": 25 * features["large_ratio"],
        "Transmission rate": 25 * min(features["bytes_per_s"] / 20_000, 1),
        "Stable throughput": 15 / (1 + features["throughput_cv"]),
    }
    score = round(sum(parts.values()), 1)
    return {"score": score, "status": "candidate" if score >= LEGACY_THRESHOLD else "low_evidence",
            "reasons": [f"{key}: {value:.1f} score points" for key, value in parts.items()]}


def legacy_features(packets, start, duration):
    bins = max(1, math.floor(duration) + 1)
    series = [0] * bins
    for p in packets:
        series[min(int(p.timestamp - start), bins - 1)] += p.size
    rate = sum(series) / bins
    return {
        "packets": len(packets), "duration_s": round(duration, 3),
        "active_ratio": sum(n > 0 for n in series) / bins,
        "large_ratio": sum(p.size >= 1000 for p in packets) / len(packets) if packets else 0,
        "bytes_per_s": rate,
        "throughput_cv": statistics.pstdev(series) / rate if rate else 0,
        "mean_packet_bytes": statistics.mean(p.size for p in packets) if packets else 0,
    }


def _ramp(value, low, high):
    """0 at `low`, 1 at `high`; works for descending ramps too."""
    return min(1.0, max(0.0, (value - low) / (high - low)))


def _median(values):
    values = sorted(values)
    return values[len(values) // 2]


def burst_residual(series):
    """Excess bytes of 100 ms bins that stand out from their local baseline.

    Raw 100 ms byte counts of a fixed-rate encoder alias against the bin edge
    (15 fps alternates one and two frames per bin) and would look periodic for
    any constant frame rate. Only bins above a local median plus a MAD margin
    are kept, so periodicity reflects large bursts such as key frames.
    """
    half = RULES["baseline_half_window_bins"]
    residual = [0.0] * len(series)
    for i, value in enumerate(series):
        if value <= 0:
            continue
        window = [v for v in series[max(0, i - half):i + half + 1] if v > 0]
        base = _median(window)
        mad = _median([abs(v - base) for v in window])
        margin = max(RULES["burst_mad_factor"] * mad, RULES["burst_min_excess_ratio"] * base)
        if value > base + margin:
            residual[i] = value - base
    return residual


def autocorrelation(series, lag):
    n = len(series)
    if lag >= n:
        return 0.0
    mean = sum(series) / n
    centered = [v - mean for v in series]
    denom = sum(v * v for v in centered)
    if denom == 0:
        return 0.0
    return sum(centered[i] * centered[i + lag] for i in range(n - lag)) / denom


def periodicity(residual):
    """Strongest autocorrelation within the preregistered lag range.

    Returns (score, period_s). The smallest lag within 90% of the peak is
    reported so a harmonic does not hide the fundamental period.
    """
    if not any(residual):
        return None, None
    bin_s = RULES["bin_s"]
    low = round(RULES["period_lag_s"][0] / bin_s)
    high = min(round(RULES["period_lag_s"][1] / bin_s), len(residual) // 2)
    if high < low:
        return None, None
    values = {lag: autocorrelation(residual, lag) for lag in range(low, high + 1)}
    peak = max(values.values())
    if peak <= 0:
        return 0.0, None
    lag = min(lag for lag, v in values.items() if v >= 0.9 * peak)
    return max(0.0, peak), round(lag * bin_s, 1)


def burst_intervals(residual):
    onsets = [i for i, v in enumerate(residual) if v > 0 and (i == 0 or residual[i - 1] == 0)]
    return [(b - a) * RULES["bin_s"] for a, b in zip(onsets, onsets[1:])], len(onsets)


def session_shape(active):
    """Group active seconds into blocks, merging gaps of up to two seconds."""
    blocks, last = [], None
    for i, on in enumerate(active):
        if not on:
            continue
        if last is not None and i - last <= RULES["gap_merge_s"] + 1:
            blocks[-1][1] = i
        else:
            blocks.append([i, i])
        last = i
    ratio = sum(active) / len(active) if active else 0
    if not blocks:
        return "none", 0
    if ratio >= RULES["continuous_active_ratio"]:
        return "continuous", len(blocks)
    return ("single_block" if len(blocks) == 1 else "intermittent"), len(blocks)


def direction_features(packets, start, duration):
    bin_s = RULES["bin_s"]
    tx = [p for p in packets if p.direction != "rx"]
    known = all(p.direction is not None for p in packets)
    tx_bytes = sum(p.size for p in tx)
    rx_bytes = sum(p.size for p in packets if p.direction == "rx")
    fine = [0] * max(1, math.floor(duration / bin_s) + 1)
    for p in tx:
        fine[min(int((p.timestamp - start) / bin_s), len(fine) - 1)] += p.size
    seconds = max(1, math.floor(duration) + 1)
    active = [False] * seconds
    for p in tx:
        active[min(int(p.timestamp - start), seconds - 1)] = True
    residual = burst_residual(fine)
    score, period = periodicity(residual)
    intervals, bursts = burst_intervals(residual)
    regular = (statistics.pstdev(intervals) / statistics.mean(intervals)
               if len(intervals) >= RULES["min_burst_intervals"] else None)
    small = sum(p.size < RULES["small_bytes"] for p in tx) / len(tx) if tx else 0
    large = sum(p.size >= RULES["large_bytes"] for p in tx) / len(tx) if tx else 0
    shape, blocks = session_shape(active)
    return {
        "packets": len(packets), "duration_s": round(duration, 3),
        "tx_packets": len(tx) if known else None,
        "rx_packets": len(packets) - len(tx) if known else None,
        "tx_bytes": tx_bytes if known else None, "rx_bytes": rx_bytes if known else None,
        "uplink_ratio": round(tx_bytes / (tx_bytes + rx_bytes), 4) if known and tx_bytes + rx_bytes else None,
        "periodicity_score": None if score is None else round(score, 4),
        "period_s": period,
        "burst_count": bursts,
        "burst_interval_cv": None if regular is None else round(regular, 4),
        "size_bimodality": round(2 * min(small, large), 4),
        "small_ratio": round(small, 4), "large_ratio": round(large, 4),
        "active_ratio": round(sum(active) / seconds, 4),
        "session_shape": shape, "active_blocks": blocks,
        "bytes_per_s": round(tx_bytes / seconds, 1),
    }


def score_v2(features):
    p = RULES["parts"]
    if features["packets"] < RULES["min_packets"] or features["duration_s"] < RULES["min_duration_s"]:
        return {"score": None, "status": "insufficient", "abstain_reasons": ["insufficient_observation"], "parts": [],
                "reasons": [f"Need at least {RULES['min_packets']} packets and {RULES['min_duration_s']} seconds of observation."]}
    parts = []

    def add(name, maximum, fraction, value, note=""):
        points = None if fraction is None else round(maximum * fraction, 1)
        parts.append({"feature": name, "points": points, "max": maximum, "value": value, "note": note})

    u = features["uplink_ratio"]
    if u is None:
        add("Uplink dominance", p["uplink"]["max"], None, None,
            "Not computed: capture does not provide transmit/receive direction.")
    else:
        note = "No receive-direction frames observed; a one-sided capture inflates this share." if not features["rx_packets"] else ""
        add("Uplink dominance", p["uplink"]["max"], _ramp(u, *p["uplink"]["ramp"]), f"{u:.0%} of bytes sent", note)
    s = features["periodicity_score"]
    if s is None:
        add("Periodic bursts", p["periodicity"]["max"], 0.0, "no bursts above local baseline")
    else:
        add("Periodic bursts", p["periodicity"]["max"], _ramp(s, *p["periodicity"]["ramp"]),
            f"autocorrelation {s:.2f} at {features['period_s']} s")
    cv = features["burst_interval_cv"]
    if cv is None:
        add("Burst regularity", p["regularity"]["max"], 0.0, f"{features['burst_count']} bursts; need {RULES['min_burst_intervals'] + 1}")
    else:
        add("Burst regularity", p["regularity"]["max"], _ramp(cv, *p["regularity"]["ramp"]), f"interval CV {cv:.2f}")
    add("Packet size mix", p["size_mix"]["max"], _ramp(features["size_bimodality"], *p["size_mix"]["ramp"]),
        f"{features['large_ratio']:.0%} ≥ {RULES['large_bytes']} B, {features['small_ratio']:.0%} < {RULES['small_bytes']} B")
    add("Sustained presence", p["presence"]["max"], features["active_ratio"], f"{features['active_ratio']:.0%} of seconds active")
    add("Session shape", p["shape"]["max"], p["shape"]["points"].get(features["session_shape"], 0.0),
        f"{features['session_shape'].replace('_', ' ')}, {features['active_blocks']} block(s)")
    reasons = [f"{x['feature']}: {'not scored' if x['points'] is None else format(x['points'], '.1f')}"
               f" of {x['max']} points ({x['value'] or x['note']})" for x in parts]
    if u is None:
        partial = round(sum(x["points"] for x in parts if x["points"] is not None), 1)
        return {"score": None, "status": "insufficient_direction", "abstain_reasons": ["insufficient_direction"],
                "parts": parts, "partial_score": partial, "reasons": reasons +
                ["Uplink features withheld instead of filled with zero; rules-0.2 abstains without direction."]}
    score = round(sum(x["points"] for x in parts), 1)
    return {"score": score, "status": "candidate" if score >= THRESHOLD else "low_evidence",
            "abstain_reasons": [], "parts": parts, "reasons": reasons}


def analyze(observations, provenance, *, salt=None, diagnostics=None, window=None):
    """Score each source. `window` is the capture span; it defaults to the eligible frames."""
    items = list(observations)
    if len(items) > MAX_PACKETS:
        raise ValueError("Capture exceeds the 200,000 packet limit; split it locally.")
    if any(not math.isfinite(p.timestamp) or p.size < 0 or p.size > 262144 or p.direction not in DIRECTIONS for p in items):
        raise ValueError("Invalid packet metadata.")
    salt = salt or secrets.token_bytes(32)
    items.sort(key=lambda p: (p.timestamp, p.direction or "", p.size))
    first = items[0].timestamp if items else 0
    last = items[-1].timestamp if items else 0
    start, end = (first, last) if window is None else (min(window[0], first), max(window[1], last))
    if not all(math.isfinite(v) for v in (start, end)):
        raise ValueError("Invalid capture window.")
    duration = end - start
    if duration > MAX_SECONDS:
        raise ValueError("Capture spans over one hour; split it locally.")
    # Phase 1 saw only transmit frames and anchored its window on them.
    sent = [p.timestamp for p in items if p.direction != "rx"]
    legacy_window = (sent[0], sent[-1] - sent[0]) if sent else (start, 0)
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
        old = legacy_features([p for p in packets if p.direction != "rx"], *legacy_window)
        features = direction_features(packets, start, duration)
        rssi = [p.rssi for p in packets if p.rssi is not None]
        device_id = pseudonym(salt, source)
        known = features["uplink_ratio"] is not None
        devices.append({"id": device_id, "model_version": MODEL_VERSION, **score_v2(features), "features": features,
                        "direction": {"available": known, "tx_frames": features["tx_packets"],
                                      "rx_frames": features["rx_packets"]},
                        "comparison": {LEGACY_VERSION: {"features": old, **classify(old)}},
                        "rssi_dbm": round(statistics.mean(rssi), 1) if rssi else None,
                        "series": series})
    devices.sort(key=lambda d: (-(d["score"] if d["score"] is not None else -1), d["id"]))
    return {"schema_version": 2, "model_version": MODEL_VERSION, "comparison_models": [LEGACY_VERSION],
            "rule_fingerprint": RULE_FINGERPRINT,
            "provenance": provenance, "provenance_notice": PROVENANCE_NOTICE.get(provenance, PROVENANCE_NOTICE["unverified_file"]),
            "ground_truth": "not_verified",
            "threshold": THRESHOLD, "thresholds": {MODEL_VERSION: THRESHOLD, LEGACY_VERSION: LEGACY_THRESHOLD},
            "duration_s": round(duration, 3),
            "packet_count": len(items), "devices": devices,
            "timeline": [{"second": i, "bytes": n} for i, n in enumerate(totals)],
            "diagnostics": diagnostics or {},
            "limitations": ["Scores are experimental pattern scores, not camera probabilities.",
                            "Video calls, live streams and backups can resemble cameras.",
                            "No candidate does not establish that a room is safe.",
                            "Silent, wired, cellular and off-channel devices are outside scope.",
                            "Device identifiers are pseudonymous and change between analyses.",
                            "rules-0.1 is recomputed on transmit-side frames for comparison only."]}


def pseudonym(salt, source):
    return "device-" + hmac.new(salt, source.encode(), hashlib.sha256).hexdigest()[:10]
