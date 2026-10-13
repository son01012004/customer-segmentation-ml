# DEV-08 — Visualization Dashboard: Implementation Plan

> **Mã task:** DEV-08
> **Tên:** Prototype Visualization Dashboard
> **Trạng thái:** PLAN — PHASE 1 ONLY (read-only; no code, no config, no ADR, no SYS edit, no Git op)
> **Ngày:** 2026-10-10
> **Phạm vi:** Tạo **prototype-layer** visualization dashboard dựa trên Experiment artifacts
> từ DEV-04 (clustering), DEV-05 (evaluation), DEV-06 (segmentation/profiling).
> **Does NOT** modify research-core visualization (`src/customer_segmentation/visualization/`);
> **Does NOT** implement research-grade comparison; **Does NOT** run new clustering
> experiments or recompute metrics; **Does NOT** create marketing visualizations beyond
> `REVIEW_REQUIRED` placeholder.
> **Architecture:** Option A (ADR-0005) — offline, single-machine, file-based.
> **Nguồn evidence:** `docs/system/DEV-08_DEV-09_readiness_report.md`,
> `docs/research/EPIC06_DOCUMENTATION_CONTRACT.md` §9,
> `src/customer_segmentation/prototype/{clustering,evaluation,segmentation,marketing}/manifest.py`,
> `src/customer_segmentation/prototype/{segmentation,evaluation}/scope.py`,
> `src/customer_segmentation/clustering/result.py`,
> `src/customer_segmentation/visualization/*.py`.

---

## 1. Nguồn tài liệu đã đọc

| Tài liệu | Vai trò cho DEV-08 | Sections đã đọc |
|---|---|---|
| `AGENTS.md` | Global rules (binding) | Toàn bộ |
| `docs/system/DEV-08_DEV-09_readiness_report.md` | DEV-08 readiness, constraint matrix, §6.1 evidence table | Toàn bộ |
| `docs/research/EPIC06_DOCUMENTATION_CONTRACT.md` | §9 visualization ownership boundary (EPIC-06/08/09) | §9 toàn bộ |
| `src/customer_segmentation/prototype/clustering/manifest.py` | ClusteringManifest schema (DEV-08 data source) | Toàn bộ |
| `src/customer_segmentation/prototype/evaluation/manifest.py` | EvaluationManifest schema + metrics (DEV-08 data source) | Toàn bộ |
| `src/customer_segmentation/prototype/evaluation/scope.py` | MetricName, MetricStatus, MetricReason enums | Toàn bộ |
| `src/customer_segmentation/prototype/segmentation/manifest.py` | SegmentationManifest schema: segment_sizes, profiles, characteristics (DEV-08 data source) | Toàn bộ |
| `src/customer_segmentation/prototype/segmentation/scope.py` | PROFILING_STATISTICS_SET, SegmentationStage | Toàn bộ |
| `src/customer_segmentation/prototype/segmentation/compare.py` | ComparisonReport schema (for multi-manifest comparison) | Toàn bộ |
| `src/customer_segmentation/prototype/segmentation/display.py` | Display conventions (banned words, disclaimer, table format) | Toàn bột |
| `src/customer_segmentation/prototype/evaluation/display.py` | Display conventions (banned words, metric table format) | Toàn bộ |
| `src/customer_segmentation/clustering/result.py` | ExperimentResult / ClusterResult schema | Toàn bộ |
| `src/customer_segmentation/visualization/{distributions,clustering,profiling,rfm}.py` | 4 NotImplementedError placeholders (research-core) | Toàn bộ |
| `src/customer_segmentation/prototype/marketing/manifest.py` | MarketingRecommendationManifest schema | Toàn bộ |
| `src/customer_segmentation/prototype/marketing/display.py` | Marketing display conventions (banned words, disclaimer) | Header + §1 |
| `src/customer_segmentation/prototype/segmentation/profile.py` | Feature profile compute + FeatureType detection | Toàn bộ |

---

## 2. Hiện trạng Evidence

### 2.1. Artifact existence audit

```
Glob data/**/clustering_manifest.json          → No matches
Glob data/**/evaluation_manifest.json          → No matches
Glob data/**/segmentation_manifest.json       → No matches
Glob data/**/experiment_log_*.json            → No matches
Glob data/**/*marketing*.json                 → No matches
```

**→ Kết luận:** Không có experiment artifact nào tồn tại trong `data/prototype/`.
DEV-08 phải được xây dựng dựa trên **schema đã định nghĩa** trong các
manifest module, không phải trên dữ liệu thực. Synthetic fixtures được dùng
cho unit tests. Acceptance criteria chỉ verify rằng code đọc đúng schema
(không verify real data vì không có).

### 2.2. Visualization ownership boundary (EPIC-06 §9)

