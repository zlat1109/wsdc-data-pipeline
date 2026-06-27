# Event renames: schedule vs points catalog

WSDC **events list** (marketing site) and **points export** (historical API) often use different names for the same brand.

## Problem

- Schedule scrape shows rebrand name (e.g. Rocket City Swing).
- Points results still use historical catalog title (e.g. Westies on the Water).
- Without explicit alias → fuzzy match errors or `new_unmapped` in mapping report.

## Fix (in order)

1. **`parser/event_name_matcher.py`** — `EVENT_NAME_MAPPINGS["Schedule Name"] = "Catalog Name"`  
   Schedule name is the key; value must match `core.events.name` exactly.

2. **`transform/event_knowledge.py`** — `KNOWN_EVENT_METADATA[event_id]` for updated `url` / `typical_location` after rebrand.

3. **Do not rename** `core.events.name` locally for rebrand-only changes — breaks join to existing result rows.

4. **`tests/test_events_list_mapping.py`** — test: schedule row → `confirmed` + correct `canonical_event_id`.

5. Verify: `python scripts/analyze_events_list_mapping.py` → `mapping/latest.json` → `confirmed`.

## Signals of rebrand (not a new event)

- Same city/state, same season, organizer site says "formerly known as …"
- Old name disappears from events list but points still have results under old title
- URL change with same organizer

## Anti-patterns

- Fuzzy match across different US states / cities
- URL-only match when names differ strongly
- Creating a second `event_id` for the same brand

## Related

- [../transform/event-names.md](../transform/event-names.md)
- [../transform/events-list.md](../transform/events-list.md)
