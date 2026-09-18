# Decisions (Architecture Decision Records)

This directory records **research and engineering decisions** taken during
the project, following the lightweight ADR template below.

ADRs are **immutable once accepted**. If a decision is later reversed,
write a *new* ADR that supersedes the old one; do not edit the old file.

## File naming

Use the next four-digit sequence and a short kebab-case title:

```
NNNN-short-kebab-title.md
```

Examples (to be added):

- `0001-primary-dataset-uci-online-retail.md`
- `0002-backup-dataset-uci-online-retail-ii.md`
- `0003-feature-framework-rfm-plus-extended-behavioral.md`

## ADR template

```markdown
# NNNN — <short title>

- **Status**: Proposed | Accepted | Superseded by NNNN
- **Date**: YYYY-MM-DD
- **Deciders**: <names>
- **Task ID**: <DS-05 | FE-01 | ...>

## Context

What is the situation that requires a decision?

## Decision

What did we decide?

## Consequences

What becomes easier? What becomes harder or riskier?

## Alternatives considered

What other options were considered, and why were they rejected?
```

## Current ADRs

(none yet — add the DS-05 dataset-selection decision first)