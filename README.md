# LoongClaw Skills

Public skills collection for the LoongClaw team.

This repository stores reusable skills that are either:

- directly related to the `loongclaw-ai/loongclaw` project and adjacent tooling
- created by the LoongClaw team for recurring engineering, analysis, and delivery workflows

## Repository Layout

```text
skills/
└── <skill-name>/
    ├── SKILL.md
    ├── agents/openai.yaml
    ├── scripts/
    ├── references/
    └── assets/
```

Each skill should stay self-contained. Keep the procedural guidance in `SKILL.md`, store reusable code in `scripts/`, put detailed analysis frameworks or reference docs in `references/`, and keep output templates in `assets/`.

## Skills

See [skills/README.md](/Users/chum/skills/skills/README.md) for the catalog.

## Current Focus

The first skill in this repository is `loong-monitor`, which analyzes recent GitHub activity in `loongclaw-ai/loongclaw` and helps produce evidence-backed status and direction reports.
