# LENS-GUARD repository policy

This is a research prototype. Never label an experimental candidate as a confirmed camera.
Keep synthetic, user-declared capture, and unverified provenance explicit in UI and exports.
Never commit captures, hardware identifiers, payloads, credentials, or third-party datasets.
Do not start wireless collection automatically. Keep hardware checks separate from analysis.
Only analyze authorized device allowlists. No decryption, probing, or authentication bypass.

Verification before handoff:
```
.venv/bin/python -m pytest -q
.venv/bin/python -m lens_guard evaluate --output docs/evaluation.json
cd web && npm ci && npm run build && npm run test:e2e
```
UI strings are English. Lint Korean documentation using the shared workspace policy.