| EPIC | Visualization owned | DEV-08 prototype layer |
|---|---|---|
| EPIC-06 (ML-01→ML-06) | Diagnostic / algorithm-specific (optional) | Out of scope |
| **EPIC-08** (Evaluation) | **Research comparison viz (silhouette, DBI, CH, runtime, ARI/AMI)** | **DEV-08 consumes DEV-05 manifest metrics** |
| **EPIC-09** (Profiling) | **Segment analysis (size, RFM profile, boxplots, radar/heatmap)** | **DEV-08 consumes DEV-06 segmentation manifest** |

DEV-08 prototype visualization nằm ở `src/customer_segmentation/prototype/visualization/`;
DEV-08 **không phải** research-core visualization và không tạo research-grade
silhouette plot hay comparison dashboard.

### 2.3. DEV-08 vs DEV-07 dependency

DEV-08 **không** phụ thuộc DEV-07 Phase B content (per `DEV-08_DEV-09_readiness_report.md` §2.3).
Marketing section của DEV-08 hiển thị `REVIEW_REQUIRED` placeholder (matching
DEV-07 Phase A behavior). Khi DEV-07 Phase B hoàn thành, DEV-08 mở rộng để
include actual marketing content (additive change, không phải rewrite).

---

## 3. Phạm vi (in-scope / out-of-scope)

### 3.1. In-scope

| # | Item | Data source | Reason |
|---|---|---|---|
| 1 | Cluster Distribution (bar chart) | SegmentationManifest: `segment_sizes` | segment_id + count + percentage |
| 2 | Cluster Visualization (2D scatter) | **BLOCKED** — xem §4.2 | No 2D coordinates in existing schemas |
| 3 | Feature Comparison (per-segment boxplot / heatmap) | SegmentationManifest: `profiles` (FeatureProfile entries) | feature_name + statistics per segment_id |
| 4 | Segment Profile (table view) | SegmentationManifest: `segment_sizes`, `characteristics` | SegmentSize + CharacteristicEntry |
| 5 | Metric Comparison (table + bar chart) | EvaluationManifest: `metrics` entries | silhouette/DBI/CH value + status |
| 6 | Marketing section (REVIEW_REQUIRED placeholder) | MarketingRecommendationManifest: `availability` | Phase A behavior; không cần MKT framework |

### 3.2. Out-of-scope (explicit)

| # | Item | Reason |
|---|---|---|
| 1 | Research-core visualization (silhouette comparison, elbow plot, dendrogram, BIC/AIC) | EPIC-06 §9: research comparison viz thuộc EPIC-08; DEV-08 chỉ consumes DEV-05 manifest |
| 2 | PCA / t-SNE / UMAP projection cho Cluster Visualization | Chưa có ADR; xem §4.2 — BLOCKED |
| 3 | RFM-specific plots (RFM radar, RFM heatmap) | Thuộc EPIC-09; DEV-08 chỉ dùng SegmentationManifest profiles |
| 4 | Marketing actual recommendation visualization | DEV-07 Phase B chưa hoàn thành; DEV-08 chỉ hiển thị REVIEW_REQUIRED |
| 5 | Backend / API / database / worker / queue | ADR-0005 Option A |
| 6 | Research evidence promotion | prototype artifacts không được promote |
| 7 | Running new clustering experiments | AGENTS.md §2.4 |
| 8 | Computing new evaluation metrics | AGENTS.md §2.4 |
| 9 | Modifying frozen contracts hoặc SYS files | AGENTS.md §2.11, §2.9 |
| 10 | "best / optimal / winner / recommended / ranking" | AGENTS.md §2.5 |
| 11 | Hard-coding cluster colors / labels in multiple places | AGENTS.md §3 "Visualization" guardrail |

---

## 4. Requirements-to-Data Matrix

### 4.1. Cluster Distribution

| Concern | Detail |
|---|---|
| **Business purpose** | Show segment size distribution to understand cluster balance |
| **Required input fields** | `SegmentationManifest.segment_sizes` → `{segment_id, count, percentage, percentage_base, is_noise}` |
| **Exact source** | `SegmentationManifest.segment_sizes` (list of `SegmentSize`) |
| **Schema reference** | `src/customer_segmentation/prototype/segmentation/manifest.py::SegmentSize` |
| **Aggregations** | Bar chart: segment_id (x-axis) vs count (y-axis). Noise row excluded from chart; reported separately |
| **Missing values / noise** | DBSCAN noise segment (`is_noise=True`, `segment_id=-1`) → displayed as separate "Noise" category or excluded per convention |
| **Chart type** | Vertical bar chart |
| **Can build from existing artifacts?** | **YES** — SegmentationManifest schema has `segment_sizes` with all required fields. No recompute needed. |
| **Unit-test strategy** | Synthetic `SegmentationManifest` with 3 segments + 1 noise; assert bar heights match counts |
| **Blocked?** | No |

