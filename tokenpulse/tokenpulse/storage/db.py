"""SQLite-backed persistent storage.

The store keeps a single row per parsed usage record (keyed by `id`) and a
row per detected user interaction.  A small in-memory cache is maintained
so the UI can poll cheap aggregates without re-walking the entire table.
"""

from __future__ import annotations

import sqlite3
import threading
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ..core.models import UsageRecord, InteractionRecord, RateLimitSnapshot


_CREATE_USAGE = """
CREATE TABLE IF NOT EXISTS usage_records (
    id TEXT PRIMARY KEY,
    ts INTEGER NOT NULL,
    tool TEXT NOT NULL,
    model TEXT NOT NULL,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cache_read_tokens INTEGER NOT NULL DEFAULT 0,
    cache_write_tokens INTEGER NOT NULL DEFAULT 0,
    thinking_tokens INTEGER NOT NULL DEFAULT 0,
    cost REAL NOT NULL DEFAULT 0,
    session_id TEXT,
    source_file TEXT NOT NULL,
    plan_type TEXT,
    primary_used_percent REAL,
    primary_resets_at INTEGER,
    secondary_used_percent REAL,
    secondary_resets_at INTEGER
);
"""

_CREATE_USAGE_INDEX = [
    "CREATE INDEX IF NOT EXISTS idx_usage_ts ON usage_records(ts);",
    "CREATE INDEX IF NOT EXISTS idx_usage_tool_ts ON usage_records(tool, ts);",
    "CREATE INDEX IF NOT EXISTS idx_usage_session ON usage_records(session_id);",
]

_CREATE_INTERACTION = """
CREATE TABLE IF NOT EXISTS interactions (
    id TEXT PRIMARY KEY,
    ts INTEGER NOT NULL,
    tool TEXT NOT NULL,
    session_id TEXT NOT NULL,
    source_file TEXT NOT NULL,
    plan_type TEXT
);
"""

_CREATE_INTERACTION_INDEX = [
    "CREATE INDEX IF NOT EXISTS idx_interaction_ts ON interactions(ts);",
    "CREATE INDEX IF NOT EXISTS idx_interaction_tool_ts ON interactions(tool, ts);",
]

_CREATE_META = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@dataclass
class Totals:
    """Aggregate counters used by the dashboard."""

    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    thinking_tokens: int = 0
    cost: float = 0.0
    records: int = 0
    interactions: int = 0

    @classmethod
    def zero(cls) -> "Totals":
        return cls()

    def add(self, other: "Totals") -> None:
        self.total_tokens += other.total_tokens
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.cache_write_tokens += other.cache_write_tokens
        self.thinking_tokens += other.thinking_tokens
        self.cost += other.cost
        self.records += other.records
        self.interactions += other.interactions


