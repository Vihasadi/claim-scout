import asyncio

from claim_scout import prompts
from claim_scout.builder import PlaybookBuilder
from claim_scout.pipeline import run
from claim_scout.schema import Playbook
from claim_scout.segments import Segment
from claim_scout.store import PlaybookStore
from claim_scout.structured import prompt_tokens
from conftest import ScriptedModel, playbook_json, won


def _segment(wins, kind="competitor", competitor="Stackwise", industry=None):
    return Segment(kind, competitor, industry, tuple(w.deal_id for w in wins))


def test_builds_a_playbook_in_one_call():
    wins = {w.deal_id: w for w in (won(i) for i in range(1, 5))}
    model = ScriptedModel(lambda s, u: playbook_json(exemplar=2))
    built = asyncio.run(PlaybookBuilder(model, 20_000, 24).build(_segment(wins.values()), wins))

    assert built.playbook.exemplar_deal_id == 2 and built.batches == 1 and built.sample_size == 4
    assert "DEAL 3" in model.calls[0][1] and "against Stackwise" in model.calls[0][0]


def test_exemplar_outside_the_sample_is_dropped():
    wins = {w.deal_id: w for w in (won(i) for i in range(1, 5))}
    model = ScriptedModel(lambda s, u: playbook_json(exemplar=999))
    built = asyncio.run(PlaybookBuilder(model, 20_000, 24).build(_segment(wins.values()), wins))
    assert built.playbook.exemplar_deal_id is None and built.playbook.exemplar_reason is None


def test_status_quo_segment_gets_its_own_framing():
    wins = {w.deal_id: w for w in (won(i, competitor=None) for i in range(1, 4))}
    model = ScriptedModel()
    asyncio.run(PlaybookBuilder(model, 20_000, 24).build(_segment(wins.values(), competitor="status quo"), wins))
    assert "no competing vendor" in model.calls[0][0]


def test_big_segment_is_read_in_batches_then_merged():
    wins = {w.deal_id: w for w in (won(i, text="x" * 1500) for i in range(1, 9))}
    segment = _segment(wins.values())
    budget = prompt_tokens(prompts.system_prompt(segment), Playbook) + 80 + 1_000
    model = ScriptedModel()

    built = asyncio.run(PlaybookBuilder(model, budget, 24).build(segment, wins))
    assert built.batches > 1
    assert len(model.calls) == built.batches + 1
    assert model.calls[-1][0].startswith(prompts.MERGE_SYSTEM)


def test_invalid_reply_fails_only_that_segment():
    wins = {w.deal_id: w for w in (won(i) for i in range(1, 4))}
    built = asyncio.run(PlaybookBuilder(ScriptedModel(lambda s, u: "oops"), 20_000, 24)
                        .build(_segment(wins.values()), wins))
    assert built is None


def _run(replay_db, store, model):
    return asyncio.run(run(replay_db, store, model, prompt_budget=20_000, min_deals=3, sample_size=24))


def test_full_run_writes_every_segment(replay_db, tmp_path):
    store = PlaybookStore(tmp_path / "playbooks.sqlite3")
    stats = _run(replay_db, store, ScriptedModel())
    # Stackwise: competitor, competitor+industry, industry. Status quo/Retail: the same three.
    assert (stats.wins, stats.segments, stats.built, stats.written) == (7, 6, 6, True)
    assert {(p.kind, p.competitor, p.industry) for p in store.all()} >= {
        ("competitor", "status quo", None), ("competitor_industry", "Stackwise", "Logistics")}


def test_rerun_replaces_instead_of_appending(replay_db, tmp_path):
    store = PlaybookStore(tmp_path / "playbooks.sqlite3")
    _run(replay_db, store, ScriptedModel())
    _run(replay_db, store, ScriptedModel(lambda s, u: playbook_json(headline="New headline.")))
    rows = store.all()
    assert len(rows) == 6 and {r.playbook.headline for r in rows} == {"New headline."}


def test_total_failure_keeps_last_runs_playbooks(replay_db, tmp_path):
    store = PlaybookStore(tmp_path / "playbooks.sqlite3")
    _run(replay_db, store, ScriptedModel())
    stats = _run(replay_db, store, ScriptedModel(lambda s, u: "502 Bad Gateway"))
    assert stats.written is False and len(store.all()) == 6


def test_missing_replay_store_writes_nothing_harmful(tmp_path):
    stats = _run(tmp_path / "missing.sqlite3", PlaybookStore(tmp_path / "p.sqlite3"), ScriptedModel())
    assert stats.wins == 0 and stats.written
