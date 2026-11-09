from datetime import date, timedelta

from claim_scout.sampling import pick_sample
from claim_scout.segments import STATUS_QUO, build_segments
from conftest import won


def test_three_cuts_and_minimum_size():
    wins = [won(i) for i in range(1, 4)] + [won(4, competitor="Corvane")]
    labels = {(s.kind, s.label) for s in build_segments(wins, min_deals=3)}
    assert labels == {
        ("competitor_industry", "vs Stackwise / Logistics"),
        ("competitor", "vs Stackwise"),
        ("industry", "Logistics"),  # all four deals, Corvane included
    }


def test_no_competitor_is_its_own_segment():
    wins = [won(i, competitor=None) for i in range(1, 4)]
    segments = build_segments(wins, min_deals=3)
    assert {s.competitor for s in segments if s.kind == "competitor"} == {STATUS_QUO}


def test_missing_industry_still_counts_for_competitor():
    wins = [won(i, industry=None) for i in range(1, 4)]
    assert [s.kind for s in build_segments(wins, min_deals=3)] == ["competitor"]


def test_small_segment_is_sent_whole_newest_first():
    deals = [won(i, closed=date(2026, 1, i)) for i in range(1, 6)]
    assert [d.deal_id for d in pick_sample(deals, 10)] == [5, 4, 3, 2, 1]


def test_sample_takes_recent_half_and_spreads_the_rest_across_size():
    deals = [won(i, closed=date(2025, 1, 1) + timedelta(days=i), amount=1000 * i) for i in range(1, 41)]
    sample = pick_sample(deals, 10)
    ids = [d.deal_id for d in sample]

    assert ids[:5] == [40, 39, 38, 37, 36]               # most recent wins
    rest_amounts = [d.amount for d in sample[5:]]
    assert rest_amounts == sorted(rest_amounts)           # one per size band, small to large
    assert min(rest_amounts) < 8_000 and max(rest_amounts) > 28_000
    assert len(set(ids)) == 10


def test_sample_is_deterministic():
    deals = [won(i, amount=500 * i) for i in range(1, 30)]
    assert pick_sample(deals, 8) == pick_sample(list(reversed(deals)), 8)
