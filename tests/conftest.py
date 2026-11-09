"""Test helpers: a scripted chat model and a replay store shaped like ClaimReplay's output."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from contextlib import closing
from datetime import date
from pathlib import Path

import pytest

from claim_scout.wins import ReplayView, WonDeal


def playbook_json(exemplar: int | None = None, headline: str = "Lead with a proof of concept.") -> str:
    return json.dumps({
        "headline": headline,
        "buyer_tendencies": ["Security reviews early"],
        "winning_moves": ["Proof of concept on a real pipeline"],
        "objections": [{"objection": "Too expensive", "best_response": "Payback case"}],
        "watch_outs": [],
        "exemplar_deal_id": exemplar,
        "exemplar_reason": "clearest example" if exemplar else None,
    })


class ScriptedModel:
    def __init__(self, respond: Callable[[str, str], str] | None = None):
        self.calls: list[tuple[str, str]] = []
        self._respond = respond or (lambda s, u: playbook_json())

    async def complete(self, system: str, user: str, *, json: bool = False) -> str:
        self.calls.append((system, user))
        return self._respond(system, user)


def won(deal_id: int, competitor: str | None = "Stackwise", industry: str | None = "Logistics",
        amount: float = 50_000, closed: date | None = None, text: str = "") -> WonDeal:
    replay = ReplayView(summary=f"Summary {deal_id}. {text}", turning_point=f"Turn {deal_id}",
                        winning_moves=[f"move {deal_id}"])
    return WonDeal(deal_id, f"Account {deal_id}", industry, competitor, amount,
                   closed or date(2026, 1, 1 + deal_id % 28), replay)


def write_replays(path: Path, deals: list[WonDeal]) -> None:
    with closing(sqlite3.connect(path)) as conn, conn:
        conn.execute("CREATE TABLE deal_replays (deal_id INTEGER PRIMARY KEY, account TEXT, industry TEXT, "
                     "competitor TEXT, amount REAL, closed_at TEXT, replay_json TEXT)")
        conn.executemany("INSERT INTO deal_replays VALUES (?, ?, ?, ?, ?, ?, ?)", [
            (d.deal_id, d.account, d.industry, d.competitor, d.amount, d.closed_at.isoformat(),
             d.replay.model_dump_json()) for d in deals
        ])


@pytest.fixture
def replay_db(tmp_path: Path) -> Path:
    path = tmp_path / "replays.sqlite3"
    deals = [won(i) for i in range(1, 5)] + [won(i, competitor=None, industry="Retail") for i in range(5, 8)]
    write_replays(path, deals)
    return path