class Storage:
    """Thread-safe SQLite store with a tiny in-memory cache."""

    def __init__(self, path: Path):
        self._path = path
        self._lock = threading.RLock()
        # check_same_thread=False is fine because we serialize with self._lock.
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.row_factory = sqlite3.Row
        self._init_schema()
        # In-memory aggregates so the UI never has to re-scan the table
        # every paint cycle.
        self._cache_totals = Totals.zero()
        self._cache_by_tool: dict[str, Totals] = defaultdict(Totals.zero)
        self._cache_by_hour: dict[int, Totals] = defaultdict(Totals.zero)  # key: hour bucket
        self._cache_latest_rate: Optional[RateLimitSnapshot] = None
        self._cache_rate_by_tool: dict[str, RateLimitSnapshot] = {}
        self._rebuild_cache()

    # --------------------------------------------------------------- schema
    def _init_schema(self) -> None:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(_CREATE_USAGE)
            cur.execute(_CREATE_INTERACTION)
            cur.execute(_CREATE_META)
            for stmt in _CREATE_USAGE_INDEX + _CREATE_INTERACTION_INDEX:
                cur.execute(stmt)
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # ---------------------------------------------------------------- writes
    def upsert_usage(self, record: UsageRecord) -> bool:
        """Insert a usage record.  Returns True if it was brand-new."""
        with self._lock:
            # Read the existing row BEFORE we overwrite it, so the cache
            # update can subtract the prior contribution.
            existing_row = self._conn.execute(
                "SELECT * FROM usage_records WHERE id = ?", (record.id,)
            ).fetchone()
            existing = self._row_to_record(existing_row) if existing_row else None
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT OR REPLACE INTO usage_records
                (id, ts, tool, model, input_tokens, output_tokens,
                 cache_read_tokens, cache_write_tokens, thinking_tokens,
                 cost, session_id, source_file, plan_type,
                 primary_used_percent, primary_resets_at,
                 secondary_used_percent, secondary_resets_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.ts,
                    record.tool,
                    record.model,
                    record.input_tokens,
                    record.output_tokens,
                    record.cache_read_tokens,
                    record.cache_write_tokens,
                    record.thinking_tokens,
                    record.cost,
                    record.session_id,
                    record.source_file,
                    record.plan_type,
                    record.primary_used_percent,
                    record.primary_resets_at,
                    record.secondary_used_percent,
                    record.secondary_resets_at,
                ),
            )
            self._conn.commit()
            self._update_cache_after_upsert(record, existing)
            return existing is None

    def upsert_interaction(self, record: InteractionRecord) -> bool:
        with self._lock:
            cur = self._conn.cursor()
            cur.execute(
                """
                INSERT OR IGNORE INTO interactions
                (id, ts, tool, session_id, source_file, plan_type)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.ts,
                    record.tool,
                    record.session_id,
                    record.source_file,
                    record.plan_type,
                ),
            )
            self._conn.commit()
            added = cur.rowcount > 0
            if added:
                self._cache_totals.interactions += 1
                self._cache_by_tool[record.tool].interactions += 1
            return added

    # ------------------------------------------------------------------ reads
    def totals(self) -> Totals:
        with self._lock:
            return Totals(
                total_tokens=self._cache_totals.total_tokens,
                input_tokens=self._cache_totals.input_tokens,
                output_tokens=self._cache_totals.output_tokens,
                cache_read_tokens=self._cache_totals.cache_read_tokens,
                cache_write_tokens=self._cache_totals.cache_write_tokens,
                thinking_tokens=self._cache_totals.thinking_tokens,
                cost=self._cache_totals.cost,
                records=self._cache_totals.records,
                interactions=self._cache_totals.interactions,
            )

    def totals_by_tool(self) -> dict[str, Totals]:
        with self._lock:
            return {k: Totals(**{f: getattr(v, f) for f in (
                "total_tokens", "input_tokens", "output_tokens",
                "cache_read_tokens", "cache_write_tokens", "thinking_tokens",
                "cost", "records", "interactions"
            )}) for k, v in self._cache_by_tool.items()}

    def hourly(self, since_ms: int) -> list[tuple[int, Totals]]:
        """Return hour-bucketed totals for the last `since_ms` milliseconds."""
        with self._lock:
            out: list[tuple[int, Totals]] = []
            for hour_ts, totals in sorted(self._cache_by_hour.items()):
                if hour_ts * 3600_000 >= since_ms:
                    out.append((hour_ts, totals))
            return out

    def latest_rate_limit(self) -> Optional[RateLimitSnapshot]:
        with self._lock:
            return self._cache_latest_rate

    def rate_limits_by_tool(self) -> dict[str, RateLimitSnapshot]:
        with self._lock:
            return dict(self._cache_rate_by_tool)

    def recent_records(self, limit: int = 50) -> list[UsageRecord]:
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM usage_records ORDER BY ts DESC LIMIT ?",
                (limit,),
            )
            return [self._row_to_record(r) for r in cur.fetchall()]

    def record_count(self) -> int:
        with self._lock:
            cur = self._conn.execute("SELECT COUNT(*) AS n FROM usage_records")
            return int(cur.fetchone()["n"])

    def last_known_ts(self) -> int:
        with self._lock:
            cur = self._conn.execute("SELECT MAX(ts) AS t FROM usage_records")
            row = cur.fetchone()
            return int(row["t"] or 0)

    # --------------------------------------------------------------- helpers
    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> UsageRecord:
        return UsageRecord(
            id=row["id"],
            ts=row["ts"],
            tool=row["tool"],
            model=row["model"],
            input_tokens=row["input_tokens"],
            output_tokens=row["output_tokens"],
            cache_read_tokens=row["cache_read_tokens"],
            cache_write_tokens=row["cache_write_tokens"],
            thinking_tokens=row["thinking_tokens"],
            cost=row["cost"],
            session_id=row["session_id"],
            source_file=row["source_file"],
            plan_type=row["plan_type"],
            primary_used_percent=row["primary_used_percent"],
            primary_resets_at=row["primary_resets_at"],
            secondary_used_percent=row["secondary_used_percent"],
            secondary_resets_at=row["secondary_resets_at"],
        )

    def breakdown_by_tool(self) -> dict:
        """Return {tool: {category: tokens}} aggregates."""
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT tool,
                       SUM(input_tokens) AS inp,
                       SUM(output_tokens) AS out,
                       SUM(cache_read_tokens) AS cr,
                       SUM(cache_write_tokens) AS cw,
                       SUM(thinking_tokens) AS th
                FROM usage_records
                GROUP BY tool
                """
            )
            out: dict = {}
            for row in cur.fetchall():
                out[row["tool"]] = {
                    "input": int(row["inp"] or 0),
                    "output": int(row["out"] or 0),
                    "cache_read": int(row["cr"] or 0),
                    "cache_write": int(row["cw"] or 0),
                    "thinking": int(row["th"] or 0),
                }
            return out

    def _add_to_cache(self, record: UsageRecord) -> None:
        """Add one record to every aggregate bucket."""
        self._cache_totals.total_tokens += record.total_tokens
        self._cache_totals.input_tokens += record.input_tokens
        self._cache_totals.output_tokens += record.output_tokens
        self._cache_totals.cache_read_tokens += record.cache_read_tokens
        self._cache_totals.cache_write_tokens += record.cache_write_tokens
        self._cache_totals.thinking_tokens += record.thinking_tokens
        self._cache_totals.cost += record.cost
        tool = self._cache_by_tool[record.tool]
        tool.total_tokens += record.total_tokens
        tool.input_tokens += record.input_tokens
        tool.output_tokens += record.output_tokens
        tool.cache_read_tokens += record.cache_read_tokens
        tool.cache_write_tokens += record.cache_write_tokens
        tool.thinking_tokens += record.thinking_tokens
        tool.cost += record.cost
        hour = record.ts // 3_600_000
        bucket = self._cache_by_hour[hour]
        bucket.total_tokens += record.total_tokens
        bucket.input_tokens += record.input_tokens
        bucket.output_tokens += record.output_tokens
        bucket.cache_read_tokens += record.cache_read_tokens
        bucket.cache_write_tokens += record.cache_write_tokens
        bucket.thinking_tokens += record.thinking_tokens
        bucket.cost += record.cost
        bucket.records += 1

        if record.primary_used_percent is not None or record.secondary_used_percent is not None:
            snap = RateLimitSnapshot(
                tool=record.tool,
                plan_type=record.plan_type,
                primary_used_percent=record.primary_used_percent,
                primary_resets_at=record.primary_resets_at,
                secondary_used_percent=record.secondary_used_percent,
                secondary_resets_at=record.secondary_resets_at,
                ts=record.ts,
            )
            self._cache_latest_rate = snap
            self._cache_rate_by_tool[record.tool] = snap

    def _sub_from_cache(self, record: UsageRecord) -> None:
        """Remove one record from every aggregate bucket."""
        self._cache_totals.total_tokens -= record.total_tokens
        self._cache_totals.input_tokens -= record.input_tokens
        self._cache_totals.output_tokens -= record.output_tokens
        self._cache_totals.cache_read_tokens -= record.cache_read_tokens
        self._cache_totals.cache_write_tokens -= record.cache_write_tokens
        self._cache_totals.thinking_tokens -= record.thinking_tokens
        self._cache_totals.cost -= record.cost
        tool = self._cache_by_tool[record.tool]
        tool.total_tokens -= record.total_tokens
        tool.input_tokens -= record.input_tokens
        tool.output_tokens -= record.output_tokens
        tool.cache_read_tokens -= record.cache_read_tokens
        tool.cache_write_tokens -= record.cache_write_tokens
        tool.thinking_tokens -= record.thinking_tokens
        tool.cost -= record.cost
        hour = record.ts // 3_600_000
        bucket = self._cache_by_hour[hour]
        bucket.total_tokens -= record.total_tokens
        bucket.input_tokens -= record.input_tokens
        bucket.output_tokens -= record.output_tokens
        bucket.cache_read_tokens -= record.cache_read_tokens
        bucket.cache_write_tokens -= record.cache_write_tokens
        bucket.thinking_tokens -= record.thinking_tokens
        bucket.cost -= record.cost
        bucket.records -= 1

    def _update_cache_after_upsert(
        self, record: UsageRecord, existing: Optional[UsageRecord] = None
    ) -> None:
        """Apply an upsert to the in-memory cache atomically.

        ``existing`` is the row that lived in the DB before this upsert
        (or ``None`` for a brand-new id).  Callers should pass it
        explicitly to avoid re-reading the DB after the row was
        overwritten.
        """
        is_new = existing is None
        if not is_new:
            differs = (
                existing.ts != record.ts
                or existing.tool != record.tool
                or existing.model != record.model
                or existing.input_tokens != record.input_tokens
                or existing.output_tokens != record.output_tokens
                or existing.cache_read_tokens != record.cache_read_tokens
                or existing.cache_write_tokens != record.cache_write_tokens
                or existing.thinking_tokens != record.thinking_tokens
                or existing.cost != record.cost
            )
            if not differs:
                # No change in user-visible counters: keep the cache
                # as-is, but the rate-limit snapshot may have moved
                # forward, so update that part.
                if record.primary_used_percent is not None or record.secondary_used_percent is not None:
                    snap = RateLimitSnapshot(
                        tool=record.tool,
                        plan_type=record.plan_type,
                        primary_used_percent=record.primary_used_percent,
                        primary_resets_at=record.primary_resets_at,
                        secondary_used_percent=record.secondary_used_percent,
                        secondary_resets_at=record.secondary_resets_at,
                        ts=record.ts,
                    )
                    self._cache_latest_rate = snap
                    self._cache_rate_by_tool[record.tool] = snap
                return
            # Roll back the old contribution before adding the new one.
            self._sub_from_cache(existing)
            # records count is the number of unique ids, which does not
            # change on REPLACE.
        # Apply the new row.
        self._add_to_cache(record)
        if is_new:
            self._cache_by_tool[record.tool].records += 1
            self._cache_totals.records += 1

    def _rebuild_cache(self) -> None:
        with self._lock:
            self._cache_totals = Totals.zero()
            self._cache_by_tool = defaultdict(Totals.zero)
            self._cache_by_hour = defaultdict(Totals.zero)
            self._cache_latest_rate = None
            self._cache_rate_by_tool = {}
            cur = self._conn.execute("SELECT * FROM usage_records")
            for row in cur.fetchall():
                rec = self._row_to_record(row)
                self._add_to_cache(rec)
                self._cache_by_tool[rec.tool].records += 1
                self._cache_totals.records += 1
            cur = self._conn.execute("SELECT COUNT(*) AS n FROM interactions")
            self._cache_totals.interactions = int(cur.fetchone()["n"])
            cur = self._conn.execute("SELECT tool, COUNT(*) AS n FROM interactions GROUP BY tool")
            for row in cur.fetchall():
                self._cache_by_tool[row["tool"]].interactions = int(row["n"])
