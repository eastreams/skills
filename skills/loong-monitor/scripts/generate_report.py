#!/usr/bin/env python3
"""Generate a Markdown monitoring report from collected repo activity."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a Markdown report from loong-monitor activity.json."
    )
    parser.add_argument(
        "--activity",
        required=True,
        help="Path to activity.json produced by collect_repo_activity.py.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path where the Markdown report will be written.",
    )
    return parser.parse_args()


def load_activity(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def count_value(summary: dict[str, Any], group: str, name: str) -> int:
    return int(summary["counts"][group][name])


def choose_focus_areas(summary: dict[str, Any]) -> list[dict[str, str]]:
    path_items = summary.get("top_paths", [])
    label_items = summary.get("top_labels", [])
    term_items = summary.get("top_terms", [])
    discussion_prs = summary["counts"].get("high_discussion_prs", [])
    evidence_urls = [item["url"] for item in discussion_prs[:2]]

    def labels_line(limit: int = 3) -> str:
        labels = [item["label"] for item in label_items[:limit]]
        return ", ".join(labels) if labels else "few stable labels"

    def terms_line(limit: int = 3) -> str:
        terms = [item["term"] for item in term_items[:limit]]
        return ", ".join(terms) if terms else "no strong recurring title terms"

    focus_areas: list[dict[str, str]] = []
    seen_titles: set[str] = set()

    for item in path_items:
        path = item["path"]
        count = item["count"]
        if path.startswith("docs/"):
            title = "Documentation, planning, and architecture surfaces"
            detail = (
                f"Recent touched paths are concentrated in `{path}` and nearby docs paths, "
                f"which suggests active design, planning, or public-facing documentation work. "
                f"Supporting signals: labels `{labels_line()}` and terms `{terms_line()}`."
            )
        elif path.startswith("crates/daemon"):
            title = "Daemon and runtime operations"
            detail = (
                f"`{path}` is one of the heaviest touched areas, pointing to operational runtime, "
                f"diagnostics, onboarding, or delivery-path work. Supporting signals: labels "
                f"`{labels_line()}` and terms `{terms_line()}`."
            )
        elif path.startswith("crates/app"):
            title = "Application and conversation runtime"
            detail = (
                f"`{path}` appears repeatedly in recent PRs, which suggests current attention on "
                f"user-facing runtime flow, orchestration, or interaction behavior."
            )
        elif path.startswith("crates/kernel") or path.startswith("crates/contracts"):
            title = "Kernel and contract shaping"
            detail = (
                f"Touches in `{path}` indicate work on core semantics, shared boundaries, or "
                f"foundation-layer behavior."
            )
        elif path.startswith(".github/") or path.startswith("scripts/"):
            title = "CI and delivery reliability"
            detail = (
                f"`{path}` indicates attention on automation, validation, or delivery flow stability."
            )
        else:
            title = f"Activity centered on `{path}`"
            detail = (
                f"`{path}` appears {count} times across detailed PR file lists, making it one of the "
                f"more active clusters in the current monitoring window."
            )

        if title in seen_titles:
            continue
        seen_titles.add(title)
        focus_areas.append(
            {
                "title": title,
                "detail": detail,
                "evidence": ", ".join(evidence_urls) if evidence_urls else "See recent PR evidence in the appendix.",
            }
        )
        if len(focus_areas) == 3:
            break

    if not focus_areas:
        focus_areas.append(
            {
                "title": "No strong path cluster detected",
                "detail": "The current sample does not show a clear dominant path cluster, so conclusions should stay conservative.",
                "evidence": "Use the evidence appendix and high-discussion items for manual review.",
            }
        )

    return focus_areas


def status_line(summary: dict[str, Any], comparison: dict[str, Any] | None) -> str:
    merged = count_value(summary, "prs", "merged")
    open_prs = count_value(summary, "prs", "open")
    open_issues = count_value(summary, "issues", "open")

    if merged >= 5 and open_prs >= 5:
        status = "active delivery with a substantial in-flight queue"
    elif merged >= 3 and open_prs >= 3:
        status = "steady delivery with ongoing implementation threads"
    elif open_prs > merged:
        status = "active work in progress with landing throughput lagging the queue"
    else:
        status = "moderate activity with a relatively light landing cadence"

    if comparison is None:
        return status

    delta = comparison["delta"]
    previous_total = (
        comparison["previous"]["counts"]["prs"]["total"]
        + comparison["previous"]["counts"]["issues"]["total"]
    )
    if previous_total == 0:
        return status + " after a quiet previous window"

    if delta["prs_merged"] > 0:
        status += "; merged throughput is up versus the previous window"
    elif delta["prs_merged"] < 0:
        status += "; merged throughput is down versus the previous window"

    if delta["issues_open"] > 0:
        status += " and open issue pressure is increasing"
    elif delta["issues_open"] < 0:
        status += " and open issue pressure is easing"

    return status


def executive_summary(payload: dict[str, Any]) -> list[str]:
    summary = payload["summary"]
    comparison = payload.get("comparison")
    lines = [
        (
            f"The repository shows {status_line(summary, comparison)} during "
            f"{payload['window']['since']} to {payload['window']['until']}."
        ),
        (
            f"The current sample includes {count_value(summary, 'prs', 'total')} PRs, "
            f"{count_value(summary, 'prs', 'merged')} merged PRs, and "
            f"{count_value(summary, 'issues', 'open')} open issues."
        ),
    ]

    top_paths = summary.get("top_paths", [])
    if top_paths:
        lines.append(
            f"The heaviest detailed file activity is concentrated in `{top_paths[0]['path']}`"
            + (
                f" and `{top_paths[1]['path']}`."
                if len(top_paths) > 1
                else "."
            )
        )

    if comparison:
        delta = comparison["delta"]
        previous_total = (
            comparison["previous"]["counts"]["prs"]["total"]
            + comparison["previous"]["counts"]["issues"]["total"]
        )
        if previous_total == 0:
            lines.append(
                "The previous same-length window had no collected PR or issue activity, so the current burst should be treated as a fresh active phase rather than a subtle trend change."
            )
        else:
            lines.append(
                "Compared with the previous window, "
                f"PR volume changed by {delta['prs_total']:+d}, merged PRs by {delta['prs_merged']:+d}, "
                f"and open issues by {delta['issues_open']:+d}."
            )

    return lines


def current_status_points(summary: dict[str, Any], comparison: dict[str, Any] | None) -> list[str]:
    points = [
        f"Merged PR activity: {count_value(summary, 'prs', 'merged')} merged in the current window.",
        f"Active PR queue: {count_value(summary, 'prs', 'open')} open PRs in the collected sample.",
        f"Issue pressure: {count_value(summary, 'issues', 'open')} open issues in the collected sample.",
    ]
    if comparison:
        delta = comparison["delta"]
        previous_total = (
            comparison["previous"]["counts"]["prs"]["total"]
            + comparison["previous"]["counts"]["issues"]["total"]
        )
        if previous_total == 0:
            points.append(
                "The previous same-length window had no collected activity, so the current window effectively establishes the recent baseline."
            )
        else:
            points.append(
                "Window-over-window deltas: "
                f"PRs {delta['prs_total']:+d}, merged {delta['prs_merged']:+d}, "
                f"open PRs {delta['prs_open']:+d}, open issues {delta['issues_open']:+d}."
            )
    return points


def risks_and_questions(summary: dict[str, Any], comparison: dict[str, Any] | None) -> list[str]:
    risks: list[str] = []
    merged = count_value(summary, "prs", "merged")
    open_prs = count_value(summary, "prs", "open")
    open_issues = count_value(summary, "issues", "open")

    if open_prs >= max(5, merged * 2):
        risks.append(
            "The open PR queue is materially larger than recent merged throughput, which may indicate review bandwidth pressure or large in-flight changes."
        )

    if open_issues >= 10:
        risks.append(
            "Open issue volume is non-trivial, so backlog growth and prioritization discipline should be watched closely."
        )

    discussion_prs = summary["counts"].get("high_discussion_prs", [])
    if discussion_prs:
        risks.append(
            f"PR #{discussion_prs[0]['number']} is among the highest-discussion threads, so it may represent a hotspot for review friction or design negotiation."
        )

    if (
        comparison
        and comparison["delta"]["issues_open"] > 0
        and (
            comparison["previous"]["counts"]["prs"]["total"]
            + comparison["previous"]["counts"]["issues"]["total"]
        )
        > 0
    ):
        risks.append(
            "Open issues increased versus the previous window, which suggests unresolved work may be accumulating faster than it is being retired."
        )

    if not risks:
        risks.append("No dominant risk signal stands out from the current evidence sample, but the report should still be read as directional rather than exhaustive.")

    return risks


def likely_next_directions(payload: dict[str, Any]) -> list[str]:
    summary = payload["summary"]
    comparison = payload.get("comparison")
    directions: list[str] = []
    open_prs = [
        item for item in payload.get("pr_search", [])
        if str(item.get("state", "")).lower() == "open"
    ]
    open_issues = [
        item for item in payload.get("issue_search", [])
        if str(item.get("state", "")).lower() == "open"
    ]

    for item in open_prs[:2]:
        directions.append(
            f"Likely near-term follow-through remains around PR #{item['number']} because it is still open and sits near the front of the recent activity queue."
        )

    for item in open_issues[:2]:
        directions.append(
            f"Issue #{item['number']} is a plausible candidate to shape upcoming work because it is still open and recently updated within the monitoring window."
        )

    if comparison:
        if comparison["emerging_paths"]:
            directions.append(
                "New path clusters are appearing in "
                + ", ".join(f"`{path}`" for path in comparison["emerging_paths"][:3])
                + ", which may signal a broadening work frontier."
            )
        if comparison["emerging_terms"]:
            directions.append(
                "Emerging title language such as "
                + ", ".join(f"`{term}`" for term in comparison["emerging_terms"][:3])
                + " suggests new emphasis areas worth tracking in the next report."
            )

    if not directions:
        directions.append(
            "The current evidence does not strongly separate one next direction from another, so follow-up reporting should wait for another cycle of PR and issue movement."
        )

    return directions[:4]


def evidence_appendix(payload: dict[str, Any]) -> list[str]:
    summary = payload["summary"]
    appendix: list[str] = []
    for item in summary["counts"].get("high_discussion_prs", [])[:5]:
        appendix.append(
            f"- PR #{item['number']}: {item['title']} ({item['comments']} comments) - {item['url']}"
        )
    for item in summary["counts"].get("high_discussion_issues", [])[:5]:
        appendix.append(
            f"- Issue #{item['number']}: {item['title']} ({item['comments']} comments) - {item['url']}"
        )
    return appendix


def render_report(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    comparison = payload.get("comparison")
    focus_areas = choose_focus_areas(summary)
    generated_at = payload.get("generated_at") or datetime.now(timezone.utc).isoformat()
    run_metadata = payload.get("run_metadata") or {}

    lines = [
        "# LoongClaw Monitor Report",
        "",
        f"- Repository: `{payload['repo']}`",
        f"- Monitoring window: {payload['window']['since']} to {payload['window']['until']}",
        f"- Generated at: {generated_at}",
    ]
    if run_metadata.get("preset"):
        lines.append(f"- Run preset: `{run_metadata['preset']}`")
    lines.extend(["", "## Executive Summary", ""])
    lines.extend(f"- {line}" for line in executive_summary(payload))

    lines.extend(["", "## Current Focus Areas", ""])
    for area in focus_areas:
        lines.append(f"- {area['title']}: {area['detail']}")
        lines.append(f"  Evidence: {area['evidence']}")

    lines.extend(["", "## Current Status", ""])
    lines.extend(f"- {line}" for line in current_status_points(summary, comparison))

    lines.extend(["", "## Risks And Open Questions", ""])
    lines.extend(f"- {line}" for line in risks_and_questions(summary, comparison))

    lines.extend(["", "## Likely Next Directions", ""])
    lines.extend(f"- {line}" for line in likely_next_directions(payload))

    lines.extend(["", "## Evidence Appendix", ""])
    lines.extend(evidence_appendix(payload))

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    activity_path = Path(args.activity)
    output_path = Path(args.output)
    payload = load_activity(activity_path)
    report = render_report(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
