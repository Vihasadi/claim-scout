"""Choosing which deals of a big segment the model gets to read.

Half the sample is the most recent wins, because what works changes as
competitors change pricing and products. The other half is spread evenly
across deal size, so a playbook for a segment full of small deals still
learns from the few large ones (and the reverse).

The selection is deterministic: the same deals give the same sample, so a
re-run changes a playbook only when the wins themselves changed.
"""

from __future__ import annotations

from datetime import date

from claim_scout.wins import WonDeal


def pick_sample(deals: list[WonDeal], size: int) -> list[WonDeal]:
    if len(deals) <= size:
        return sorted(deals, key=_newest_first)
    by_recency = sorted(deals, key=_newest_first)
    recent = by_recency[: size // 2]
    rest = sorted(by_recency[size // 2:], key=lambda d: (d.amount or 0, d.deal_id))
    slots = size - len(recent)
    step = len(rest) / slots
    spread = [rest[int(i * step + step / 2)] for i in range(slots)]  # the middle of each size band
    return recent + spread


def _newest_first(deal: WonDeal) -> tuple[int, int]:
    return (-(deal.closed_at or date.min).toordinal(), deal.deal_id)
