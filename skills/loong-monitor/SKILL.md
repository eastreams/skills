---
name: loong-monitor
description: Scan recent GitHub activity in loongclaw-ai/loongclaw and related LoongClaw repositories to build evidence-backed reports on recent PRs, issues, current focus areas, project status, risks, and likely next directions. Use this skill for weekly or monthly monitoring, repo health snapshots, delivery reviews, roadmap check-ins, or any request to analyze where LoongClaw work is concentrating and how the project is evolving.
---

# Loong Monitor

## Overview

This skill turns recent GitHub issue and pull request activity into a concise monitoring report for LoongClaw. It is designed for status reviews, activity scans, roadmap inference, delivery retrospectives, and periodic project health snapshots.

Use it when the user asks questions like:

- "最近 LoongClaw 主要在做什么？"
- "Scan LoongClaw PRs and issues from the last 30 days."
- "Summarize the current state of `loongclaw-ai/loongclaw`."
- "What looks like the next likely direction based on recent activity?"
- "Generate a weekly report for LoongClaw repo progress."

## Workflow

### 1. Define the monitoring window

Default to the last 30 days unless the user specifies a narrower or wider range.

Capture:

- target repository, usually `loongclaw-ai/loongclaw`
- time window: `--days`, or explicit `--since` and `--until`
- whether you want previous-window comparison enabled
- whether you need only a summary or a full report artifact

If the request is ambiguous, make a reasonable default and state it.

### 2. Collect evidence first

Run the collector script before writing conclusions:

```bash
python3 skills/loong-monitor/scripts/collect_repo_activity.py \
  --repo loongclaw-ai/loongclaw \
  --days 30 \
  --compare-previous \
  --output /tmp/loong-monitor
```

Useful variants:

```bash
python3 skills/loong-monitor/scripts/collect_repo_activity.py \
  --repo loongclaw-ai/loongclaw \
  --since 2026-03-01 \
  --until 2026-03-31 \
  --limit 80 \
  --detail-limit 25 \
  --output /tmp/loong-monitor-march
```

For one-click weekly or monthly reporting, use the preset runner:

```bash
python3 skills/loong-monitor/scripts/run_monitor_cycle.py \
  --preset weekly
```

```bash
python3 skills/loong-monitor/scripts/run_monitor_cycle.py \
  --preset monthly \
  --repo loongclaw-ai/loongclaw
```

The script produces:

- `activity.json`: raw collected issue and PR data plus computed summary signals
- `summary.md`: a compact evidence digest you can quote and reason over
- `report.md`: a full Markdown monitoring report when you use the one-click preset runner
- `run.txt`: a small manifest showing the exact output paths for the run

When you need a full report, generate it from the collected artifact:

```bash
python3 skills/loong-monitor/scripts/generate_report.py \
  --activity /tmp/loong-monitor/activity.json \
  --output /tmp/loong-monitor/report.md
```

### 3. Interpret with discipline

Use the collected evidence to separate three layers of conclusions:

1. Facts: counts, merged PRs, open issues, touched paths, comment volume, labels.
2. Working interpretation: what those signals suggest about current team focus or operational status.
3. Inference: plausible next directions or emerging themes. Label these clearly as inference.

Do not treat inferred roadmap direction as confirmed fact unless it is explicitly stated in issues, PR descriptions, or linked docs.

### 4. Produce the report

Use [assets/report-template.md](assets/report-template.md) as the output skeleton when the user wants a written report.

Prefer the generated report script when the user asks for a reusable report artifact, a weekly digest, or a compare-the-last-two-windows assessment.
Prefer the preset runner when the user explicitly wants a weekly report, monthly report, or a repeatable one-command monitoring workflow.

Minimum report structure:

- Monitoring window and repo
- Executive summary
- Current focus areas
- Current status and delivery signals
- Comparison to previous window when requested
- Risks, blockers, and unresolved threads
- Likely next directions
- Evidence appendix with linked issue and PR references

## Analytical Rules

- Prefer merged PRs when describing delivered work.
- Prefer open PRs and open issues when describing current queue, risks, or upcoming work.
- Use touched file paths, labels, and recurring title terms to identify focus areas.
- Call out uncertainty when the sample size is small or labels are sparse.
- Cite item numbers and URLs for every non-trivial claim.
- Avoid overstating momentum from a single noisy PR or issue.

For the full analysis framework and phrasing rules, read [references/analysis-framework.md](references/analysis-framework.md).

## Output Expectations

Good outputs from this skill should answer:

- What changed recently?
- Where is most engineering attention going?
- What is currently blocked, active, or stabilizing?
- What does the recent activity imply about likely next work?

If the evidence is weak, say that directly and explain what data is missing.