### 4.2. Cluster Visualization (2D scatter)

| Concern | Detail |
|---|---|
| **Business purpose** | Visualize cluster geometry in 2D to assess separation and overlap |
| **Required input fields** | (a) Customer-level data: feature vectors `X` shape `(n, p)`. (b) Cluster labels `y` shape `(n,)`. (c) 2D projection coordinates `(n, 2)` |
| **Exact source** | (a) DEV-03 ML Dataset parquet (feature matrix). (b) DEV-04 cluster_labels parquet. (c) **MISSING** — no 2D coordinates in existing schemas |
| **Schema reference** | `ClusteringManifest` (DEV-04) — has `feature_set`, `n_samples`, `n_clusters`; does NOT have 2D coordinates. `ExperimentResult` — has `cluster_labels`, `n_clusters`; does NOT have 2D projection |
| **Aggregations** | Scatter: projected x vs projected y, colored by cluster label |
| **Missing values / noise** | DBSCAN noise (label=-1) → marked distinctly |
| **Can build from existing artifacts?** | **NO** — clustering and segmentation manifests do not contain 2D coordinates. No projection methodology exists in the prototype. |
| **Projection needed?** | **YES** — requires explicit methodological decision. Options: PCA (linear, fast), t-SNE (non-linear, slow), UMAP (non-linear, preserves global structure). Any choice is a methodology decision requiring ADR or owner approval per AGENTS.md §2.9 ("No silent policy changes"). |
| **Unit-test strategy** | Synthetic fixture with 20 points + 2 clusters + hardcoded PCA projection matrix; verify scatter data shape `(n, 2)` |
| **BLOCKED?** | **YES — BLOCKED** (projection methodology not defined). This chart cannot be implemented without either: (a) an approved ADR defining the projection methodology, or (b) an owner decision. All other charts can proceed. |

### 4.3. Feature Comparison

| Concern | Detail |
|---|---|
| **Business purpose** | Compare feature distributions across segments to understand segment differentiation |
| **Required input fields** | `SegmentationManifest.profiles` → list of `FeatureProfile` entries: `{segment_id, feature_name, statistics: {mean, median, std, q1, q3, min, max}}` |
| **Exact source** | `SegmentationManifest.profiles` (list of `FeatureProfile`) |
| **Schema reference** | `src/customer_segmentation/prototype/segmentation/manifest.py::FeatureProfile` |
| **Aggregations** | Heatmap: rows = feature names, columns = segment_ids, cell = `mean` value (normalized). Or grouped boxplot (if raw data available). For prototype: use pre-computed mean values from `profiles` |
| **Missing values / noise** | `FeatureProfile` has `None` for missing statistics → shown as blank cell or "N/A" |
| **Chart type** | Heatmap of normalized mean values per segment × feature; OR grouped bar chart (top 5 features) |
| **Can build from existing artifacts?** | **YES** — SegmentationManifest has full `profiles` list with statistics per segment × feature. No recompute needed. |
| **Unit-test strategy** | Synthetic `SegmentationManifest` with 3 segments × 4 features × 7 statistics; assert heatmap dimensions and cell values |
| **Note** | Values are post-preprocessing (scaled/transformed) — `preprocessing_warning` in manifest must be surfaced as chart note. Cannot use original business units |
| **Blocked?** | No |

### 4.4. Segment Profile

| Concern | Detail |
|---|---|
| **Business purpose** | Summary view of segment characteristics for interpretation |
| **Required input fields** | `SegmentationManifest.segment_sizes` (size info) + `SegmentationManifest.characteristics` (characteristic_id + description + source_features) + `SegmentationManifest.n_segments` |
| **Exact source** | `SegmentationManifest.segment_sizes`, `SegmentationManifest.characteristics`, top-level fields |
| **Schema reference** | `src/customer_segmentation/prototype/segmentation/manifest.py::CharacteristicEntry`, `::SegmentSize` |
| **Aggregations** | Per-segment card: segment_id, count, percentage, list of characteristic entries (rule + description). Group characteristics by segment_id |
| **Missing values** | `CharacteristicEntry.segment_id=-1` → noise segment (DBSCAN); excluded from characteristics table |
| **Chart type** | Structured text table (segment × characteristics); not a chart |
| **Can build from existing artifacts?** | **YES** — SegmentationManifest has both `segment_sizes` and `characteristics` |
| **Unit-test strategy** | Synthetic manifest with 3 segments, 2 characteristics each; verify table layout and grouping |
| **Blocked?** | No |

### 4.5. Metric Comparison

