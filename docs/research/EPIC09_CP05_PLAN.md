# CP-05 — Segment Interpretability & Business Relevance Evaluation (PLAN)

> **Mục đích:** Tài liệu này là **implementation PLAN** cho CP-05 (EPIC-09).
> Đây KHÔNG phải implementation, KHÔNG phải source code, KHÔNG phải
> runner, KHÔNG phải test.
>
> **TUYỆT ĐỐI KHÔNG** trong bước này:
> - Chạy code / tạo file / sửa file ngoài file plan này.
> - Implement source package.
> - Implement runner.
> - Implement tests.
> - Chạy experiment mới.
> - Thay đổi methodology.
> - Commit / push / PR.
>
> Sau khi plan được viết xong, **STOP** để mentor review và approve.

---

## 1. Objective

### 1.1. Mục tiêu tổng quát

CP-05 đánh giá **khả năng diễn giải** và **khả năng ứng dụng phân tích**
của các Customer Segment hiện có, dựa trên evidence surface đã được
CP-01 → CP-04 (và EXP-05 nếu có) sản xuất ra.

CP-05 trả lời các câu hỏi:

1. Mỗi segment có **đặc điểm phân biệt** đủ rõ không (distinctiveness)?
2. Profile của segment có **dễ hiểu** không (interpretability)?
3. Các feature trong cùng segment có **nhất quán** không (behavioral
   consistency)?
4. Segment có **quy mô hợp lý** để phân tích không (segment size)?
5. Bằng chứng về **stability** hiện có là gì (stability)?
6. Dataset có hỗ trợ **business interpretation** cho segment không
   (business relevance)?

### 1.2. Mục tiêu cụ thể (output)

CP-05 sản xuất ra ba output chính:

1. **Interpretability Report** — đánh giá khả năng diễn giải của
   segment (trả lời Q1, Q2, Q3).
2. **Business Relevance Analysis** — đánh giá dataset có support
   business interpretation ở mức nào (trả lời Q6).
3. **Final Segment Definition** — definition rõ ràng cho TỪNG segment
   (KHÔNG chọn segment tốt nhất).

### 1.3. Ranh giới cứng

CP-05 KHÔNG:

- Chọn segment tốt nhất / phân khúc quan trọng nhất.
- Tạo algorithm ranking (K-Means vs DBSCAN, ...).
- Đặt tên segment mới — chỉ đánh giá các tên đã có từ CP-04.
- Tạo marketing strategy / campaign targeting / business action plan.
- Composite scoring / ranking khung đánh giá segment.
- Re-run experiment / re-fit model / re-impute.
- Modify CP-01 → CP-04 artifacts.

CP-05 CHỈ:

- Đọc (read-only) CP-01 → CP-04 evidence.
- Phân loại (categorize) segment theo status taxonomy rõ ràng.
- Tổng hợp evidence vào Final Segment Definition (per-segment).
- Ghi limitation / pending review rõ ràng.

---

## 2. Scope

### 2.1. In scope

- Đánh giá **6 trục** (evaluation axes):
  - Distinctiveness.
  - Interpretability.
  - Behavioral consistency.
  - Segment size.
  - Stability.
  - Business relevance.
- **Final Segment Definition** (per-segment) aggregating 6 trục đánh
  giá + CP-01 → CP-04 evidence.
- Methodology gate tests: NO forbidden tokens
  ("champion", "vip", "loyal", "best", "winner", "optimal",
  "recommended", "at-risk", ...).
- CP-01 → CP-04 consistency check (cluster customer counts,
  percentile values match).
- EXP-03 limitation handling (5 units = `NOT_AVAILABLE`).
- DBSCAN noise không coi là Customer Segment.
- Read-only verification (SHA-256 của CP-01 → CP-04 artifacts không
  đổi trước / sau CP-05 run).
- Lint / format / determinism.

### 2.2. Out of scope (deferred to future work)

- Marketing Recommendation cụ thể (campaign, promotion, ...).
- Customer Lifetime Value (CLV) prediction.
- Churn / Retention prediction.
- Customer Loyalty index construction.
- Customer intent / next-purchase prediction.
- Profitability / margin analysis.
- RFM-only vs RFM Extended comparison (ADR-0004 future work).
- K-Medoids inclusion (per ADR-0003, OUT OF SCOPE).
- Cross-algorithm segment taxonomy mapping.
- ARI / AMI computation (deferred to EPIC-08).
- Statistical significance testing (no methodology approval).
- PCA / UMAP multivariate visualization.

### 2.3. Methodology scope (locked)

CP-05 giữ nguyên methodology của các phase trước:

| Item | Status (locked) | Source |
|---|---|---|
| Algorithm scope | 5 algorithms (K-Means, Agglomerative, DBSCAN, GMM, Fuzzy C-Means). K-Medoids OUT OF SCOPE. | ADR-0003 |
| Feature set | RFM Extended (14 features) trên UCI Online Retail. | FE-05, FE-06 |
| Preprocessing | FE-06 C7 (median imputation + Yeo-Johnson + RobustScaler). | FE-06 |
| Analysis unit | 10 units = 5 algorithms × 2 conditions (EXP-01 working-default + EXP-03 working-selected). | CP-01 §3.2 |
| Feature values | RAW interpretable values (KHÔNG dùng Yeo-Johnson + RobustScaler values). | CP-02 §4 |
| Direction thresholds | ±10% (analytical default). | CP-02 §4.4 |
| CP-03 classification thresholds | WORKING_ANALYTICAL_THRESHOLD (50%, 15%, 0.7, 0.5). | CP-03 §4.5 |
| Decision status taxonomy | verbatim từ CP-04 unit_provenance.csv. | CP-04 |
| DBSCAN noise | Tách riêng; KHÔNG phải Customer Segment. | CP-04 §3.2 |

CP-05 KHÔNG promote bất kỳ WORKING_* nào thành FINAL.

---

## 3. Existing Evidence (read-only inputs)

CP-05 đọc thẳng evidence từ các artifact đã tồn tại. KHÔNG recompute.

### 3.1. CP-01 evidence

| Artifact | Path | Use trong CP-05 |
|---|---|---|
| `cp01_cluster_size_table.csv` | `reports/profiling/cp01/` | Per-(unit, cluster) customer count + percentage. |
| `cp01_noise_summary.csv` | `reports/profiling/cp01/` | DBSCAN noise fact (n_customers, pct). |
| `cp01_distribution_indicators.csv` | `reports/profiling/cp01/` | largest/smallest/ratio/range/deviation. |
| `cp01_unit_provenance.csv` | `reports/profiling/cp01/` | units × configuration_status × labels_persisted. |

### 3.2. CP-02 evidence

| Artifact | Use trong CP-05 |
|---|---|
| `cp02_feature_profile_table.csv` | Per-(unit, cluster, feature) count, median, P25, P75, n_missing. |
| `cp02_relative_comparison.csv` | rel_diff_median_pct, rel_diff_mean_pct, reference_status. |
| `cp02_behavioral_interpretation.csv` | direction (HIGHER / LOWER / COMPARABLE / ZERO_REFERENCE / NA). |
| `cp02_unit_provenance.csv` | unit configuration_status. |

### 3.3. CP-03 evidence

| Artifact | Use trong CP-05 |
|---|---|
| `cp03_segment_comparison_matrix.csv` | 462 rows × 26 cols aggregating CP-02 + IQR overlap. |
| `cp03_distinguishing_features.csv` | per-(unit, feature) effect_range_rel_pct, iqr_overlap_mean, classification. |
| `cp03_overlap_analysis.csv` | pairwise IQR overlap coefficient. |
| `cp03_unit_provenance.csv` | unit configuration_status. |

### 3.4. CP-04 evidence

| Artifact | Use trong CP-05 |
|---|---|
| `cp04_segment_profiles.csv` | per-(unit, cluster) SegmentProfile (size, RFM tiers, behavioural profile). |
| `cp04_segment_naming.csv` | segment name, modifier, naming rationale, naming_status. |
| `cp04_segment_evidence.csv` | per-(profile, feature) evidence rows. |
| `cp04_iqr_overlap.csv` (nếu có) | IQR overlap với OVERALL per (profile, feature). |
| `cp04_cp01_consistency.csv` | cluster customer counts match CP-01. |
| `cp04_unit_provenance.csv` | unit labels_persisted. |
| `cp04_runner_manifest.json` | SHA-256 của tất cả CP-01/02/03 inputs. |

