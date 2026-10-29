"""Build-only synthetic demo snapshots for the public, static Vercel UI.

The public site never exposes the authorized-capture /api/analyze route.
The snapshots are derived from the same Python demo engine as the local app.
"""
from pathlib import Path
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from lens_guard.demo import demo_report  # noqa: E402

public = ROOT / "web" / "public"
public.mkdir(parents=True, exist_ok=True)
report = demo_report(seed=42, seconds=60)
assert report["provenance"] == "synthetic_demo"
assert report["ground_truth"] == "not_verified"
assert report["devices"] and report["timeline"]
(public / "demo.json").write_text(
    json.dumps(report, separators=(",", ":"), allow_nan=False) + "\n",
    encoding="utf-8",
)
shutil.copyfile(ROOT / "docs" / "evaluation.json", public / "evaluation.json")
print(f"Public static demo: {len(report['devices'])} simulated sources; no PCAP endpoint.")
