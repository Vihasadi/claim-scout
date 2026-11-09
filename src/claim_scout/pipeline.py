"""One run: load wins → cut segments → build every playbook → replace the store.

If segments qualified but every one of them failed (the model server was
down, say), the store is left alone: last run's playbooks are more useful
than none.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from pathlib import Path

from claim_scout import prompts
from claim_scout.builder import PlaybookBuilder
from claim_scout.llm import ChatModel
from claim_scout.segments import build_segments
from claim_scout.store import PlaybookStore
from claim_scout.wins import load_wins

logger = logging.getLogger(__name__)


@dataclass
class RunStats:
    wins: int = 0
    segments: int = 0
    built: int = 0
    failed: int = 0
    written: bool = False
    seconds: float = 0.0


async def run(
    replay_db: Path, store: PlaybookStore, model: ChatModel, *, prompt_budget: int, min_deals: int, sample_size: int,
) -> RunStats:
    started = time.perf_counter()
    wins = load_wins(replay_db)
    segments = build_segments(wins, min_deals)
    stats = RunStats(wins=len(wins), segments=len(segments))

    builder = PlaybookBuilder(model, prompt_budget, sample_size)
    by_id = {w.deal_id: w for w in wins}
    results = await asyncio.gather(*(builder.build(s, by_id) for s in segments))
    built = [r for r in results if r is not None]
    stats.built, stats.failed = len(built), len(segments) - len(built)

    if segments and not built:
        logger.error("all %d segments failed; keeping the previous playbooks", len(segments))
    else:
        store.replace_all(built, prompts.PROMPT_VERSION)
        stats.written = True
    stats.seconds = round(time.perf_counter() - started, 1)
    logger.info("run finished: %s", stats)
    return stats
