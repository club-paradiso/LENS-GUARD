# rules-0.2 preregistration

Registered 2026-10-27 (Asia/Seoul), before the locked `test` and held-out `shift` splits were run. This file is committed first; the evaluation that uses those splits is committed afterwards. Synthetic figures here and in `evaluation.json` describe generator behavior, **not real-world camera detection accuracy**.

Rule fingerprint: `1e16c3418576a8d0` (first 16 hex digits of SHA-256 over `engine.RULES` serialized with sorted keys). `tests/test_direction.py` fails if the rules change without this file changing.

## Frozen rule

Gate: at least 100 frames (both directions) and a 10-second capture window, otherwise `insufficient`. Without transmit/receive direction for every frame the uplink share is not computed and the status is `insufficient_direction` with a null score; nothing is filled with zero.

Features use the allowlisted source's transmitted frames unless stated:

| Part | Max | Definition | Full points / zero points |
|---|---:|---|---|
| Uplink dominance | 30 | tx bytes ÷ (tx + rx bytes) | ≥ 0.85 / ≤ 0.55, linear between |
| Periodic bursts | 25 | Max autocorrelation, lags 0.5–8.0 s, of the 100 ms burst-residual series | ≥ 0.50 / ≤ 0.15 |
| Burst regularity | 15 | CV of intervals between burst onsets; needs ≥ 3 intervals, else 0 | CV ≤ 0.2 / CV ≥ 0.8 |
| Packet size mix | 10 | 2 × min(share < 600 B, share ≥ 1000 B) | ≥ 0.40 / ≤ 0.05 |
| Sustained presence | 10 | Share of 1-second bins with tx traffic | proportional |
| Session shape | 10 | Active seconds grouped with ≤ 2 s gaps: continuous (≥ 90% active) / intermittent / single block | 10 / 5 / 0 |

Burst residual: a 100 ms bin is kept when it exceeds the median of non-empty bins within ±1 s by more than max(4 × MAD, 0.5 × median); other bins become 0. This removes frame-rate aliasing (15 fps alternating one and two frames per bin) so that only large bursts, such as key frames, form a period. The reported period is the smallest lag within 90% of the peak.

**Threshold: score ≥ 55 → `candidate`**, otherwise `low_evidence`. A candidate is a lead for review, never a confirmed camera.

rules-0.1 is unchanged (threshold 70) and is recomputed on transmit-side frames using its original window, for comparison only.

## Splits

| Split | Generator | Seeds | Use |
|---|---|---|---|
| dev | base | 1000–1019 (20 × 9 profiles = 180) | Tuning. All numbers below. |
| test | base | 5000–5029 (270) | Locked. Run once after this commit. |
| shift | shift variant | 9000–9029 (270) | Held out. Generator changes listed in EXPERIMENTS.md. Never used for tuning. |

Camera labels: `camera_stream`, `camera_low_rate`, `camera_motion`. Non-camera: `video_call`, `live_stream_upload`, `cloud_backup`, `web_browsing`, `iot_sensor`, `idle`. Abstentions count as non-candidate in the binary matrix and are also reported as an abstention rate.

## Tuning history on dev (only dev was used)

| Threshold | TP | FP | TN | FN | Note |
|---:|---:|---:|---:|---:|---|
| 65 (initial) | 58 | 19 | 101 | 2 | FN: 2 camera_motion. FP: 19 live_stream_upload. |
| **55 (frozen)** | 60 | 20 | 100 | 0 | FP: 20 live_stream_upload. |

Dev scores for the change: highest non-camera other than live streams 46.5 (video_call), lowest camera 61.4 (camera_motion); 55 sits between them. No feature definition, weight or ramp was changed after the first dev run. rules-0.1 on dev: TP 59, FP 60, TN 60, FN 1.

The dev separation is wide because the generator encodes the assumed differences (direction symmetry of calls, finite non-periodic backups). It is not evidence that those assumptions hold for real devices.

## Predictions written before running test and shift

1. test: close to dev. live_stream_upload stays a false positive in nearly every session (camera-like by construction).
2. test: rules-0.2 false positives on video_call and cloud_backup far below rules-0.1.
3. shift, expected rules-0.2 failures:
   - camera_stream with 10-second GOP lies beyond the 8-second lag range, and lower I/P ratio with pacing weakens bursts → some misses.
   - cloud_backup with a one-second token bucket is periodic and uplink dominant → false positives likely.
   - iot_sensor with one-second telemetry passes the 100-frame gate and is periodic → false positives possible.
   - video_call presenter mode (uplink share 0.7–0.9, key frames every 3–5 s) → false positives likely.
   - camera_low_rate at 1–3 fps → periodicity and regularity weaken → misses possible.
4. visibility ablation (test sessions without direction): rules-0.2 abstains on every session that passes the frame gate.

## Commitment

Rules and thresholds are not changed after viewing test or shift. Any later change becomes a new version (rules-0.3) with these results retained and the change described here.
