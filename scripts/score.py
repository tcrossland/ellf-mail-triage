"""Score annotators' labels against a reference, by period and language.

Usage:
    python scripts/score.py REFERENCE PREDICTED [PREDICTED ...]
        --archive ARCHIVE [--meta SPLIT] [--keep KINDS] [--drop KINDS]
        [--max-costly F] [--min-agreement F] [--max-language-gap F]
        [--min-language-n N]

REFERENCE and each PREDICTED are dataset exports (`ellf datasets export`):
one example per line, with meta.id and the accepted label in
user_anns.accept (or accept). Each PREDICTED is scored on the messages it
shares with REFERENCE, the number left out is reported.

ARCHIVE is what scripts/mail_to_jsonl.py writes. Each five-year period's
share of the received mail in it (meta.sent false) weights that period's
score, since the splits oversample old periods. SPLIT, a split from
scripts/make_splits.py, supplies meta.year and meta.lang by meta.id for
exports made before the importer guessed the language.

A costly mistake is a message the reference gives a kind to keep (--keep)
that the annotator gives a kind to drop (--drop). The bar is the design's:
at most --max-costly of the mail to keep given a dropped kind, overall and
in each language with at least --min-language-n messages; period-weighted
agreement of at least --min-agreement; and no such language more than
--max-language-gap behind another. Each rate comes with its 95% Wilson
interval.

Prints counts and rates only, never a message. Standard library only: this
runs on the host, outside Ellf.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

KEEP = ("WORK", "PERSONAL", "ADMIN")
DROP = ("AUTOMATED", "BULK")


@dataclass(frozen=True)
class Rate:
    hits: int
    n: int

    @property
    def value(self) -> float:
        return self.hits / self.n if self.n else math.nan

    def interval(self, z: float = 1.96) -> tuple[float, float]:
        """The Wilson score interval."""
        if not self.n:
            return (math.nan, math.nan)
        p, n = self.value, self.n
        centre = (p + z * z / (2 * n)) / (1 + z * z / n)
        half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
        return (max(0.0, centre - half), min(1.0, centre + half))

    def __str__(self) -> str:
        if not self.n:
            return "n/a"
        low, high = self.interval()
        return f"{self.hits}/{self.n} {self.value:.1%} ({low:.0%} to {high:.0%})"


@dataclass(frozen=True)
class Group:
    name: str
    agreement: Rate
    costly: Rate


@dataclass(frozen=True)
class Report:
    scored: int
    missing: int
    overall: Group
    weighted_agreement: float
    weighted_costly: float
    by_label: tuple[tuple[str, Rate, Rate], ...]  # label, recall, precision
    by_period: tuple[Group, ...]
    by_language: tuple[Group, ...]
    confusion: tuple[tuple[str, str, int], ...]  # reference, predicted, count


def period(year: int | None) -> int | None:
    """The first year of the five-year period a year falls in, as make_splits has it."""
    return None if year is None else year - year % 5


def answer_label(row: Mapping) -> str | None:
    """The accepted label of an exported example, or None."""
    accepted = (row.get("user_anns") or {}).get("accept") or row.get("accept") or []
    return accepted[0] if accepted else None


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def answers(rows: Iterable[Mapping]) -> dict[str, str]:
    """Each message id's accepted label; examples without one are skipped."""
    out = {}
    for row in rows:
        label = answer_label(row)
        if label is not None and row.get("answer", "accept") == "accept":
            out[row["meta"]["id"]] = label
    return out


def metas(*sources: Iterable[Mapping]) -> dict[str, dict]:
    """Each id's meta, later sources overriding earlier ones key by key."""
    out: dict[str, dict] = {}
    for rows in sources:
        for row in rows:
            meta = row.get("meta") or {}
            out.setdefault(meta["id"], {}).update(meta)
    return out


def period_shares(archive: Iterable[Mapping]) -> dict[int | None, float]:
    """Each period's share of the received mail."""
    counts = Counter(
        period((r.get("meta") or {}).get("year")) for r in archive if not r["meta"].get("sent")
    )
    total = sum(counts.values())
    return {p: c / total for p, c in counts.items()}


def group(name: str, ids: list[str], ref: Mapping, pred: Mapping, keep: set, drop: set) -> Group:
    to_keep = [i for i in ids if ref[i] in keep]
    return Group(
        name,
        Rate(sum(ref[i] == pred[i] for i in ids), len(ids)),
        Rate(sum(pred[i] in drop for i in to_keep), len(to_keep)),
    )


def weighted(groups: Iterable[Group], shares: Mapping, attr: str) -> float:
    """The rates of the period groups, weighted by the periods' shares of the archive
    (renormalised over the periods scored)."""
    pairs = [
        (shares.get(g.name, 0.0), getattr(g, attr).value) for g in groups if getattr(g, attr).n
    ]
    total = sum(w for w, _ in pairs)
    return sum(w * v for w, v in pairs) / total if total else math.nan


