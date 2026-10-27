"""Seeded simulations, explicitly not measurements from physical devices.

Each profile has its own parameters. A parameter is marked [S] when a public
source supports it (see docs/EXPERIMENTS.md) and [A] when it is our assumption.
The `shift` variant changes parameters for a held-out set that was never used
to tune rules-0.2. Generator numbers describe the generator, not real devices.
"""

import math
import random
from .engine import Observation, analyze

CAMERA_PROFILES = ("camera_stream", "camera_low_rate", "camera_motion")
CONFOUNDER_PROFILES = ("video_call", "live_stream_upload", "cloud_backup", "web_browsing", "iot_sensor", "idle")
PROFILES = CAMERA_PROFILES + CONFOUNDER_PROFILES
VARIANTS = ("base", "shift")
MTU_FRAME = 1514  # Ethernet frame carrying a 1500-byte IP packet
ACK_FRAME = 66  # TCP ACK with timestamp option [A]
HEADER = 54  # Ethernet + IPv4 + TCP/UDP-RTP headers, rounded [A]


class Trace:
    """Collects observations for one source inside a [0, seconds) window."""

    def __init__(self, rng, seconds, source, *, loss=0.0, jitter=0.0):
        self.rng, self.seconds, self.source = rng, seconds, source
        self.loss, self.jitter = loss, jitter
        self.items = []

    def frame(self, t, size, direction):
        if self.jitter:
            t += self.rng.random() * self.jitter
        if 0 <= t < self.seconds and self.rng.random() >= self.loss:
            self.items.append(Observation(t, self.source, int(size), -50 + self.rng.randint(-5, 5), direction))

    def message(self, t, nbytes, direction, *, max_frame=MTU_FRAME, spacing=0.0004, ack=False):
        """Split an application message into frames; optionally acknowledge every second frame."""
        payload = max_frame - HEADER
        count = max(1, math.ceil(nbytes / payload))
        for i in range(count):
            size = HEADER + (payload if i < count - 1 else nbytes - payload * (count - 1))
            self.frame(t + i * spacing, max(60, size), direction)
            if ack and i % 2:
                self.frame(t + i * spacing + 0.01, ACK_FRAME, "rx" if direction == "tx" else "tx")
        return count * spacing


def video(trace, rng, *, fps, kbps, gop_s, ip_ratio, start=0.0, end=None, motion=None, ack=True,
          audio=True, max_frame=MTU_FRAME, pace=0.0, keyframes=None, direction="tx"):
    """Encoder model: fixed frame clock, P frames, and I frames every `gop_s` seconds.

    `keyframes` overrides the fixed GOP with explicit key-frame times (video calls
    request key frames on demand instead). `motion(t)` multiplies P-frame size;
    I frames grow less with motion, so their ratio to P frames shrinks [A].
    """
    end = trace.seconds if end is None else end
    gop = max(1, round(gop_s * fps)) if gop_s else None
    per_frame = kbps * 125 / fps
    p_size = per_frame * (gop or 60) / ((gop or 60) - 1 + ip_ratio)
    pending = sorted(keyframes or [])
    i, t = 0, start
    while t < end:
        m = motion(t) if motion else 1.0
        key = (gop and i % gop == 0) or (pending and t >= pending[0])
        if pending and t >= pending[0]:
            pending.pop(0)
        size = (ip_ratio * p_size * m ** 0.3 if key else p_size * m) * rng.lognormvariate(0, 0.15)
        payload = max_frame - HEADER
        spacing = pace / fps / max(1, math.ceil(size / payload)) if pace else 0.0004
        trace.message(t + rng.gauss(0, 0.001), size, direction, max_frame=max_frame, spacing=spacing, ack=ack)
        i += 1
        t = start + i / fps
    if audio:  # 20 ms audio frames are common for voice codecs [A]
        t = start
        while t < end:
            trace.frame(t, rng.randint(90, 260), direction)
            t += 0.02
    if not ack:  # RTCP-style receiver reports once per second [A]
        t = start + rng.random()
        while t < end:
            trace.frame(t, rng.randint(80, 140), "rx" if direction == "tx" else "tx")
            t += 1.0


