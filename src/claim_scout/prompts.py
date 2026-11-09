"""Prompt text. Bump PROMPT_VERSION whenever a prompt changes meaning; it is stored with each playbook."""

from __future__ import annotations

from claim_scout.segments import STATUS_QUO, Segment

PROMPT_VERSION = "2026-11-a"

_SCOPE = {
    "competitor_industry": "deals we won against {competitor} at {industry} companies",
    "competitor": "deals we won against {competitor}, across industries",
    "industry": "deals we won at {industry} companies, whoever we were up against",
}

_STATUS_QUO_NOTE = (
    "In these deals there was no competing vendor: the buyer's alternative was to change nothing and keep "
    "their in-house checks. Treat inertia, not a rival product, as the thing we beat.\n\n"
)

_RULES = """\
Rules:
- A pattern needs support from at least two deals. One-off events go in watch_outs at most.
- Use only what the deal cards say. No outside knowledge about vendors or industries.
- Write for an account executive preparing for a deal like these: specific and reusable, no filler.
- exemplar_deal_id must be one of the DEAL ids shown, or null."""


def system_prompt(segment: Segment) -> str:
    scope = _SCOPE[segment.kind].format(competitor=segment.competitor, industry=segment.industry)
    note = _STATUS_QUO_NOTE if segment.competitor == STATUS_QUO else ""
    return (
        "You are a sales strategist. Below are summaries of "
        f"{scope}. Each card says how one deal was won. Find what these wins have in common and turn it "
        f"into a playbook for the next deal like them.\n\n{note}{_RULES}"
    )


def deals_message(segment: Segment, cards: str, *, shown: int, part: tuple[int, int] | None = None) -> str:
    header = f"Segment: {segment.label} ({len(segment.deal_ids)} won deals, {shown} shown)"
    if part:
        header += f"\nThis is batch {part[0]} of {part[1]}; write the playbook these deals alone support."
    return f"{header}\n\n{cards}"


MERGE_SYSTEM = """\
You are a sales strategist. The deals in one segment were too many to read at once, so they were read in \
batches and each batch produced a draft playbook. Merge the drafts into one playbook. Keep patterns that \
several drafts agree on, combine duplicates, and drop anything only one draft mentions unless it is \
clearly important. exemplar_deal_id must be one of the exemplar ids proposed in the drafts, or null."""
