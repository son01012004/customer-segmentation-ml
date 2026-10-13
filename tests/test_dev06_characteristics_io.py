"""Tests for the ``segment_characteristics.json`` on-disk contract (P1-1 fix).

These tests pin down the structure mandated by plan §4.2:

- Nested dict keyed by ``segment_id`` (as string), then by
  ``characteristic_id``.
- Each entry has: ``characteristic_id``, ``description``,
  ``source_features`` (list), ``derived_stats`` (dict),
  ``is_invariant: False`` (fixed invariant per OQ-SEG-CHAR-01).
- Noise segments (``segment_id == -1``) are EXCLUDED from the output
  (plan §5: characteristics do not compute for noise).
- Segments with no characteristics are OMITTED (no empty ``{}`` placeholders).

The tests use the public pipeline-level write function
``_write_characteristics_json`` (re-exported via ``import``) to avoid
exercising the whole Stage A→H driver.
"""

from __future__ import annotations

import json
from pathlib import Path

from customer_segmentation.prototype.segmentation.characteristics import (
    derive_segment_characteristics,
)
from customer_segmentation.prototype.segmentation.manifest import (
    CharacteristicEntry,
    FeatureProfile,
)
from customer_segmentation.prototype.segmentation.pipeline import (
    _write_characteristics_json,
)


def _make_chars() -> list[CharacteristicEntry]:
    """3 entries: 2 for segment 0, 1 for segment 2."""
    return [
        CharacteristicEntry(
            characteristic_id="mean_high_Recency",
            description="Mean of Recency above dataset mean by 1 std.",
            source_features=["Recency"],
            derived_stats={"rule": "mean_high", "actual": 1.5, "threshold": 1.0},
            segment_id=0,
        ),
        CharacteristicEntry(
            characteristic_id="mean_low_Monetary",
            description="Mean of Monetary below dataset mean by 1 std.",
            source_features=["Monetary"],
            derived_stats={"rule": "mean_low", "actual": -0.5, "threshold": -1.0},
            segment_id=0,
        ),
        CharacteristicEntry(
            characteristic_id="median_above_dataset_median_Tenure",
            description="Median of Tenure above dataset median.",
            source_features=["Tenure"],
            derived_stats={"rule": "median_above_dataset_median", "actual": 1.0},
            segment_id=2,
        ),
    ]


# ---------------------------------------------------------------------------
# Nested-by-segment_id structure
# ---------------------------------------------------------------------------


