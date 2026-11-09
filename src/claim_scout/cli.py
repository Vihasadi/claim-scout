"""Command line.

    claim-scout run                          # rebuild every playbook from the current replays
    claim-scout show                         # list the playbooks
    claim-scout show --competitor Stackwise  # print the matching playbooks in full
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from claim_scout.config import ConfigError, Settings, load_settings
from claim_scout.llm import OpenAIChat
from claim_scout.pipeline import run
from claim_scout.store import PlaybookStore


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="claim-scout", description="Find what won deals have in common.")
    parser.add_argument("--env-file", type=Path, help="path to a .env file (default: ./.env)")
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("run", help="rebuild every playbook from ClaimReplay's replays")
    show = sub.add_parser("show", help="print playbooks")
    show.add_argument("--competitor")
    show.add_argument("--industry")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    for noisy in ("httpx", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    try:
        settings = load_settings(args.env_file, need_llm=args.command == "run")
    except ConfigError as exc:
        print(f"Configuration error: {exc}\nSee .env.example.", file=sys.stderr)
        return 2

    if args.command == "show":
        return _show(settings, args.competitor, args.industry)
    return asyncio.run(_run(settings))


async def _run(settings: Settings) -> int:
    model = OpenAIChat(settings.llm)
    try:
        stats = await run(settings.replay_db, PlaybookStore(settings.playbook_db), model,
                          prompt_budget=settings.llm.prompt_budget, min_deals=settings.min_deals,
                          sample_size=settings.sample_size)
    finally:
        await model.aclose()
    print(f"wins: {stats.wins} | segments: {stats.segments} | built: {stats.built} | failed: {stats.failed} | "
          f"{'written' if stats.written else 'NOT written (kept previous)'} | {stats.seconds}s")
    return 0 if stats.written else 1


def _show(settings: Settings, competitor: str | None, industry: str | None) -> int:
    rows = PlaybookStore(settings.playbook_db).all()
    matches = [r for r in rows
               if (competitor is None or (r.competitor or "").lower() == competitor.lower())
               and (industry is None or (r.industry or "").lower() == industry.lower())]
    if not matches:
        print("No matching playbooks. Run `claim-scout run` first?", file=sys.stderr)
        return 1
    full = competitor is not None or industry is not None
    for r in matches:
        label = " / ".join(p for p in (f"vs {r.competitor}" if r.competitor else None, r.industry) if p)
        print(f"[{r.kind}] {label} ({r.deal_count} deals): {r.playbook.headline}")
        if full:
            print(r.playbook.model_dump_json(indent=2), end="\n\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
