"""Tests for case-insensitive LOCATION_RAW_ALIASES canonicalization."""

from transform.geography.resolve import _canonical_location_raw, canonical_location_raw


def test_canonical_location_raw_case_insensitive():
    assert canonical_location_raw("Milano, Italy") == "Milan, Italy"
    assert canonical_location_raw("milano, italy") == "Milan, Italy"
    assert canonical_location_raw("MILANO, ITALY") == "Milan, Italy"


def test_canonical_location_raw_koln_ascii_variants():
    assert _canonical_location_raw("Köln, NRW, Germany") == "Cologne, Germany"
    assert _canonical_location_raw("Koln, NRW, Germany") == "Cologne, Germany"
    assert _canonical_location_raw("Koeln, Germany") == "Cologne, Germany"
    assert _canonical_location_raw("koln, germany") == "Cologne, Germany"


def test_canonical_location_raw_unknown_passthrough():
    assert canonical_location_raw("Austin, TX, United States") == "Austin, TX, United States"
    assert canonical_location_raw("") == ""
