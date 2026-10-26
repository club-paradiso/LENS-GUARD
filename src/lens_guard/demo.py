"""Seeded simulations, explicitly not measurements from physical devices."""

import random
from .engine import Observation, analyze

PROFILES = ("camera_stream", "camera_low_rate", "camera_motion", "video_call", "cloud_backup", "web_browsing", "iot_sensor", "idle")


def scenario(profile, seed=42, seconds=60, source="02:00:00:00:00:01"):
    rng = random.Random(seed)
    rate = rng.randint(30, 75)
    items = []
    for second in range(seconds):
        if profile in ("camera_stream", "video_call"):
            count, size = rate + rng.randint(-5, 5), 1250
        elif profile == "camera_low_rate":
            count, size = rng.randint(3, 8), 650
        elif profile == "camera_motion":
            count, size = (rate if 15 <= second % 40 < 25 else 2), 1200
        elif profile == "cloud_backup":
            count, size = rate * 2, 1450
        elif profile == "web_browsing":
            count, size = (rng.randint(30, 90) if second % 12 < 2 else 1), 900
        elif profile == "iot_sensor":
            count, size = (1 if second % 5 == 0 else 0), 160
        elif profile == "idle":
            count, size = 0, 0
        else:
            raise ValueError("Unknown simulation profile.")
        for i in range(count):
            items.append(Observation(second + (i + rng.random() * .5) / max(count, 1), source,
                                     max(60, size + rng.randint(-100, 100)), -50 + rng.randint(-5, 5)))
    return items


def demo_report(seed=42, seconds=60):
    profiles = ("camera_stream", "video_call", "web_browsing", "camera_motion", "iot_sensor")
    items = []
    for i, profile in enumerate(profiles):
        items.extend(scenario(profile, seed + i, seconds, f"02:00:00:00:00:{i+1:02x}"))
    report = analyze(items, "synthetic_demo", salt=b"lens-guard-demo-only")
    report["simulation"] = {"seed": seed, "profiles": list(profiles), "physical_devices": 0}
    return report


def write_fixture(path, seconds=60):
    from scapy.all import Ether, Raw, PcapWriter
    # Synthetic zero-filled bytes; no captured communication contents.
    with PcapWriter(str(path), linktype=1, sync=True) as writer:
        for item in scenario("camera_stream", seconds=seconds):
            p = Ether(src=item.source, dst="02:00:00:00:00:ff", type=0x88B5) / Raw(bytes(item.size - 14))
            p.time = 1700000000 + item.timestamp
            writer.write(p)