### 3.5. EXP-05 evidence (optional read)

CP-05 có thể đọc (read-only) để báo cáo **raw labels availability**:

| Artifact | Use trong CP-05 |
|---|---|
| `reports/exp05/exp05_cluster_labels.parquet` | raw cluster labels across 75 EXP-05 runs. CP-05 KHÔNG tự compute ARI/AMI. |

CP-05 KHÔNG compute ARI / AMI / Hungarian. CP-05 chỉ báo cáo:
- EXP-05 Block R `REPRODUCIBILITY_VERIFIED` (cùng seed → cùng labels).
- Block S, Block N raw labels có sẵn nhưng ARI/AMI computation
  **DEFERRED TO EPIC-08**.

### 3.6. SHA-256 chain

CP-05 runner GHI SHA-256 của tất cả inputs (CP-01 → CP-04 + EXP-05
nếu đọc) vào `cp05_runner_manifest.json`. Runner verify SHA-256
identical trước / sau run (read-only guarantee).

---

## 4. Analysis Units

CP-05 giữ nguyên **10 analysis units** từ CP-01 → CP-04:

| Condition | Source | units |
|---|---|---|
| EXP-01 working-default | `cluster_labels_EXP-01-{algo}_rep4.parquet` | 5 (kmeans, agglomerative, dbscan, gmm, fuzzy_cmeans) |
| EXP-03 working-selected | `exp03_selected_configurations.csv` | 5 (NOT_AVAILABLE) |

Mỗi unit có:

- `unit_id` (verbatim từ CP-04).
- `algorithm` (kmeans / agglomerative / dbscan / gmm / fuzzy_cmeans).
- `source_experiment` (EXP-01 hoặc EXP-03).
- `configuration_status` (verbatim từ `cp04_unit_provenance.csv`):
  - EXP-01: `WORKING_DEFAULT`.
  - EXP-03 kmeans: `TIED_WORKING_SELECTED`.
  - EXP-03 others: `WORKING_SELECTED`.
- `labels_persisted` (True / False).

CP-05 KHÔNG tạo analysis unit mới; KHÔNG merge / split unit.

---

## 5. Distinctiveness Evaluation

### 5.1. Mục tiêu

Đánh giá từng segment có **đặc điểm phân biệt** đủ rõ để được xem là
một segment "có ý nghĩa phân tích" hay không.

### 5.2. Inputs

- `cp03_distinguishing_features.csv`: per-(unit, feature) classification
  (HIGH_DIFFERENCE_OBSERVED, MODERATE_DIFFERENCE_OBSERVED,
  HIGH_OVERLAP, LOW_DIFFERENCE_OBSERVED, NOT_ASSESSABLE).
- `cp03_segment_comparison_matrix.csv`: per-(unit, cluster, feature)
  classification thuộc về cluster.

### 5.3. Methodology

Với mỗi segment (cluster không phải noise trong EXP-01 unit):

1. Lấy tập features có classification tại (unit):
   - Nếu `n_clusters_assessable ≥ MIN_ASSESSABLE_CLUSTERS (2)`:
     phân loại theo HIGH / MODERATE / HIGH_OVERLAP / LOW_DIFFERENCE / NOT_ASSESSABLE.
   - Nếu `n_clusters_assessable < 2`: feature = `NOT_ASSESSABLE`.

2. Với mỗi cluster, xác định "this cluster contributes to distinction
   in feature F" nếu:
   - Feature F có classification HIGH_DIFFERENCE_OBSERVED tại (unit).
   - Cluster's median ≠ OVERALL median hơn
     `WORKING_HIGH_DIFFERENCE_EFFECT_PCT` (50%) theo
     `effect_range_rel_pct`.
   - Cluster's IQR overlap với OVERALL ≤
     `WORKING_MODERATE_OVERLAP_MEAN` (0.5).

3. Đếm `n_distinguishing_features = |{features cluster contributes to
   distinction}|`.

4. Phân loại status:
   - `DISTINCT` — `n_distinguishing_features ≥ 2`.
   - `LIMITED_DISTINCTIVENESS` — `n_distinguishing_features == 1`.
   - `NOT_DISTINCT` — `n_distinguishing_features == 0` VÀ có ≥ 1 feature
     HIGH_OVERLAP.
   - `NOT_ASSESSABLE` — không có feature nào `n_clusters_assessable ≥ 2`.

### 5.4. Hard constraints

- KHÔNG tạo composite score (ví dụ: weighted sum của effect range).
- KHÔNG ranking giữa các segment (segment A "distinct hơn" segment B
  là ranking).
- KHÔNG threshold mới ngoài `WORKING_ANALYTICAL_THRESHOLD` từ CP-03.
- KHÔNG nhân đôi feature redundancy (BasketSize ↔ AverageQuantity:
  chỉ tính 1 evidence độc lập — kế thừa từ CP-04).

### 5.5. Output schema

`cp05_distinctiveness_evaluation.csv`:

```
unit_id, algorithm, source_experiment, cluster_id, cluster_label,
configuration_status, labels_persisted,
n_features_assessable, n_distinguishing_features,
n_high_overlap_features, distinctiveness_status,
supporting_features (semicolon-separated), rationale
```

### 5.6. Limitations cần ghi nhận

- DBSCAN clusters rất nhỏ (n ≤ 10) có std / P25 / P75 NaN → `NOT_ASSESSABLE`
  cho nhiều features. CP-05 ghi nhận nhưng KHÔNG ép status.
- Distinctiveness phụ thuộc classification thresholds (CP-03 working
  defaults) — thay đổi thresholds sẽ thay đổi status.

---

## 6. Interpretability Evaluation

### 6.1. Mục tiêu

Đánh giá từng segment có profile "dễ hiểu" không, dựa trên CP-04
naming framework.

### 6.2. Inputs

- `cp04_segment_naming.csv`: segment name, modifier, naming rationale,
  naming_status (`NAMED`, `COMPARATIVE`, `NOT_AVAILABLE`, `NOISE`).
- `cp04_segment_evidence.csv`: per-(profile, feature) evidence rows.
- `cp02_behavioral_interpretation.csv`: direction profile (cho
  over-inference check).
- `cp03_distinguishing_features.csv`: HIGH_DIFFERENCE_OBSERVED features
  (cho modifier grounding).

### 6.3. Methodology

Với mỗi segment (cluster có `labels_persisted=True`):

1. Lấy `naming_status` từ CP-04:
   - `NAMED` → tiếp tục đánh giá.
   - `COMPARATIVE` → phân loại `COMPARATIVE` (CP-04 §4.3 fallback).
   - `NOT_AVAILABLE` → phân loại `NOT_AVAILABLE` (giữ nguyên CP-04).
   - `NOISE` → `NOT_APPLICABLE` (DBSCAN noise ≠ segment).

2. Với `NAMED`, kiểm tra **rationale groundedness**:
   - Rationale phải reference ít nhất 1 feature direction từ CP-02
     (evidence-backed).
   - Rationale không được là boilerplate (template không có feature
     reference).
   - Modifier (nếu có) phải ứng với HIGH_DIFFERENCE_OBSERVED feature
     trong CP-03.

3. Kiểm tra **profile complexity**:
   - Đếm features với direction ∈ {HIGHER, LOWER} trong segment
     (không tính ZERO_REFERENCE / NA / COMPARABLE).
   - Nếu n > 6: profile phức tạp, dễ khó diễn giải ngắn gọn.

