# Experiment Logs

Each experiment run by any team member must be recorded here so that
results are **reproducible** by any other team member or by an external
reviewer.

## Required fields per experiment

| Field             | Description                                                       |
| ----------------- | ----------------------------------------------------------------- |
| Experiment ID     | `EXP-001`, `EXP-002`, ... (matches `experiment.name`).             |
| Date              | ISO-8601 date the experiment was executed.                        |
| Author            | Name and (optionally) email of the runner.                        |
| Task ID           | Pipeline task ID (e.g. `FE-01`, `CL-02`).                         |
| Git commit        | Commit hash of the repo at the time of the run.                   |
| Config hash       | SHA-256 of the resolved YAML configs.                             |
| Random seed       | Integer used by all RNGs.                                         |
| Environment       | Python version, OS, CPU model, RAM.                               |
| Raw dataset       | `primary` or `backup`, plus filename and SHA-256.                   |
| Preprocessing     | Which cleaning rules were applied.                                |
| Feature version   | Which RFM / extended features were used.                            |
| Clustering setup  | Algorithms and hyperparameters.                                   |
| Evaluation        | Internal metrics, stability, runtime.                             |
| Artifacts         | Paths to generated figures and tables.                            |
| Notes             | Free-form observations and caveats.                               |

## File naming

```
NNNN-<task-id>-<short-name>.md
```

Example:

```
0001-FE-01-rfm-baseline.md
```

## Reproducibility checklist

Before publishing:

- [ ] Config files referenced by the experiment are committed.
- [ ] Random seeds are stored in the log.
- [ ] Environment info is stored in the log.
- [ ] Any external dataset used has its SHA-256 recorded.
- [ ] Generated figures and tables reference the experiment ID.