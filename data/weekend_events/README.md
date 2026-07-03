# Upcoming weekend snapshots

Populated automatically by `wsdc-telegram-bot` after each Thursday `#Upcoming_WSDC_Events` post.

`check_updates.py` uses the newest snapshot whose events are **not yet in Supabase** as the event-coverage gate (e.g. wait for Baltic Swing, skip J&J / Orange Blossom once loaded).

On **Friday evening** (~20:00 Europe/Madrid), if some pending events are already in live data but one straggler is not (e.g. Neverland), the probe triggers full-parse anyway — but only when at least one event matched. Zero matches (single-event weekend not loaded) or no concluded events in the snapshot → no parse until the next week.

Manual sync (only if automation failed): see `wsdc-telegram-bot/docs/PIPELINE_SNAPSHOT_SYNC.md`.
