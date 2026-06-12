# Upcoming weekend snapshots

Populated automatically by `wsdc-telegram-bot` after each Thursday `#Upcoming_WSDC_Events` post.

`check_updates.py` uses the newest snapshot whose events are **not yet in Supabase** as the event-coverage gate (e.g. wait for Baltic Swing, skip J&J / Orange Blossom once loaded).

Manual sync (only if automation failed): see `wsdc-telegram-bot/docs/PIPELINE_SNAPSHOT_SYNC.md`.
