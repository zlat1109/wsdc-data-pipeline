# Upcoming weekend snapshots

Populated automatically by `wsdc-telegram-bot` after each Thursday `#Upcoming_WSDC_Events` post.

`check_updates.py` merges **concluded** events across all snapshots within a 21-day lookback (`EVENT_GATE_LOOKBACK_DAYS`). Carry-over from last week (e.g. delayed Neverland) stays in the gate together with the current weekend.

**Partial-readiness gate:** full-parse triggers when **at least one** pending event appears in live WSDC data and is not yet in Supabase — it does **not** wait for all pending events. Each trigger still runs a **full** registry parse (`--full`). Stragglers carry over to the next week.

Events whose `end_date` is today count as concluded on Mon–Fri probes (e.g. Jul 2–6 events on Monday Jul 6).

Manual sync (only if automation failed): see `wsdc-telegram-bot/docs/PIPELINE_SNAPSHOT_SYNC.md`.