def motion_episodes(rng, seconds, count, length, gain):
    spans = []
    for _ in range(rng.randint(*count)):
        a = rng.uniform(0, seconds)
        spans.append((a, a + rng.uniform(*length), rng.uniform(*gain)))
    return lambda t: max([g for a, b, g in spans if a <= t < b], default=1.0)


def scenario(profile, seed=42, seconds=60, source="02:00:00:00:00:01", variant="base"):
    if variant not in VARIANTS:
        raise ValueError("Unknown simulation variant.")
    rng = random.Random(f"{variant}:{profile}:{seed}")
    shift = variant == "shift"
    # Shift: Wi-Fi contention jitter and missed frames in the capture [A].
    trace = Trace(rng, seconds, source, loss=rng.uniform(0.01, 0.05) if shift else 0.0,
                  jitter=rng.uniform(0.005, 0.03) if shift else 0.0)
    if profile == "camera_stream":
        # Rate: CamLoPA reports 35–130 packets/s and 369–1050 B mean length [S] ≈ 0.1–1.1 Mbps.
        # fps, GOP and I/P ratio are not given by the papers [A].
        video(trace, rng, fps=rng.choice((10, 12, 30)) if shift else rng.choice((15, 20, 25)),
              kbps=rng.uniform(1500, 4000) if shift else rng.uniform(300, 1100),
              gop_s=rng.choice((5, 6, 8, 10)) if shift else rng.choice((1, 2, 2, 4)),
              ip_ratio=rng.uniform(2, 4) if shift else rng.uniform(3, 8),
              ack=rng.random() < 0.7, audio=rng.random() < 0.7, pace=rng.uniform(0.2, 0.6) if shift else 0.0)
    elif profile == "camera_low_rate":
        # SCamF Table 1 minimum camera volume 5.2 kbps, average 52.5 kbps [S].
        video(trace, rng, fps=rng.choice((1, 2, 3)) if shift else rng.choice((5, 8, 10)),
              kbps=rng.uniform(30, 80) if shift else rng.uniform(60, 250),
              gop_s=rng.choice((3, 6, 10)) if shift else rng.choice((2, 4, 5)),
              ip_ratio=rng.uniform(2, 4) if shift else rng.uniform(3, 6), audio=False)
    elif profile == "camera_motion":
        # Motion raises inter-frame size (SCamF §4.3, CamLoPA §IV-B) [S]; magnitudes [A].
        video(trace, rng, fps=rng.choice((15, 20, 25)), kbps=rng.uniform(100, 300),
              gop_s=rng.choice((2, 4, 6)) if shift else rng.choice((1, 2, 4)),
              ip_ratio=rng.uniform(2, 4) if shift else rng.uniform(3, 6),
              motion=motion_episodes(rng, seconds, (2, 5) if shift else (1, 4), (5, 20) if shift else (5, 15),
                                     (6, 10) if shift else (3, 6)), audio=rng.random() < 0.5)
    elif profile == "live_stream_upload":
        # A broadcaster encoder is a camera-like stream by construction: a known, unresolved confounder [A].
        video(trace, rng, fps=rng.choice((30, 60)), kbps=rng.uniform(1500, 3000),
              gop_s=4 if shift else 2, ip_ratio=rng.uniform(3, 6), audio=True)
    elif profile == "video_call":
        # Two-way media: the remote party's stream arrives as rx [A]. Key frames on demand
        # (picture-loss requests) instead of a fixed GOP; RTP packets capped near 1200 B [A].
        up = rng.uniform(500, 1500)
        down = up * (rng.uniform(0.1, 0.4) if shift else rng.uniform(0.7, 1.4))
        for direction, kbps in (("tx", up), ("rx", down)):
            mean_gap = rng.uniform(3, 5) if shift else rng.uniform(8, 30)
            keys, t = [0.0], 0.0
            while t < seconds:
                t += rng.uniform(mean_gap * 0.9, mean_gap * 1.1) if shift else rng.expovariate(1 / mean_gap)
                keys.append(t)
            video(trace, rng, fps=rng.choice((24, 30)), kbps=kbps, gop_s=None, ip_ratio=rng.uniform(3, 6),
                  ack=False, max_frame=1242, pace=0.4, keyframes=keys, direction=direction)
    elif profile == "cloud_backup":
        # Uplink-saturating TCP transfer of finite length (base) or app rate limit with a
        # one-second token bucket (shift, which makes it periodic) [A]. Mostly full-size
        # frames, like SCamF's download traffic with FU rate near 1 [S].
        rate = rng.uniform(2000, 6000) * 125
        begin = 0 if shift else rng.uniform(0, 10)
        stop = seconds if shift else begin + rng.uniform(15, 40)
        level, t = 1.0, begin
        while t < stop:
            if shift:
                trace.message(t, rate * rng.uniform(0.9, 1.1), "tx", spacing=0.0008, ack=True)
                t += 1.0
                continue
            level = min(1.5, max(0.3, 0.7 * level + 0.3 * (1 + rng.gauss(0, 0.25))))
            if rng.random() < 0.02:
                level *= 0.5
            trace.message(t, rate * 0.1 * level, "tx", spacing=0.1 / max(1, rate * 0.1 * level / 1460), ack=True)
            t += 0.1
    elif profile == "web_browsing":
        # Downlink-heavy page loads (base) or segment-based media streaming every 2–6 s (shift) [A].
        t = rng.uniform(0, 3)
        period = rng.uniform(2, 6)
        while t < seconds:
            for k in range(rng.randint(3, 20) if not shift else 2):
                trace.frame(t + k * 0.02, rng.randint(200, 800), "tx")
            size = rng.uniform(0.3, 1.5) * 1e6 if shift else rng.lognormvariate(math.log(400_000), 1.0)
            trace.message(t + 0.05, size, "rx", spacing=0.0006, ack=True)
            t += period * rng.uniform(0.95, 1.05) if shift else rng.expovariate(1 / rng.uniform(6, 15))
    elif profile == "iot_sensor":
        # Small periodic reports; chattier one-second telemetry in the shift set [A].
        period = 1.0 if shift else rng.uniform(5, 30)
        t = rng.uniform(0, period)
        while t < seconds:
            for k in range(rng.randint(1, 3)):
                trace.frame(t + k * 0.01, rng.randint(300, 600) if shift else rng.randint(120, 400), "tx")
            trace.frame(t + 0.05, ACK_FRAME, "rx")
            t += period
    elif profile == "idle":
        # Sparse discovery and keep-alive frames in both directions [A].
        t = rng.uniform(0, 10)
        while t < seconds:
            trace.frame(t, rng.randint(60, 200), rng.choice(("tx", "rx")))
            t += rng.uniform(2, 6) if shift else rng.uniform(10, 30)
    else:
        raise ValueError("Unknown simulation profile.")
    return sorted(trace.items, key=lambda p: (p.timestamp, p.direction, p.size))


