"""Tests for scripts/score.py, on invented labels."""

import json
import math

import pytest
from conftest import load_script

score = load_script("score")


def _export(labels: dict[str, str], meta: dict[str, dict] | None = None) -> list[dict]:
    meta = meta or {}
    return [
        {"meta": {"id": i, **meta.get(i, {})}, "answer": "accept", "user_anns": {"accept": [label]}}
        for i, label in labels.items()
    ]


def test_wilson_interval():
    low, high = score.Rate(94, 100).interval()
    assert low == pytest.approx(0.875, abs=0.002) and high == pytest.approx(0.972, abs=0.002)
    assert score.Rate(0, 10).interval()[0] == 0.0
    assert math.isnan(score.Rate(0, 0).value)


def test_answers_take_the_accepted_label_and_skip_the_rest():
    rows = _export({"a": "WORK", "b": "BULK"}) + [
        {"meta": {"id": "c"}, "answer": "ignore", "user_anns": {"accept": ["WORK"]}},
        {"meta": {"id": "d"}, "accept": ["ADMIN"]},
        {"meta": {"id": "e"}, "answer": "accept", "user_anns": {"accept": []}},
    ]
    assert score.answers(rows) == {"a": "WORK", "b": "BULK", "d": "ADMIN"}


def test_later_meta_fills_in_keys_without_dropping_others():
    meta = score.metas([{"meta": {"id": "a", "year": 2004}}], [{"meta": {"id": "a", "lang": "es"}}])
    assert meta == {"a": {"id": "a", "year": 2004, "lang": "es"}}


def test_period_shares_count_received_mail_only():
    archive = [
        {"meta": {"year": y, "sent": s}}
        for y, s in [(2001, False), (2006, False), (2007, False), (2008, True)]
    ]
    assert score.period_shares(archive) == pytest.approx({2000: 1 / 3, 2005: 2 / 3})


def _report():
    ref = {"a": "WORK", "b": "PERSONAL", "c": "BULK", "d": "ADMIN", "e": "AUTOMATED", "f": "WORK"}
    pred = {"a": "WORK", "b": "BULK", "c": "BULK", "d": "ADMIN", "e": "ADMIN"}
    meta = {
        "a": {"year": 2001, "lang": "en"},
        "b": {"year": 2002, "lang": "es"},
        "c": {"year": 2016, "lang": "es"},
        "d": {"year": 2017, "lang": "en"},
        "e": {"year": 2018},
    }
    return score.score(ref, pred, meta, {2000: 0.2, 2015: 0.8})


def test_scores_overall_by_period_and_language():
    report = _report()
    assert (report.scored, report.missing) == (5, 1)
    assert (report.overall.agreement.hits, report.overall.agreement.n) == (3, 5)
    # b, PERSONAL given BULK, is the one costly mistake among the 3 to keep
    assert (report.overall.costly.hits, report.overall.costly.n) == (1, 3)
    periods = {g.name: g for g in report.by_period}
    assert periods[2000].agreement.value == 0.5 and periods[2015].agreement.value == pytest.approx(
        2 / 3
    )
    assert report.weighted_agreement == pytest.approx(0.2 * 0.5 + 0.8 * 2 / 3)
    assert report.weighted_costly == pytest.approx(0.2 * 0.5 + 0.8 * 0.0)
    langs = {g.name: g.agreement.n for g in report.by_language}
    assert langs == {"en": 2, "es": 2, "unknown": 1}
    assert ("PERSONAL", "BULK", 1) in report.confusion and (
        "AUTOMATED",
        "ADMIN",
        1,
    ) in report.confusion


def test_recall_and_precision_per_label():
    by_label = {label: (r, p) for label, r, p in _report().by_label}
    recall, precision = by_label["BULK"]
    assert (recall.hits, recall.n) == (1, 1) and (precision.hits, precision.n) == (1, 2)


def test_the_bar_checks_languages_with_enough_messages_only():
    report = _report()
    results = dict(score.judge(report, score.Bar(min_language_n=2)))
    assert results["costly mistakes at most 2% overall"] is False
    assert results["costly mistakes at most 2% in en"] is True
    assert results["costly mistakes at most 2% in es"] is False
    assert "costly mistakes at most 2% in unknown" not in results
    assert len(score.judge(report, score.Bar())) == 2  # no language has 50


def test_main_prints_counts_only(tmp_path, capsys):
    def write(name, rows):
        path = tmp_path / name
        path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        return path

    ref = write(
        "person.jsonl",
        _export({"a": "WORK", "b": "BULK"}, {"a": {"year": 2001}, "b": {"year": 2002}}),
    )
    llm = write("llm.jsonl", _export({"a": "WORK", "b": "WORK"}))
    split = write("eval.jsonl", [{"text": "Secret words", "meta": {"id": "a", "lang": "en"}}])
    archive = write(
        "archive.jsonl", [{"text": "Secret words", "meta": {"year": 2001, "sent": False}}]
    )
    assert score.main([str(ref), str(llm), "--archive", str(archive), "--meta", str(split)]) == 0
    out = capsys.readouterr().out
    assert "## llm" in out and "1/2 50.0%" in out and "BULK given WORK: 1" in out
    assert "Secret" not in out
