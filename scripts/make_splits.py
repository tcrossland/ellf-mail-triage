"""Draw the pilot, eval set and training pool from the importer's JSONL.

Usage:
    python scripts/make_splits.py INPUT -o OUTDIR [--seed N] [--pilot N]
        [--eval N] [--train N] [--category-min N] [--eval-period-min N]
        [--include-sent]

INPUT is what scripts/mail_to_jsonl.py writes: one {"text", "meta"} per line,
with meta.id, meta.year, meta.gmail_category and meta.sent.

Your own mail (meta.sent: Gmail's Sent and Drafts) is left out of the sample
unless --include-sent is given: the model sorts the mail you receive. The
sample, pilot + eval + train messages, is drawn from the rest in three passes:

    1. From each Gmail category present, the first --category-min messages
       (all of them, if there are fewer), so nearly empty categories such as
       Promotions or Social still turn up.
    2. From each five-year period (2005-2009, 2010-2014, ...), enough messages
       for the eval set to hold about --eval-period-min of them (all of the
       period, if it has fewer), so results can be given by age of mail.
    3. The rest of the sample is shared over the years in proportion to the
       messages not yet taken.

Old periods are oversampled, so an overall score on the eval set has to weight
each period by its share of the archive.

The sample is then split so that the pilot, eval set and training pool each
have the same spread over years and categories: the pilot and eval set get
exactly their sizes, the pool the rest. Everything not sampled goes to
rest.jsonl. Lines are written unchanged.

Every choice follows a ranking by a hash of the seed and the message's id, so
the same archive and seed give the same splits whatever the input order, and
messages added later barely change them.

Standard library only: this runs on the host, outside Ellf.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from collections.abc import Hashable, Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

SPLITS = ("pilot", "eval", "train", "rest")


@dataclass(frozen=True)
class Row:
    line: str
    id: str
    year: int | None
    category: str | None
    sent: bool = False


@dataclass(frozen=True)
class Splits:
    pilot: tuple[Row, ...]
    eval: tuple[Row, ...]
    train: tuple[Row, ...]
    rest: tuple[Row, ...]


def parse_row(line: str) -> Row:
    meta = json.loads(line).get("meta") or {}
    if not meta.get("id"):
        raise ValueError("a line has no meta.id; make the input with scripts/mail_to_jsonl.py")
    return Row(
        line, str(meta["id"]), meta.get("year"), meta.get("gmail_category"), bool(meta.get("sent"))
    )


def _hash(seed: int, *parts: object) -> int:
    key = "\x00".join(str(p) for p in (seed, *parts))
    return int.from_bytes(hashlib.sha256(key.encode()).digest()[:8])


def ranked(rows: Iterable[Row], seed: int) -> list[Row]:
    """The rows in a fixed pseudo-random order that depends only on the seed and each id."""
    return sorted(rows, key=lambda r: (_hash(seed, r.id), r.id))


def _sort_key(key: Hashable) -> tuple[bool, str]:
    return key is None, str(key)


def quotas(counts: Mapping[Hashable, int], n: int) -> dict[Hashable, int]:
    """n shared out in proportion to counts, by largest remainder; all of it if n covers them."""
    total = sum(counts.values())
    if n >= total:
        return dict(counts)
    exact = {k: n * c / total for k, c in counts.items()}
    shares = {k: int(v) for k, v in exact.items()}
    by_remainder = sorted(exact, key=lambda k: (shares[k] - exact[k], _sort_key(k)))
    for k in by_remainder[: n - sum(shares.values())]:
        shares[k] += 1
    return shares


def period(year: int | None) -> int | None:
    """The first year of the five-year period a year falls in."""
    return None if year is None else year - year % 5


def choose(rows: list[Row], n: int, category_min: int, period_min: int, seed: int) -> list[Row]:
    """The sample: minimums per Gmail category and per period, then the years' shares."""
    order = ranked(rows, seed)
    if n >= len(order):
        return order
    picked: dict[str, Row] = {}
    categories = sorted({r.category for r in order if r.category}, key=_sort_key)
    for category in categories:
        for row in [r for r in order if r.category == category][:category_min]:
            picked[row.id] = row
    periods = sorted({period(r.year) for r in order if r.year is not None})
    for start in periods:
        have = sum(period(r.year) == start for r in picked.values())
        fill = [r for r in order if period(r.year) == start and r.id not in picked]
        for row in fill[: max(0, period_min - have)]:
            picked[row.id] = row
    left = [r for r in order if r.id not in picked]
    for year, share in quotas(Counter(r.year for r in left), max(0, n - len(picked))).items():
        for row in [r for r in left if r.year == year][:share]:
            picked[row.id] = row
    return ranked(picked.values(), seed)


