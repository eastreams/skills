#!/usr/bin/env python3
"""Run a preset loong-monitor collection and report generation cycle."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run loong-monitor in one step for rolling or calendar reporting."
    )
    parser.add_argument(
        "--repo",
        default="loongclaw-ai/loongclaw",
        help="GitHub repository in owner/name form.",
    )
    parser.add_argument(
        "--preset",
        choices=["weekly", "monthly", "quarter", "calendar-week", "calendar-month", "calendar-quarter"],
        required=True,
        help=(
            "Reporting preset. "
            "weekly=last 7 days, monthly=last 30 days, quarter=last 90 days, "
            "calendar-week=from Monday of the containing ISO week to --until, "
            "calendar-month=from the first day of the containing month to --until, "
            "calendar-quarter=from the first day of the containing quarter to --until."
        ),
    )
    parser.add_argument(
        "--until",
        help="Optional window end date in YYYY-MM-DD format. Defaults to today in UTC.",
    )
    parser.add_argument(
        "--output-root",
        default="/tmp/loong-monitor-runs",
        help="Directory under which the run directory will be created.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=60,
        help="Maximum number of issues and PRs to collect per type.",
    )
    parser.add_argument(
        "--detail-limit",
        type=int,
        default=25,
        help="Maximum number of detailed PR and issue lookups per type.",
    )
    parser.add_argument(
        "--no-compare-previous",
        action="store_true",
        help="Disable previous-window comparison for this run.",
    )
    return parser.parse_args()


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def compute_window(preset: str, until: date) -> tuple[date, date]:
    if preset == "weekly":
        since = until - timedelta(days=6)
    elif preset == "monthly":
        since = until - timedelta(days=29)
    elif preset == "quarter":
        since = until - timedelta(days=89)
    elif preset == "calendar-week":
        since = until - timedelta(days=until.weekday())
    elif preset == "calendar-month":
        since = until.replace(day=1)
    else:
        quarter_start_month = ((until.month - 1) // 3) * 3 + 1
        since = until.replace(month=quarter_start_month, day=1)
    return since, until


def slug_repo(repo: str) -> str:
    return repo.replace("/", "__")


def run_command(command: list[str]) -> None:
    completed = subprocess.run(command, text=True)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def enrich_activity_json(activity_path: Path, preset: str, run_dir: Path) -> None:
    payload = json.loads(activity_path.read_text(encoding="utf-8"))
    payload["run_metadata"] = {
        "preset": preset,
        "run_dir": str(run_dir),
        "window_mode": "calendar" if preset.startswith("calendar-") else "rolling",
    }
    activity_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    until = parse_date(args.until) if args.until else datetime.now(timezone.utc).date()
    since, until = compute_window(args.preset, until)

    run_dir = (
        Path(args.output_root)
        / slug_repo(args.repo)
        / f"{args.preset}-{since.isoformat()}_to_{until.isoformat()}"
    )
    run_dir.mkdir(parents=True, exist_ok=True)

    script_dir = Path(__file__).resolve().parent
    collect_script = script_dir / "collect_repo_activity.py"
    report_script = script_dir / "generate_report.py"

    collect_command = [
        sys.executable,
        str(collect_script),
        "--repo",
        args.repo,
        "--since",
        since.isoformat(),
        "--until",
        until.isoformat(),
        "--limit",
        str(args.limit),
        "--detail-limit",
        str(args.detail_limit),
        "--output",
        str(run_dir),
    ]
    if not args.no_compare_previous:
        collect_command.append("--compare-previous")

    run_command(collect_command)
    enrich_activity_json(run_dir / "activity.json", args.preset, run_dir)
    run_command(
        [
            sys.executable,
            str(report_script),
            "--activity",
            str(run_dir / "activity.json"),
            "--output",
            str(run_dir / "report.md"),
        ]
    )

    manifest = run_dir / "run.txt"
    manifest.write_text(
        "\n".join(
            [
                f"repo={args.repo}",
                f"preset={args.preset}",
                f"since={since.isoformat()}",
                f"until={until.isoformat()}",
                f"compare_previous={'false' if args.no_compare_previous else 'true'}",
                f"activity={run_dir / 'activity.json'}",
                f"summary={run_dir / 'summary.md'}",
                f"report={run_dir / 'report.md'}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"Run directory: {run_dir}")
    print(f"Activity JSON: {run_dir / 'activity.json'}")
    print(f"Summary: {run_dir / 'summary.md'}")
    print(f"Report: {run_dir / 'report.md'}")
    print(f"Manifest: {manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