| Concern | Detail |
|---|---|
| **Business purpose** | Compare evaluation metrics across clustering configurations |
| **Required input fields** | `EvaluationManifest.metrics.entries` → `{silhouette: {value, status, reason, lower_is_better}, davies_bouldin: {...}, calinski_harabasz: {...}}` + `EvaluationManifest.algorithm`, `EvaluationManifest.noise_policy_used`, `EvaluationManifest.n_clusters_realized`, `EvaluationManifest.evaluation_id` |
| **Exact source** | `EvaluationManifest.metrics` (instance of `EvaluationMetricsResult`) |
| **Schema reference** | `src/customer_segmentation/prototype/evaluation/manifest.py::EvaluationMetricEntry`, `::EvaluationMetricsResult`; `scope.py::MetricName`, `MetricStatus`, `MetricReason` |
| **Aggregations** | Table: algorithm | k | noise_policy | silhouette | DBI | CH | status. Bar chart: metric value per algorithm (grouped by metric). **No ranking** — values displayed as-is |
| **Missing values** | `MetricStatus != VALID_VALUE` → display `--` or status badge; `reason` shown as tooltip |
| **Metric semantics** | silhouette ∈ [-1, 1], higher=better; DBI ∈ [0, +∞), lower=better; CH ∈ [0, +∞), higher=better. `lower_is_better` flag from `EvaluationMetricEntry` drives chart orientation |
| **Can build from existing artifacts?** | **YES** — EvaluationManifest has full metrics structure. **Multiple EvaluationManifests** (one per clustering configuration) enable comparison |
| **Unit-test strategy** | Synthetic `EvaluationManifest` with 2 configs; synthetic `EvaluationManifest` with all statuses; verify table and bar chart data |
| **Note** | Do NOT combine metrics with incompatible meanings (e.g., don't compute an aggregate score). Display each metric separately. Per EPIC-06 §9: DEV-08 does not own silhouette comparison plot (that's EPIC-08 territory); DEV-08 consumes evaluation manifests and displays them in dashboard format |
| **Blocked?** | No |

### 4.6. Marketing section (REVIEW_REQUIRED placeholder)

| Concern | Detail |
|---|---|
| **Business purpose** | Display marketing recommendations per segment |
| **Required input fields** | `MarketingRecommendationManifest.availability`, `recommendations[].availability` |
| **Exact source** | `MarketingRecommendationManifest` |
| **Schema reference** | `src/customer_segmentation/prototype/marketing/manifest.py::MarketingRecommendationManifest`, `::MarketingRecommendationEntry` |
| **Display** | If `availability == REVIEW_REQUIRED` (Phase A): show placeholder banner "Marketing recommendations: REVIEW_REQUIRED" + link to DEV-07 Phase B decision. If Phase B (availability == AVAILABLE): show per-segment recommendation table |
| **Missing data** | Phase A: only `REVIEW_REQUIRED` placeholder. Phase B: `recommendations` list with actual content |
| **Can build from existing artifacts?** | **YES** — Phase A placeholder works without MKT framework. Phase B requires DEV-07 Phase B to be completed |
| **Unit-test strategy** | Synthetic manifest with `availability=REVIEW_REQUIRED`; verify placeholder banner. Synthetic manifest with `availability=AVAILABLE` (if Phase B done); verify table |
| **BLOCKED?** | **NO** for Phase A placeholder. YES for Phase B actual content (waits for DEV-07 Phase B completion — not a blocker for DEV-08 implementation) |

---

## 5. Data Source Classification

| Data source | Exists? | Required fields present? | Accessible without new experiment? | DEV-08 chart |
|---|---|---|---|---|
| `SegmentationManifest` | **NO ARTIFACT** (schema exists) | YES: `segment_sizes`, `profiles`, `characteristics` | YES (schema-based) | Distribution, Feature Comparison, Segment Profile |
| `EvaluationManifest` | **NO ARTIFACT** (schema exists) | YES: `metrics`, `algorithm`, `noise_policy` | YES (schema-based) | Metric Comparison |
| `ClusteringManifest` | **NO ARTIFACT** (schema exists) | PARTIAL: has `n_clusters`, `algorithm`, `n_samples`; does NOT have 2D coordinates | YES (schema-based) | Metadata only |
| `MarketingRecommendationManifest` | **NO ARTIFACT** (schema exists) | YES: `availability`, `recommendations` | YES (schema-based) | Marketing placeholder |
| Dev-03 ML Dataset parquet | **MAY exist** (DEV-03 có thể đã chạy) | YES: feature matrix | YES | Cluster Visualization (BLOCKED — projection) |

**Kết luận:** 4 trong 5 chart có thể implement từ schema mà không cần experiment artifacts thực (synthetic fixtures cho tests). Cluster Visualization bị BLOCKED.

---

## 6. Architecture và Implementation Plan

### 6.1. Package structure

