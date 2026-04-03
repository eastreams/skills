#!/usr/bin/env python3
"""Collect GitHub issue and PR activity for a monitoring window."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

TITLE_STOPWORDS = {
    "a",
    "an",
    "and",
    "api",
    "bug",
    "by",
    "docs",
    "doc",
    "feat",
    "feature",
    "for",
    "from",
    "fix",
    "in",
    "into",
    "on",
    "of",
    "or",
    "pr",
    "refactor",
    "repo",
    "the",
    "to",
    "update",
    "with",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect recent issue and pull request activity for a GitHub repository."
    )
    parser.add_argument("--repo", required=True, help="GitHub repository in owner/name form.")
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Monitoring window length in days when --since is not provided.",
    )
    parser.add_argument("--since", help="Window start date in YYYY-MM-DD format.")
    parser.add_argument("--until", help="Window end date in YYYY-MM-DD format.")
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
        help="Maximum number of issue and PR detail lookups per type.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Directory where activity.json and summary.md will be written.",
    )
    return parser.parse_args()


def run_json(command: list[str]) -> Any:
    try:
        completed = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        sys.stderr.write(exc.stderr)
        raise
    return json.loads(completed.stdout)


def iso_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def compute_window(args: argparse.Namespace) -> tuple[date, date]:
    until = iso_date(args.until) if args.until else datetime.now(timezone.utc).date()
    since = iso_date(args.since) if args.since else until - timedelta(days=args.days)
    if since > until:
        raise SystemExit("--since must be on or before --until")
    return since, until


def search_items(repo: str, kind: str, since: date, until: date, limit: int) -> list[dict[str, Any]]:
    query = f"repo:{repo} is:{kind} updated:{since.isoformat()}..{until.isoformat()}"
    per_page = min(limit, 100)
    page = 1
    items: list[dict[str, Any]] = []
    while len(items) < limit:
        page_items = run_json(
            [
                "gh",
                "api",
                "-X",
                "GET",
                "search/issues",
                "-f",
                f"q={query}",
                "-f",
                "sort=updated",
                "-f",
                "order=desc",
                "-f",
                f"per_page={per_page}",
                "-f",
                f"page={page}",
            ]
        )["items"]
        if not page_items:
            break
        items.extend(page_items)
        if len(page_items) < per_page:
            break
        page += 1
    return items[:limit]


def pr_detail(repo: str, number: int) -> dict[str, Any]:
    return run_json(
        [
            "gh",
            "pr",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            (
                "number,title,url,state,isDraft,createdAt,updatedAt,closedAt,mergedAt,"
                "author,labels,reviewDecision,comments,changedFiles,additions,deletions,files"
            ),
        ]
    )


def pr_snapshot(repo: str, number: int) -> dict[str, Any]:
    return run_json(
        [
            "gh",
            "pr",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            "number,state,mergedAt",
        ]
    )


def issue_detail(repo: str, number: int) -> dict[str, Any]:
    return run_json(
        [
            "gh",
            "issue",
            "view",
            str(number),
            "--repo",
            repo,
            "--json",
            "number,title,url,state,createdAt,updatedAt,closedAt,author,labels,comments",
        ]
    )


def title_terms(items: list[dict[str, Any]]) -> list[dict[str, int]]:
    terms: Counter[str] = Counter()
    for item in items:
        title = item.get("title", "").lower()
        for token in "".join(ch if ch.isalnum() else " " for ch in title).split():
            if len(token) < 4 or token in TITLE_STOPWORDS:
                continue
            terms[token] += 1
    return [{"term": term, "count": count} for term, count in terms.most_common(10)]


def extract_top_labels(items: list[dict[str, Any]]) -> list[dict[str, int]]:
    labels: Counter[str] = Counter()
    for item in items:
        for label in item.get("labels", []):
            name = label["name"] if isinstance(label, dict) else label
            labels[name] += 1
    return [{"label": label, "count": count} for label, count in labels.most_common(10)]


def top_authors(items: list[dict[str, Any]]) -> list[dict[str, int]]:
    authors: Counter[str] = Counter()
    for item in items:
        author = item.get("author") or item.get("user") or {}
        login = author.get("login")
        if login:
            authors[login] += 1
    return [{"author": author, "count": count} for author, count in authors.most_common(10)]


def top_paths(prs: list[dict[str, Any]]) -> list[dict[str, int]]:
    paths: Counter[str] = Counter()
    for pr in prs:
        for file_info in pr.get("files", []):
            path = file_info.get("path", "")
            if not path:
                continue
            parts = [part for part in path.split("/") if part]
            if not parts:
                continue
            prefix = parts[0] if len(parts) == 1 else "/".join(parts[:2])
            paths[prefix] += 1
    return [{"path": path, "count": count} for path, count in paths.most_common(10)]


def item_counts(
    pr_search: list[dict[str, Any]],
    issue_search: list[dict[str, Any]],
    pr_snapshots: list[dict[str, Any]],
    detailed_prs: list[dict[str, Any]],
    detailed_issues: list[dict[str, Any]],
) -> dict[str, Any]:
    pr_open = sum(1 for pr in pr_search if pr.get("state", "").lower() == "open")
    issue_open = sum(1 for issue in issue_search if issue.get("state", "").lower() == "open")
    merged = sum(1 for pr in pr_snapshots if pr.get("mergedAt"))
    high_discussion_prs = sorted(
        detailed_prs,
        key=lambda item: len(item.get("comments", [])),
        reverse=True,
    )[:5]
    high_discussion_issues = sorted(
        detailed_issues,
        key=lambda item: len(item.get("comments", [])),
        reverse=True,
    )[:5]
    return {
        "prs": {
            "total": len(pr_search),
            "merged": merged,
            "open": pr_open,
            "closed_unmerged": len(pr_search) - merged - pr_open,
        },
        "issues": {
            "total": len(issue_search),
            "open": issue_open,
            "closed": len(issue_search) - issue_open,
        },
        "high_discussion_prs": [
            {
                "number": item["number"],
                "title": item["title"],
                "comments": len(item.get("comments", [])),
                "url": item["url"],
            }
            for item in high_discussion_prs
        ],
        "high_discussion_issues": [
            {
                "number": item["number"],
                "title": item["title"],
                "comments": len(item.get("comments", [])),
                "url": item["url"],
            }
            for item in high_discussion_issues
        ],
    }


def build_summary(
    repo: str,
    since: date,
    until: date,
    pr_search: list[dict[str, Any]],
    issue_search: list[dict[str, Any]],
    summary: dict[str, Any],
) -> str:
    lines = [
        f"# Activity Summary for {repo}",
        "",
        f"- Window: {since.isoformat()} to {until.isoformat()}",
        f"- PRs collected: {summary['counts']['prs']['total']}",
        f"- Issues collected: {summary['counts']['issues']['total']}",
        f"- Merged PRs: {summary['counts']['prs']['merged']}",
        f"- Open PRs: {summary['counts']['prs']['open']}",
        f"- Open issues: {summary['counts']['issues']['open']}",
        (
            "- Detailed lookups used for file-path and discussion signals: "
            f"top {min(len(pr_search), summary['detail_limit'])} PRs and "
            f"top {min(len(issue_search), summary['detail_limit'])} issues"
        ),
        "",
        "## Top Labels",
    ]
    if summary["top_labels"]:
        lines.extend(
            f"- {item['label']}: {item['count']}"
            for item in summary["top_labels"]
        )
    else:
        lines.append("- No labels found in collected items.")

    lines.extend(["", "## Top Touched Paths"])
    if summary["top_paths"]:
        lines.extend(
            f"- {item['path']}: {item['count']}"
            for item in summary["top_paths"]
        )
    else:
        lines.append("- No file-path details available from collected PRs.")

    lines.extend(["", "## Common Title Terms"])
    if summary["top_terms"]:
        lines.extend(
            f"- {item['term']}: {item['count']}"
            for item in summary["top_terms"]
        )
    else:
        lines.append("- No strong recurring title terms detected.")

    lines.extend(["", "## Most Active Authors"])
    if summary["top_authors"]:
        lines.extend(
            f"- {item['author']}: {item['count']}"
            for item in summary["top_authors"]
        )
    else:
        lines.append("- No author activity detected.")

    lines.extend(["", "## High-Discussion PRs"])
    if summary["counts"]["high_discussion_prs"]:
        lines.extend(
            f"- PR #{item['number']} ({item['comments']} comments): {item['title']} - {item['url']}"
            for item in summary["counts"]["high_discussion_prs"]
        )
    else:
        lines.append("- None.")

    lines.extend(["", "## High-Discussion Issues"])
    if summary["counts"]["high_discussion_issues"]:
        lines.extend(
            f"- Issue #{item['number']} ({item['comments']} comments): {item['title']} - {item['url']}"
            for item in summary["counts"]["high_discussion_issues"]
        )
    else:
        lines.append("- None.")

    lines.extend(["", "## Recent PRs"])
    lines.extend(
        f"- PR #{pr['number']} [{str(pr['state']).upper()}] {pr['title']} - {pr['html_url']}"
        for pr in pr_search[:10]
    )

    lines.extend(["", "## Recent Issues"])
    lines.extend(
        f"- Issue #{issue['number']} [{str(issue['state']).upper()}] {issue['title']} - {issue['html_url']}"
        for issue in issue_search[:10]
    )

    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    since, until = compute_window(args)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    pr_search = search_items(args.repo, "pr", since, until, args.limit)
    issue_search = search_items(args.repo, "issue", since, until, args.limit)

    pr_numbers = [item["number"] for item in pr_search[: args.detail_limit]]
    issue_numbers = [item["number"] for item in issue_search[: args.detail_limit]]
    pr_snapshot_numbers = [item["number"] for item in pr_search]

    prs = [pr_detail(args.repo, number) for number in pr_numbers]
    issues = [issue_detail(args.repo, number) for number in issue_numbers]
    pr_snapshots = [pr_snapshot(args.repo, number) for number in pr_snapshot_numbers]

    summary = {
        "detail_limit": args.detail_limit,
        "counts": item_counts(pr_search, issue_search, pr_snapshots, prs, issues),
        "top_labels": extract_top_labels(pr_search + issue_search),
        "top_authors": top_authors(pr_search + issue_search),
        "top_paths": top_paths(prs),
        "top_terms": title_terms(pr_search + issue_search),
    }

    payload = {
        "repo": args.repo,
        "window": {
            "since": since.isoformat(),
            "until": until.isoformat(),
        },
        "limits": {
            "search_limit": args.limit,
            "detail_limit": args.detail_limit,
        },
        "summary": summary,
        "pr_search": pr_search,
        "issue_search": issue_search,
        "pr_snapshots": pr_snapshots,
        "prs": prs,
        "issues": issues,
    }

    activity_path = output_dir / "activity.json"
    summary_path = output_dir / "summary.md"
    activity_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    summary_path.write_text(
        build_summary(args.repo, since, until, pr_search, issue_search, summary),
        encoding="utf-8",
    )

    print(f"Wrote {activity_path}")
    print(f"Wrote {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
