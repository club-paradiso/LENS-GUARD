# Architecture and experimental model

The single loopback process serves the built React app and FastAPI endpoints. No external API, cloud storage, model key, analytics, remote font, or subscription is used at runtime. Initial dependency installation uses public package registries.

```
Demo generator ───────────────────────┐
                                     v
PCAP bytes -> container validation -> allowlisted L2 metadata + tx/rx direction
          -> 100 ms and 1 s bins -> rules-0.2 score (+ rules-0.1 comparison) -> JSON -> React
Labeled manifest -> same path per capture -> metrics (user-declared provenance)
```

`Observation` contains timestamp, local source identifier, original frame length, optional RSSI and direction (`tx` sent by the allowlisted device, `rx` addressed to it, or unknown). Captured bytes are never persisted by the server; packet bodies are not decoded. A supplied file can itself contain sensitive payloads: the original remains the user's responsibility. Filtering is analysis minimization, not retroactive protection against over-broad collection.

Ethernet, raw 802.11 and Radiotap are supported in classic PCAP and timestamped PCAPNG. Classic micro/nanosecond timestamps and byte order are supported. PCAPNG simple packets without timestamps are rejected. Unsupported links fail explicitly. Files are bounded to 32 MiB, 200,000 records, one hour of eligible observations and 64 authorized MACs. Partial records fail instead of silently producing a complete-looking report. Other PCAPNG block variants are not comprehensively validated.

For 802.11, data and QoS data frames with exactly one of To DS / From DS contribute. Direction is taken from the current hop: an allowlisted transmitter address (addr2; equal to SA in To DS frames) is `tx`, an allowlisted receiver address (addr1; equal to DA in From DS frames) is `rx`. Addresses relayed in addr3 are not counted, so one transfer is not counted twice. Direct/ad-hoc, WDS, management, control, null-data and retry frames are excluded. A monitor capture still misses frames on other channels or out of range, so a low receive count may be a visibility loss. Retry exclusion may undercount traffic when the original transmission was missed. Aggregate frames are not split into constituent MSDUs. Original lengths, not payload contents, inform features. RSSI describes reception, never distance. FCS and encapsulation differences can affect byte thresholds.

Ethernet: an allowlisted source MAC is `tx`, an allowlisted destination MAC is `rx`. If both are allowlisted, the frame counts for both devices. It cannot prove wireless origin; gateways, virtual interfaces and routed captures can aggregate other devices. The count shown is observed sources, not a count of physical cameras.

The analysis window is the capture span, including records discarded by the allowlist, so a transfer that stops before the capture ends is visible as a finite block. Only the duration, not the absolute time, is reported. Capture spans over one hour are rejected.

## Rule score rules-0.2

There is no trained model. Definitions, ramps and the threshold are frozen in [PREREGISTRATION.md](PREREGISTRATION.md); `engine.RULES` holds every number and its fingerprint is tested against that file. Evidence for each feature is in [RESEARCH.md](RESEARCH.md#phase-2-traffic-characteristics-behind-rules-02).

| Part | Max | Feature |
|---|---:|---|
| Uplink dominance | 30 | tx ÷ (tx + rx) bytes |
| Periodic bursts | 25 | Max autocorrelation (lags 0.5–8 s) of the 100 ms burst residual, and its period |
| Burst regularity | 15 | CV of intervals between burst onsets |
| Packet size mix | 10 | 2 × min(share < 600 B, share ≥ 1000 B) |
| Sustained presence | 10 | Share of seconds with tx traffic |
| Session shape | 10 | continuous / intermittent / single block |

The burst residual keeps only 100 ms bins above a local baseline (median of non-empty bins within ±1 s plus max(4 × MAD, 0.5 × median)). Without it, a fixed frame rate aliasing against the bin edges would look periodic. Score ≥ 55 is `candidate`; otherwise `low_evidence`. Fewer than 100 frames or a window under 10 seconds gives `insufficient`. If any frame lacks direction the uplink part is not computed and the status is `insufficient_direction` with a null score; the remaining parts are shown with a partial score out of 70. A device with no receive frames gets an explicit note that a one-sided capture inflates its uplink share.

Each device includes `parts` (points, maximum, measured value, note), `abstain_reasons`, `direction` and `comparison["rules-0.1"]`.

### rules-0.1 (comparison)

Unchanged code and threshold 70: 35 × active-second share + 25 × share of frames ≥ 1,000 B + 25 × min(bytes/s ÷ 20,000, 1) + 15 ÷ (1 + CV of per-second bytes). It is recomputed on frames that are not `rx`, with phase 1's window (first to last such frame), so phase 1 results reproduce exactly. On a new bidirectional capture, a From DS frame sent by an allowlisted AP is now `tx` and enters rules-0.1, which phase 1 excluded.

A report includes provenance, model version, threshold, feature values, score explanations, parser skip counts and limitations. Per-analysis HMAC pseudonyms prevent raw MAC disclosure and casual cross-report linkage; demo IDs use a public fixed salt for determinism. There is no absolute capture time, IP, SSID, DNS, URL or payload in the report. Pseudonyms are not a formal anonymization guarantee.

## API and UI

- `GET /api/health`: no capture status hidden behind a fake live indicator.
- `GET /api/demo`: deterministic simulated observations, seed and duration bounded.
- `GET /api/evaluation`: summary of the committed synthetic evaluation (no per-session rows).
- `POST /api/analyze`: bounded binary body, authorization assertion and source allowlist in headers. The app never accepts a filesystem path.
- `/`: local production dashboard. Replay animates the completed time series at 4×; scores remain full-window scores. Run simulation requests an expanding 10–60-second simulated window from the Python engine once per second after each response; source counts, scores and features update. Neither mode is live radio collection.

Host and Origin checks prevent ordinary cross-origin requests and DNS rebinding. The service binds to 127.0.0.1. It is a single-user development service, not a hardened multi-user deployment; concurrent large uploads are not globally rate-limited. Do not expose it on a LAN or through a tunnel.