```
src/customer_segmentation/prototype/visualization/
├── __init__.py
├── scope.py                    # VISUALIZATION_MANIFEST_SCHEMA_VERSION, constants
├── exceptions.py              # VisualizationError
├── storage.py                 # resolve_visualization_dir (reads from dev02 storage root)
├── loaders.py                 # load_segmentation_manifest, load_evaluation_manifest,
│                               #   load_marketing_manifest (wrapper around existing loaders)
├── charts/
│   ├── __init__.py
│   ├── cluster_distribution.py  # plot_segment_sizes (bar chart)
│   ├── feature_comparison.py    # plot_feature_heatmap / plot_feature_bars
│   ├── segment_profile.py       # format_segment_profile_table (text table)
│   ├── metric_comparison.py     # plot_metric_table + plot_metric_bars
│   └── marketing_placeholder.py  # format_marketing_placeholder
├── dashboard.py                # DashboardGenerator (composes all charts)
├── display.py                  # Display helpers (format functions, no banned words)
├── logging_config.py           # Per-stage logging
└── pipeline.py                 # VisualizationPipeline (orchestrates chart generation)
```

**Nguyên tắc:**
- Mỗi chart module có public `plot_*` function (matplotlib output) và
  `format_*` function (text/JSON output cho CLI).
- `DashboardGenerator` compose tất cả charts cho một segmentation + evaluation pair.
- **Không hard-code colors / labels** — use a single color source (configurable
  via YAML). AGENTS.md §3 "Visualization" guardrail.

### 6.2. Data access layer

```python
# loaders.py — thin wrappers, reuse existing manifest loaders
from customer_segmentation.prototype.segmentation.manifest import (
    read_segmentation_manifest,
)
from customer_segmentation.prototype.evaluation.manifest import (
    read_evaluation_manifest,
)
from customer_segmentation.prototype.marketing.manifest import (
    read_marketing_manifest,
)

def load_segmentation_manifest(path: Path) -> SegmentationManifest:
    return read_segmentation_manifest(path)

def load_evaluation_manifest(path: Path) -> EvaluationManifest:
    return read_evaluation_manifest(path)

def load_marketing_manifest(path: Path) -> MarketingRecommendationManifest:
    return read_marketing_manifest(path)
```

### 6.3. Chart implementations

#### 6.3.1. Cluster Distribution (`cluster_distribution.py`)

```python
import matplotlib.pyplot as plt
import pandas as pd

def plot_segment_sizes(
    segment_sizes: list[SegmentSize],
    output_path: Path,
    *,
    title: str = "Segment Size Distribution",
    exclude_noise: bool = True,
) -> None:
    """Render segment sizes as a vertical bar chart.

    Noise segment (is_noise=True, segment_id=-1) is shown separately
    or excluded per ``exclude_noise`` flag.

    Post-preprocessing disclaimer: segment sizes reflect post-preprocessing
    data (noise policy applied per DEV-05/DEV-06).
    """
    # Filter noise if requested
    rows = [s for s in segment_sizes if not (exclude_noise and s.is_noise)]
    df = pd.DataFrame([
        {"segment_id": s.segment_id, "count": s.count, "pct": s.percentage}
        for s in rows
    ])
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(df["segment_id"].astype(str), df["count"])
    ax.set_xlabel("Segment ID")
    ax.set_ylabel("Customer Count")
    ax.set_title(title)
    for bar, pct in zip(bars, df["pct"]):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height(),
                f"{pct:.1f}%", ha="center", va="bottom", fontsize=8)
    fig.tight_layout()
    fig.savefig(output_path)
    plt.close(fig)
```

#### 6.3.2. Feature Comparison (`feature_comparison.py`)

```python
def plot_feature_heatmap(
    profiles: list[FeatureProfile],
    output_path: Path,
    *,
    statistic: str = "mean",  # which statistic to plot
    normalize: bool = True,   # z-score normalize across segments
    title: str = "Feature Comparison Across Segments (Mean, Normalized)",
) -> None:
    """Render per-segment feature means as a heatmap.

    Values are post-preprocessing (scaled/transformed). A warning annotation
    is added to the figure per ``preprocessing_warning``.
    """
    # Group profiles by segment_id, pivot to (feature_name × segment_id) matrix
    # Normalize across segments if requested
    # Render with matplotlib.imshow / seaborn.heatmap
```

**Note:** Per `SEGMENTATION_MANIFEST_SCHEMA_VERSION` note: `preprocessing_warning`
field in SegmentationManifest carries the mandatory disclaimer about
post-preprocessing values. Chart must display this warning.

#### 6.3.3. Metric Comparison (`metric_comparison.py`)

