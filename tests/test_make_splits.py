"""Tests for scripts/make_splits.py, on synthetic records shaped like the importer's output."""

import json
import random
from collections import Counter

import pytest
from conftest import load_script

ms = load_script("make_splits")

SIZES = {"pilot": 100, "eval_": 300, "train": 1000}


def _line(i: int, year: int | None, category: str | None, sent: bool = False) -> str:
    meta = {"id": f"{i:016x}", "year": year, "gmail_category": category, "sent": sent}
    return json.dumps({"text": f"Subject: message {i}", "meta": meta})


def _archive() -> list[str]:
    """6,000 records over 2006-2020, lopsided like a real archive, with categories from 2011."""
    rng = random.Random(1)
    years = list(range(2006, 2021))
    weights = [1 + (y - 2006) for y in years]  # more mail in later years
    lines, rare = [], ["social"] * 3 + ["promotions"] * 12 + ["forums"] * 40
    for i in range(6000):
        year = rng.choices(years, weights)[0]
        category = None
        if year >= 2011:
            category = rare.pop() if rare and rng.random() < 0.02 else "personal"
            if category == "personal" and rng.random() < 0.3:
                category = "updates"
        lines.append(_line(i, year, category))
    lines += [_line(6000 + i, None, None) for i in range(20)]  # unreadable dates
    lines += [_line(6500 + i, 1999, None) for i in range(10)]  # a nearly empty period
    lines += [_line(7000 + i, 2015, None, sent=True) for i in range(500)]  # your own mail
    return lines


@pytest.fixture(scope="module")
def rows():
    return [ms.parse_row(line) for line in _archive()]


def _splits(rows, seed=0, eval_period_min=40, **sizes):
    return ms.make_splits(
        rows, **{**SIZES, **sizes}, category_min=30, seed=seed, eval_period_min=eval_period_min
    )


def _ids(rows):
    return [r.id for r in rows]


def test_splits_are_disjoint_and_cover_the_archive(rows):
    s = _splits(rows)
    every = _ids(s.pilot) + _ids(s.eval) + _ids(s.train) + _ids(s.rest)
    assert sorted(every) == sorted(_ids(rows))
    assert len(s.pilot) == 100 and len(s.eval) == 300
    assert len(s.train) == 1000


def test_same_seed_same_splits_whatever_the_input_order(rows):
    shuffled = rows[:]
    random.Random(7).shuffle(shuffled)
    a, b = _splits(rows), _splits(shuffled)
    for name in ("pilot", "eval", "train"):
        assert _ids(getattr(a, name)) == _ids(getattr(b, name))
    assert _ids(_splits(rows, seed=1).pilot) != _ids(a.pilot)


def test_sent_mail_is_left_out_unless_asked_for(rows):
    s = _splits(rows)
    assert not any(r.sent for r in s.pilot + s.eval + s.train)
    assert sum(r.sent for r in s.rest) == 500
    with_sent = _splits(rows, include_sent=True)
    assert any(r.sent for r in with_sent.pilot + with_sent.eval + with_sent.train)


def test_rare_categories_are_all_taken_and_others_get_their_minimum(rows):
    s = _splits(rows)
    sampled = Counter(r.category for r in s.pilot + s.eval + s.train)
    assert sampled["social"] == 3
    assert sampled["promotions"] == 12
    assert sampled["forums"] >= 30


def test_each_period_gets_its_minimum_in_the_eval_set(rows):
    without = Counter(ms.period(r.year) for r in _splits(rows, eval_period_min=0).eval)
    assert without[2005] < 30  # a small period, sampled in proportion
    s = _splits(rows)
    in_eval = Counter(ms.period(r.year) for r in s.eval)
    for start in (2005, 2010, 2015, 2020):
        assert in_eval[start] >= 36, start  # about 40
    assert sum(ms.period(r.year) == 1995 for r in s.pilot + s.eval + s.train) == 10


def test_beyond_the_minimums_bigger_years_get_more(rows):
    s = _splits(rows, eval_period_min=0)
    drawn = Counter(r.year for r in s.pilot + s.eval + s.train)
    assert drawn[2019] > drawn[2016] > drawn[2012]


def test_pilot_and_eval_have_the_samples_spread(rows):
    s = _splits(rows)
    sample = s.pilot + s.eval + s.train
    before_2011 = sum(r.year is not None and r.year < 2011 for r in sample) / len(sample)
    assert before_2011 > 0.1
    for part in (s.pilot, s.eval):
        share = sum(r.year is not None and r.year < 2011 for r in part) / len(part)
        assert abs(share - before_2011) < 0.03


def test_a_small_archive_is_all_sampled(rows):
    small = rows[:500]
    s = _splits(small)
    assert len(s.pilot) == 100 and len(s.eval) == 300 and len(s.train) == 100
    assert s.rest == ()


def test_periods_are_five_years():
    assert [ms.period(y) for y in (1999, 2000, 2004, 2005, None)] == [1995, 2000, 2000, 2005, None]


def test_quotas_share_by_largest_remainder():
    assert ms.quotas({2009: 1, 2010: 1, 2011: 1}, 2) == {2009: 1, 2010: 1, 2011: 0}
    assert ms.quotas({2009: 10, 2010: 30}, 4) == {2009: 1, 2010: 3}
    assert ms.quotas({2009: 2, None: 1}, 5) == {2009: 2, None: 1}


def test_a_line_without_an_id_is_refused():
    with pytest.raises(ValueError):
        ms.parse_row(json.dumps({"text": "x", "meta": {}}))


def test_main_writes_four_files_unchanged(tmp_path, capsys):
    lines = _archive()
    source = tmp_path / "mail.jsonl"
    source.write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert ms.main([str(source), "-o", str(tmp_path / "out")]) == 0
    written = []
    for name in ("pilot", "eval", "train", "rest"):
        written += (tmp_path / "out" / f"{name}.jsonl").read_text(encoding="utf-8").splitlines()
    assert sorted(written) == sorted(lines)
    assert capsys.readouterr().err.startswith("pilot: 100 (")


def test_repeated_ids_are_refused(tmp_path):
    source = tmp_path / "mail.jsonl"
    source.write_text(_line(1, 2015, None) + "\n" + _line(1, 2016, None) + "\n")
    with pytest.raises(SystemExit):
        ms.main([str(source), "-o", str(tmp_path / "out")])
