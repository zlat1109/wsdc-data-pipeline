"""Database connection helpers."""

import os
import re
import sys
from pathlib import Path
from typing import Any

import psycopg
from dotenv import load_dotenv

# Supabase adds these for Prisma/pgbouncer; psycopg rejects unknown URI params.
_STRIP_QUERY_RE = re.compile(
    r"[?&](?:pgbouncer=(?:true|false)|connection_limit=\d+)"
)


def _load_env() -> None:
    load_dotenv(Path(__file__).parent.parent / ".env")


def sanitize_database_url(dsn: str) -> str:
    """Remove Supabase-specific query params without urlparse (breaks on special chars)."""
    dsn = dsn.strip().strip('"').strip("'")
    dsn = _STRIP_QUERY_RE.sub("", dsn)
    return dsn.rstrip("?&")


def _parse_database_url(dsn: str) -> dict[str, Any]:
    """Parse postgresql:// URL; uses rsplit('@') so passwords may contain '@'."""
    dsn = sanitize_database_url(dsn)
    if not dsn.startswith(("postgresql://", "postgres://")):
        raise ValueError("DATABASE_URL must start with postgresql:// or postgres://")

    remainder = dsn.split("://", 1)[1]
    if "/" in remainder:
        authority, _, path_part = remainder.partition("/")
        dbname = path_part.split("?", 1)[0] or "postgres"
    else:
        authority = remainder.split("?", 1)[0]
        dbname = "postgres"

    if "@" not in authority:
        raise ValueError("DATABASE_URL is missing user/password or host")

    userinfo, hostport = authority.rsplit("@", 1)
    user, _, password = userinfo.partition(":")
    if not user:
        raise ValueError("DATABASE_URL is missing database user")

    host = hostport
    port = 5432
    if ":" in hostport:
        host, port_str = hostport.rsplit(":", 1)
        port = int(port_str)

    return {
        "host": host,
        "port": port,
        "dbname": dbname,
        "user": user,
        "password": password,
        "sslmode": os.getenv("DB_SSLMODE", "require"),
    }


def get_connection_kwargs() -> dict[str, Any]:
    """Build psycopg connection kwargs from .env."""
    _load_env()

    # Optional split vars — safest when password has special characters.
    if os.getenv("DB_PASSWORD"):
        return {
            "host": os.getenv("DB_HOST", "localhost").strip(),
            "port": int(os.getenv("DB_PORT", "5432")),
            "dbname": os.getenv("DB_NAME", "postgres").strip(),
            "user": os.getenv("DB_USER", "postgres").strip(),
            "password": os.getenv("DB_PASSWORD", "").strip().strip('"').strip("'"),
            "sslmode": os.getenv("DB_SSLMODE", "require"),
        }

    dsn = os.getenv("DATABASE_URL", "").strip().strip('"').strip("'")
    if not dsn:
        sys.exit(
            "DATABASE_URL is not set (expected in .env).\n"
            "Tip: if your password has special characters (@, #, !), "
            "set DB_HOST, DB_USER, DB_PASSWORD, DB_PORT, DB_NAME instead."
        )
    return _parse_database_url(dsn)


def connect():
    """Open a psycopg connection using .env settings."""
    return psycopg.connect(**get_connection_kwargs())


def load_database_url() -> str:
    """Return a sanitized URI (legacy helper). Prefer connect() instead."""
    return sanitize_database_url(
        os.getenv("DATABASE_URL", "").strip().strip('"').strip("'")
        or _kwargs_to_uri(get_connection_kwargs())
    )


def _kwargs_to_uri(kwargs: dict[str, Any]) -> str:
    from urllib.parse import quote

    user = quote(str(kwargs["user"]), safe="")
    password = quote(str(kwargs.get("password", "")), safe="")
    host = kwargs["host"]
    port = kwargs["port"]
    dbname = kwargs["dbname"]
    return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"