```python
def plot_metric_bars(
    manifests: list[EvaluationManifest],
    output_path: Path,
    *,
    title: str = "Metric Comparison",
) -> None:
    """Render evaluation metrics as grouped bar chart.

    One group per manifest (algorithm + k + noise_policy), three bars per
    group (silhouette, DBI, CH). DBI direction is inverted in display
    (higher = better for all three).

    No ranking. No aggregate score.
    """
    # For each manifest, extract silhouette/DBI/CH values
    # Group by evaluation_id
    # For DBI: negate or use "higher = better" display convention
    # For MISSING/NOT_APPLICABLE/COMPUTATION_ERROR: show hatched bar or gap
```

#### 6.3.4. Segment Profile (`segment_profile.py`)

```python
def format_segment_profile_table(
    manifest: SegmentationManifest,
) -> str:
    """Return a printable table of segment profiles.

    Columns: segment_id | count | pct | characteristics
    """
    # Format SegmentSize rows + CharacteristicEntry grouping
    # Banned word check (R-DEV-06-08): verify no "champion", "loyal", etc.
```

#### 6.3.5. Marketing Placeholder (`marketing_placeholder.py`)

```python
REVIEW_REQUIRED_PLACEHOLDER: Final[str] = (
    "Marketing recommendations: REVIEW_REQUIRED. "
    "Content is pending DEV-07 Phase B owner decisions. "
    "See docs/system/DEV-07_phase_b_decision_memo.md."
)

def format_marketing_placeholder(
    manifest: MarketingRecommendationManifest,
) -> str:
    if manifest.availability == "REVIEW_REQUIRED":
        return REVIEW_REQUIRED_PLACEHOLDER
    # Phase B: format actual recommendations
    # (DEV-07 Phase B must be complete first)
```

### 6.4. Dashboard generator

```python
class DashboardGenerator:
    """Compose all charts for one segmentation + evaluation pair."""

    def __init__(
        self,
        segmentation_manifest: SegmentationManifest,
        evaluation_manifests: list[EvaluationManifest] | None = None,
        marketing_manifest: MarketingRecommendationManifest | None = None,
        output_dir: Path,
    ):
        self.seg_manifest = segmentation_manifest
        self.eval_manifests = evaluation_manifests or []
        self.mkt_manifest = marketing_manifest
        self.output_dir = Path(output_dir)

    def generate(self) -> dict[str, Path]:
        """Generate all charts. Returns {chart_name: output_path}."""
        paths = {}
        paths["cluster_distribution"] = self._chart_distribution()
        paths["feature_comparison"] = self._chart_feature_comparison()
        paths["segment_profile"] = self._chart_profile()
        paths["metric_comparison"] = self._chart_metric_comparison()
        paths["marketing"] = self._format_marketing()
        return paths

    def _chart_distribution(self) -> Path:
        # calls plot_segment_sizes from cluster_distribution module
    def _chart_feature_comparison(self) -> Path:
        # calls plot_feature_heatmap from feature_comparison module
    def _chart_profile(self) -> Path:
        # calls format_segment_profile_table from segment_profile module
    def _chart_metric_comparison(self) -> Path:
        # calls plot_metric_bars from metric_comparison module
    def _format_marketing(self) -> Path:
        # calls format_marketing_placeholder from marketing_placeholder module
```

### 6.5. Error and empty-state handling

| Situation | Handling |
|---|---|
| SegmentationManifest has 0 segment_sizes | Empty chart with "No segments found" annotation |
| FeatureProfile entries all `None` for a statistic | Blank cell + "N/A" label |
| EvaluationManifest metric status != VALID_VALUE | Show `--` or status badge (VALID_VALUE / NOT_APPLICABLE / COMPUTATION_ERROR / MISSING) |
| DBSCAN noise segment present | `is_noise=True` row shown separately; excluded from feature heatmap |
| MarketingManifest availability = REVIEW_REQUIRED | Placeholder banner only |
| MarketingManifest absent (DEV-07 not run) | No marketing section, no error |
| Multiple EvaluationManifests for same clustering | Grouped bar chart; one group per manifest |
| Empty evaluation list | Metric chart skipped with note |

### 6.6. Research safety

- `research_safety.automatically_promoted_to_research = False` enforced on
  all chart metadata.
- Charts display mandatory disclaimer: "Values are post-preprocessing
  (scaled/transformed) — not directly interpretable in original business units."
- No "best / optimal / winner / recommended / ranking / aggregate" language
  in chart titles, labels, or output.
- Banned word check: run `check_no_banned_substrings` on all text outputs.

---

## 7. Proposed File Changes

### 7.1. New files

