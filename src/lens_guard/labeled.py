"""Metrics for user-labeled captures of owned or explicitly authorized devices.

Labels, ownership and collection method are the user's declarations. This
module checks their form, not their truth, and never reports file paths or MACs.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import secrets

from .engine import LEGACY_VERSION, MODEL_VERSION, pseudonym
from .evaluation import metrics, per_profile, result
from .pcap import MAX_BYTES, MAC, analyze_capture

PROVENANCE = "user_declared_authorized_capture"
CAMERA_LABELS = {"camera_stream", "camera_low_rate", "camera_motion", "camera_other"}
OTHER_LABELS = {"video_call", "live_stream_upload", "cloud_backup", "web_browsing", "media_streaming",
                "iot_sensor", "idle", "other_non_camera"}
METHODS = {"own_host_tcpdump", "owned_ap_port_mirror", "owned_network_monitor_mode", "other_declared"}
AUTHORITY = {"owned", "explicit_permission"}
CAPTURE_KEYS = {"file", "devices", "method", "authority", "authorization_statement", "captured_at", "notes"}
MAX_CAPTURES = 200


def fail(where, message):
    raise ValueError(f"{where}: {message}")


def load_manifest(path):
    path = Path(path)
    if path.suffix != ".json" or not path.is_file():
        raise ValueError("Manifest must be an existing .json file.")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Manifest is not valid UTF-8 JSON.") from exc
    if not isinstance(manifest, dict) or set(manifest) - {"schema_version", "collector_statement", "captures"}:
        raise ValueError("Manifest allows only schema_version, collector_statement and captures.")
    if manifest.get("schema_version") != 1:
        raise ValueError("Manifest schema_version must be 1.")
    if not isinstance(manifest.get("collector_statement"), str) or len(manifest["collector_statement"].strip()) < 20:
        raise ValueError("collector_statement must describe ownership or permission (at least 20 characters).")
    captures = manifest.get("captures")
    if not isinstance(captures, list) or not 1 <= len(captures) <= MAX_CAPTURES:
        raise ValueError(f"captures must list 1–{MAX_CAPTURES} entries.")
    base = path.resolve().parent
    return [validate_capture(c, i, base) for i, c in enumerate(captures)]


def validate_capture(entry, index, base):
    where = f"captures[{index}]"
    if not isinstance(entry, dict):
        fail(where, "must be an object.")
    unknown = set(entry) - CAPTURE_KEYS
    if unknown:
        fail(where, f"unknown field(s): {', '.join(sorted(unknown))}.")
    name = entry.get("file")
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        fail(where, "file must be a path relative to the manifest.")
    file = (base / name).resolve()
    if not file.is_relative_to(base):
        fail(where, "file must stay inside the manifest's directory.")
    if file.suffix not in (".pcap", ".pcapng", ".cap") or not file.is_file():
        fail(where, "file must be an existing .pcap, .pcapng or .cap file.")
    if file.stat().st_size > MAX_BYTES:
        fail(where, "file exceeds 32 MiB.")
    devices = entry.get("devices")
    if not isinstance(devices, list) or not 1 <= len(devices) <= 64:
        fail(where, "devices must list 1–64 labeled devices.")
    seen = set()
    for j, device in enumerate(devices):
        if not isinstance(device, dict) or set(device) != {"mac", "label"}:
            fail(f"{where}.devices[{j}]", "needs exactly mac and label.")
        mac = device["mac"].strip().lower() if isinstance(device["mac"], str) else ""
        if not MAC.fullmatch(mac) or int(mac[:2], 16) & 1:
            fail(f"{where}.devices[{j}]", "mac must be a unicast address like 02:00:00:00:00:01.")
        if mac in seen:
            fail(f"{where}.devices[{j}]", "duplicate mac.")
        if device["label"] not in CAMERA_LABELS | OTHER_LABELS:
            fail(f"{where}.devices[{j}]", f"label must be one of {', '.join(sorted(CAMERA_LABELS | OTHER_LABELS))}.")
        seen.add(mac)
    if entry.get("method") not in METHODS:
        fail(where, f"method must be one of {', '.join(sorted(METHODS))}.")
    if entry.get("authority") not in AUTHORITY:
        fail(where, "authority must be owned or explicit_permission.")
    statement = entry.get("authorization_statement")
    if not isinstance(statement, str) or len(statement.strip()) < 10:
        fail(where, "authorization_statement is required.")
    try:
        captured = datetime.fromisoformat(entry.get("captured_at", ""))
    except (TypeError, ValueError):
        fail(where, "captured_at must be an ISO 8601 time with a UTC offset.")
    if captured.tzinfo is None or captured > datetime.now(timezone.utc):
        fail(where, "captured_at must include a UTC offset and not be in the future.")
    return {"file": file, "devices": [{"mac": d["mac"].strip().lower(), "label": d["label"]} for d in devices],
            "method": entry["method"], "authority": entry["authority"]}


def evaluate_labeled(manifest_path):
    captures = load_manifest(manifest_path)
    rows = []
    for index, capture in enumerate(captures):
        salt = secrets.token_bytes(32)
        data = capture["file"].read_bytes()
        report = analyze_capture(data, [d["mac"] for d in capture["devices"]], PROVENANCE, salt=salt)
        found = {d["id"]: d for d in report["devices"]}
        for device in capture["devices"]:
            match = found.get(pseudonym(salt, device["mac"]))
            rows.append({"capture": index, "device": pseudonym(salt, device["mac"]), "profile": device["label"],
                         "camera_label": device["label"] in CAMERA_LABELS, "method": capture["method"],
                         MODEL_VERSION: result(match, MODEL_VERSION), LEGACY_VERSION: result(match, LEGACY_VERSION),
                         "abstain_reasons": match["abstain_reasons"] if match else ["no_observation"],
                         "visibility": report["diagnostics"].get("visibility")})
    return {"schema_version": 1, "provenance": PROVENANCE, "authenticity": "not_verified_by_program",
            "notice": ("Labels, ownership, permission and collection method are user declarations. LENS-GUARD checks "
                       "their format only. Metrics describe these captures, not general detection accuracy."),
            "captures": len(captures), "labeled_devices": len(rows),
            "camera_devices": sum(r["camera_label"] for r in rows),
            **{model: {**metrics(rows, model), "per_label": per_profile(rows, model)}
               for model in (MODEL_VERSION, LEGACY_VERSION)},
            "rows": rows}
