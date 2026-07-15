"""SQLite job ledger.

Each job is stored as a JSON blob in the ``jobs`` table (with the id and
status mirrored as columns for cheap listing). The runners update job rows
as execution progresses.
"""
from __future__ import annotations

import datetime
import json
import sqlite3
from typing import Any

from .config import DB_PATH


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    status TEXT,
    kind TEXT,
    created_at TEXT,
    data TEXT
)
"""


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    # Ensure the table on every connect: the db file may be removed at runtime
    # (e.g. during cleanup), and CREATE TABLE IF NOT EXISTS is cheap/idempotent.
    c.execute(_SCHEMA)
    c.commit()
    return c


def init() -> None:
    """Explicit initialiser (kept for compatibility); _conn() already ensures
    the schema, so this is a no-op."""
    with _conn() as c:
        pass


def create(job_id: str, **fields: Any) -> dict:
    now = _now()
    data = {
        "id": job_id,
        "status": "queued",
        "kind": "local",
        "created_at": now,
        "updated_at": now,
        **fields,
    }
    with _conn() as c:
        c.execute(
            "INSERT INTO jobs(id, status, kind, created_at, data) VALUES (?,?,?,?,?)",
            (job_id, data["status"], data["kind"], now, json.dumps(data, ensure_ascii=False)),
        )
    return data


def get(job_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT data FROM jobs WHERE id=?", (job_id,)).fetchone()
    return json.loads(row["data"]) if row else None


def update(job_id: str, **fields: Any) -> dict | None:
    j = get(job_id)
    if j is None:
        return None
    j.update(fields)
    j["updated_at"] = _now()
    with _conn() as c:
        c.execute(
            "UPDATE jobs SET status=?, kind=?, data=? WHERE id=?",
            (j.get("status"), j.get("kind"), json.dumps(j, ensure_ascii=False), job_id),
        )
    return j


def list_all() -> list[dict]:
    with _conn() as c:
        rows = c.execute(
            "SELECT data FROM jobs ORDER BY created_at DESC"
        ).fetchall()
    return [json.loads(r["data"]) for r in rows]


def delete(job_id: str) -> bool:
    with _conn() as c:
        cur = c.execute("DELETE FROM jobs WHERE id=?", (job_id,))
        return cur.rowcount > 0


init()
