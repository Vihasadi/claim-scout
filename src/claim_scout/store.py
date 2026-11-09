"""The playbook store.

Playbooks describe the current set of wins, so each run replaces the whole
table inside one transaction: readers (ClaimPrep, ClaimCoach) see either last
run's playbooks or this run's, never a mix.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from contextlib import closing
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from claim_scout.builder import BuiltPlaybook
from claim_scout.schema import Playbook

_SCHEMA = """
CREATE TABLE IF NOT EXISTS segment_playbooks (
    id             INTEGER PRIMARY KEY,
    kind           TEXT    NOT NULL,   -- competitor_industry, competitor, industry
    competitor     TEXT,               -- 'status quo' when there was no competing vendor
    industry       TEXT,
    deal_count     INTEGER NOT NULL,   -- every won deal in the segment
    sample_size    INTEGER NOT NULL,   -- deals the model actually read
    playbook_json  TEXT    NOT NULL,
    prompt_version TEXT    NOT NULL,
    generated_at   TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_segment_playbooks_lookup ON segment_playbooks (competitor, industry);
"""


@dataclass(frozen=True)
class StoredPlaybook:
    kind: str
    competitor: str | None
    industry: str | None
    deal_count: int
    playbook: Playbook
    generated_at: str


class PlaybookStore:
    def __init__(self, path: Path):
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(self._path)) as conn:
            conn.executescript(_SCHEMA)

    def replace_all(self, built: Sequence[BuiltPlaybook], prompt_version: str) -> None:
        now = datetime.now(UTC).isoformat(timespec="seconds")
        rows = [(b.segment.kind, b.segment.competitor, b.segment.industry, len(b.segment.deal_ids), b.sample_size,
                 b.playbook.model_dump_json(), prompt_version, now) for b in built]
        with closing(sqlite3.connect(self._path)) as conn, conn:
            conn.execute("DELETE FROM segment_playbooks")
            conn.executemany(
                "INSERT INTO segment_playbooks (kind, competitor, industry, deal_count, sample_size, playbook_json, "
                "prompt_version, generated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)

    def all(self) -> list[StoredPlaybook]:
        with closing(sqlite3.connect(self._path)) as conn:
            rows = conn.execute(
                "SELECT kind, competitor, industry, deal_count, playbook_json, generated_at FROM segment_playbooks "
                "ORDER BY kind, competitor, industry").fetchall()
        return [StoredPlaybook(k, c, i, n, Playbook.model_validate_json(p), g) for k, c, i, n, p, g in rows]
