# ADR-0003 — Algorithm Scope: Five-Algorithm Benchmark

## Status

Accepted

## Date

2026-09-22

## Task ID

EPIC-06 / EPIC-07 / EPIC-08

## Deciders

Researcher / Mentor

## Context

The repository documentation (README.md, AGENTS.md, FE-05, FE-06, and related methodology docs) previously claimed the benchmark scope consists of four clustering algorithms: **K-Means, K-Medoids, Agglomerative Clustering, and DBSCAN**.

Investigation of the actual implementation revealed:

1. `src/customer_segmentation/clustering/kmedoids.py` contains only `raise NotImplementedError("fit_kmedoids is not implemented yet.")` — no functional implementation.
2. `configs/clustering.yaml` has `kmedoids: enabled: true` but with `metric: "TODO"` and `init: "TODO"`.
3. `AlgorithmRegistry.list_registered()` returns exactly five names: `kmeans`, `agglomerative`, `dbscan`, `gmm`, `fuzzy_cmeans`. K-Medoids is **not registered**.
4. EXP-01 through EXP-05 ran exactly **five** algorithms: K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means.
5. EPIC-06 documentation contract describes six ML documents (ML-01 through ML-06), where ML-06 covers Fuzzy C-Means and the "Algorithm Baseline" — consistent with five working adapters.
6. The `AGENTS.md` §3 table lists "4 fixed algorithms" including K-Medoids, creating a documented contradiction with the implemented system.

There is no empirical evidence that K-Medoids was ever run in any experiment. The four-algorithm claim in AGENTS.md and related documentation is inconsistent with the five-algorithm implementation.

## Decision

The benchmark algorithm scope is **five algorithms**:

1. **K-Means** (`kmeans`) — hard centroid-based clustering
2. **Agglomerative Clustering** (`agglomerative`) — hierarchical clustering with Ward linkage
3. **DBSCAN** (`dbscan`) — density-based clustering
4. **Gaussian Mixture Model** (`gmm`) — probabilistic model-based clustering
5. **Fuzzy C-Means** (`fuzzy_cmeans`) — soft/fuzzy clustering with Bezdek update equations

**K-Medoids** is explicitly **DEFERRED / OUT OF SCOPE** for the current research phase (EPIC-06 through EPIC-08).

This decision applies to:
- EPIC-06 (clustering experiment framework and adapters)
- EPIC-07 (controlled experiments: EXP-01 through EXP-05)
- EPIC-08 (stability and evaluation)

K-Medoids may be reconsidered for a future research phase (e.g., EPIC-X) via a new ADR.

## Consequences

### Easier

- Documentation is now consistent with the implemented system (185 runs across 5 algorithms).
- No misleading claim that a fourth algorithm was benchmarked when it was not.
- EPIC-08 can proceed with a clear, verified algorithm scope.
- RQ1 evaluation covers exactly the algorithms that have experimental evidence.

### Harder or Riskier

- Readers expecting a four-algorithm benchmark per earlier docs may be confused. This is mitigated by explicit documentation of the change.
- Any future claim comparing against K-Medoids literature will be incomplete. This is acceptable given the current research scope.

## Alternatives Considered

### Option A: Implement K-Medoids + Rerun EXP-01 through EXP-05

- **Estimated impact**: ~70–90 new experimental runs across 5 experiments.
- **Additional dependency**: `scikit-learn-extra` (requires ADR for new dependency).
- **New tests**: ~15–20 tests in `tests/test_ml07_kmedoids.py`.
- **Timeline**: ~2–4 weeks for implementation, testing, and reruns.
- **Decision**: Rejected for the current phase. The implementation cost is disproportionate to the research benefit, given that 185 runs on 5 algorithms already provide substantial evidence for RQ1. K-Medoids can be added in a future phase.

### Option B: Update Documentation to Reflect Five-Algorithm Scope (CHOSEN)

- **Estimated impact**: Documentation updates only; zero experimental reruns.
- **Additional dependency**: None.
- **Timeline**: ~2–3 days for documentation.
- **Decision**: Accepted. This aligns documentation with the implemented system and removes the misleading K-Medoids claim without disrupting the existing evidence base.

## Scope of This Decision

This ADR covers:
- EPIC-06 (ML-01 through ML-06 algorithm adapters)
- EPIC-07 (EXP-01 through EXP-05)
- EPIC-08 (stability and evaluation)

This ADR does NOT:
- Prevent future implementation of K-Medoids in a separate research phase
- Change the interpretation boundary for RQ1 (no "best algorithm" claim)
- Affect the validity of existing experimental results (185 runs on 5 algorithms remain valid)

## References

- `src/customer_segmentation/clustering/kmedoids.py` — placeholder only
- `src/customer_segmentation/clustering/registry.py` — `list_registered()` excludes kmedoids
- `configs/clustering.yaml` — `kmedoids: enabled: true` with `metric: "TODO"`
- EXP-01 through EXP-05 manifests — all reference exactly 5 algorithms
- `docs/research/review/METHODOLOGY_RESOLUTION_PROPOSAL.md` — analysis leading to this decision
