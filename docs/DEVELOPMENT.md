# Development

Create `.venv`, install `requirements-lock.txt`, then install this checkout with `.venv/bin/pip install --no-deps --no-build-isolation -e .`. The checked-in lock includes test tools and the PDF reader used during research. `web/package-lock.json` fixes frontend versions. Edit `web/src`, never `web/dist`; build output is ignored.

Production-style local run: build with `npm run build --prefix web`, then `.venv/bin/python -m lens_guard serve`. The backend serves the local bundle on port 8765. Do not bind the server to a public address. In development, run the backend and `npm run dev --prefix web`; Vite proxies `/api` to loopback.

Source modules: `pcap.py` validates containers and extracts bounded header metadata; `engine.py` aggregates/scorers; `demo.py` generates examples and synthetic PCAP; `evaluation.py` produces scenario-level confusion tables; `api.py` exposes local HTTP routes; `hardware.py` reports tools without collecting traffic. Frontend code is in `web/src/main.tsx` and `web/src/style.css`.

Run repository verification from AGENTS.md. Browser tests require `npx playwright install chromium` from `web` first and use the local backend. Test-generated captures and downloads are under ignored work/test directories. No raw capture belongs in version control. Development does not need a cloud account or API key.

To update dependencies, change the direct requirements/package manifest, resolve and regenerate the corresponding lockfiles with pip/npm, then run the verification. To regenerate the Python environment lock: `.venv/bin/pip freeze --exclude-editable > requirements-lock.txt` (use a task-local venv, never the system environment).

Next research milestone: acquire a small labeled, authorized physical capture corpus, evaluate the existing frozen rule first, report error cases, then introduce independently validated features or a classifier. Keep device-level held-out splits and provenance. Do not optimize the generator to improve headline accuracy.
