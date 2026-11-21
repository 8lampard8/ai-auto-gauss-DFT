"""SQLite job ledger.

Each job is stored as a JSON blob in the ``jobs`` table (with the id and
status mirrored as columns for cheap listing). The runners update job rows
from background threads as execution progresses, so every read-modify-write
is serialised with a process-wide lock and done inside one transaction.
"""
from __future__ import annotations

import datetime
import json
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterable, Iterator

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

_LOCK = threading.RLock()

# Terminal states: a late update from a watcher thread must not resurrect a
# job the user already cancelled.
TERMINAL = ("succeeded", "failed", "cancelled")


@contextmanager
def _conn() -> Iterator[sqlite3.Connection]:
    """Short-lived connection that is always committed *and closed*.

    (``with sqlite3.connect(...)`` alone only commits - it never closes the
    connection, which leaks file handles under the 4s polling of the UI.)
    """
    c = sqlite3.connect(DB_PATH, timeout=30)
    c.row_factory = sqlite3.Row
    try:
        # Idempotent; also recreates the table if the db file was removed.
        c.execute(_SCHEMA)
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def init() -> None:
    with _LOCK, _conn() as c:
        try:
            c.execute("PRAGMA journal_mode=WAL")
        except sqlite3.DatabaseError:
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
    with _LOCK, _conn() as c:
        c.execute(
            "INSERT INTO jobs(id, status, kind, created_at, data) VALUES (?,?,?,?,?)",
            (job_id, data["status"], data["kind"], now, json.dumps(data, ensure_ascii=False)),
        )
    return data


def get(job_id: str) -> dict | None:
    with _conn() as c:
        row = c.execute("SELECT data FROM jobs WHERE id=?", (job_id,)).fetchone()
    return json.loads(row["data"]) if row else None


def update(job_id: str, _skip_if_status: Iterable[str] | None = None,
           **fields: Any) -> dict | None:
    """Atomically merge ``fields`` into the job.

    If the job's current status is in ``_skip_if_status`` the update is
    dropped (returns the unchanged job) - used by watcher threads so that a
    cancelled job isn't overwritten with "failed" when its process dies.
    """
    with _LOCK, _conn() as c:
        row = c.execute("SELECT data FROM jobs WHERE id=?", (job_id,)).fetchone()
        if row is None:
            return None
        j = json.loads(row["data"])
        if _skip_if_status and j.get("status") in set(_skip_if_status):
            return j
        j.update(fields)
        j["updated_at"] = _now()
        c.execute(
            "UPDATE jobs SET status=?, kind=?, data=? WHERE id=?",
            (j.get("status"), j.get("kind"), json.dumps(j, ensure_ascii=False), job_id),
        )
    return j


def list_all() -> list[dict]:
    with _conn() as c:
        rows = c.execute("SELECT data FROM jobs ORDER BY created_at DESC").fetchall()
    return [json.loads(r["data"]) for r in rows]


def list_by_status(*statuses: str) -> list[dict]:
    if not statuses:
        return []
    q = ",".join("?" * len(statuses))
    with _conn() as c:
        rows = c.execute(f"SELECT data FROM jobs WHERE status IN ({q})", statuses).fetchall()
    return [json.loads(r["data"]) for r in rows]


def delete(job_id: str) -> bool:
    with _LOCK, _conn() as c:
        cur = c.execute("DELETE FROM jobs WHERE id=?", (job_id,))
        return cur.rowcount > 0


init()
