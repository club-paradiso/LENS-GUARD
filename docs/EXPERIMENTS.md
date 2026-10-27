# Evaluation protocol (phase 2)

**Every number in this file is synthetic generator behavior, not real-world camera detection accuracy.** No physical device was measured. Real labeled captures: 0.

```sh
.venv/bin/python -m lens_guard evaluate --split dev                     # tuning only
.venv/bin/python -m lens_guard evaluate --output docs/evaluation.json   # all splits (schema_version 2)
```

## Why phase 1 numbers could not separate calls from cameras

Phase 1 generated `video_call` and `camera_stream` with the same code path (same rate, same 1,250-byte size) and without direction. No feature could separate them, so its 50% precision was a property of the generator. That generator is frozen as `scenario_v1` only to reproduce the phase 1 rules-0.1 results; `tests/test_direction.py` checks all 96 committed phase 1 scores.

## Design against circular validation

1. Profiles have independent parameters. Each is marked **[S]** when a public source supports it and **[A]** when it is our assumption (also in `demo.py` comments).
2. Three splits with disjoint seeds: `dev` 1000–1019 (tuning), locked `test` 5000–5029 (same generator), held-out `shift` 9000–9029 (changed parameters, never used for tuning). 9 profiles × seeds = 180 / 270 / 270 sessions of 60 seconds.
3. The rule, threshold and predictions were committed in [PREREGISTRATION.md](PREREGISTRATION.md) (commit `b6d8149`) before test and shift were run. The first full evaluation was committed next (`b694457`). A fingerprint test ties the rules to that file.
4. `live_stream_upload` is labeled non-camera but is a camera-like encoder stream by construction. It measures an unresolved confounder; it was not tuned away.
5. A visibility ablation removes receive frames and direction from the locked test sessions to show the abstention path.

The dev separation is wide because the generator encodes our hypotheses. Test repeats the same generator with new seeds, so it checks overfitting to seeds, not validity. Only shift and future real captures challenge the hypotheses.

## Generator parameters

| Profile | Base parameters | Shift changes | Basis |
|---|---|---|---|
| camera_stream | 15/20/25 fps; 0.3–1.1 Mbps; GOP 1, 2 or 4 s; I/P size 3–8; TCP ACK every 2nd frame in 70%; audio 50 fps in 70% | 10/12/30 fps; 1.5–4 Mbps; GOP 5–10 s; I/P 2–4; frames paced over 20–60% of the interval | Rate from CamLoPA 35–130 packets/s, 369–1,050 B mean [S]; fps, GOP, I/P ratio [A] |
| camera_low_rate | 5/8/10 fps; 60–250 kbps; GOP 2–5 s; I/P 3–6 | 1–3 fps; 30–80 kbps; GOP 3–10 s; I/P 2–4 | SCamF Table 1 camera minimum volume 5.2 kbps, mean 52.5 kbps [S]; others [A] |
| camera_motion | 15–25 fps; 100–300 kbps static; 1–4 motion episodes of 5–15 s at 3–6× P-frame size; I frames scale with motion^0.3 | 2–5 episodes of 5–20 s at 6–10×; GOP 2–6 s; I/P 2–4 | Motion raises inter-frame size (SCamF §4.3, CamLoPA §IV-B) [S]; magnitudes [A] |
| live_stream_upload | 30/60 fps; 1.5–3 Mbps; GOP 2 s; audio | GOP 4 s | [A] |
| video_call | Uplink 0.5–1.5 Mbps; downlink 0.7–1.4× uplink; 24/30 fps; key frames on demand, mean interval 8–30 s; RTP frames ≤ 1,242 B; RTCP | Presenter: downlink 0.1–0.4× uplink; key frames every 3–5 s | [A]. None of the three papers studies calls. |
| cloud_backup | 2–6 Mbps TCP, AR(1) throughput noise, random halving; starts 0–10 s, lasts 15–40 s; full-size frames | App rate limit: one burst per second for the whole window | Full-size share near 1 like SCamF's download class [S]; the rest [A] |
| web_browsing | Page loads at mean 6–15 s intervals, log-normal size around 400 kB downlink; small requests | Segment streaming every 2–6 s, 0.3–1.5 MB | [A] |
| iot_sensor | 1–3 frames of 120–400 B every 5–30 s | 1–3 frames of 300–600 B every second | [A] |
| idle | Keep-alive every 10–30 s, both directions | Every 2–6 s | [A] |

All shift sessions also add 1–5% frame loss and 5–30 ms timestamp jitter [A].

## Results

