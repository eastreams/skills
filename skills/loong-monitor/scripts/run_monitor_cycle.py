#!/usr/bin/env python3
"""Run a preset loong-monitor collection and report generation cycle."""

from __future__ import annotations

import argparse
import json
import shutil
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
    parser.add_argument(
        "--copy-to",
        help=(
            "Optional publish root. When set, the run directory is copied to "
            "<copy-to>/<repo_slug>/<run-name>/ and latest views are refreshed."
        ),
    )
    parser.add_argument(
        "--index-file",
        help=(
            "Optional Markdown index path for published runs. "
            "Defaults to <copy-to>/<repo_slug>/index.md when --copy-to is set."
        ),
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


def reset_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.parent.mkdir(parents=True, exist_ok=True)


def publish_run(run_dir: Path, repo_slug: str, preset: str, copy_root: str) -> dict[str, str]:
    publish_root = Path(copy_root) / repo_slug
    published_dir = publish_root / run_dir.name
    latest_preset_dir = publish_root / f"latest-{preset}"
    latest_dir = publish_root / "latest"

    for target in (published_dir, latest_preset_dir, latest_dir):
        reset_dir(target)
        shutil.copytree(run_dir, target)

    return {
        "publish_root": str(publish_root),
        "published_dir": str(published_dir),
        "latest_preset_dir": str(latest_preset_dir),
        "latest_dir": str(latest_dir),
    }


def write_publish_index(
    publish_root: Path,
    repo: str,
    index_path: Path,
) -> None:
    publish_root.mkdir(parents=True, exist_ok=True)
    run_dirs = sorted(
        [
            path for path in publish_root.iterdir()
            if path.is_dir() and not path.name.startswith("latest")
        ],
        key=lambda path: path.name,
        reverse=True,
    )
    latest_dirs = sorted(
        [
            path for path in publish_root.iterdir()
            if path.is_dir() and path.name.startswith("latest")
        ],
        key=lambda path: path.name,
    )

    lines = [
        "# Loong Monitor Published Index",
        "",
        f"- Repository slug root: `{publish_root}`",
        f"- Source repository: `{repo}`",
        f"- Updated at: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Latest Views",
        "",
    ]

    if latest_dirs:
        for path in latest_dirs:
            report = path / "report.md"
            manifest = path / "run.txt"
            lines.append(
                f"- `{path.name}`: report `{report}`, manifest `{manifest}`"
            )
    else:
        lines.append("- No latest views published yet.")

    lines.extend(["", "## Recent Published Runs", ""])
    if run_dirs:
        for path in run_dirs[:20]:
            report = path / "report.md"
            summary = path / "summary.md"
            manifest = path / "run.txt"
            lines.append(
                f"- `{path.name}`: report `{report}`, summary `{summary}`, manifest `{manifest}`"
            )
    else:
        lines.append("- No published runs found.")

    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


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
    repo_slug = slug_repo(args.repo)

    run_dir = (
        Path(args.output_root)
        / repo_slug
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

    publish_info: dict[str, str] = {}
    if args.copy_to:
        publish_info = publish_run(run_dir, repo_slug, args.preset, args.copy_to)
        index_path = (
            Path(args.index_file)
            if args.index_file
            else Path(publish_info["publish_root"]) / "index.md"
        )
        write_publish_index(Path(publish_info["publish_root"]), args.repo, index_path)
        publish_info["index_file"] = str(index_path)

    manifest_lines = [
        f"repo={args.repo}",
        f"preset={args.preset}",
        f"since={since.isoformat()}",
        f"until={until.isoformat()}",
        f"compare_previous={'false' if args.no_compare_previous else 'true'}",
        f"activity={run_dir / 'activity.json'}",
        f"summary={run_dir / 'summary.md'}",
        f"report={run_dir / 'report.md'}",
    ]
    if publish_info:
        manifest_lines.extend(
            [
                f"publish_root={publish_info['publish_root']}",
                f"published_dir={publish_info['published_dir']}",
                f"latest_preset_dir={publish_info['latest_preset_dir']}",
                f"latest_dir={publish_info['latest_dir']}",
                f"index_file={publish_info['index_file']}",
            ]
        )

    manifest = run_dir / "run.txt"
    manifest.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    if publish_info:
        for target in (
            Path(publish_info["published_dir"]),
            Path(publish_info["latest_preset_dir"]),
            Path(publish_info["latest_dir"]),
        ):
            manifest_target = target / "run.txt"
            manifest_target.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    print(f"Run directory: {run_dir}")
    print(f"Activity JSON: {run_dir / 'activity.json'}")
    print(f"Summary: {run_dir / 'summary.md'}")
    print(f"Report: {run_dir / 'report.md'}")
    print(f"Manifest: {manifest}")
    if publish_info:
        print(f"Published directory: {publish_info['published_dir']}")
        print(f"Latest preset directory: {publish_info['latest_preset_dir']}")
        print(f"Latest directory: {publish_info['latest_dir']}")
        print(f"Index file: {publish_info['index_file']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
