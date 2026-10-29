"""Loopback application; uploaded captures live only in request memory."""

import json
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from .demo import demo_report
from .pcap import MAX_BYTES, analyze_capture

app = FastAPI(title="LENS-GUARD", docs_url=None, redoc_url=None, openapi_url=None)
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "testserver"}
EVALUATION = Path(__file__).resolve().parents[2] / "docs" / "evaluation.json"


@app.middleware("http")
async def local_only(request, call_next):
    if request.url.hostname not in ALLOWED_HOSTS:
        return JSONResponse({"detail": "Loopback host required."}, status_code=403)
    origin = request.headers.get("origin")
    if origin and origin != f"{request.url.scheme}://{request.headers.get('host')}":
        return JSONResponse({"detail": "Same-origin requests only."}, status_code=403)
    if request.method == "POST" and request.headers.get("x-lens-guard") != "local-analysis":
        return JSONResponse({"detail": "Local application header required."}, status_code=403)
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
    return response


@app.get("/api/health")
def health():
    return {"status": "ok", "capture_running": False, "mode": "offline_only"}


@app.get("/api/demo")
def demo(seed: int = 42, seconds: int = 60):
    if not 10 <= seconds <= 120 or not 0 <= seed <= 100000:
        raise HTTPException(422, "Demo requires 10–120 seconds and seed 0–100000.")
    return demo_report(seed, seconds)


@app.get("/api/evaluation")
def evaluation_summary():
    """Committed synthetic evaluation without per-session rows."""
    try:
        data = json.loads(EVALUATION.read_text())
    except (OSError, ValueError) as exc:
        raise HTTPException(404, "No committed evaluation found.") from exc
    keys = ("schema_version", "provenance", "disclaimer", "physical_devices", "model_version", "comparison_models",
            "rule_fingerprint", "thresholds", "session_seconds", "camera_profiles", "splits", "interpretation")
    return {k: data[k] for k in keys if k in data}


@app.post("/api/analyze")
async def analyze(request: Request):
    if request.headers.get("x-authorized") != "yes":
        raise HTTPException(400, "Confirm you are authorized to analyze these devices.")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_BYTES:
            raise HTTPException(413, "Maximum capture size is 32 MiB.")
        data.extend(chunk)
    try:
        return await run_in_threadpool(analyze_capture, bytes(data),
                                      request.headers.get("x-device-allowlist", "").split(","),
                                      request.headers.get("x-source-kind", "unverified_file"))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


dist = Path(__file__).resolve().parents[2] / "web" / "dist"
if dist.is_dir():
    app.mount("/", StaticFiles(directory=dist, html=True), name="dashboard")
