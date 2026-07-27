"""Location patches must respect the one-row-per-place-string invariant."""

from db.enrich_known_events import _apply_location_patch

STOCKHOLM = {
    "event_city": "Stockholm",
    "event_state": "",
    "event_country": "Sweden",
    "event_location": "Stockholm, Sweden",
    "event_location_standardized": "Stockholm, Sweden",
}


class FakeCursor:
    """Minimal cursor: owner lookup answers from `owner`, row lookup from `existing`."""

    def __init__(self, *, owner=None, existing=None):
        self._owner = owner
        self._existing = existing
        self._last = ""
        self.statements: list[str] = []

    def execute(self, sql, params=None):
        self._last = " ".join(sql.split())
        self.statements.append(self._last)

    def fetchone(self):
        if "location_id <> " in self._last:
            return (self._owner,) if self._owner is not None else None
        return self._existing


def test_patch_skipped_when_another_location_owns_the_string():
    cur = FakeCursor(owner=199)

    _apply_location_patch(cur, 231, STOCKHOLM, force=True)

    assert not any(s.startswith(("INSERT", "UPDATE")) for s in cur.statements)


def test_missing_location_is_inserted_when_string_is_free():
    cur = FakeCursor(owner=None, existing=None)

    _apply_location_patch(cur, 231, STOCKHOLM, force=True)

    assert any(s.startswith("INSERT INTO core.locations") for s in cur.statements)


def test_existing_location_is_updated_when_forced():
    cur = FakeCursor(owner=None, existing=("Stockholm", "Sweden", "Stockholm, SE"))

    _apply_location_patch(cur, 199, STOCKHOLM, force=True)

    assert any(s.startswith("UPDATE core.locations") for s in cur.statements)