def spread(sample: list[Row], seed: int) -> list[Row]:
    """The sample ordered so that any run of it has about the same mix of years and categories.

    Each (year, category) stratum is laid evenly along [0, 1) from a random start, and
    the rows are sorted by that position.
    """
    strata: dict[tuple, list[Row]] = defaultdict(list)
    for row in ranked(sample, seed):
        strata[(row.year, row.category)].append(row)
    position: dict[str, float] = {}
    for key, members in strata.items():
        start = _hash(seed, "start", *key) / 2**64
        for i, row in enumerate(members):
            position[row.id] = (i + start) / len(members)
    return sorted(sample, key=lambda r: (position[r.id], _hash(seed, r.id)))


def make_splits(
    rows: list[Row],
    pilot: int,
    eval_: int,
    train: int,
    category_min: int,
    seed: int,
    eval_period_min: int = 0,
    include_sent: bool = False,
) -> Splits:
    pool = rows if include_sent else [r for r in rows if not r.sent]
    n = pilot + eval_ + train
    period_min = -(-eval_period_min * n // eval_) if eval_ else 0  # rounded up
    sample = choose(pool, n, category_min, period_min, seed)
    order = spread(sample, seed)
    chosen = {r.id for r in sample}
    return Splits(
        pilot=tuple(order[:pilot]),
        eval=tuple(order[pilot : pilot + eval_]),
        train=tuple(order[pilot + eval_ :]),
        rest=tuple(r for r in rows if r.id not in chosen),
    )


def summary(splits: Splits) -> str:
    """Counts per split, by Gmail category: no message content."""
    lines = []
    for name in SPLITS:
        rows = getattr(splits, name)
        years = sorted(r.year for r in rows if r.year is not None)
        span = f"{years[0]}-{years[-1]}" if years else "no dates"
        cats = Counter(r.category or "none" for r in rows)
        detail = ", ".join(f"{c} {n}" for c, n in sorted(cats.items()))
        ages = Counter(period(r.year) for r in rows)
        by_age = ", ".join(
            f"{p}-{p + 4} {n}" if p is not None else f"no date {n}"
            for p, n in sorted(ages.items(), key=lambda kv: _sort_key(kv[0]))
        )
        sent = sum(r.sent for r in rows)
        lines.append(f"{name}: {len(rows)} ({span}; {detail}; sent {sent})\n  {by_age}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("input", type=Path, help="JSONL from scripts/mail_to_jsonl.py")
    parser.add_argument("-o", "--output", type=Path, required=True, help="folder to write to")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--pilot", type=int, default=100)
    parser.add_argument("--eval", type=int, default=300)
    parser.add_argument("--train", type=int, default=1000)
    parser.add_argument("--category-min", type=int, default=30)
    parser.add_argument("--eval-period-min", type=int, default=30)
    parser.add_argument("--include-sent", action="store_true", help="sample your own mail too")
    args = parser.parse_args(argv)

    with args.input.open(encoding="utf-8") as f:
        rows = [parse_row(line.rstrip("\n")) for line in f if line.strip()]
    if len({r.id for r in rows}) != len(rows):
        parser.error("meta.id values repeat; make the input with scripts/mail_to_jsonl.py")
    splits = make_splits(
        rows,
        args.pilot,
        args.eval,
        args.train,
        args.category_min,
        args.seed,
        args.eval_period_min,
        args.include_sent,
    )

    args.output.mkdir(parents=True, exist_ok=True)
    for name in SPLITS:
        lines = "".join(r.line + "\n" for r in getattr(splits, name))
        (args.output / f"{name}.jsonl").write_text(lines, encoding="utf-8")
    print(summary(splits), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