```
src/customer_segmentation/prototype/visualization/
├── __init__.py
├── scope.py                    # VISUALIZATION_SCHEMA_VERSION, DEFAULT_COLOR_PALETTE
├── exceptions.py               # VisualizationError
├── storage.py                  # resolve_visualization_dir (from dev02 storage root)
├── loaders.py                  # load_*_manifest wrappers
├── charts/
│   ├── __init__.py
│   ├── cluster_distribution.py
│   ├── feature_comparison.py
│   ├── segment_profile.py
│   ├── metric_comparison.py
│   └── marketing_placeholder.py
├── dashboard.py
├── display.py                  # Text/JSON display helpers
├── logging_config.py
└── pipeline.py

configs/dev08_visualization.yaml

scripts/dev08_run_dashboard.py   # CLI entry point

tests/test_dev08_*.py           # (see §9)
```

### 7.2. No modification to

- `src/customer_segmentation/visualization/*.py` — research-core placeholders
- `src/customer_segmentation/prototype/{clustering,evaluation,segmentation,marketing}/` — existing manifests
- `docs/system/SYS-*.md`, `docs/decisions/*.md`
- `AGENTS.md`, `.gitignore`, `pyproject.toml`
- `data/processed/`, `data/raw/`, `reports/`

---

## 8. Dependencies

- `matplotlib` — already in `pyproject.toml` (used by research-core visualization placeholders)
- `pandas` — already in `pyproject.toml`
- `numpy` — already in `pyproject.toml`
- `seaborn` — **NOT** in `pyproject.toml`; check before adding

