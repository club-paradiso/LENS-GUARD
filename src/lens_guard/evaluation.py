"""Fixed-seed synthetic stress suite, not real-world accuracy validation."""

from .demo import PROFILES, scenario
from .engine import analyze, MODEL_VERSION, THRESHOLD


def evaluate():
    rows = []
    matrix = dict(tp=0, fp=0, tn=0, fn=0)
    for profile in PROFILES:
        for seed in range(100, 112):
            report = analyze(scenario(profile, seed), "synthetic_evaluation")
            device = report["devices"][0] if report["devices"] else None
            predicted = bool(device and device["status"] == "candidate")
            truth = profile.startswith("camera_")
            outcome = ("tp" if predicted else "fn") if truth else ("fp" if predicted else "tn")
            matrix[outcome] += 1
            rows.append({"profile": profile, "seed": seed, "camera_label": truth,
                         "predicted_candidate": predicted, "status": device["status"] if device else "no_observation",
                         "score": device["score"] if device else None, "outcome": outcome})
    tp, fp, tn, fn = (matrix[k] for k in ("tp", "fp", "tn", "fn"))
    return {"provenance": "synthetic_evaluation", "model_version": MODEL_VERSION,
            "threshold": THRESHOLD, "sessions": len(rows), "physical_devices": 0,
            "seeds": "100–111; demo uses 42; no training or fitted parameters",
            "confusion_matrix": matrix,
            "metrics": {"accuracy": (tp + tn) / len(rows), "precision": tp / (tp + fp) if tp + fp else None,
                        "recall": tp / (tp + fn) if tp + fn else None,
                        "false_positive_rate": fp / (fp + tn) if fp + tn else None},
            "per_profile": {p: {"sessions": 12, "candidates": sum(r["predicted_candidate"] for r in rows if r["profile"] == p)} for p in PROFILES},
            "interpretation": "Synthetic scenario coverage only. Not an estimate of physical camera detection accuracy. Abstentions count as non-candidate; inspect status separately. Similar generators create correlated trials, so no statistical confidence interval is claimed.",
            "rows": rows}
