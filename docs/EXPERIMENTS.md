# Evaluation protocol

Run `.venv/bin/python -m lens_guard evaluate --output docs/evaluation.json` to regenerate the committed synthetic evaluation. The rule is fixed before this run; there is no fitting or training set. Seeds 100–111 are separate from the interactive demo seed 42.

Eight profiles × 12 seeds produce 96 sessions: steady video-like camera, low-rate camera, motion-only camera, video call, cloud backup, web browsing, sensor and idle. Each non-idle session lasts up to 60 simulated seconds. Empty/insufficient outcomes count as non-candidate for the binary confusion matrix and retain their own status in row-level data. A non-candidate does not mean a safe room.

Video calls deliberately share the camera stream generator: their indistinguishable metadata must produce false positives. Backups add sustained large-packet traffic. Low-rate and motion-only camera profiles deliberately expose the baseline's false negatives. These are correlated synthetic trials, not independent real camera observations; a high or low score measures behavior of this generator and rule, not deployable detection accuracy. No real-world confidence interval or measured physical accuracy is claimed.

A future authorized study should register thresholds, device labels and splits before testing. Separate train/development/test by physical device, model and session; do not randomly split overlapping windows from the same capture. Include multiple codecs, resolutions, night/static/motion scenes, local recording, idle cameras, mesh/AP topology, distance, channels, video calls, cloud sync, gaming and background updates. Report precision, recall, false-positive rate, abstention rate, per-device confusion, visibility losses and collection duration. Retain a device-held-out test set and report uncertainty at the device/session level.

No real capture dataset was supplied or collected for this delivery. That prevents a physical detection accuracy measurement; synthetic evaluation does not resolve this limitation.
