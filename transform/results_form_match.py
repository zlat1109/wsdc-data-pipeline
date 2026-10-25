"""Match WSDC Results Form rows (scoring software per event) to our editions.

A Results Form lives in a ``<year> Events`` folder and names the event the way
the organiser writes it ("Liberty Swing 2024", "DCSX"), which often differs
from the WSDC registry name ("Liberty Swing Dance Championships"). We match by
name within the folder year, gated by the form's month when it can be parsed,
and also compare against Competition Results edition names (scraped from the
same platforms organisers use).
"""

from __future__ import annotations

import difflib
import re
from collections.abc import Iterable, Mapping

import pandas as pd

MIN_SCORE = 0.75
MIN_MARGIN = 0.05

_STOP = re.compile(
    r"\b(wcs|west coast swing|dance|the|of|and|festival|fest|championships?|"
    r"convention|event|weekend|open|wsdc|challenge|classic)\b"
)
_MONTHS = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]


def normalize_event_name(name: str) -> str:
    s = re.sub(r"\b(19|20)\d{2}\b", "", str(name).lower())
    s = re.sub(r"[^a-z0-9 ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    stripped = re.sub(r"\s+", " ", _STOP.sub(" ", s)).strip()
    return stripped or s


def form_start_month(event_dates: str) -> int | None:
    """Start month from the free-text dates field, or None when ambiguous."""
    d = str(event_dates or "").strip().lower()
    if not d or d == "nan":
        return None
    for i, mon in enumerate(_MONTHS, 1):
        if re.search(rf"\b{mon}", d):
            return i
    iso = re.match(r"(\d{4})[-.](\d{1,2})[-.](\d{1,2})", d)
    if iso:
        return int(iso.group(2))
    # Day-first European formats: "22-24.03.2024", "12.04.2024", "12/04 au 14/04/24"
    dotted = re.match(r"\d{1,2}(?:-\d{1,2})?[.](\d{1,2})[.]", d)
    if dotted:
        return int(dotted.group(1))
    if " au " in d or re.search(r"\d+ to \d+", d):
        m = re.search(r"\d{1,2}/(\d{1,2})", d)
        return int(m.group(1)) if m else None
    us = re.match(r"(\d{1,2})/\d{1,2}", d)
    if us and 1 <= int(us.group(1)) <= 12:
        return int(us.group(1))
    return None


def name_score(form_name: str, edition_name: str, *, month_known: bool) -> float:
    score = difflib.SequenceMatcher(None, form_name, edition_name).ratio()
    a, b = set(form_name.split()), set(edition_name.split())
    short, long_ = (a, b) if len(a) <= len(b) else (b, a)
    # "Freedom Swing" ⊂ "Freedom Swing Dance Challenge" — only trusted with a month gate
    if month_known and short and short <= long_ and sum(map(len, short)) >= 4:
        score = max(score, 0.9)
    return score


def match_forms(
    forms: pd.DataFrame,
    editions: pd.DataFrame,
    extra_names: Mapping[int, Iterable[str]] | None = None,
) -> pd.DataFrame:
    """Add ``m_edition_id``, ``m_score``, ``m_margin``, ``m_ok`` to ``forms``.

    ``forms`` needs ``form_year_folder``, ``event_name``, ``event_dates``;
    ``editions`` needs ``edition_id``, ``event_year``, ``event_month``, ``event_name``.
    """
    extra_names = extra_names or {}
    ed = editions[["edition_id", "event_year", "event_month", "event_name"]].copy()
    ed["edition_id"] = ed["edition_id"].astype(int)
    ed["event_year"] = ed["event_year"].astype(int)
    ed["event_month"] = ed["event_month"].astype(int)
    ed["names"] = [
        {normalize_event_name(n)} | {normalize_event_name(x) for x in extra_names.get(e, [])}
        for e, n in zip(ed["edition_id"], ed["event_name"])
    ]

    matched, scores, margins = [], [], []
    for _, row in forms.iterrows():
        month = form_start_month(row.get("event_dates"))
        cand = ed[ed["event_year"] == int(row["form_year_folder"])]
        if month:
            diff = (cand["event_month"] - month).abs()
            cand = cand[(diff <= 1) | (diff == 11)]
        fname = normalize_event_name(row.get("event_name", ""))
        if cand.empty or not fname:
            matched.append(None)
            scores.append(0.0)
            margins.append(0.0)
            continue
        ranked = cand["names"].map(
            lambda ns: max(name_score(fname, x, month_known=month is not None) for x in ns)
        ).sort_values(ascending=False)
        best = float(ranked.iloc[0])
        second = float(ranked.iloc[1]) if len(ranked) > 1 else 0.0
        matched.append(int(cand.loc[ranked.index[0], "edition_id"]))
        scores.append(best)
        margins.append(best - second)

    out = forms.copy()
    out["m_edition_id"] = matched
    out["m_score"] = scores
    out["m_margin"] = margins
    out["m_ok"] = (out["m_score"] >= MIN_SCORE) & (out["m_margin"] >= MIN_MARGIN)
    return out
