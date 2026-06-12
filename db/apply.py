"""Apply SQL migrations from db/migrations/ in filename order.

Applied migrations are recorded in public.schema_migrations and skipped
on subsequent runs. Each migration runs in its own transaction.

Usage:
    python db/apply.py             # apply pending migrations
    python db/apply.py --dry-run   # only show what would be applied
"""

import argparse
import sys
from pathlib import Path

import psycopg

from connection import load_database_url

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    migrations = sorted(MIGRATIONS_DIR.glob("[0-9]*.sql"))
    if not migrations:
        sys.exit(f"No migrations found in {MIGRATIONS_DIR}")

    with psycopg.connect(load_database_url()) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS public.schema_migrations (
                    filename   text PRIMARY KEY,
                    applied_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
            cur.execute("SELECT filename FROM public.schema_migrations")
            applied = {row[0] for row in cur.fetchall()}
        conn.commit()

        pending = [m for m in migrations if m.name not in applied]
        if not pending:
            print("Nothing to apply: all migrations are up to date.")
            return

        for migration in pending:
            if args.dry_run:
                print(f"Would apply: {migration.name}")
                continue
            print(f"Applying {migration.name} ...", end=" ", flush=True)
            with conn.cursor() as cur:
                cur.execute(migration.read_text(encoding="utf-8"))
                cur.execute(
                    "INSERT INTO public.schema_migrations (filename) VALUES (%s)",
                    (migration.name,),
                )
            conn.commit()
            print("OK")

    print(f"Done: {len(pending)} migration(s) {'pending' if args.dry_run else 'applied'}.")


if __name__ == "__main__":
    main()
