"""Builds one segment's playbook.

The sampled deal cards usually fit in one prompt. When they don't, they are
packed into batches, each batch yields a draft playbook (in parallel), and
a merge call reconciles the drafts. The exemplar deal is then checked in
code: a model can name a plausible-looking id it was never shown, and a
playbook pointing at the wrong deal is worse than one pointing at none.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from claim_scout import prompts
from claim_scout.budget import estimate_tokens, pack
from claim_scout.llm import ChatModel
from claim_scout.sampling import pick_sample
from claim_scout.schema import Playbook
from claim_scout.segments import Segment
from claim_scout.structured import ask, prompt_tokens
from claim_scout.wins import WonDeal

logger = logging.getLogger(__name__)

_SLACK = 80


@dataclass(frozen=True)
class BuiltPlaybook:
    segment: Segment
    playbook: Playbook
    sample_size: int
    batches: int


class PlaybookBuilder:
    def __init__(self, model: ChatModel, prompt_budget: int, sample_size: int):
        self._model = model
        self._budget = prompt_budget
        self._sample_size = sample_size

    async def build(self, segment: Segment, wins: dict[int, WonDeal]) -> BuiltPlaybook | None:
        """The playbook, or None if the model could not produce a valid one (logged)."""
        sample = pick_sample([wins[i] for i in segment.deal_ids], self._sample_size)
        system = prompts.system_prompt(segment)
        room = self._budget - prompt_tokens(system, Playbook) - _SLACK
        cards = [d.card() for d in sample]
        batches = pack(cards, room)
        try:
            if len(batches) == 1:
                message = prompts.deals_message(segment, batches[0], shown=len(sample))
                playbook = await ask(self._model, system, message, Playbook)
            else:
                playbook = await self._build_in_batches(segment, system, batches, len(sample))
        except Exception as exc:  # noqa: BLE001 - one segment failing must not stop the others
            logger.warning("segment %s failed: %s", segment.label, type(exc).__name__)
            return None

        shown = {d.deal_id for d in sample}
        if playbook.exemplar_deal_id is not None and playbook.exemplar_deal_id not in shown:
            logger.info("segment %s: exemplar %s was not in the sample, dropped", segment.label,
                        playbook.exemplar_deal_id)
            playbook = playbook.model_copy(update={"exemplar_deal_id": None, "exemplar_reason": None})
        return BuiltPlaybook(segment, playbook, sample_size=len(sample), batches=len(batches))

    async def _build_in_batches(self, segment: Segment, system: str, batches: list[str], shown: int) -> Playbook:
        drafts = await asyncio.gather(*(
            ask(self._model, system,
                prompts.deals_message(segment, batch, shown=shown, part=(i, len(batches))), Playbook)
            for i, batch in enumerate(batches, start=1)
        ))
        merge_input = "\n\n".join(f"DRAFT {i}\n{d.model_dump_json()}" for i, d in enumerate(drafts, start=1))
        room = self._budget - prompt_tokens(prompts.MERGE_SYSTEM, Playbook) - _SLACK
        if estimate_tokens(merge_input) > room:
            # Drafts are short; this only trips with a tiny context window. Merge the first ones that fit.
            merge_input = pack(merge_input.split("\n\n"), room)[0]
        return await ask(self._model, prompts.MERGE_SYSTEM, f"Segment: {segment.label}\n\n{merge_input}", Playbook)
