# Architecture and experimental model

The single loopback process serves the built React app and FastAPI endpoints. No external API, cloud storage, model key, analytics, remote font, or subscription is used at runtime. Initial dependency installation uses public package registries.

```
Demo generator ───────────────────────┐
                                     v
PCAP bytes -> container validation -> allowlisted L2 metadata
                                     -> 1-second bins -> rule score -> JSON -> React
```

`Observation` contains timestamp, local source identifier, original frame length, and optional RSSI. Captured bytes are never persisted by the server; packet bodies are not decoded. A supplied file can itself contain sensitive payloads: the original remains the user's responsibility. Filtering is analysis minimization, not retroactive protection against over-broad collection.

Ethernet, raw 802.11 and Radiotap are supported in classic PCAP and timestamped PCAPNG. Classic micro/nanosecond timestamps and byte order are supported. PCAPNG simple packets without timestamps are rejected. Unsupported links fail explicitly. Files are bounded to 32 MiB, 200,000 records, one hour of eligible observations and 64 authorized MACs. Partial records fail instead of silently producing a complete-looking report. Other PCAPNG block variants are not comprehensively validated.

For 802.11, only station-to-distribution-system data and QoS data frames contribute. AP downlink, direct/ad-hoc, WDS, management, control, null-data and retry frames are excluded. Retry exclusion may undercount traffic when the original transmission was missed. Aggregate frames are not split into constituent MSDUs. Original lengths, not payload contents, inform features. RSSI describes reception, never distance. FCS and encapsulation differences can affect byte thresholds.

Ethernet uses the authorized source MAC only. It cannot prove wireless origin; gateways, virtual interfaces and routed captures can aggregate other devices. The count shown is observed sources, not a count of physical cameras.

## Rule score v0.1

There is no trained model. After at least 100 packets and 10 seconds, compute over the full eligible observation window:

- 35 × fraction of one-second bins containing traffic
- 25 × fraction of frames at least 1,000 bytes
- 25 × min(mean bytes/second ÷ 20,000, 1)
- 15 ÷ (1 + coefficient of variation of per-second byte counts)

A score of at least 70 means `candidate`; otherwise `low_evidence`. Short/sparse observations return `insufficient` with a null score. The window is anchored at the first eligible frame; partial final seconds count as a full bin. Thresholds are engineering choices, not published SCamF/Lumos thresholds or calibrated probabilities. The rule prioritizes sustained high-volume streams; motion-only and low-rate cameras can be missed.

A report includes provenance, model version, threshold, feature values, score explanations, parser skip counts and limitations. Per-analysis HMAC pseudonyms prevent raw MAC disclosure and casual cross-report linkage; demo IDs use a public fixed salt for determinism. There is no absolute capture time, IP, SSID, DNS, URL or payload in the report. Pseudonyms are not a formal anonymization guarantee.

## API and UI

- `GET /api/health`: no capture status hidden behind a fake live indicator.
- `GET /api/demo`: deterministic simulated observations, seed and duration bounded.
- `POST /api/analyze`: bounded binary body, authorization assertion and source allowlist in headers. The app never accepts a filesystem path.
- `/`: local production dashboard. Replay animates the completed time series at 4×; scores remain full-window scores. Run simulation requests an expanding 10–60-second simulated window from the Python engine once per second after each response; source counts, scores and features update. Neither mode is live radio collection.

Host and Origin checks prevent ordinary cross-origin requests and DNS rebinding. The service binds to 127.0.0.1. It is a single-user development service, not a hardened multi-user deployment; concurrent large uploads are not globally rate-limited. Do not expose it on a LAN or through a tunnel.