def test_characteristics_json_is_nested_by_segment_id(tmp_path: Path) -> None:
    """Top-level keys are segment_ids (as strings)."""
    chars = _make_chars()
    path = tmp_path / "seg_char.json"
    _write_characteristics_json(chars, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    # Top-level keys: only segments that have at least one characteristic.
    assert set(payload.keys()) == {"0", "2"}


def test_characteristics_json_each_segment_value_is_dict_of_characteristic_id(
    tmp_path: Path,
) -> None:
    """Each segment value is a dict keyed by characteristic_id."""
    chars = _make_chars()
    path = tmp_path / "seg_char.json"
    _write_characteristics_json(chars, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    # Segment 0 has 2 characteristics.
    assert set(payload["0"].keys()) == {"mean_high_Recency", "mean_low_Monetary"}
    # Segment 2 has 1 characteristic.
    assert set(payload["2"].keys()) == {"median_above_dataset_median_Tenure"}


def test_characteristics_json_entry_fields_and_types(tmp_path: Path) -> None:
    """Each entry has the required fields with correct types."""
    chars = _make_chars()
    path = tmp_path / "seg_char.json"
    _write_characteristics_json(chars, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    entry = payload["0"]["mean_high_Recency"]
    assert entry["characteristic_id"] == "mean_high_Recency"
    assert isinstance(entry["description"], str)
    assert isinstance(entry["source_features"], list)
    assert entry["source_features"] == ["Recency"]
    assert isinstance(entry["derived_stats"], dict)
    assert entry["derived_stats"]["rule"] == "mean_high"


def test_characteristics_json_is_invariant_is_false(tmp_path: Path) -> None:
    """``is_invariant`` field is present and False on every entry (per plan §4.2)."""
    chars = _make_chars()
    path = tmp_path / "seg_char.json"
    _write_characteristics_json(chars, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    for seg_id, seg_dict in payload.items():
        for cid, entry in seg_dict.items():
            assert "is_invariant" in entry, f"entry {seg_id}/{cid} missing 'is_invariant'"
            assert entry["is_invariant"] is False, (
                f"entry {seg_id}/{cid} has is_invariant={entry['is_invariant']!r}, "
                "expected False"
            )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_characteristics_json_empty_input_writes_empty_object(tmp_path: Path) -> None:
    """No characteristics → empty JSON object on disk."""
    path = tmp_path / "seg_char.json"
    _write_characteristics_json([], path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload == {}


def test_characteristics_json_excludes_noise_segment(tmp_path: Path) -> None:
    """Noise (segment_id == -1) entries are EXCLUDED from the JSON."""
    chars = [
        CharacteristicEntry(
            characteristic_id="mean_high_Recency",
            description="d",
            source_features=["Recency"],
            derived_stats={"rule": "mean_high"},
            segment_id=0,
        ),
        CharacteristicEntry(
            characteristic_id="mean_low_Recency",
            description="d",
            source_features=["Recency"],
            derived_stats={"rule": "mean_low"},
            segment_id=-1,  # noise — should be excluded
        ),
    ]
    path = tmp_path / "seg_char.json"
    _write_characteristics_json(chars, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    # Only segment 0 should be present.
    assert set(payload.keys()) == {"0"}


def test_characteristics_json_segment_with_only_noise_is_empty(tmp_path: Path) -> None:
    """If only noise characteristics exist, the JSON is empty."""
    chars = [
        CharacteristicEntry(
            characteristic_id="mean_high_Recency",
            description="d",
            source_features=["Recency"],
            derived_stats={"rule": "mean_high"},
            segment_id=-1,
        ),
    ]
    path = tmp_path / "seg_char.json"
    _write_characteristics_json(chars, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload == {}


# ---------------------------------------------------------------------------
# Multi-segment & round-trip
# ---------------------------------------------------------------------------


def test_characteristics_json_multiple_segments_distinct_keys(
    tmp_path: Path,
) -> None:
    """3+ segments with distinct characteristics → distinct top-level keys."""
    chars = [
        CharacteristicEntry(
            characteristic_id="mean_high_a",
            description="d",
            source_features=["a"],
            derived_stats={"rule": "mean_high"},
            segment_id=0,
        ),
        CharacteristicEntry(
            characteristic_id="mean_low_b",
            description="d",
            source_features=["b"],
            derived_stats={"rule": "mean_low"},
            segment_id=1,
        ),
        CharacteristicEntry(
            characteristic_id="median_above_dataset_median_c",
            description="d",
            source_features=["c"],
            derived_stats={"rule": "median_above_dataset_median"},
            segment_id=2,
        ),
    ]
    path = tmp_path / "seg_char.json"
    _write_characteristics_json(chars, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert set(payload.keys()) == {"0", "1", "2"}
    assert payload["0"]["mean_high_a"]["source_features"] == ["a"]
    assert payload["1"]["mean_low_b"]["source_features"] == ["b"]
    assert payload["2"]["median_above_dataset_median_c"]["source_features"] == ["c"]


def test_characteristics_json_round_trip_via_to_dict(tmp_path: Path) -> None:
    """The on-disk JSON can be reconstructed from the source entries' to_dict.
    No silent loss of fields."""
    chars = _make_chars()
    path = tmp_path / "seg_char.json"
    _write_characteristics_json(chars, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    # Rebuild expected from to_dict (filtered to non-noise).
    expected: dict[str, dict[str, dict]] = {}
    for c in chars:
        if c.segment_id == -1:
            continue
        seg_key = str(c.segment_id)
        expected.setdefault(seg_key, {})[c.characteristic_id] = {
            "characteristic_id": c.characteristic_id,
            "description": c.description,
            "source_features": list(c.source_features),
            "derived_stats": dict(c.derived_stats),
            "is_invariant": False,
        }
    assert payload == expected


# ---------------------------------------------------------------------------
# Integration: derived output mirrors the plan §4.2 schema
# ---------------------------------------------------------------------------


def test_characteristics_json_from_derive_is_nested_by_segment_id(
    tmp_path: Path,
) -> None:
    """End-to-end: derive_segment_characteristics → _write_characteristics_json
    produces the plan §4.2 nested shape."""
    profiles = [
        FeatureProfile(
            segment_id=0,
            feature_name="Recency",
            statistics={"mean": 5.0, "median": 4.0},
        ),
        FeatureProfile(
            segment_id=0,
            feature_name="Monetary",
            statistics={"mean": 100.0, "median": 95.0},
        ),
        FeatureProfile(
            segment_id=1,
            feature_name="Recency",
            statistics={"mean": 25.0, "median": 24.0},
        ),
        FeatureProfile(
            segment_id=1,
            feature_name="Monetary",
            statistics={"mean": 300.0, "median": 295.0},
        ),
    ]
    dataset_stats = {
        "Recency": {"mean": 15.0, "median": 14.0, "std": 8.16},
        "Monetary": {"mean": 200.0, "median": 195.0, "std": 81.6},
    }
    chars = derive_segment_characteristics(
        profiles=profiles, dataset_stats=dataset_stats, z_threshold=1.0
    )
    path = tmp_path / "seg_char.json"
    _write_characteristics_json(chars, path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    # Top-level keys MUST be segment_ids of the source profiles.
    assert set(payload.keys()) == {"0", "1"}
    # Every entry has is_invariant=False.
    for seg_dict in payload.values():
        for entry in seg_dict.values():
            assert entry["is_invariant"] is False
