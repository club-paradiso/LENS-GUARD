"""Seeded synthetic evaluation, not real-world accuracy validation.

`dev` seeds tune rules-0.2. `test` (same generator, locked seeds) and `shift`
(changed generator parameters) run only after docs/PREREGISTRATION.md is
committed. All figures describe generator behavior, not detection accuracy.
"""

from .demo import CAMERA_PROFILES, LEGACY_PROFILES, PROFILES, scenario, scenario_v1
from .engine import LEGACY_THRESHOLD, LEGACY_VERSION, MODEL_VERSION, RULE_FINGERPRINT, RULES, THRESHOLD, Observation, analyze

SECONDS = 60
SPLITS = {
    "dev": {"variant": "base", "seeds": range(1000, 1020), "purpose": "Rule development; tuned on these sessions."},
    "test": {"variant": "base", "seeds": range(5000, 5030), "purpose": "Locked seeds, same generator; run after preregistration."},
    "shift": {"variant": "shift", "seeds": range(9000, 9030),
              "purpose": "Held-out generator variant (bitrate, GOP, jitter, loss, confounder behavior); never used for tuning."},
}
DISCLAIMER = ("Synthetic generator behavior only. These figures are not real-world camera detection accuracy "
              "and carry no physical-device evidence.")
ABSTAIN = ("insufficient", "insufficient_direction", "no_observation")


def metrics(rows, model):
    m = dict(tp=0, fp=0, tn=0, fn=0)
    abstained = 0
    for r in rows:
        status = r[model]["status"]
        predicted = status == "candidate"
        abstained += status in ABSTAIN
        m[("tp" if predicted else "fn") if r["camera_label"] else ("fp" if predicted else "tn")] += 1
    tp, fp, tn, fn = (m[k] for k in ("tp", "fp", "tn", "fn"))
    n = len(rows)
    return {"confusion_matrix": m,
            "accuracy": (tp + tn) / n if n else None,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "false_positive_rate": fp / (fp + tn) if fp + tn else None,
            "abstention_rate": abstained / n if n else None}


def per_profile(rows, model):
    out = {}
    for r in rows:
        p = out.setdefault(r["profile"], {"camera_label": r["camera_label"], "sessions": 0, "tp": 0, "fp": 0, "tn": 0,
                                          "fn": 0, "abstained": 0})
        p["sessions"] += 1
        predicted = r[model]["status"] == "candidate"
        p[("tp" if predicted else "fn") if r["camera_label"] else ("fp" if predicted else "tn")] += 1
        p["abstained"] += r[model]["status"] in ABSTAIN
    return out


def result(device, version):
    if device is None:
        return {"status": "no_observation", "score": None}
    d = device if version == MODEL_VERSION else device["comparison"][LEGACY_VERSION]
    return {"status": d["status"], "score": d["score"]}


def session_rows(split, strip_direction=False):
    spec = SPLITS[split]
    rows = []
    for profile in PROFILES:
        for seed in spec["seeds"]:
            items = scenario(profile, seed, SECONDS, variant=spec["variant"])
            if strip_direction:
                items = [Observation(p.timestamp, p.source, p.size, p.rssi) for p in items if p.direction != "rx"]
            report = analyze(items, "synthetic_evaluation", window=(0, SECONDS))
            device = report["devices"][0] if report["devices"] else None
            rows.append({"split": split, "profile": profile, "seed": seed, "camera_label": profile in CAMERA_PROFILES,
                         MODEL_VERSION: result(device, MODEL_VERSION), LEGACY_VERSION: result(device, LEGACY_VERSION),
                         "features": None if device is None else {k: device["features"][k] for k in (
                             "uplink_ratio", "periodicity_score", "period_s", "burst_interval_cv",
                             "size_bimodality", "session_shape", "active_ratio")}})
    return rows


def summarize(rows):
    return {model: {**metrics(rows, model), "per_profile": per_profile(rows, model)}
            for model in (MODEL_VERSION, LEGACY_VERSION)}


def evaluate_v1():
    """Reproduce the phase 1 evaluation: frozen generator, seeds 100–111, rules-0.1."""
    rows = []
    for profile in LEGACY_PROFILES:
        for seed in range(100, 112):
            report = analyze(scenario_v1(profile, seed), "synthetic_evaluation")
            device = report["devices"][0] if report["devices"] else None
            rows.append({"profile": profile, "camera_label": profile.startswith("camera_"),
                         LEGACY_VERSION: result(device, LEGACY_VERSION)})
    return {"generator": "scenario_v1 (phase 1, frozen)", "seeds": "100–111", "sessions": len(rows),
            "metrics": metrics(rows, LEGACY_VERSION)}


def evaluate(splits=tuple(SPLITS)):
    unknown = set(splits) - set(SPLITS)
    if unknown:
        raise ValueError(f"Unknown split: {', '.join(sorted(unknown))}")
    rows = {split: session_rows(split) for split in splits}
    out = {"schema_version": 2, "provenance": "synthetic_evaluation", "disclaimer": DISCLAIMER,
           "physical_devices": 0, "model_version": MODEL_VERSION, "comparison_models": [LEGACY_VERSION],
           "rule_fingerprint": RULE_FINGERPRINT, "rules": RULES,
           "thresholds": {MODEL_VERSION: THRESHOLD, LEGACY_VERSION: LEGACY_THRESHOLD},
           "session_seconds": SECONDS, "profiles": list(PROFILES), "camera_profiles": list(CAMERA_PROFILES),
           "splits": {split: {"variant": SPLITS[split]["variant"],
                              "seeds": f"{SPLITS[split]['seeds'].start}–{SPLITS[split]['seeds'].stop - 1}",
                              "purpose": SPLITS[split]["purpose"], "sessions": len(rows[split]),
                              **summarize(rows[split])} for split in splits},
           "interpretation": ("Abstentions count as non-candidate in the binary matrix and are reported as an abstention "
                              "rate. live_stream_upload is labeled non-camera and is camera-like by construction; it is "
                              "an expected false positive. Trials from one generator are correlated; no confidence "
                              "interval is claimed. " + DISCLAIMER)}
    if "test" in splits:
        stripped = session_rows("test", strip_direction=True)
        out["visibility_ablation"] = {
            "description": "Locked test sessions with receive frames removed and direction set to unknown, as in a "
                           "transmit-only capture. rules-0.2 must abstain instead of scoring.",
            **summarize(stripped)}
        out["legacy_reproduction"] = evaluate_v1()
    out["rows"] = [r for split in splits for r in rows[split]]
    return out
