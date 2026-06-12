"""Database connection helpers."""

import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from dotenv import load_dotenv

# Supabase adds these for Prisma/pgbouncer; psycopg rejects unknown URI params.
_STRIP_QUERY_PARAMS = {"pgbouncer", "connection_limit"}


def load_database_url() -> str:
    load_dotenv(Path(__file__).parent.parent / ".env")
    dsn = os.getenv("DATABASE_URL", "").strip().strip('"').strip("'")
    if not dsn:
        sys.exit("DATABASE_URL is not set (expected in .env or environment)")
    return sanitize_database_url(dsn)


def sanitize_database_url(dsn: str) -> str:
    """Remove Supabase-specific query params that psycopg cannot parse."""
    parsed = urlparse(dsn.strip().strip('"').strip("'"))
    if not parsed.query:
        return dsn
    params = parse_qs(parsed.query, keep_blank_values=True)
    filtered = {k: v for k, v in params.items() if k not in _STRIP_QUERY_PARAMS}
    query = urlencode(filtered, doseq=True)
    return urlunparse(parsed._replace(query=query))
