from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

from .base import DbBackend
from .postgres import PostgresBackend
from .sqlite import SqliteBackend


def make_backend(target: Path | str | None) -> DbBackend:
    if isinstance(target, Path):
        return SqliteBackend(target)
    load_dotenv()
    dsn = target or os.environ.get("DATABASE_URL")
    if not dsn:
        msg = "DATABASE_URL is not set; cannot connect to Postgres."
        raise RuntimeError(msg)
    return PostgresBackend(dsn)