def score(
    ref: Mapping[str, str],
    pred: Mapping[str, str],
    meta: Mapping[str, Mapping],
    shares: Mapping,
    keep: Iterable[str] = KEEP,
    drop: Iterable[str] = DROP,
) -> Report:
    keep, drop = set(keep), set(drop)
    ids = sorted(set(ref) & set(pred))
    labels = sorted(set(ref.values()) | set(pred.values()))
    by_period: dict = defaultdict(list)
    by_lang: dict = defaultdict(list)
    for i in ids:
        m = meta.get(i, {})
        by_period[period(m.get("year"))].append(i)
        by_lang[m.get("lang") or "unknown"].append(i)
    periods = tuple(
        group(p, by_period[p], ref, pred, keep, drop)
        for p in sorted(by_period, key=lambda p: (p is None, p or 0))
    )
    return Report(
        scored=len(ids),
        missing=len(set(ref) - set(pred)),
        overall=group("all", ids, ref, pred, keep, drop),
        weighted_agreement=weighted(periods, shares, "agreement"),
        weighted_costly=weighted(periods, shares, "costly"),
        by_label=tuple(
            (
                label,
                Rate(
                    sum(ref[i] == pred[i] == label for i in ids), sum(ref[i] == label for i in ids)
                ),
                Rate(
                    sum(ref[i] == pred[i] == label for i in ids), sum(pred[i] == label for i in ids)
                ),
            )
            for label in labels
        ),
        by_period=periods,
        by_language=tuple(
            group(lang, by_lang[lang], ref, pred, keep, drop)
            for lang in sorted(by_lang, key=lambda k: (-len(by_lang[k]), k))
        ),
        confusion=tuple(
            sorted((r, p, n) for (r, p), n in Counter((ref[i], pred[i]) for i in ids).items())
        ),
    )


@dataclass(frozen=True)
class Bar:
    max_costly: float = 0.02
    min_agreement: float = 0.85
    max_language_gap: float = 0.10
    min_language_n: int = 50


def judge(report: Report, bar: Bar) -> list[tuple[str, bool]]:
    """Each test of the bar, with whether the report passes it."""
    langs = [
        g for g in report.by_language if g.agreement.n >= bar.min_language_n and g.name != "unknown"
    ]
    tests = [
        (
            f"costly mistakes at most {bar.max_costly:.0%} overall",
            report.overall.costly.value <= bar.max_costly,
        ),
        (
            f"period-weighted agreement at least {bar.min_agreement:.0%}",
            report.weighted_agreement >= bar.min_agreement,
        ),
    ]
    tests += [
        (
            f"costly mistakes at most {bar.max_costly:.0%} in {g.name}",
            g.costly.value <= bar.max_costly,
        )
        for g in langs
    ]
    if len(langs) > 1:
        values = [g.agreement.value for g in langs]
        tests.append(
            (
                f"no language more than {bar.max_language_gap:.0%} behind",
                max(values) - min(values) <= bar.max_language_gap,
            )
        )
    return tests


def render(name: str, report: Report, bar: Bar) -> str:
    out = [f"## {name}", ""]
    out.append(
        f"Scored on {report.scored} messages; {report.missing} of the reference's have no answer."
    )
    out.append("")
    agreement = report.overall.agreement
    out.append(f"- Agreement: {agreement}; weighted by period {report.weighted_agreement:.1%}")
    out.append(
        f"- Costly mistakes (keep given drop): {report.overall.costly}; "
        f"weighted by period {report.weighted_costly:.1%}"
    )
    out += ["", "| Label | Recall | Precision |", "|---|---|---|"]
    out += [f"| {label} | {recall} | {precision} |" for label, recall, precision in report.by_label]
    for title, groups in (("Period", report.by_period), ("Language", report.by_language)):
        out += ["", f"| {title} | Agreement | Costly mistakes |", "|---|---|---|"]
        out += [
            f"| {g.name if g.name is not None else 'no date'} | {g.agreement} | {g.costly} |"
            for g in groups
        ]
    out += ["", "Confusion (reference, then answer, where they differ):", ""]
    out += [f"- {r} given {p}: {n}" for r, p, n in report.confusion if r != p]
    out += ["", "Bar:", ""]
    out += [f"- {'pass' if ok else 'FAIL'}: {test}" for test, ok in judge(report, bar)]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("reference", type=Path, help="export of the reference labels")
    parser.add_argument(
        "predicted", type=Path, nargs="+", help="exports of the annotators to score"
    )
    parser.add_argument("--archive", type=Path, required=True, help="JSONL from mail_to_jsonl.py")
    parser.add_argument("--meta", type=Path, help="a split from make_splits.py, for year and lang")
    parser.add_argument("--keep", default=",".join(KEEP), help="kinds to keep, comma-separated")
    parser.add_argument("--drop", default=",".join(DROP), help="kinds that are dropped")
    parser.add_argument("--max-costly", type=float, default=Bar.max_costly)
    parser.add_argument("--min-agreement", type=float, default=Bar.min_agreement)
    parser.add_argument("--max-language-gap", type=float, default=Bar.max_language_gap)
    parser.add_argument("--min-language-n", type=int, default=Bar.min_language_n)
    args = parser.parse_args(argv)

    bar = Bar(args.max_costly, args.min_agreement, args.max_language_gap, args.min_language_n)
    ref_rows = read_jsonl(args.reference)
    meta = metas(ref_rows, read_jsonl(args.meta) if args.meta else [])
    shares = period_shares(read_jsonl(args.archive))
    ref = answers(ref_rows)
    for path in args.predicted:
        report = score(
            ref, answers(read_jsonl(path)), meta, shares, args.keep.split(","), args.drop.split(",")
        )
        print(render(path.stem, report, bar))
    return 0


if __name__ == "__main__":
    sys.exit(main())
