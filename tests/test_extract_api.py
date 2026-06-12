"""Tests for parser.extract_api."""

from parser.extract_api import extract_role_row


def test_extract_role_row_minimal():
    data = {
        "dancer_wsdcid": 28367,
        "dancer_first": "Donnaluz",
        "dancer_last": "Bush",
        "short_dominate_role": "Follower",
        "short_non_dominate_role": "Leader",
        "dominate_required": "NOV",
        "dominate_allowed": "NOV",
        "non_dominate_lookup": [
            {
                "non_dominate_required": "NEW",
                "non_dominate_allowed": "NEW",
                "non_dominate_recommended": "NEW",
            }
        ],
        "non_dominate_role_highest_level_points": "N/A",
        "non_dominate_role_highest_level": "N/A",
    }
    row = extract_role_row(data)
    assert row["dancer_id"] == 28367
    assert row["dancer_name"] == "Donnaluz Bush"
    assert row["dominate_role"] == "Follower"
