# Development

Create `.venv`, install `requirements-lock.txt`, then install this checkout with `.venv/bin/pip install --no-deps --no-build-isolation -e .`. The checked-in lock includes test tools and the PDF reader used during research. `web/package-lock.json` fixes frontend versions. Edit `web/src`, never `web/dist`; build output is ignored.

Production-style local run: build with `npm run build --prefix web`, then `.venv/bin/python -m lens_guard serve`. The backend serves the local bundle on port 8765. Do not bind the server to a public address. In development, run the backend and `npm run dev --prefix web`; Vite proxies `/api` to loopback.

Source modules: `pcap.py` validates containers and extracts bounded header metadata; `engine.py` aggregates/scorers; `demo.py` generates examples and synthetic PCAP; `evaluation.py` produces scenario-level confusion tables; `api.py` exposes local HTTP routes; `hardware.py` reports tools without collecting traffic. Frontend code is in `web/src/main.tsx` and `web/src/style.css`.

Run repository verification from AGENTS.md. On macOS the venv's editable-install `.pth` file can receive the `hidden` file flag (observed for this checkout under `~/Documents`); Python 3.13+ then skips it and `python -m lens_guard` fails with "No module named lens_guard". Check with `ls -lO .venv/lib/python3.*/site-packages/*.pth` and clear it with `chflags nohidden` on those files. Playwright sets `PYTHONPATH` itself.

Evaluation discipline: tune rules only with `lens_guard evaluate --split dev`. The locked `test` and held-out `shift` splits are for preregistered rules (docs/PREREGISTRATION.md). Changing `engine.RULES` changes its fingerprint and fails `test_preregistration_matches_current_rules` until a new version is registered. CI regenerates the evaluation and compares confusion matrices with `scripts/compare-evaluation.py`. Browser tests require `npx playwright install chromium` from `web` first and use the local backend. Test-generated captures and downloads are under ignored work/test directories. No raw capture belongs in version control. Development does not need a cloud account or API key.

To update dependencies, change the direct requirements/package manifest, resolve and regenerate the corresponding lockfiles with pip/npm, then run the verification. To regenerate the Python environment lock: `.venv/bin/pip freeze --exclude-editable > requirements-lock.txt` (use a task-local venv, never the system environment).

Next research milestone: collect owned-device labeled captures (docs/OWNED_DEVICE_PROTOCOL.ko.md), evaluate the frozen rules-0.2 first with `evaluate-labeled`, report error cases, then introduce independently validated features or a classifier. Keep device-level held-out splits and provenance. Do not optimize the generator to improve headline accuracy.
