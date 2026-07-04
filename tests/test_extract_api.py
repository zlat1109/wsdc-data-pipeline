"""Tests for parser.extract_api."""

from parser.extract_api import extract_results_rows, extract_role_row


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
    assert row["dancer_id"] == "28367"
    assert row["dancer_name"] == "Donnaluz Bush"
    assert row["dominate_role"] == "Follower"


def test_extract_results_row_stringifies_numeric_event_id():
    data = {
        "dancer_wsdcid": 1,
        "leader": {
            "placements": {
                "West Coast Swing": {
                    "Advanced": {
                        "division": {"name": "Advanced"},
                        "competitions": [
                            {
                                "result": 1,
                                "points": 10,
                                "event": {
                                    "id": 66,
                                    "name": "SwingTime",
                                    "location": "Denver, CO, United States",
                                    "year": 2017,
                                    "month": 3,
                                    "date": "March 2017",
                                },
                            }
                        ],
                    }
                }
            }
        },
    }
    rows = extract_results_rows(data)
    assert len(rows) == 1
    row = rows[0]
    assert row["event_name_id"] == "66"
    assert row["event_points"] == "10"
    assert row["event_year"] == "2017"
    assert row["dancer_id"] == "1"
