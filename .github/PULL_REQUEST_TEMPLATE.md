## Summary

<!-- One or two sentences describing the change. -->

## Task ID

<!-- Which research/engineering task does this PR address? -->
<!-- Examples: DS-05, FE-01, PR-02, CL-03, EV-04, PF-05, VI-06 -->

## Description

<!-- What does this PR do, and why? Reference the relevant ADR in docs/decisions/. -->

## Files Changed

<!-- Bullet list of the main files added or modified. -->

## Validation Performed

<!-- Describe the validation you ran locally. -->
- [ ] `ruff check .` passes
- [ ] `black --check .` passes
- [ ] `pytest` passes
- [ ] No raw data is included in the diff
- [ ] No generated reports/figures are included in the diff

## Research Impact

<!-- Does this change a research question, methodology, or feature definition? -->
<!-- If yes, link the ADR that records the decision. -->

## Reproducibility Notes

<!-- If this PR affects an experiment, list: -->
<!-- - experiment ID -->
<!-- - config hash -->
<!-- - random seed -->
<!-- - environment (Python version, OS) -->
<!-- - path to generated artifacts -->

## Checklist

- [ ] Branch is up to date with `master`
- [ ] Commit messages follow the team convention
- [ ] No raw or processed datasets are committed
- [ ] New configuration values are documented in `configs/`
- [ ] New public functions/classes have type hints and docstrings
- [ ] New public behavior has at least one test
- [ ] Relevant ADRs and docs are updated