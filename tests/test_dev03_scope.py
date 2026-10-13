"""Tests for the preprocessing scope enums."""

from __future__ import annotations

from customer_segmentation.prototype.preprocessing.scope import (
    CLEANING_RULE_STATUSES,
    DATASET_PROFILE_CATEGORIES,
    FEATURE_STATUSES,
    IMPUTATION_METHODS,
    OPTIONAL_TRANSFORM_GRID,
    OPTIONAL_TRANSFORM_OUTCOMES,
    OUTLIER_ACTIONS,
    OUTLIER_METHODS,
    PREPROCESSED_SCOPES,
    PREPROCESSING_OUTCOME_FAIL,
    PREPROCESSING_OUTCOME_PASS,
    PREPROCESSING_OUTCOME_WARNING,
    PREPROCESSING_OUTCOMES,
    PREPROCESSING_STAGES,
    CleaningRuleStatus,
    OutlierAction,
    PreprocessedScope,
    PreprocessingOutcome,
    PreprocessingStage,
    ScalingMethod,
    TransformationMethod,
    preprocess_dataset,
)


def test_preprocessed_scope_has_one_value() -> None:
    assert frozenset({"PREPROCESSED_PROTOTYPE"}) == PREPROCESSED_SCOPES
    assert PreprocessedScope.PREPROCESSED_PROTOTYPE.value == "PREPROCESSED_PROTOTYPE"


def test_preprocessing_stages_enum_has_seven_values() -> None:
    assert frozenset({"A", "B", "C", "D", "E", "F", "G"}) == PREPROCESSING_STAGES
    assert len(list(PreprocessingStage)) == 7
    # Stages are ordered A→G.
    assert [s.value for s in PreprocessingStage] == ["A", "B", "C", "D", "E", "F", "G"]


def test_preprocessing_outcomes_three_values() -> None:
    assert frozenset({"PASS", "WARNING", "FAIL"}) == PREPROCESSING_OUTCOMES
    assert PreprocessingOutcome.PASS.value == PREPROCESSING_OUTCOME_PASS
    assert PreprocessingOutcome.WARNING.value == PREPROCESSING_OUTCOME_WARNING
    assert PreprocessingOutcome.FAIL.value == PREPROCESSING_OUTCOME_FAIL


def test_cleaning_rule_statuses_three_values() -> None:
    assert (
        frozenset({"WORKING_ASSUMPTION", "PENDING_MENTOR_REVIEW", "REVIEW_REQUIRED"})
        == CLEANING_RULE_STATUSES
    )
    # Statuses are mirrored from FE-02 KEY_ANNOTATIONS.
    assert CleaningRuleStatus.WORKING_ASSUMPTION.value == "WORKING_ASSUMPTION"
    assert CleaningRuleStatus.PENDING_MENTOR_REVIEW.value == "PENDING_MENTOR_REVIEW"
    assert CleaningRuleStatus.REVIEW_REQUIRED.value == "REVIEW_REQUIRED"


def test_feature_statuses_match_fe05_semantics() -> None:
    assert (
        frozenset(
            {
                "WORKING_ASSUMPTION",
                "RETAIN_CANDIDATE",
                "PENDING_REVIEW",
                "EXCLUDE",
                "UNSUPPORTED",
            }
        )
        == FEATURE_STATUSES
    )


def test_imputation_methods_three_values() -> None:
    assert frozenset({"none", "median", "mean"}) == IMPUTATION_METHODS


def test_outlier_actions_match_fe02() -> None:
    assert frozenset({"none", "clip", "remove", "flag"}) == OUTLIER_ACTIONS


def test_outlier_methods_match_fe02() -> None:
    assert frozenset({"iqr", "zscore"}) == OUTLIER_METHODS


def test_dataset_profile_categories_three_values() -> None:
    assert frozenset({"file_level", "structural", "data_quality"}) == DATASET_PROFILE_CATEGORIES


def test_optional_transform_outcomes() -> None:
    assert frozenset({"PASS", "WARNING", "FAIL"}) == OPTIONAL_TRANSFORM_OUTCOMES


def test_optional_transform_grid_is_3x4() -> None:
    # Transformation (3) × Scaling (4) = 12 cells.
    assert len(OPTIONAL_TRANSFORM_GRID) == 12
    # All combos present.
    expected = {
        (t, s)
        for t in ("none", "log1p", "yeo_johnson")
        for s in ("none", "standard", "minmax", "robust")
    }
    assert set(OPTIONAL_TRANSFORM_GRID) == expected


def test_transformation_methods_match_exp04_grid() -> None:
    # FE-06 EXP-04 3 trans options (none/log1p/yeo_johnson).
    assert {t.value for t in TransformationMethod} == {"none", "log1p", "yeo_johnson"}


def test_scaling_methods_match_exp04_grid() -> None:
    # FE-06 EXP-04 4 scaling options (none/standard/minmax/robust).
    assert {s.value for s in ScalingMethod} == {"none", "standard", "minmax", "robust"}


def test_enums_are_str_enum() -> None:
    # str-Enum mixin: e.g. comparing with string works.
    assert PreprocessedScope.PREPROCESSED_PROTOTYPE == "PREPROCESSED_PROTOTYPE"
    assert TransformationMethod.LOG1P == "log1p"
    assert OutlierAction.NONE == "none"


def test_preprocess_dataset_is_callable_smoke() -> None:
    # We don't actually run it (would need a real DEV-02 dataset); we
    # only verify it's callable and re-exports the pipeline entry.
    assert callable(preprocess_dataset)
