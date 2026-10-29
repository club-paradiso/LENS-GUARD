import argparse
import json
from pathlib import Path
from .demo import demo_report, write_fixture
from .evaluation import SPLITS, evaluate
from .hardware import capabilities
from .labeled import evaluate_labeled
from .pcap import MAX_BYTES, analyze_capture


def main():
    parser = argparse.ArgumentParser(description="LENS-GUARD local experimental traffic analysis")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("demo", "evaluate", "capabilities"):
        p = sub.add_parser(name)
        p.add_argument("--output", type=Path)
        if name == "evaluate":
            p.add_argument("--split", choices=["dev", "test", "shift", "all"], default="all",
                           help="dev tunes rules; test and shift run only after docs/PREREGISTRATION.md is committed")
    p = sub.add_parser("analyze")
    p.add_argument("file", type=Path)
    p.add_argument("--allow-mac", action="append", required=True)
    p.add_argument("--authorized", action="store_true", required=True)
    p.add_argument("--source", choices=["synthetic_file", "user_declared_authorized_capture", "unverified_file"], default="unverified_file")
    p.add_argument("--output", type=Path)
    p = sub.add_parser("evaluate-labeled", help="metrics for user-labeled captures of owned or authorized devices")
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--output", type=Path)
    p = sub.add_parser("fixture")
    p.add_argument("output", type=Path)
    p = sub.add_parser("serve")
    p.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    try:
        if args.command == "serve":
            import uvicorn
            uvicorn.run("lens_guard.api:app", host="127.0.0.1", port=args.port, access_log=False)
            return
        if args.command == "fixture":
            args.output.parent.mkdir(parents=True, exist_ok=True)
            write_fixture(args.output)
            print("Synthetic fixture created; MAC 02:00:00:00:00:01. No physical capture.")
            return
        if args.command == "analyze":
            with args.file.open("rb") as stream:
                data = stream.read(MAX_BYTES + 1)
            report = analyze_capture(data, args.allow_mac, args.source)
        elif args.command == "evaluate-labeled":
            report = evaluate_labeled(args.manifest)
        elif args.command == "evaluate":
            report = evaluate(SPLITS if args.split == "all" else (args.split,))
        else:
            report = {"demo": demo_report, "capabilities": capabilities}[args.command]()
        content = json.dumps(report, indent=2, allow_nan=False) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(content)
        else:
            print(content, end="")
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Analysis failed: {exc}\n")
