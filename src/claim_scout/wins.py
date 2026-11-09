"""Won deals, as read back from ClaimReplay's replay store.

Only the fields a playbook needs are parsed, and unknown fields are
ignored, so ClaimReplay can grow its replay format without breaking this.
"""

from __future__ import annotations

import logging
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError

logger = logging.getLogger(__name__)


class _Objection(BaseModel):
    model_config = ConfigDict(extra="ignore")
    objection: str
    response: str
    outcome: str = "resolved"


class ReplayView(BaseModel):
    model_config = ConfigDict(extra="ignore")
    summary: str = ""
    turning_point: str = ""
    winning_moves: list[str] = []
    objections: list[_Objection] = []
    competitor_notes: str | None = None


@dataclass(frozen=True)
class WonDeal:
    deal_id: int
    account: str
    industry: str | None
    competitor: str | None      # None: no competing vendor, the alternative was the status quo
    amount: float | None
    closed_at: date | None
    replay: ReplayView

    def card(self) -> str:
        """The deal as the model sees it in a playbook prompt."""
        amount = f"${self.amount:,.0f}/yr" if self.amount else "amount unknown"
        lines = [
            f"DEAL {self.deal_id} | {self.account} | {self.industry or 'industry unknown'} | {amount} | "
            f"won {self.closed_at or 'date unknown'} | vs {self.competitor or 'status quo'}",
            f"Summary: {self.replay.summary}",
            f"Turning point: {self.replay.turning_point}",
        ]
        lines += [f"Move: {m}" for m in self.replay.winning_moves]
        lines += [f'Objection: "{o.objection}" -> {o.response} ({o.outcome})' for o in self.replay.objections]
        if self.replay.competitor_notes:
            lines.append(f"Versus competitor: {self.replay.competitor_notes}")
        return "\n".join(lines)


def _to_date(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value[:10]) if value else None
    except ValueError:
        return None


def load_wins(replay_db: Path) -> list[WonDeal]:
    """Every replayed deal. A replay that can't be parsed is skipped and logged by id."""
    if not Path(replay_db).exists():
        logger.warning("No replay store at %s; run ClaimReplay first", replay_db)
        return []
    uri = f"{Path(replay_db).resolve().as_uri()}?mode=ro"
    with closing(sqlite3.connect(uri, uri=True)) as conn:
        rows = conn.execute(
            "SELECT deal_id, account, industry, competitor, amount, closed_at, replay_json FROM deal_replays"
        ).fetchall()
    wins = []
    for deal_id, account, industry, competitor, amount, closed_at, replay_json in rows:
        try:
            replay = ReplayView.model_validate_json(replay_json)
        except ValidationError:
            logger.warning("deal %s: replay could not be parsed, skipped", deal_id)
            continue
        wins.append(WonDeal(deal_id, account, industry, competitor or None, amount, _to_date(closed_at), replay))
    return wins