| Split | Model | TP | FP | TN | FN | Accuracy | Precision | Recall | FPR | Abstained |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| dev | rules-0.1 | 59 | 60 | 60 | 1 | 66.1% | 49.6% | 98.3% | 50.0% | 22.2% |
| dev | rules-0.2 | 60 | 20 | 100 | 0 | 88.9% | 75.0% | 100.0% | 16.7% | 22.2% |
| test | rules-0.1 | 90 | 90 | 90 | 0 | 66.7% | 50.0% | 100.0% | 50.0% | 22.6% |
| test | rules-0.2 | 90 | 30 | 150 | 0 | 88.9% | 75.0% | 100.0% | 16.7% | 22.2% |
| shift | rules-0.1 | 88 | 90 | 90 | 2 | 65.9% | 49.4% | 97.8% | 50.0% | 11.5% |
| shift | rules-0.2 | 87 | 77 | 103 | 3 | 70.4% | 53.0% | 96.7% | 42.8% | 11.1% |

Abstentions (`insufficient`, `insufficient_direction`, no observation) count as non-candidate and are also shown as a rate. Sensor and idle sessions with too few frames make up most of it.

Candidates per profile, rules-0.1 → rules-0.2:

| Profile | dev (20) | test (30) | shift (30) |
|---|---|---|---|
| camera_stream | 20 → 20 | 30 → 30 | 30 → 30 |
| camera_low_rate | 19 → 20 | 30 → 30 | 28 → 30 |
| camera_motion | 20 → 20 | 30 → 30 | 30 → 27 |
| video_call | 20 → 0 | 30 → 0 | 30 → **29** |
| live_stream_upload | 20 → 20 | 30 → 30 | 30 → 30 |
| cloud_backup | 20 → 0 | 30 → 0 | 30 → 0 |
| web_browsing | 0 → 0 | 0 → 0 | 0 → 0 |
| iot_sensor | 0 → 0 | 0 → 0 | 0 → **18** |
| idle | 0 → 0 | 0 → 0 | 0 → 0 |

Visibility ablation (locked test sessions without direction): rules-0.2 abstained on all 270 (180 TN, 90 FN in the binary matrix); rules-0.1 gave the same result as on the full test split. Phase 1 reproduction: rules-0.1 on `scenario_v1` seeds 100–111 gives TP 24, FP 24, TN 36, FN 12, identical to phase 1.

## Predictions versus outcome

| Preregistered prediction | Outcome |
|---|---|
| test close to dev; live streams stay false positives | Held: identical rates, live streams 30/30 |
| test: call and backup false positives far below rules-0.1 | Held: 0/30 each, versus 30/30 each |
| shift: long-GOP cameras missed | **Wrong**: 30/30 still candidates. Uplink, presence and shape gave 50 points, and harmonics within 8 s still produced periodicity. |
| shift: rate-limited backup becomes candidate | **Wrong**: 0/30. Every active bin was a full burst, so no bin stood out from its local baseline; the score stayed at 49.8. |
| shift: one-second sensor may become candidate | Held: 18/30 |
| shift: presenter call becomes candidate | Held: 29/30 |
| shift: 1–3 fps cameras may be missed | Not observed: 30/30 candidates |
| ablation: rules-0.2 abstains | Held: 100% abstention |

No rule or threshold was changed after these runs.

## Failure analysis

- **Margin above "continuous upload".** Uplink dominance (30), sustained presence (10) and continuous shape (10) give 50 points to any steady uplink stream. The threshold is 55. Any weak periodicity or a mixed packet size pushes such traffic over: shift sensors scored 49.3–75.3, rate-limited backups 49.8, and the three missed motion cameras 50.7–52.2. The rule therefore depends heavily on whether real confounders are bidirectional, which is an untested assumption.
- **video_call (shift).** In presenter mode the uplink share was 0.69–0.88 and key frames every 3–5 s gave regular bursts (median interval CV 0.07). In these metadata features that is a camera.
- **live_stream_upload.** A broadcaster encoder with a fixed GOP is the same traffic shape as a camera stream. Metadata alone is not expected to separate them.
- **camera_motion (shift).** With 6–10× motion gain the I/P ratio shrinks; key frames stop standing out and periodicity falls (0–0.13 in the misses).
- **iot_sensor (shift).** One-second telemetry passes the 100-frame gate and is uplink-dominant and steady.

## Real labeled data path

`lens-guard evaluate-labeled --manifest <path>` computes the same metrics for user-labeled captures; see [OWNED_DEVICE_PROTOCOL.ko.md](OWNED_DEVICE_PROTOCOL.ko.md). It has been tested only with synthetic manifests. **Real data: not validated.** Mac-only captures can supply non-camera labels (calls, backups, browsing, idle); camera labels require an owned IP camera.

A future physical study should keep device-level held-out splits, preregister before testing, report per-device confusion and visibility losses, and include calls in presenter mode, live streaming, rate-limited sync and chatty IoT telemetry, the confounders the shift set exposed.
