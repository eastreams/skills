# Loong Monitor Analysis Framework

Use this reference after collecting evidence with `scripts/collect_repo_activity.py`.

## Goal

Convert recent issue and PR activity into a defensible monitoring report that distinguishes:

- direct evidence
- interpretation grounded in evidence
- forward-looking inference

## Evidence Hierarchy

Use stronger signals first:

1. Merged PRs
2. Open PRs with active updates or review activity
3. Open issues with comments or linked implementation
4. Closed issues without linked code
5. Labels and title keywords

If stronger signals are unavailable, explicitly downgrade confidence.

## Focus Area Detection

Prefer the following evidence in this order:

1. Repeated path prefixes from changed files in recent PRs
2. Repeated labels across PRs and issues
3. Recurring title terms that are specific to the project domain
4. Clusters of linked issues and PRs around a single feature or subsystem

Good focus-area phrasing:

- "Recent merged PRs concentrate on `crates/kernel` and `docs/`, suggesting active kernel hardening plus architecture documentation work."
- "Open issues and PRs are clustered around release automation, which indicates current attention on delivery reliability."

Weak phrasing to avoid:

- "The team is definitely pivoting to X."
- "This proves the roadmap is Y."

## Status Assessment

Assess the project status using these lenses:

- delivery velocity: merged PR count, cadence, and recency
- queue pressure: number of active open PRs and issues
- review friction: long-lived PRs, many comments, stalled updates
- stabilization signals: docs, tests, refactors, cleanup, architecture work
- expansion signals: new subsystems, new feature threads, exploratory issues

When previous-window comparison is available, evaluate whether:

- merged throughput is rising, flat, or falling
- open PR pressure is growing faster than merged throughput
- open issue count is accumulating or shrinking
- new labels, terms, or path clusters indicate a genuine new direction rather than noise

Status labels should be plain and descriptive, for example:

- "active delivery with moderate review queue"
- "stabilization and hardening phase"
- "architecture consolidation with limited feature expansion"
- "exploratory planning with low implementation throughput"

## Next-Direction Inference

Only infer next directions from patterns such as:

- an open PR building directly on recent merged work
- a cluster of issues around the same subsystem
- repeated documentation, architecture, or release work that usually precedes a release or consolidation phase
- unfinished high-comment or high-priority threads

Always mark these statements as inference or likely direction.

If a new direction is inferred from only one PR or issue, say that confidence is low.

## Report Checklist

Before finalizing the report, ensure it includes:

- explicit monitoring window
- total issue and PR counts for the window
- comparison notes when a previous-window sample was collected
- at least 3 concrete linked artifacts in the evidence section when available
- a clear distinction between current facts and future inference
- a statement of uncertainty if labels, file paths, or sample size are weak
