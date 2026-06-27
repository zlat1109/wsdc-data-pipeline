"""Tests for geo-aware event identity."""

from transform.geography.geo_event import (
    classify_event_id_pair,
    geo_event_key,
    geo_key,
    geo_keys_mergeable,
    metro_cluster_for,
)


def test_geo_key_us_city_state_country():
    assert geo_key("Denver", "Colorado", "United States") == "denver|colorado|united_states"


def test_geo_key_metro_boston_framingham():
    assert metro_cluster_for("Boston", "Massachusetts", "United States") == "greater_boston_ma"
    assert metro_cluster_for("Framingham", "Massachusetts", "United States") == "greater_boston_ma"
    assert geo_key("Boston", "Massachusetts", "United States") == "metro:greater_boston_ma"
    assert geo_key("Framingham", "Massachusetts", "United States") == "metro:greater_boston_ma"
    assert geo_keys_mergeable(
        geo_key("Boston", "Massachusetts", "United States"),
        geo_key("Framingham", "Massachusetts", "United States"),
    )


def test_geo_event_key_includes_name_and_geo():
    key = geo_event_key("Swingtime in the Rockies", "Denver", "Colorado", "United States")
    assert key.startswith("swingtime_in_the_rockies::")


def test_classify_worlds_ucwdc_keep_separate():
    dallas = geo_key("Dallas", "Texas", "United States")
    orlando = geo_key("Orlando", "Florida", "United States")
    assert classify_event_id_pair(75, 152, dallas, orlando) == "keep_separate"


def test_classify_swingtime_merge_candidate():
    denver = geo_key("Denver", "Colorado", "United States")
    assert classify_event_id_pair(47, 66, denver, denver) == "merge_candidate"
