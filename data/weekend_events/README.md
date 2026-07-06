# Upcoming weekend snapshots

Populated automatically by `wsdc-telegram-bot` after each Thursday `#Upcoming_WSDC_Events` post.

`check_updates.py` merges **concluded** events across all snapshots within a 21-day lookback (`EVENT_GATE_LOOKBACK_DAYS`). Carry-over from last week (e.g. delayed Neverland) stays in the gate together with the current weekend. Live WSDC data must cover **all** pending events before full-parse triggers.

On **Friday evening** (~20:00 Europe/Madrid), if some pending events are already in live data but one straggler is not (e.g. Neverland), the probe triggers full-parse anyway — but only when at least one event matched. Zero matches (single-event weekend not loaded) or no concluded events in the snapshot → no parse until the next week.

Events whose `end_date` is today count as concluded on Mon–Fri probes (e.g. Jul 2–6 events on Monday Jul 6).

Manual sync (only if automation failed): see `wsdc-telegram-bot/docs/PIPELINE_SNAPSHOT_SYNC.md`.