LEGACY_PROFILES = ("camera_stream", "camera_low_rate", "camera_motion", "video_call", "cloud_backup", "web_browsing", "iot_sensor", "idle")


def scenario_v1(profile, seed=42, seconds=60, source="02:00:00:00:00:01"):
    """Phase 1 generator, frozen to reproduce the committed rules-0.1 results.

    It shares one code path for camera_stream and video_call and has no
    direction, so no feature can separate those two profiles.
    """
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


DEMO_PROFILES = ("camera_stream", "video_call", "web_browsing", "camera_motion", "cloud_backup", "iot_sensor")


def demo_report(seed=42, seconds=60):
    items = []
    for i, profile in enumerate(DEMO_PROFILES):
        items.extend(scenario(profile, seed + i, seconds, f"02:00:00:00:00:{i+1:02x}"))
    report = analyze(items, "synthetic_demo", salt=b"lens-guard-demo-only", window=(0, seconds))
    report["simulation"] = {"seed": seed, "profiles": list(DEMO_PROFILES), "physical_devices": 0}
    return report


def write_fixture(path, seconds=60, profile="camera_stream", seed=42, source="02:00:00:00:00:01"):
    from scapy.all import Ether, Raw, PcapWriter
    peer = "02:00:00:00:00:ff"
    # Synthetic zero-filled bytes; no captured communication contents.
    with PcapWriter(str(path), linktype=1, sync=True) as writer:
        for item in scenario(profile, seed, seconds, source):
            src, dst = (source, peer) if item.direction == "tx" else (peer, source)
            p = Ether(src=src, dst=dst, type=0x88B5) / Raw(bytes(item.size - 14))
            p.time = 1700000000 + item.timestamp
            writer.write(p)
