# Methodology

This directory holds the **research methodology** documents for the project:
research questions, hypotheses, study design, unit of analysis, and the
benchmarking protocol.

These documents are **fixed by the project lead** and must not be modified
by individual contributors. Any change to a research question or to the
benchmarking protocol must be:

1. Proposed in a Pull Request with a clear rationale.
2. Reviewed and approved by the project lead.
3. Recorded as an Architecture Decision Record in
   [`../decisions/`](../decisions/).

## Current documents

| File | Status | Description |
|------|--------|-------------|
| `research_questions.md` | ✅ ACTIVE | RQ1, RQ2, RQ3 official definitions |
| `methodology_overview.md` | ✅ ACTIVE | Study design, benchmarking protocol, experiment pipeline |
| `TODO_unit_of_analysis.md` | ⏳ PENDING | Unit of analysis rationale (to be added if needed) |

## Key decisions (ADRs)

| ADR | Decision |
|-----|----------|
| ADR-0001 | Primary dataset = UCI Online Retail |
| ADR-0002 | Backup dataset = UCI Online Retail II |
| ADR-0003 | Algorithm scope = 5 algorithms (K-Medoids OUT OF SCOPE) |
| ADR-0004 | Research Questions RQ1, RQ2, RQ3 definitions |

See [`../decisions/`](docs/decisions/) for full ADR text.