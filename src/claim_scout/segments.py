"""Cutting the won deals into segments worth a playbook.

Three cuts, from most to least specific:

- competitor + industry: "beating Stackwise at logistics companies"
- competitor:            "beating Stackwise"
- industry:              "winning logistics companies", whoever we were up against

Deals with no competing vendor count as their own "competitor", the status
quo, because winning against doing nothing is a different sale from winning
against another vendor.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Literal

from claim_scout.wins import WonDeal

Kind = Literal["competitor_industry", "competitor", "industry"]
STATUS_QUO = "status quo"


@dataclass(frozen=True)
class Segment:
    kind: Kind
    competitor: str | None   # STATUS_QUO for deals with no competing vendor; None for industry segments
    industry: str | None     # None for competitor segments
    deal_ids: tuple[int, ...]

    @property
    def label(self) -> str:
        parts = [f"vs {self.competitor}" if self.competitor else None, self.industry]
        return " / ".join(p for p in parts if p)


def build_segments(wins: Iterable[WonDeal], min_deals: int) -> list[Segment]:
    """Every segment with at least `min_deals` deals, most specific kind first."""
    buckets: dict[tuple[Kind, str | None, str | None], list[int]] = defaultdict(list)
    for w in wins:
        rival = w.competitor or STATUS_QUO
        buckets[("competitor", rival, None)].append(w.deal_id)
        if w.industry:
            buckets[("industry", None, w.industry)].append(w.deal_id)
            buckets[("competitor_industry", rival, w.industry)].append(w.deal_id)

    order = {"competitor_industry": 0, "competitor": 1, "industry": 2}
    segments = [Segment(kind, rival, industry, tuple(ids))
                for (kind, rival, industry), ids in buckets.items() if len(ids) >= min_deals]
    return sorted(segments, key=lambda s: (order[s.kind], s.label))