4. Kiểm tra **over-inference markers**:
   - Không có forbidden tokens trong segment name và rationale
     (covered by CP-04 methodology gate).
   - KHÔNG có "loyal", "champion", "VIP", "at-risk", "best customer",
     "high-value customer", "promising", "declining" trong rationale
     (CP-05 thêm rule này ngoài CP-04's existing gate).

5. Phân loại status:
   - `HIGH_INTERPRETABILITY` — `NAMED` + rationale grounded + modifier
     grounded + n_distinguishing ≤ 6 + no over-inference markers.
   - `INTERPRETABLE` — `NAMED` + rationale grounded + modifier grounded
     + n_distinguishing ≤ 6 + no over-inference markers (một hoặc nhiều
     condition trên có thể flexible; rationale phải grounded).
   - `PARTIALLY_INTERPRETABLE` — `NAMED` + rationale partially grounded
     HOẶC n_distinguishing > 6 (complex).
   - `LIMITED_INTERPRETABILITY` — `NAMED` + rationale generic / không
     feature reference.
   - `COMPARATIVE` — CP-04 status `COMPARATIVE`.
   - `NOT_AVAILABLE` — CP-04 status `NOT_AVAILABLE`.
   - `NOT_APPLICABLE` — CP-04 status `NOISE` (DBSCAN noise).

### 6.4. Hard constraints

- KHÔNG tự đặt tên mới cho segment.
- KHÔNG ranking các segment theo interpretability (segment A
  "hiểu được hơn" segment B là ranking).
- KHÔNG tạo "interpretability score" (composite).
- KHÔNG threshold cứng cho "complex profile" — chỉ **WARNING** flag.

### 6.5. Output schema

`cp05_interpretability_evaluation.csv`:

```
unit_id, algorithm, source_experiment, cluster_id, cluster_label,
naming_status (CP-04), segment_name (CP-04), n_modifiers (CP-04),
n_features_higher_or_lower, n_features_comparable, n_features_na,
rationale_grounded (bool), modifier_grounded (bool),
complexity_flag (bool), over_inference_markers (bool),
interpretability_status, supporting_evidence, limitations
```

### 6.6. Limitations cần ghi nhận

- Subjective: "rationale grounded" là rule-based heuristic, không phải
  ngữ nghĩa sâu.
- DBSCAN small clusters: rationale có thể dựa trên ít feature evidence
  → `LIMITED_INTERPRETABILITY` phổ biến hơn.

---

## 7. Behavioral Consistency Evaluation

### 7.1. Mục tiêu

Kiểm tra trong cùng một segment, các feature có **nhất quán** với
naming framework của CP-04 hay không. Phát hiện mâu thuẫn giữa RFM
tier và behavioral modifier.

### 7.2. Inputs

- `cp04_segment_naming.csv`: segment name (RFM tiers + behavioural
  modifiers) + rationale.
- `cp02_behavioral_interpretation.csv`: direction cho 14 features.
- `cp03_distinguishing_features.csv`: HIGH_DIFFERENCE_OBSERVED features
  (cho modifier grounding).
- `cp04_segment_evidence.csv`: per-(profile, feature) evidence.

### 7.3. Methodology

Với mỗi segment có `naming_status = NAMED`:

1. **RFM tier grounding**:
   - Từ segment name (CP-04), tách RecencyTier / FrequencyTier /
     MonetaryTier.
   - Lấy direction của Recency / Frequency / Monetary từ
     `cp02_behavioral_interpretation.csv` tại (unit, cluster).
   - So khớp:
     - `Recent` ↔ direction = LOWER (Recency thấp hơn population).
     - `Older` ↔ direction = HIGHER.
     - `Mixed` ↔ direction = COMPARABLE / NA.
     - `Frequent` ↔ direction = HIGHER.
     - `Occasional` ↔ direction = LOWER.
     - `HighValue` ↔ direction = HIGHER.
     - `LowValue` ↔ direction = LOWER.
   - Rule: nếu direction ≠ mapping → RFM tier `INCONSISTENT`.

2. **Modifier grounding**:
   - Với mỗi behavioural modifier trong segment name
     (`LongTenured` / `IrregularCadence` / `Bulk` / `Active`):
     - Kiểm tra theo CP-04 §4.2 rules.
     - Cụ thể:
       - `LongTenured` ↔ TenureDays direction = HIGHER VÀ feature
         classification = HIGH_DIFFERENCE_OBSERVED.
       - `IrregularCadence` ↔ PurchaseIntervalStd direction = HIGHER VÀ
         classification = HIGH_DIFFERENCE_OBSERVED.
       - `Bulk` ↔ TotalQuantity direction = HIGHER VÀ Monetary direction =
         HIGHER VÀ cả hai HIGH_DIFFERENCE_OBSERVED.
       - `Active` ↔ ActiveDays direction = HIGHER VÀ classification =
         HIGH_DIFFERENCE_OBSERVED VÀ Frequency direction ≠ ActiveDays
         direction.

3. **RFM-behavioural cross-check**:
   - Nếu MonetaryTier = `HighValue` nhưng RecencyTier = `Recent` và
     TenureDays direction = LOWER → flag inconsistency (new customer
     với high value hiếm gặp). KHÔNG tự sửa tên segment; chỉ flag.

4. **NaN handling**:
   - PurchaseIntervalMean / Std có structural NaN ở clusters n ≤ 1
     invoice. Nếu segment name có `IrregularCadence` mà direction =
     NA (do NaN) → MODIFIER `UNRESOLVED` (KHÔNG `INCONSISTENT`).

5. Phân loại status:
   - `CONSISTENT` — RFM tiers grounded + modifiers grounded + no cross-
     check inconsistency.
   - `PARTIALLY_CONSISTENT` — RFM tiers grounded + ít nhất 1 modifier
     grounded + có ≥1 unresolved flag.
   - `MODIFIER_INCONSISTENT` — RFM tiers grounded + ≥1 modifier
     INCONSISTENT.
   - `RFM_INCONSISTENT` — ≥1 RFM tier INCONSISTENT.
   - `NOT_ASSESSABLE` — direction NA ở 2+ features quyết định RFM tier.
   - `NOT_APPLICABLE` — naming_status ≠ NAMED.

### 7.4. Hard constraints

- KHÔNG tự sửa lại segment name (CP-04 naming framework là owned by
  CP-04).
- KHÔNG tạo composite score.
- KHÔNG gọi segment "inconsistent" theo nghĩa negative judgement
  (chỉ flag evidence).

### 7.5. Output schema

`cp05_behavioral_consistency_evaluation.csv`:

```
unit_id, algorithm, source_experiment, cluster_id, cluster_label,
naming_status, segment_name, recency_tier, frequency_tier,
monetary_tier, modifiers,
recency_tier_grounded (bool), frequency_tier_grounded (bool),
monetary_tier_grounded (bool),
modifier_<name>_grounded (bool per modifier),
n_inconsistencies, cross_check_flags (semicolon-separated),
consistency_status, supporting_evidence, limitations
```

### 7.6. Limitations cần ghi nhận

- Naming framework của CP-04 dùng ±10% threshold cho RFM tiers. Nếu
  mentor thay đổi threshold thì consistency status cũng thay đổi.
- DBSCAN small clusters (n ≤ 10) có structural NaN → nhiều
  MODIFIER `UNRESOLVED`. CP-05 không sửa — chỉ flag.

---

## 8. Segment Size Evaluation

### 8.1. Mục tiêu

Báo cáo quy mô segment và flag các case quá nhỏ để phân tích
statistical reliability.

### 8.2. Inputs

- `cp01_cluster_size_table.csv`: n_customers, pct_of_assigned,
  pct_of_total, relative_size_ratio.
- `cp01_noise_summary.csv`: noise fact (DBSCAN).

### 8.3. Methodology

Với mỗi segment (non-noise cluster):

1. Lấy `n_customers`, `pct_of_total` (denominator bao gồm noise cho
   DBSCAN), `pct_of_assigned` (denominator không bao gồm noise).

2. Phân loại theo **`WORKING_ANALYTICAL_SIZE_BAND`** (cần mentor
   review trước khi FINAL):

   - `DOMINANT` — `pct_of_assigned ≥ 50%`.
   - `LARGE` — `25% ≤ pct_of_assigned < 50%`.
   - `MEDIUM` — `5% ≤ pct_of_assigned < 25%`.
   - `SMALL` — `1% ≤ pct_of_assigned < 5%`.
   - `VERY_SMALL` — `pct_of_assigned < 1%`.

3. **`STATISTICAL_RELIABILITY_FLAG`** (warning, không phải status):
   - `LOW` — `n_customers < 30` (Central Limit Theorem rough heuristic;
     KHÔNG phải research-grade threshold).
   - `ADEQUATE` — `n_customers ≥ 30`.

4. **DBSCAN cross-check**:
   - Với DBSCAN, báo cáo `pct_of_total` (gồm noise) riêng vì
     denominator khác.

### 8.4. Hard constraints

- KHÔNG tạo threshold mới cho "segment quá nhỏ" / "segment quá lớn"
  — các band trên là `WORKING_ANALYTICAL_SIZE_BAND`, cần mentor
  review trước khi promote.
- KHÔNG tự sửa bands để ép PASS.
- KHÔNG tạo "size score" (composite).
- KHÔNG dùng threshold để loại segment ra khỏi Final Definition.

### 8.5. Output schema

`cp05_segment_size_evaluation.csv`:

```
unit_id, algorithm, source_experiment, cluster_id, cluster_label,
n_customers, pct_of_assigned, pct_of_total, relative_size_ratio,
size_band (WORKING_ANALYTICAL_SIZE_BAND), statistical_reliability_flag,
n_noise_customers (DBSCAN only), noise_pct_of_total (DBSCAN only),
evidence_source, limitations
```

### 8.6. Limitations cần ghi nhận

- Bands này là analytical defaults. Mentor có thể promote thành
  research-grade sau khi review.
- `n_customers < 30` warning dựa trên CLT heuristic, không phải
  research-grade.
- DBSCAN có thể có rất nhiều cluster `VERY_SMALL` — đây là expected
  pattern, không phải bug.

---

## 9. Stability Evaluation

### 9.1. Mục tiêu

Báo cáo **availability** và **nature** của stability evidence hiện có
cho mỗi segment. CP-05 KHÔNG tự compute ARI / AMI.

### 9.2. Phân biệt cứng: Reproducibility vs Stability

| Concept | Definition | Source |
|---|---|---|
| **Reproducibility** | Same seed + same config + same input → identical cluster labels across repeats. | EXP-05 Block R. |
| **Seed Stability** | Cluster labels across different seeds (label-alignment metrics: ARI, AMI). | EXP-05 Block S; ARI/AMI deferred to EPIC-08. |
| **Perturbation Robustness** | Cluster labels under feature-space perturbation (sigma ≠ 0). | EXP-05 Block N; ARI/AMI deferred to EPIC-08. |

CP-05 KHÔNG gọi một segment `STABLE` chỉ dựa trên Block R
(reproducibility chỉ chứng minh determinism, không phải stability
under variation).

### 9.3. Inputs

- `exp05_reproducibility_results.csv`: Block R per-algorithm
  reproducibility status.
- `exp05_seed_sweep.csv` (nếu có): Block S raw labels availability.
- `exp05_noise_perturbation.csv` (nếu có): Block N raw labels
  availability.
- CP-01/02/03/04 evidence để map segment → algorithm.

### 9.4. Methodology

Với mỗi segment (cluster):

1. Lấy algorithm. Tra `exp05_reproducibility_results.csv` cho
   algorithm đó.
   - Nếu `REPRODUCIBILITY_VERIFIED` → reproducibility flag
     `VERIFIED`.
   - Ngược lại → `NOT_VERIFIED` hoặc `NOT_APPLICABLE`.

2. Tra `exp05_seed_sweep.csv` cho algorithm ∈ {K-Means, GMM, Fuzzy
   C-Means}:
   - Nếu có ≥ 5 seeds với raw labels → seed_stability status
     `RAW_EVIDENCE_AVAILABLE_NO_METRIC` (ARI/AMI chưa compute).
   - Nếu có < 5 seeds → `PARTIAL_RAW_EVIDENCE`.
   - Nếu không có → `NOT_AVAILABLE`.

3. Tra `exp05_noise_perturbation.csv` cho algorithm:
   - Nếu có ≥ 3 sigmas × 3 seeds → perturbation_status
     `RAW_EVIDENCE_AVAILABLE_NO_METRIC`.
   - Ngược lại → tương tự mapping.

4. Phân loại stability status (cẩn thận wording):
   - `REPRODUCIBILITY_VERIFIED_NO_STABILITY_METRIC` —
     Block R pass + Block S/N raw labels tồn tại nhưng chưa compute.
   - `REPRODUCIBILITY_VERIFIED_STABILITY_PENDING_EPIC08` — tương tự,
     ARI/AMI computation pending EPIC-08.
   - `REPRODUCIBILITY_NOT_VERIFIED` — Block R fail.
   - `STABILITY_RAW_EVIDENCE_PARTIAL` — một số Block thiếu.
   - `STABILITY_NOT_ASSESSABLE` — không có Block R, S, N evidence.

   **Wording boundary:**
   - KHÔNG ĐƯỢC viết "Segment X is stable" /
     "Cluster X is highly stable" /
     "Segment X has proven stability" nếu chưa có stability metric
     (ARI/AMI/NMI/Hungarian).
   - CP-05 PHẢI ghi rõ: "Segment-level stability remains pending
     EPIC-08." khi chỉ có EXP-05 evidence mà chưa compute metric.

### 9.5. Hard constraints

- CP-05 KHÔNG compute ARI / AMI / Hungarian.
- CP-05 KHÔNG gọi segment `STABLE` dựa trên Block R đơn thuần.
- CP-05 KHÔNG cross-claim stability giữa các algorithm.
- CP-05 KHÔNG dùng stability status để rank algorithm / segment.

### 9.6. Output schema

`cp05_stability_evaluation.csv`:

```
unit_id, algorithm, source_experiment, cluster_id, cluster_label,
reproducibility_status (Block R), seed_stability_status (Block S),
perturbation_status (Block N), n_seeds_observed, n_sigmas_observed,
stability_status, stability_evidence_note,
limitations (e.g., "ARI/AMI computation deferred to EPIC-08")
```

### 9.7. Limitations cần ghi nhận

- ARI / AMI chưa compute → CHƯA THỂ gọi segment ổn định hay không ổn
  định. CP-05 chỉ báo cáo **evidence availability**.
- Agglomerative và DBSCAN deterministic (không có seed axis) nên
  Block S áp dụng 1-sigma behavior (chỉ Block N / Block R có ý
  nghĩa).

---

## 10. Business Relevance Evaluation

### 10.1. Mục tiêu

Đánh giá dataset có **support** business interpretation cho segment ở
mức nào. CP-05 làm **rất hẹp** ở trục này để tránh suy diễn.

### 10.2. Inputs

- `data/processed/customer_candidates.parquet`: feature availability
  (descriptive).
- CP-02 → CP-04 evidence (RFM tiers, behavioural profile).

### 10.3. Methodology

Với mỗi segment:

1. Liệt kê **dataset-supported interpretations** (từ RAW features):

   | Feature | Inferred observation (data-supported) |
   |---|---|
   | Recency | Có invoice gần đây hơn / xa hơn population median. |
   | Frequency | Có nhiều / ít invoice hơn population. |
   | Monetary | Chi tiêu RAW GBP cao hơn / thấp hơn population. |
   | TotalQuantity | Tổng quantity items (signed) cao hơn / thấp hơn. |
   | TenureDays | Quan hệ kéo dài / ngắn hơn population. |
   | ActiveDays | Calendar-level activity nhiều / ít hơn population. |
   | PurchaseIntervalMean / Std | Cadence ổn định / biến động (CHỈ khi non-NaN). |
   | AverageInvoiceValue | Invoice size (GBP) cao hơn / thấp hơn population. |
   | ProductsPerInvoice | Diversity per invoice. |
   | CancellationRate, ReturnRate | **NOT_ASSESSABLE** (per CP-03 — không đưa vào business interpretation). |

2. **KHÔNG ĐƯỢC** infer các khái niệm sau (per AGENTS.md §2 và
   CP-04 §4.4 hard constraints):
   - Customer Lifetime Value (CLV).
   - Loyalty (definition không có trong dataset).
   - Churn / retention risk.
   - Future purchase intent.
   - Profitability / margin.
   - Customer satisfaction / NPS.
   - Risk of default / credit risk.

3. Phân loại business relevance status:
   - `SUPPORTED` — segment có ít nhất 3 features trong table trên
     với direction ∈ {HIGHER, LOWER} (không tính COMPARABLE / NA) VÀ
     direction ≠ NA. Interpretation có thể diễn đạt từ RAW features
     (RFM tiers + behavioural profile).
   - **`SUPPORTED` được hiểu là**: "Có đủ behavioral feature-level
     evidence trong dataset để mô tả business relevance trong phạm vi
     nghiên cứu". `SUPPORTED` KHÔNG có nghĩa "business value đã được
     chứng minh".
   - `LIMITED` — segment có 1-2 features với direction ∈ {HIGHER,
     LOWER} từ table trên.
   - `NOT_ASSESSABLE` — segment không có feature nào với direction ∈
     {HIGHER, LOWER} HOẶC toàn bộ features COMPARABLE / NA.
   - `NOT_APPLICABLE` — DBSCAN noise.

4. **Business interpretation text** (per segment, có constraints):
   - CHỈ dùng các từ khóa: "quan sát thấy", "có xu hướng",
     "theo dữ liệu", "RAW feature evidence shows".
   - KHÔNG dùng: "loyal", "champion", "VIP", "at-risk",
     "high-value customer", "promising", "declining",
     "engagement", "loyalty indicator", "purchase probability".
   - KHÔNG gợi ý campaign / promotion / action.

### 10.4. Hard constraints

- KHÔNG tạo marketing recommendation / campaign plan.
- KHÔNG suy diễn LTV / churn / loyalty / profitability / intent.
- KHÔNG dùng CancellationRate / ReturnRate (NOT_ASSESSABLE per CP-03).
- KHÔNG tạo composite "business relevance score".
- KHÔNG ranking segment theo business relevance.

### 10.5. Output schema

`cp05_business_relevance_evaluation.csv`:

```
unit_id, algorithm, source_experiment, cluster_id, cluster_label,
n_features_supported_direction, n_features_na,
feature_evidence (semicolon-separated feature:direction),
business_relevance_status, business_interpretation_text (1-3
sentences, qualitative, descriptive only),
over_inference_check (bool), limitations
```

### 10.6. Limitations cần ghi nhận

- Dataset là retail transactional (UCI Online Retail). Business
  interpretation BỊ GIỚI HẠN bởi feature set có sẵn.
- CancellationRate / ReturnRate `NOT_ASSESSABLE` per CP-03 → KHÔNG
  có cancellation-based interpretation.
- Time period của data (1 năm) → KHÔNG có yếu tố mùa vụ / multi-year
  cohort behavior.

---

## 11. Final Segment Definition

### 11.1. Mục tiêu

Tạo **definition rõ ràng cho TỪNG segment** — KHÔNG chọn segment tốt
nhất. Definition này là bản tổng hợp evidence từ CP-01 → CP-04 + 6
trục đánh giá CP-05.

### 11.2. Inputs

- Tất cả 6 evaluation outputs (§5-§10).
- `cp04_segment_profiles.csv`, `cp04_segment_naming.csv`,
  `cp04_segment_evidence.csv`.

### 11.3. Schema per segment

`cp05_final_segment_definition.csv` columns:

```
# Identity
segment_id               # Format: "{unit_id}__C{cluster_id}"
unit_id
algorithm
source_experiment
configuration_status
labels_persisted
cluster_id
cluster_label

# Naming (từ CP-04)
naming_status            # NAMED | COMPARATIVE | NOT_AVAILABLE | NOISE
segment_name             # From CP-04 if NAMED; "DBSCAN noise" if NOISE; descriptor otherwise
modifiers                # From CP-04
naming_rationale         # From CP-04

# Size (từ §8)
n_customers
pct_of_assigned
pct_of_total
relative_size_ratio
size_band
statistical_reliability_flag

# RFM profile (từ CP-04)
recency_tier
frequency_tier
monetary_tier

# Behavioural profile (từ CP-04)
behavioural_modifiers_summary
behavioural_profile_text

# Distinguishing features (từ §5)
n_distinguishing_features
n_features_assessable
distinctiveness_status
distinctiveness_supporting_features

# Interpretability (từ §6)
interpretability_status
interpretability_note

# Behavioral consistency (từ §7)
consistency_status
n_inconsistencies
consistency_note

# Stability (từ §9)
reproducibility_status
seed_stability_status
perturbation_status
stability_status
stability_note

# Business relevance (từ §10)
n_features_supported_direction
business_relevance_status
business_interpretation_text

# Evidence source
evidence_sources         # CP-XX artifact paths used
inconsistencies_across_cps  # Cross-CP findings (empty if clean)

# Limitations
limitations              # Combined from all CP-XX

# Status flags
is_actionable            # bool: distinctiveness_status in {DISTINCT} AND interpretability_status in {HIGH_INTERPRETABILITY, INTERPRETABLE} AND consistency_status in {CONSISTENT, PARTIALLY_CONSISTENT} AND business_relevance_status in {SUPPORTED}
priority_band            # WORKING_ANALYTICAL_PRIORITY_BAND (HIGH / MEDIUM / LOW / NOT_PRIORITIZED)
```

### 11.4. Methodology

Với mỗi segment (non-noise cluster):

1. Pull evidence từ CP-01 → CP-04 (verbatim, không re-compute).
2. Pull 6 evaluation axes status từ §5-§10.
3. Concatenate thành Final Segment Definition row.
4. Apply `is_interpretation_ready` rule (chỉ là deterministic flag):
   - TRUE chỉ khi tất cả 4 axes đạt minimum threshold (theo working
     defaults trong schema trên).
   - KHÔNG có ý nghĩa "nên target" / "có giá trị" / "nên ưu tiên".
5. Apply `interpretation_readiness`:
   - `READY` — `is_interpretation_ready == True` AND `size_band ∈
     {DOMINANT, LARGE}`.
   - `CONDITIONAL` — `is_interpretation_ready == True` AND `size_band ∈
     {MEDIUM, SMALL}`.
   - `LIMITED` — `is_interpretation_ready == True` AND
     `size_band == VERY_SMALL`.
   - `NOT_ASSESSABLE` — `is_interpretation_ready == False`.

### 11.5. Hard constraints

   - `is_interpretation_ready` và `interpretation_readiness` chỉ là
     **flags hỗ trợ đọc**, KHÔNG phải "winner" claim hay
     "best segment" claim.
   - KHÔNG tạo overall algorithm ranking dựa trên
     `interpretation_readiness`.
   - KHÔNG marketing recommendation kèm theo `interpretation_readiness`.
   - Final Segment Definition KHÔNG bao gồm:
     - Action items cho marketing / campaign.
     - Predicted customer behavior ngoài dữ liệu hiện tại.
     - Business value judgement (ví dụ: "high-value segment" — đây là
       forbidden token).

### 11.6. Limitations cần ghi nhận

- Interpretation Readiness (`interpretation_readiness` + `is_interpretation_ready`) thay vì priority_band/is_actionable — ghi rõ boundary này trong schema, report và documentation.
- Working analytical thresholds (§5-§10) có thể thay đổi sau mentor
  review.
- EXP-03 segments = `NOT_AVAILABLE` cho tất cả 6 axes (per
  `EV03-HP-01`).

---

## 12. DBSCAN Handling

CP-05 xử lý DBSCAN theo đúng convention đã thiết lập ở CP-01 → CP-04:

1. **Noise (`ClusterLabel == -1`) KHÔNG phải Customer Segment.**
   - Trong Final Definition: `naming_status = NOISE`, `cluster_label
     = noise (-1)`.
   - 6 evaluation axes: status = `NOT_APPLICABLE`.
   - KHÔNG đưa noise vào priority_band computation.
   - KHÔNG đặt tên cho noise.

2. **`K_realized = 17` ≠ requested K** cho DBSCAN:
   - KHÔNG so sánh trực tiếp segment count giữa DBSCAN và
     fixed-K algorithms.
   - Trong Final Definition, ghi `notes: "DBSCAN realised K ≠
     requested K"`.

3. **DBSCAN small clusters (n ≤ 10)**:
   - Phổ biến có `n_distinguishing_features = 0` (NaN-heavy feature
     matrices).
   - Distinctiveness status = `LIMITED_DIFFERENTIVENESS` hoặc
     `NOT_ASSESSABLE`.
   - Interpretability status = `LIMITED_INTERPRETABILITY` thường xuyên.
   - KHÔNG ép status thành `DISTINCT` / `INTERPRETABLE`.

4. **DBSCAN evidence attribution**:
   - Tất cả evidence pointing to DBSCAN đều ghi rõ
     `algorithm = "dbscan"` và `unit_id` chứa `EXP-01-dbscan`.
   - KHÔNG cross-map cluster ID DBSCAN ↔ K-Means / GMM / Agglomerative.

5. **DBSCAN noise in business interpretation**:
   - KHÔNG có business interpretation cho noise.
   - KHÔNG so sánh noise với customer segment.

---

## 13. EXP-03 Limitation

CP-05 giữ limitation đã được CP-01 → CP-04 ghi nhận:

1. **EXP-03 customer-level profiles = `NOT_AVAILABLE`.**
   - 5 EXP-03 units (kmeans, agglomerative, dbscan, gmm,
     fuzzy_cmeans) KHÔNG có per-customer labels.
   - Per `EV03-HP-01`: EXP-03 không persist per-customer cluster
     labels parquet.

2. **CP-05 KHÔNG rerun EXP-03** để tạo profiles giả.
   - KHÔNG tự fit lại EXP-03 working-selected configurations.
   - KHÔNG tự đặt tên cho EXP-03 segments.

3. **CP-05 outputs cho EXP-03 units**:
   - Tất cả 6 evaluation axes: status = `NOT_AVAILABLE`.
   - Final Segment Definition cho EXP-03: chỉ chứa configuration
     metadata (`K`, hyperparameters, `configuration_status`).
   - `priority_band = NOT_PRIORITIZED`.
   - KHÔNG empty rows giả (`is_actionable = False` thay vì `True`).

4. **Manifest records**:
   - 5 EXP-03 units ghi `labels_persisted = False`.
   - CP-05 runner ghi rõ EXP-03 evaluation outputs là empty
     (`n_rows = 0`) trong `cp05_runner_manifest.json`.

---

## 14. Cross-Algorithm Boundary

CP-05 KHÔNG:

1. Tạo **overall algorithm ranking** (K-Means "tốt hơn" DBSCAN).
2. Chọn **best segment across algorithms**.
3. Tạo **winning algorithm** claim.
4. **Cross-map** cluster IDs giữa các algorithm (K-Means C2 ≠ GMM
   C2).
5. So sánh priority_band giữa các algorithm.
6. Aggregate priority_band distribution across algorithms thành
   "best" claim.

CP-05 CÓ THỂ:

1. **Descriptive cross-algorithm observations** (KHÔNG ranking):
   - Per algorithm, báo cáo bao nhiêu segment thuộc
     distinctiveness_status nào.
   - KHÔNG gọi distribution này là "winner".

2. **Cross-algorithm scope note** trong Final Segment Definition:
   - Mỗi segment ghi `algorithm` rõ ràng.
   - `is_actionable` được compute **per-segment**, KHÔNG aggregate.

3. **Stability per-algorithm**:
   - §9 evaluation per-algorithm.
   - KHÔNG cross-rank.

4. **Inherited CP-03 limitation**:
   - Cross-algorithm comparison NOT within scope (CP-03 §12).
   - CP-05 inherits boundary.

### 14.1. Cross-algorithm documentation

CP-05 report có thể chứa section "Per-algorithm Distribution" mô tả:

```
K-Means: 4 segments, n_distinct = 2, n_partial = 1, n_not_assessable
= 1.
Agglomerative: ...
DBSCAN: 17 segments, ...
GMM: ...
Fuzzy C-Means: ...
```

Đây chỉ là **descriptive** — KHÔNG gọi đây là ranking.

---

## 15. Proposed Source Structure

CP-05 theo convention của CP-04 (đã READ từ
`src/customer_segmentation/profiling/cp04/`).

### 15.1. Module layout

```
src/customer_segmentation/profiling/cp05/
├── __init__.py            # Exports public API
├── provenance.py          # Cp05AnalysisUnit + load CP-01/02/03/04 evidence
├── distinctiveness.py     # §5 logic + status taxonomy
├── interpretability.py    # §6 logic
├── consistency.py         # §7 logic
├── size_evaluation.py     # §8 logic + WORKING_ANALYTICAL_SIZE_BAND
├── stability.py           # §9 logic (read-only on EXP-05)
├── business_relevance.py  # §10 logic
├── final_definition.py    # §11 Final Segment Definition builder
├── report.py              # Cp05ReportContext + Markdown report
└── runner.py              # Cp05Runner + run_cp05() + manifest writer
```

### 15.2. Public API

```python
# Provenance
build_cp05_analysis_units(cp04_unit_provenance: Path) -> list[Cp05AnalysisUnit]
load_cp04_evidence(unit: Cp05AnalysisUnit) -> Cp04EvidenceBundle
get_cp05_artifact_shas(...) -> dict[str, str]

# Evaluation axes
evaluate_distinctiveness(unit, evidence) -> DistinctivenessResult
evaluate_interpretability(unit, evidence) -> InterpretabilityResult
evaluate_consistency(unit, evidence) -> ConsistencyResult
evaluate_size(unit, evidence) -> SizeResult
evaluate_stability(unit, exp05_evidence) -> StabilityResult
evaluate_business_relevance(unit, evidence) -> BusinessRelevanceResult

# Final Definition
build_final_segment_definition(unit, all_evaluations) -> FinalSegmentDefinition

# Runner
run_cp05(output_dir: Path = ...) -> Cp05RunResult
Cp05Runner(output_dir=...).run()
```

### 15.3. Conventions kế thừa từ CP-04

- Public functions có docstring + type hints.
- Status taxonomy dùng string enum, KHÔNG magic strings.
- Manifest SHA-256 chain (CP-01 → CP-04 + EXP-05 nếu có).
- `--no-exp03` runner flag để skip EXP-03 units.
- Determinism: sort DataFrame trước khi ghi CSV.

---

## 16. Proposed Artifacts

Tất cả artifacts ghi vào `reports/profiling/cp05/`:

### 16.1. CSV / data outputs

| File | Rows × Cols (target) | Source |
|---|---|---|
| `cp05_distinctiveness_evaluation.csv` | ~33 (non-noise) | §5 |
| `cp05_interpretability_evaluation.csv` | ~33 | §6 |
| `cp05_behavioral_consistency_evaluation.csv` | ~33 | §7 |
| `cp05_segment_size_evaluation.csv` | ~33 | §8 |
| `cp05_stability_evaluation.csv` | ~33 | §9 |
| `cp05_business_relevance_evaluation.csv` | ~33 | §10 |
| `cp05_final_segment_definition.csv` | 39 (33 NAMED + 1 NOISE + 5 NOT_AVAILABLE) | §11 |

### 16.2. Provenance / metadata

| File | Content |
|---|---|
| `cp05_unit_provenance.csv` | 10 rows × unit_id, algorithm, configuration_status, labels_persisted, n_evaluations_done |
| `cp05_runner_manifest.json` | SHA-256 of CP-01/02/03/04 (and EXP-05 if read) inputs, run_timestamp, library_versions |

### 16.3. Markdown report

| File | Content |
|---|---|
| `cp05_report.md` | 12-15 sections covering objective, scope, methodology per axis, per-algorithm tables, Final Definition summary, limitations, traceability |

---

## 17. Proposed Tests

`tests/test_cp05.py` — target **~50 unit tests**.

### 17.1. Test categories

| Category | Test count target | Focus |
|---|---|---|
| Provenance | 6 | Analysis units, K-Medoids absent, EXP-03 labels_persisted |
| Distinctiveness (§5) | 5 | Status taxonomy, evidence chain, redundancy handling |
| Interpretability (§6) | 5 | Naming inheritance, rationale grounded, over-inference markers |
| Consistency (§7) | 6 | RFM tier grounding, modifier grounding, cross-check flags, NaN handling |
| Segment size (§8) | 4 | Bands, statistical reliability flag, DBSCAN denominator |
| Stability (§9) | 5 | Reproducibility vs stability distinction, no ARI/AMI compute, Block R/S/N status mapping |
| Business relevance (§10) | 5 | Dataset-supported features table, forbidden tokens, KHÔNG suy diễn |
| Final definition (§11) | 4 | Aggregation, is_actionable rule, priority_band rule, EXP-03 NOT_AVAILABLE |
| CP-04 consistency | 4 | cluster counts, segment names, naming_status |
| Runner | 8 | All artifacts written, deterministic, manifest SHA-256, --no-exp03 |
| Methodology gate | 6 | Forbidden tokens in report/CSV (per CP-04 gate + CP-05-specific tokens) |
| Read-only | 2 | SHA-256 CP-01/02/03/04 unchanged before/after |

**Total target**: ~60 unit tests.

### 17.2. Specific forbidden tokens (CP-05 extends CP-04's gate)

CP-05 adds these tokens to methodology gate tests:

```
best segment
best cluster
best customer
promising customer
declining customer
engagement
loyalty indicator
purchase probability
high-value customer
tier 1 customer
tier 2 customer
marketing recommendation
campaign recommendation
churn risk
retention risk
customer lifetime value
CLV
```

Inherits all CP-04 forbidden tokens (champion, vip, at-risk, ...).

### 17.3. Determinism

CP-05 output phải deterministic across reruns (sử dụng sorted
DataFrames + string set dict trong status evaluation).

### 17.4. Negative tests (NOT_ALLOWED behaviors)

Một số test phải verify CP-05 **KHÔNG** làm:

- KHÔNG compute ARI / AMI.
- KHÔNG ranking algorithm.
- KHÔNG tạo "best segment" / "winner segment" claim.
- KHÔNG marketing recommendation text trong outputs.
- KHÔNG suy diễn LTV / churn / loyalty từ RAW data.

---

## 18. Validation / Acceptance Criteria

CP-05 đạt `READY` gate khi tất cả conditions dưới đây PASS.

### 18.1. Functional validation

| Item | Evidence |
|---|---|
| 6 evaluation axes implemented với methodology | Tests in §17.1 PASS |
| Final Segment Definition builder | `tests/test_final_definition.py` PASS |
| Runner tạo đủ artifacts | `tests/test_runner.py::test_all_artifacts_written` PASS |
| Determinism across reruns | `test_determinism.py` PASS |
| `--no-exp03` flag hoạt động | `test_runner.py::test_no_exp03_flag` PASS |

### 18.2. Data integrity

| Item | Evidence |
|---|---|
| Read-only on CP-01 → CP-04 | SHA-256 identical before/after CP-05 run |
| Read-only on EXP-05 (if read) | SHA-256 identical |
| No NaN/Inf explosion | `test_data_integrity.py` PASS |
| Row count consistent | 33 non-noise + 1 NOISE + 5 NOT_AVAILABLE = 39 |
| EXP-03 = NOT_AVAILABLE | All 5 EXP-03 rows in all evaluation CSVs |

### 18.3. Methodology validation

| Item | Evidence |
|---|---|
| No forbidden tokens | `TestMethodologyGate` PASS (CP-04 inherited + CP-05 new tokens) |
| No composite scoring | Code review + tests verify only categorical status |
| No ARI/AMI compute | `tests/test_stability.py` confirms no such function in src |
| No marketing recommendation | Code review + `test_no_marketing_text` PASS |
| No algorithm ranking | `test_no_overall_algorithm_ranking` PASS |

### 18.4. CP-XX consistency

| Item | Evidence |
|---|---|
| cluster_id match với CP-04 | 100% match |
| naming_status match với CP-04 | 100% match |
| n_customers match với CP-01 size table | 100% match |
| distinguishing_features subset match với CP-03 | 100% match (CP-05 may filter) |

### 18.5. Lint / format

- `ruff check src/customer_segmentation/profiling/cp05/ tests/test_cp05.py scripts/run_cp05.py`: All clean.
- `black --check ...`: All clean.

### 18.6. Documentation

- `docs/evaluation/CP-05.md` (target ~250-350 lines, 11 sections
  matching CP-04 structure).
- `docs/research/EPIC09_CP05_PLAN.md` (this file) **ghi nhận PENDING**
  → nếu implement khác plan thì phải update plan trước.

---

## 19. Research Risks

### 19.1. Risk matrix

| ID | Risk | Mitigation |
|---|---|---|
| R1 | Composite scoring temptation (e.g., weighted priority_band) | Tests verify categorical status only; no numerical score produced. |
| R2 | Marketing recommendation temptation | Methodology gate tests + `TestNoMarketingText`. |
| R3 | Business interpretation beyond data | §10 forbidden tokens list + manual review of `business_interpretation_text`. |
| R4 | Stability claim misuse (calling segment "stable" from reproducibility only) | §9 hard distinction rule; `TestStabilityWording`. |
| R5 | Cross-algorithm ranking temptation | §14 hard boundary; `TestNoOverallAlgorithmRanking`. |
| R6 | Threshold bias (chọn threshold để PASS evaluation) | All thresholds explicitly `WORKING_ANALYTICAL_*` với mentor review pending. |
| R7 | CancellationRate / ReturnRate misuse | §10 hard rule prohibits business interpretation from these features. |
| R8 | DBSCAN cross-comparison misuse | §12 hard rule prohibits direct cluster ID mapping. |
| R9 | EXP-03 rerun temptation | §13 hard rule prohibits rerun; no synthetic labels. |
| R10 | Modifying CP-04 artifacts to "pass" CP-05 | Read-only guarantee + SHA-256 chain. |

### 19.2. Escalation triggers

DỪNG và báo mentor nếu:

- Xuất hiện yêu cầu thay đổi algorithm scope (R11).
- Xuất hiện yêu cầu tạo "best segment" claim (R5 expansion).
- Xuất hiện yêu cầu marketing strategy cụ thể (R2 expansion).
- Dataset được mở rộng với features mới mà chưa có ở FE-05
  (methodology change).

---

## 20. Open Decisions / Mentor Review

Các decision sau cần mentor input (KHÔNG auto-resolve):

### 20.1. Methodology-level decisions (require mentor + ADR)

| ID | Question | Default (working) | Impact |
|---|---|---|---|
| `CP05-MD-01` | Threshold cho `priority_band` (`HIGH` / `MEDIUM` / `LOW`) có phù hợp với research goal? | `WORKING_ANALYTICAL_PRIORITY_BAND` như trong §11.4. | Quyết định cách aggregate 6 axes. |
| `CP05-MD-02` | Có nên coi `is_actionable = True` là implicit "winning" không? (AGENTS.md §2.5 forbids.) | `is_actionable` is a flag, not a claim. §11.4 wording explicitly limits interpretation. | Quyết định wording trong report. |
| `CP05-MD-03` | ARI / AMI computation có cần được promote vào CP-05 hay deferred thuần túy sang EPIC-08? | Deferred to EPIC-08 per ADR-0004. CP-05 chỉ báo cáo evidence availability. | Nếu promote, cần chạy EPIC-08 trước CP-05. |
| `CP05-MD-04` | Có nên thêm cross-algorithm segment mapping (descriptive only) hay không? | KHÔNG map per §14. Reader tự xem. | Nếu thêm, cần ADR + scope expansion. |

### 20.2. Engineering-level decisions (require review only)

| ID | Question | Default |
|---|---|---|
| `CP05-ED-01` | Schema của Final Segment Definition có quá rộng / quá hẹp không? | 35 columns per §11.3. |
| `CP05-ED-02` | Báo cáo Markdown có cần section "Per-algorithm Distribution" không? | Có, descriptive only (§14.1). |
| `CP05-ED-03` | Test count target ~60 có phù hợp không? | Tương đương CP-04 (46 tests) + mở rộng 6 axes. |

### 20.3. PENDING_REVIEW items

Sau khi implement, các item sau vẫn PENDING_REVIEW:

- WORKING_ANALYTICAL_SIZE_BAND (§8.3).
- WORKING_ANALYTICAL_PRIORITY_BAND (§11.4).
- Interpretability thresholds (§6.3) — heuristic, không research-grade.
- Business interpretation text wording (§10.3) — needs mentor linguistic
  review.

---

## 21. Implementation Sequence

### 21.1. Ordered tasks

1. **Skeleton + provenance**
   - Create `src/customer_segmentation/profiling/cp05/` directory.
   - Implement `provenance.py` (load CP-01/02/03/04 evidence).
   - Set up `__init__.py` exports.

2. **Evaluation axes (one by one)**
   - §8 Segment size (simplest, no EXP-05 dependency).
   - §5 Distinctiveness (depends on CP-03 classification).
   - §6 Interpretability (depends on CP-04 naming + over-inference
     markers).
   - §7 Consistency (depends on §5 + §6 inputs).
   - §9 Stability (depends on EXP-05 read).
   - §10 Business relevance (independent).

3. **Final Segment Definition**
   - §11 aggregation logic in `final_definition.py`.

4. **Runner + manifest**
   - `runner.py` orchestrates 6 axes + final definition.
   - Manifest writer với SHA-256 chain.

5. **Report**
   - `report.py` Markdown builder.

6. **Tests**
   - Write tests song song với implementation (TDD).
   - Target ~60 tests.

7. **Validation**
   - `ruff check`, `black --check`.
   - `pytest tests/test_cp05.py`.
   - Full regression: `pytest tests/test_cp01.py tests/test_cp02.py
     tests/test_cp03.py tests/test_cp04.py tests/test_cp05.py`.

8. **Documentation**
   - Write `docs/evaluation/CP-05.md` (matching CP-04 structure).

### 21.2. Estimated effort

| Step | Effort estimate |
|---|---|
| Skeleton + provenance | 1-2 hours |
| 6 evaluation axes | 8-12 hours |
| Final Definition | 2-3 hours |
| Runner + manifest | 2-3 hours |
| Report | 2-3 hours |
| Tests | 6-8 hours |
| Validation | 1-2 hours |
| Documentation | 2-3 hours |
| **Total** | **24-37 hours** |

### 21.3. Dependencies

- CP-01 → CP-04 artifacts (DONE).
- EXP-05 cluster_labels.parquet availability (DONE).
- Python ≥ 3.10, pandas, numpy (already in deps).
- KHÔNG thêm dependency mới.

---

## 22. Final Review Gate

CP-05 chỉ được coi là `READY FOR IMPLEMENTATION` khi tất cả items trong
plan này được mentor approve. Sau khi implement, gate `READY FOR
REVIEW` được check theo bảng dưới.

### 22.1. Plan acceptance gate (current document)

| Item | Status (plan only) |
|---|---|
| CP-05 scope rõ | ✅ §1, §2 |
| Không overlap ngoài scope với CP-04 | ✅ §2.2 |
| Distinctiveness có methodology rõ | ✅ §5 |
| Interpretability có methodology rõ | ✅ §6 |
| Behavioral consistency có methodology rõ | ✅ §7 |
| Segment size có methodology rõ | ✅ §8 (working analytical, PENDING_REVIEW) |
| Stability không nhầm với reproducibility | ✅ §9 hard distinction |
| Business relevance có boundary rõ | ✅ §10.2-§10.4 |
| DBSCAN xử lý riêng | ✅ §12 |
| EXP-03 limitation giữ nguyên | ✅ §13 |
| Không có overall algorithm ranking | ✅ §14 |
| Không có best/winner/recommended claim | ✅ §14 + §11.5 |
| Có source/artifact plan | ✅ §15, §16 |
| Có test plan | ✅ §17 |
| Có validation plan | ✅ §18 |
| Có open decisions | ✅ §20 |
| Có final review gate | ✅ §22 |

### 22.2. Implementation acceptance gate (after mentor approves)

Sau khi implement CP-05 theo plan này, gate `READY` được check theo
bảng §18. Tóm tắt:

| Category | Required |
|---|---|
| 6 evaluation axes methodology documented | PASS |
| Final Segment Definition built correctly | PASS |
| EXP-03 NOT_AVAILABLE preserved | PASS |
| DBSCAN noise ≠ segment | PASS |
| No forbidden tokens | PASS |
| Read-only SHA-256 chain | PASS |
| Tests passing | ~60 tests PASS |
| Lint / format clean | ruff + black clean |
| Documentation complete | `docs/evaluation/CP-05.md` |
| No methodology change | Locked per §2.3 |

### 22.3. Review milestones

| Milestone | Reviewer | Output |
|---|---|---|
| Plan | Mentor | Approve / Request changes |
| Provenance + evaluation axes (after step 1+2) | Lead | Methodology check |
| Final Definition + runner (after step 3+4) | Lead | Implementation check |
| Tests + docs (after step 6+8) | Mentor | Acceptance check |
| Final ready | Mentor | `READY` gate |

---

## Appendix A — Glossary of CP-05 terms

| Term | Definition |
|---|---|
| **Evaluation axis** | Một trong 6 trục đánh giá (distinctiveness, interpretability, consistency, size, stability, business relevance). |
| **Status taxonomy** | String enum các kết quả phân loại cho mỗi axis (e.g., `DISTINCT`, `LIMITED_DIFFERENTIVENESS`, ...). |
| **WORKING_ANALYTICAL_SIZE_BAND** | Thresholds tạm thời để phân loại size (DOMINANT / LARGE / MEDIUM / SMALL / VERY_SMALL), cần mentor review. |
| **WORKING_ANALYTICAL_PRIORITY_BAND** | Thresholds tạm thời để gán priority_band (HIGH / MEDIUM / LOW / NOT_PRIORITIZED), cần mentor review. |
| **`is_actionable`** | Boolean flag (KHÔNG phải claim) computed từ 4 axes đạt minimum threshold. |
| **Reproducibility** | Same seed + same config + same input → identical labels (Block R). |
| **Stability** | Robust to seed / perturbation variation (requires ARI/AMI from EPIC-08). |
| **Distinguishing feature** | Feature với `HIGH_DIFFERENCE_OBSERVED` classification từ CP-03 + cluster contributes to distinction. |

## Appendix B — Inherited limitations từ CP-01 → CP-04

CP-05 inherits các limitations sau (verbatim):

| ID | Limitation | Source |
|---|---|---|
| L1 (CP-05-L1) | EXP-03 working-selected cluster profiles = NOT_AVAILABLE | EV03-HP-01, CP-04 §7 L1 |
| L2 (CP-05-L2) | DBSCAN `K_realized = 17` không so sánh trực tiếp với fixed-K algorithms | CP-04 §7 L3 |
| L3 (CP-05-L3) | CP-02 direction thresholds ±10% là analytical defaults | CP-02 §4.4 |
| L4 (CP-05-L4) | CP-03 WORKING_ANALYTICAL_THRESHOLD là analytical defaults | CP-03 §4.5 |
| L5 (CP-05-L5) | CancellationRate / ReturnRate = NOT_ASSESSABLE per CP-03 → KHÔNG dùng làm primary business evidence | CP-03 + CP-04 |
| L6 (CP-05-L6) | AverageQuantity ↔ BasketSize redundant → chỉ coi 1 evidence độc lập | FE-06 + CP-04 |
| L7 (CP-05-L7) | PurchaseIntervalMean / Std structural NaN → KHÔNG diễn giải NaN như quan sát trực tiếp | CP-02 §6.3 |
| L8 (CP-05-L8) | Naming KHÔNG phải ground truth — interpretive label | CP-04 §7 L8 |
| L9 (CP-05-L9) | RAW values (GBP, days) được dùng — KHÔNG transformed values | CP-02 §5, CP-04 §7 L9 |
| L10 (CP-05-L10) | Cross-algorithm comparison KHÔNG overall ranking | CP-04 §7 L10 + §14 |

## Appendix C — Cross-CP precedence rules

Nếu có conflict giữa CP-04 output và CP-05 evaluation:

1. **CP-04 naming** is authoritative cho `naming_status`, `segment_name`,
   `naming_rationale`. CP-05 evaluate dựa trên (KHÔNG override) CP-04.
2. **CP-01 size** is authoritative cho `n_customers`, `pct_of_*`. CP-05
   re-use trực tiếp (§8).
3. **CP-03 classification** is authoritative cho distinguishing features
   classification. CP-05 re-use (§5).
4. **CP-02 direction** is authoritative cho direction (HIGHER / LOWER /
   COMPARABLE / NA / ZERO_REFERENCE). CP-05 re-use (§7, §10).
5. **EXP-05 block status** is authoritative cho reproducibility / seed /
   perturbation status. CP-05 re-use (§9).
6. Nếu có conflict giữa các nguồn trên (e.g., SHA-256 mismatch), CP-05
   KHÔNG tự sửa — báo cáo và chờ mentor.

---

*Plan version: EPIC09-CP05-PLAN-v1.0 (DRAFT, AWAITING MENTOR REVIEW).*

*KHÔNG commit / push / PR trong giai đoạn plan.*