**Constraint check:** If seaborn is not in `pyproject.toml`, use `matplotlib`
only (AGENTS.md §5: "Adding a new dependency requires adding it to
`pyproject.toml::dependencies` + ADR explaining why"). If seaborn is already
present, use it; if not, use pure matplotlib.

Let me verify seaborn status in pyproject.toml:

```bash
# TBD: grep seaborn from pyproject.toml
```

If seaborn absent → pure matplotlib implementation.

---

## 9. Test Plan

### 9.1. Unit test strategy

| Test | Fixture | Asserts |
|---|---|---|
| `test_cluster_distribution.py` | Synthetic `SegmentationManifest`: 3 segments + 1 noise | Bar heights match counts; noise excluded/included correctly |
| `test_feature_comparison.py` | Synthetic `SegmentationManifest`: 2 segments × 3 features × 5 stats | Heatmap dimensions `(n_features, n_segments)`; z-score normalization range |
| `test_segment_profile.py` | Synthetic `SegmentationManifest`: 3 segments, 4 characteristics | Table contains all segment IDs; characteristic grouping correct |
| `test_metric_comparison.py` | 2 synthetic `EvaluationManifest` with varying statuses | Table rows match manifests; bar values match metric values; MISSING handled |
| `test_marketing_placeholder.py` | Synthetic `MarketingRecommendationManifest` Phase A + Phase B | Phase A: placeholder banner. Phase B: actual table |
| `test_banned_words.py` | All display/format function outputs | No banned substrings outside disclaimer |
| `test_empty_state.py` | Empty segment_sizes, missing metrics | Graceful degradation with "N/A" annotations |

### 9.2. Integration test strategy

- Read actual manifests from `src/customer_segmentation/prototype/*/manifest.py`
  schema (no real data needed; use synthetic fixtures matching schema).
- Verify DashboardGenerator produces output files with correct extensions.
- Verify `research_safety` metadata in chart annotations.

### 9.3. Research safety tests

```python
def test_no_banned_words_in_display():
    from customer_segmentation.prototype.visualization.display import (
        check_no_banned_substrings,
    )
    # ... generate display output ...
    banned = check_no_banned_substrings(output)
    assert banned == [], f"Banned words found: {banned}"
```

---

## 10. Task Sequence với Dependencies

```
Phase 1: Foundation (no experiment artifacts needed)
├── 1.1. Create package structure: scope.py, exceptions.py, __init__.py
├── 1.2. Create storage.py + loaders.py (wrapper around existing loaders)
├── 1.3. Create logging_config.py (per-stage logging)
├── 1.4. Create configs/dev08_visualization.yaml
└── 1.5. Create scripts/dev08_run_dashboard.py (CLI)

Phase 2: Chart modules (independent, parallel)
├── 2.1. Implement cluster_distribution.py + tests
├── 2.2. Implement segment_profile.py (table) + tests
├── 2.3. Implement metric_comparison.py + tests
├── 2.4. Implement feature_comparison.py + tests
├── 2.5. Implement marketing_placeholder.py + tests

Phase 3: Composition
├── 3.1. Implement dashboard.py (DashboardGenerator)
├── 3.2. Implement display.py (text/JSON helpers)
├── 3.3. Implement pipeline.py (orchestrator)
└── 3.4. Full integration test

Phase 4: Validation
├── 4.1. pytest tests/test_dev08_*.py
├── 4.2. ruff check src/customer_segmentation/prototype/visualization/
├── 4.3. black --check src/customer_segmentation/prototype/visualization/
└── 4.4. Verify no banned words in any output

Phase 5: Real-data acceptance (after experiment artifacts exist)
├── 5.1. Run dashboard on real SegmentationManifest + EvaluationManifest (DEV-04/05/06 must complete first)
├── 5.2. Verify charts consume real manifest data
└── 5.3. Acceptance criteria check against real data

BLOCKED Task (cannot start without owner decision):
└── B1. Cluster Visualization (2D scatter)
    Requires: Approved ADR defining projection methodology (PCA / t-SNE / UMAP)
    Until then: include stub with "BLOCKED: awaiting projection methodology decision" note
```

---

## 11. Risks và Unresolved Decisions

| Risk / Decision | Type | Impact | Mitigation |
|---|---|---|---|
| **Cluster Visualization: projection methodology undefined** | BLOCKER | Cannot implement 2D scatter | Owner decision required: PCA (linear, fast) or t-SNE or UMAP. Until then, chart shows "BLOCKED" note |
| **No experiment artifacts exist** | Risk | Cannot verify real-data acceptance | Build to schema + synthetic fixtures. Real-data test waits for DEV-04/05/06 completion |
| **seaborn not in pyproject.toml** | Risk | May need pure matplotlib | Use pure matplotlib if seaborn absent. No new dependency without ADR |
| **DEV-07 Phase B content not available** | Risk | Marketing section is placeholder only | Phase A placeholder sufficient. Phase B is additive change |
| **Feature comparison: post-preprocessing values** | Design | Values not in original business units | Mandatory disclaimer in chart. `preprocessing_warning` from manifest surfaced |
| **Metric Comparison: multiple manifests** | Design | Need to load multiple EvaluationManifests | `load_evaluation_manifests_for_clustering_id()` — enumerate manifests by clustering_id |

---

## 12. Acceptance Checklist

| # | Criterion | Evidence | Status |
|---|---|---|---|
| AC-1 | Cluster Distribution bar chart implemented | `plot_segment_sizes()` in `cluster_distribution.py` + test | **CAN IMPLEMENT** |
| AC-2 | Feature Comparison heatmap implemented | `plot_feature_heatmap()` in `feature_comparison.py` + test | **CAN IMPLEMENT** |
| AC-3 | Segment Profile table implemented | `format_segment_profile_table()` in `segment_profile.py` + test | **CAN IMPLEMENT** |
| AC-4 | Metric Comparison table + bar chart implemented | `plot_metric_bars()` + `format_metric_table()` in `metric_comparison.py` + test | **CAN IMPLEMENT** |
| AC-5 | Marketing placeholder (REVIEW_REQUIRED) implemented | `format_marketing_placeholder()` in `marketing_placeholder.py` + test | **CAN IMPLEMENT** |
| AC-6 | Cluster Visualization 2D scatter | **BLOCKED** — projection methodology undefined | **BLOCKED** |
| AC-7 | All charts consume real Experiment manifests | Charts read from `SegmentationManifest` / `EvaluationManifest` schemas | Schema-based (real data needs DEV-04/05/06 completion) |
| AC-8 | No banned words in output | `check_no_banned_substrings()` passes on all display outputs | Unit test enforces |
| AC-9 | Research safety metadata on charts | `research_safety.automatically_promoted_to_research=False` on chart metadata | Unit test |
| AC-10 | pytest tests pass | `pytest tests/test_dev08_*.py` | After Phase 4 |
| AC-11 | ruff / black clean | `ruff check` + `black --check` | After Phase 4 |

---

## 13. Commands và Checks

```bash
# Phase 4 validation
pytest tests/test_dev08_*.py -v
ruff check src/customer_segmentation/prototype/visualization/
black --check src/customer_segmentation/prototype/visualization/
ruff check src/customer_segmentation/prototype/visualization/charts/

# Real-data acceptance (after DEV-04/05/06 complete)
python scripts/dev08_run_dashboard.py \
  --segmentation-id <segmentation_id> \
  --output-dir data/prototype/datasets/<dataset_id>/visualization/
```

---

## 14. Smallest Next Implementation Task

**Task 1.1: Create `prototype/visualization/` package foundation**

Create the minimal foundation:

```
src/customer_segmentation/prototype/visualization/
├── __init__.py           # PUBLIC API: all public classes/functions
├── scope.py              # VISUALIZATION_SCHEMA_VERSION = "1.0.0", DEFAULT_COLOR_PALETTE
├── exceptions.py         # VisualizationError
└── charts/
    └── __init__.py
```

This establishes the package without any chart logic, providing the
scaffolding for all subsequent chart modules. No experiment artifacts needed.
No dependency on real data.

---

*Plan status: DRAFT — chờ owner review trước khi implement. Cluster
Visualization (AC-6) bị BLOCKED; tất cả chart khác có thể implement ngay.*
