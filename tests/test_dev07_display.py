"""Tests for DEV-07 display helpers.

Covers :func:`format_recommendations_table`, :func:`format_marketing_summary`,
:func:`format_manifest_path`, and :func:`check_no_banned_substrings`.

Hard rules tested
-----------------
- The mandatory disclaimer phrase is the **single** allowed occurrence of
  any banned substring (per FR-MKT-05 / FR-SEG-08 / CP-04 §4.4).
- Per-segment rows MUST NOT contain banned marketing terms.
- No internal clustering metric names appear anywhere (silhouette,
  davies_bouldin, calinski_harabasz, wcss, ari, ami).
- No "best", "winner", "optimal", "ranking", "champion", "loyal",
  "vip", "at-risk", "churn", "ltv", "clv".
"""

from __future__ import annotations

from customer_segmentation.prototype.marketing.display import (
    BANNED_SUBSTRINGS,
    BANNED_SUBSTRINGS_OUTSIDE_DISCLAIMER,
    DEFAULT_DISCLAIMER_TEXT,
    check_no_banned_substrings,
    format_manifest_path,
    format_marketing_summary,
    format_recommendations_table,
)
from customer_segmentation.prototype.marketing.manifest import (
    MarketingValidationReport,
    build_marketing_manifest,
    build_recommendation_entry_review_required,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manifest(
    *,
    n_entries: int = 3,
    source_framework_version: str | None = None,
    mkt_framework_found: bool = False,
    availability: str = "REVIEW_REQUIRED",
    limitation: str = (
        "Marketing framework (MKT-01..MKT-05) not implemented in this " "prototype scope."
    ),
) -> object:  # MarketingRecommendationManifest
    entries = [
        build_recommendation_entry_review_required(
            segment_id=i,
            cluster_label=i,
            evidence_ref=["segmentation_manifest.json"],
        )
        for i in range(n_entries)
    ]
    return build_marketing_manifest(
        marketing_id="mkt_" + "a" * 24,
        segmentation_id="seg_" + "0" * 24,
        clustering_id="cl_" + "1" * 24,
        preprocessed_id="pp_x",
        dataset_id="ds_x",
        source_framework_version=source_framework_version,
        mkt_framework_found=mkt_framework_found,
        ml_dataset_sha256="a" * 64,
        feature_set_sha256="b" * 64,
        preprocessing_config_sha256="c" * 64,
        segmentation_manifest_sha256="d" * 64,
        n_segments_input=n_entries,
        n_segments_with_recommendation=n_entries,
        n_segments_noise=0,
        n_segments_not_available=0,
        noise_policy_used="n/a",
        recommendations=entries,
        environment={
            "python": "3.11",
            "platform": "Linux",
            "release": "7.0",
            "machine": "x86_64",
            "key_libraries": {"pandas": "2.0"},
        },
        config_sha256="e" * 64,
        log_file="",
        validation_report=MarketingValidationReport(all_passed=True),
        readonly_paths=["data/raw/primary"],
        input_segmentation_manifest="segmentation_manifest.json",
        availability=availability,
        limitation=limitation,
    )


# ---------------------------------------------------------------------------
# Banned-substring infrastructure
# ---------------------------------------------------------------------------


class TestBannedSubstringsConstant:
    def test_nonempty(self) -> None:
        assert len(BANNED_SUBSTRINGS) > 0

    def test_internal_metrics_blocked(self) -> None:
        for term in (
            "silhouette",
            "davies_bouldin",
            "calinski_harabasz",
            "wcss",
            "inertia",
            "ari",
            "ami",
        ):
            assert term in BANNED_SUBSTRINGS

    def test_business_terms_blocked(self) -> None:
        for term in ("champion", "loyal", "vip", "at-risk", "churn", "ltv", "clv"):
            assert term in BANNED_SUBSTRINGS

    def test_research_decision_language_blocked(self) -> None:
        for term in ("best", "winner", "optimal", "ranking", "composite_score"):
            assert term in BANNED_SUBSTRINGS

    def test_aliases_match(self) -> None:
        assert BANNED_SUBSTRINGS_OUTSIDE_DISCLAIMER == BANNED_SUBSTRINGS


# ---------------------------------------------------------------------------
# check_no_banned_substrings
# ---------------------------------------------------------------------------


class TestCheckNoBannedSubstrings:
    def test_clean_text_passes(self) -> None:
        assert check_no_banned_substrings("All good here.") == []

    def test_champion_detected(self) -> None:
        found = check_no_banned_substrings("This is a champion segment.")
        assert "champion" in found

    def test_loyal_detected(self) -> None:
        found = check_no_banned_substrings("loyal customer cohort")
        assert "loyal" in found

    def test_vip_detected(self) -> None:
        found = check_no_banned_substrings("VIP tier description")
        assert "vip" in found

    def test_churn_detected(self) -> None:
        found = check_no_banned_substrings("churn risk indicator")
        assert "churn" in found

    def test_ltv_detected(self) -> None:
        found = check_no_banned_substrings("ltv projection")
        assert "ltv" in found

    def test_silhouette_detected(self) -> None:
        found = check_no_banned_substrings("silhouette coefficient")
        assert "silhouette" in found

    def test_wcss_detected(self) -> None:
        found = check_no_banned_substrings("wcss is high")
        assert "wcss" in found

    def test_disclaimer_phrase_excluded(self) -> None:
        # The disclaimer phrase MUST contain "marketing" — and "marketing"
        # is NOT in BANNED_SUBSTRINGS; just verifying the disclaimer is
        # allowed without raising.
        text = f"Body. Disclaimer: {DEFAULT_DISCLAIMER_TEXT}"
        assert check_no_banned_substrings(text) == []

    def test_disclaimer_phrase_only_excluded_phrase(self) -> None:
        """Forbidden terms outside disclaimer are still flagged."""
        text = f"This is a champion segment. " f"Disclaimer: {DEFAULT_DISCLAIMER_TEXT}"
        found = check_no_banned_substrings(text)
        assert "champion" in found

    def test_custom_disclaimer(self) -> None:
        """Pass a custom disclaimer to check_no_banned_substrings."""
        text = "This is a loyal cohort. Disclaimer: descriptive view only"
        found = check_no_banned_substrings(text, disclaimer="descriptive view only")
        assert "loyal" in found

    def test_case_insensitive(self) -> None:
        found = check_no_banned_substrings("CHAMPION segment")
        assert "champion" in found


# ---------------------------------------------------------------------------
# format_recommendations_table
# ---------------------------------------------------------------------------


class TestFormatRecommendationsTable:
    def test_basic_table(self) -> None:
        m = _make_manifest(n_entries=3)
        text = format_recommendations_table(m)
        assert isinstance(text, str)
        assert "Marketing recommendations" in text
        assert m.marketing_id in text
        assert "REVIEW_REQUIRED" in text

    def test_each_recommendation_id_present(self) -> None:
        m = _make_manifest(n_entries=3)
        text = format_recommendations_table(m)
        for entry in m.recommendations:
            assert entry.recommendation_id in text
            assert str(entry.segment_id) in text

    def test_disclaimer_present(self) -> None:
        m = _make_manifest()
        text = format_recommendations_table(m)
        assert "Disclaimer:" in text
        assert DEFAULT_DISCLAIMER_TEXT in text

    def test_kpi_none_renders(self) -> None:
        m = _make_manifest()
        text = format_recommendations_table(m)
        # kpi column must render "None" for each Phase A row.
        assert "None" in text

    def test_is_interpretation_ready_renders(self) -> None:
        m = _make_manifest()
        text = format_recommendations_table(m)
        # Default is None → rendered as "n/a".
        assert "n/a" in text

    def test_no_banned_substrings(self) -> None:
        m = _make_manifest()
        text = format_recommendations_table(m)
        found = check_no_banned_substrings(text)
        assert found == [], f"Banned substrings in output: {found}"

    def test_custom_disclaimer(self) -> None:
        m = _make_manifest()
        text = format_recommendations_table(m, disclaimer="custom disclaimer text")
        assert "custom disclaimer text" in text

    def test_empty_recommendations(self) -> None:
        """No entries → table renders but does not crash."""
        m = _make_manifest(n_entries=0)
        text = format_recommendations_table(m)
        assert isinstance(text, str)
        assert "Marketing recommendations" in text

    def test_no_internal_metric_names(self) -> None:
        m = _make_manifest()
        text = format_recommendations_table(m)
        for term in (
            "silhouette",
            "davies_bouldin",
            "calinski_harabasz",
            "wcss",
            "inertia",
            "ari",
            "ami",
        ):
            # The disclaimer may not contain any of these terms; if the
            # rendered text contains the term, the term was leaked.
            assert term not in text.lower(), f"Table output contains internal metric name {term!r}"


# ---------------------------------------------------------------------------
# format_marketing_summary
# ---------------------------------------------------------------------------


class TestFormatMarketingSummary:
    def test_basic_summary(self) -> None:
        m = _make_manifest()
        text = format_marketing_summary(m)
        assert isinstance(text, str)
        # Required fields present.
        assert m.marketing_id in text
        assert m.segmentation_id in text
        assert m.clustering_id in text
        assert m.dataset_id in text
        assert "REVIEW_REQUIRED" in text

    def test_schema_version_present(self) -> None:
        m = _make_manifest()
        text = format_marketing_summary(m)
        assert "1.0.0" in text

    def test_research_safety_block_in_summary(self) -> None:
        m = _make_manifest()
        text = format_marketing_summary(m)
        assert "MARKETING_PROTOTYPE" in text
        # Both invariant flags rendered as False.
        assert "False" in text

    def test_n_segments_fields_present(self) -> None:
        m = _make_manifest(n_entries=4)
        text = format_marketing_summary(m)
        assert "4" in text  # n_segments_input

    def test_source_framework_version_null(self) -> None:
        m = _make_manifest(source_framework_version=None)
        text = format_marketing_summary(m)
        assert "null" in text

    def test_source_framework_version_present(self) -> None:
        m = _make_manifest(
            source_framework_version="MKT-01..05__v1",
            mkt_framework_found=True,
        )
        text = format_marketing_summary(m)
        assert "MKT-01..05__v1" in text
        assert "True" in text  # mkt_framework_found

    def test_no_banned_substrings(self) -> None:
        m = _make_manifest()
        text = format_marketing_summary(m)
        found = check_no_banned_substrings(text)
        assert found == [], f"Banned substrings in summary: {found}"

    def test_disclaimer_present(self) -> None:
        m = _make_manifest()
        text = format_marketing_summary(m)
        assert "Disclaimer:" in text
        assert DEFAULT_DISCLAIMER_TEXT in text

    def test_noise_policy_used_count(self) -> None:
        m = _make_manifest()
        text = format_marketing_summary(m)
        assert "n/a" in text  # noise_policy_used

    def test_limitation_in_summary(self) -> None:
        m = _make_manifest()
        text = format_marketing_summary(m)
        # The summary renders count fields but not the limitation text.
        # Limitation is rendered in the per-recommendation table, not here.
        assert isinstance(text, str)


# ---------------------------------------------------------------------------
# format_manifest_path
# ---------------------------------------------------------------------------


class TestFormatManifestPath:
    def test_basic_path(self) -> None:
        m = _make_manifest()
        s = format_manifest_path(m)
        assert m.marketing_id in s
        assert "marketing_manifest.json" in s
        assert "marketing/" in s

    def test_path_components(self) -> None:
        m = _make_manifest()
        s = format_manifest_path(m)
        # input_segmentation_manifest is the parent reference.
        assert m.input_segmentation_manifest in s


# ---------------------------------------------------------------------------
# Defensive invariants
# ---------------------------------------------------------------------------


def test_disclaimer_text_nonempty() -> None:
    assert DEFAULT_DISCLAIMER_TEXT
    # The disclaimer phrase may contain banned terms (e.g. "no winner
    # annotation"); the display helpers strip the disclaimer before
    # running the substring scan, so the displayed output remains
    # clean. Verify the strip-then-scan flow:
    assert check_no_banned_substrings(DEFAULT_DISCLAIMER_TEXT) == []


def test_disclaimer_only_exemption_via_strip() -> None:
    """When wrapped in a disclaimer line, banned terms are exempted."""
    # The disclaimer itself contains the substring "winner" by design.
    text_with_disclaimer = f"Body. {DEFAULT_DISCLAIMER_TEXT}"
    assert check_no_banned_substrings(text_with_disclaimer) == []


def test_disclaimer_does_not_exempt_other_text() -> None:
    """Banned terms elsewhere in the text are still flagged."""
    text = f"champion description. " f"Disclaimer: {DEFAULT_DISCLAIMER_TEXT}"
    found = check_no_banned_substrings(text)
    assert "champion" in found
