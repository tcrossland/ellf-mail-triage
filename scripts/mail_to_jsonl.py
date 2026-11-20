"""Turn a mail archive into JSONL for `ellf publish data`.

Usage:
    python scripts/mail_to_jsonl.py SOURCE [-o OUT] [--body-chars N] [--no-header-lines]

SOURCE is one of:
    an mbox file           e.g. a Google Takeout export; Gmail labels come
                           from each message's X-Gmail-Labels header
    a folder of .eml files searched recursively; labels from X-Gmail-Labels
                           where a file has one
    a Got Your Back backup a folder with msg-db.sqlite; labels from its
                           labels table

Each line written is {"text": ..., "meta": {...}}. The text is what the model
sees: the sender's name and domain, the subject and whether the message has a
List-Unsubscribe header, then a blank line and the start of the visible body.
With --no-header-lines it is the body alone. The meta holds:

    id                 a hash of the Message-ID (or of the message's content
                       when it has none), so no address is kept
    date, year         from the Date header, in UTC; null when unreadable
    from_domain        the sender's domain, lower case
    list_unsubscribe   whether the List-Unsubscribe header is present
    gmail_category     personal, social, promotions, updates or forums, from
                       Gmail's category label; null when there is none
    sent               whether Gmail labelled it Sent or Drafts: your own mail
    lang               a rough guess at the body's language from its common
                       words: en, es, fr, de, pt or it; null when unclear

The same message gives the same record from every kind of SOURCE. Records are
sorted by date, then id, and a message seen twice is written once. Chats
(Gmail's Chat label) are skipped. Counts go to stderr.

Standard library only: this runs on the host, outside Ellf.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import mailbox
import re
import sqlite3
import sys
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from datetime import UTC, datetime
from email import policy
from email.message import EmailMessage
from email.parser import BytesParser
from email.utils import getaddresses, parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path

GYB_DB = "msg-db.sqlite"
CATEGORIES = ("personal", "social", "promotions", "updates", "forums")
DEFAULT_BODY_CHARS = 1000

# Common short words that mostly belong to one language, for a rough guess.
COMMON_WORDS: dict[str, frozenset[str]] = {
    lang: frozenset(words.split())
    for lang, words in {
        "en": "the and of to is you your that this with for are have will please "
        "thanks from was not be our can would",
        "es": "el los las del y por para con una es está gracias hola saludos pero "
        "más muy usted también este esta nos le lo",
        "fr": "le les des et est pour avec une vous nous pas sur dans merci bonjour "
        "mais très aussi cette",
        "de": "der die und ist nicht mit ein eine sie wir für auf den dem bitte danke "
        "auch sehr oder",
        "pt": "os não você obrigado obrigada também com muito isso são olá foi ao uma mas nós",
        "it": "il gli che non per sono è della delle anche grazie ciao molto ma questo questa",
    }.items()
}
_WORD = re.compile(r"[^\W\d_]+")

_PARSER = BytesParser(policy=policy.default)
_SPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class Record:
    text: str
    id: str
    date: str | None
    year: int | None
    from_domain: str | None
    list_unsubscribe: bool
    gmail_category: str | None
    sent: bool = False
    lang: str | None = None

    def to_json(self) -> str:
        meta = {
            "id": self.id,
            "date": self.date,
            "year": self.year,
            "from_domain": self.from_domain,
            "list_unsubscribe": self.list_unsubscribe,
            "gmail_category": self.gmail_category,
            "sent": self.sent,
            "lang": self.lang,
        }
        return json.dumps({"text": self.text, "meta": meta}, ensure_ascii=False)


@dataclass(frozen=True)
class Counts:
    read: int = 0
    written: int = 0
    chats: int = 0
    duplicates: int = 0
    unreadable: int = 0


# Reading the sources: each yields (raw message bytes, labels or None).
# None means "take the labels from the message's X-Gmail-Labels header".


def read_mbox(path: Path) -> Iterator[tuple[bytes, frozenset[str] | None]]:
    box = mailbox.mbox(path, create=False)
    try:
        for key in box.iterkeys():
            yield box.get_bytes(key), None
    finally:
        box.close()


def read_eml_folder(folder: Path) -> Iterator[tuple[bytes, frozenset[str] | None]]:
    for path in sorted(folder.rglob("*.eml")):
        yield path.read_bytes(), None


def read_gyb(folder: Path) -> Iterator[tuple[bytes, frozenset[str] | None]]:
    root = folder.resolve()
    con = sqlite3.connect(f"file:{folder / GYB_DB}?mode=ro", uri=True)
    try:
        labels: dict[int, set[str]] = {}
        for num, label in con.execute("SELECT message_num, label FROM labels"):
            labels.setdefault(num, set()).add(label)
        rows = con.execute(
            "SELECT message_num, message_filename FROM messages ORDER BY message_num"
        ).fetchall()
    finally:
        con.close()
    for num, name in rows:
        path = (root / name).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            continue
        yield path.read_bytes(), frozenset(labels.get(num, ()))


def read_source(source: Path) -> Iterator[tuple[bytes, frozenset[str] | None]]:
    if source.is_file():
        return read_mbox(source)
    if (source / GYB_DB).is_file():
        return read_gyb(source)
    if source.is_dir():
        return read_eml_folder(source)
    raise FileNotFoundError(source)


# Turning one message into a record: pure functions of their inputs.


def header_labels(value: str | None) -> frozenset[str]:
    """Labels in an X-Gmail-Labels header: comma-separated, quoted if they hold a comma."""
    if not value:
        return frozenset()
    row = next(csv.reader([value], skipinitialspace=True), [])
    return frozenset(label.strip() for label in row if label.strip())


def _label_key(label: str) -> str:
    return label.strip().upper().replace(" ", "_")


def gmail_category(labels: Iterable[str]) -> str | None:
    """Gmail's category: CATEGORY_PROMOTIONS (Gmail API, gyb), Category Promotions (Takeout)."""
    keys = {_label_key(label) for label in labels}
    return next((c for c in CATEGORIES if f"CATEGORY_{c.upper()}" in keys), None)


def is_chat(labels: Iterable[str]) -> bool:
    return any(_label_key(label) in ("CHAT", "CHATS") for label in labels)


def is_sent(labels: Iterable[str]) -> bool:
    """Your own mail: Gmail's SENT or DRAFT label (gyb), Sent or Drafts (Takeout)."""
    return any(_label_key(label) in ("SENT", "DRAFT", "DRAFTS") for label in labels)


def guess_language(text: str, min_words: int = 3) -> str | None:
    """The language whose common words the text uses most, if clearly ahead.

    None when fewer than `min_words` common words are found, or when the
    runner-up has more than two thirds as many.
    """
    words = _WORD.findall(text.lower())
    hits = sorted(
        ((sum(w in common for w in words), lang) for lang, common in COMMON_WORDS.items()),
        reverse=True,
    )
    (best, lang), (second, _) = hits[0], hits[1]
    if best < min_words or second * 3 > best * 2:
        return None
    return lang


class _TextOfHtml(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in ("script", "style", "head", "title"):
            self._skip += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "head", "title") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip:
            self.parts.append(data)


_HTML_CHUNK = 8192


def html_text(html: str, enough: int | None = None) -> str:
    """The visible text of an HTML document, words separated by spaces.

    With `enough`, parsing stops once the text, with its spaces collapsed,
    is longer than that; a prefix of that length is the same as when the
    whole document is parsed, and big newsletters are parsed only in part.
    """
    parser = _TextOfHtml()
    start = 0
    while start < len(html):
        # Cut just before a tag, so no run of text is split between two parts
        end = html.find("<", start + _HTML_CHUNK) if enough is not None else -1
        end = len(html) if end == -1 else end
        parser.feed(html[start:end])
        start = end
        if enough is not None and len(_SPACE.sub(" ", " ".join(parser.parts)).strip()) > enough + 1:
            return " ".join(parser.parts)
    parser.close()
    return " ".join(parser.parts)


def _part_text(part: EmailMessage) -> str:
    try:
        return part.get_content()
    except LookupError, UnicodeError, ValueError:
        payload = part.get_payload(decode=True) or b""
        return payload.decode("utf-8", errors="replace")


def visible_body(msg: EmailMessage, enough: int | None = None) -> str:
    """The plain-text body, or the text of the HTML body when there is none, on one line.

    With `enough`, an HTML body is parsed only until it has more than that
    many characters of text (see `html_text`).
    """
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    text = _part_text(part)
    if part.get_content_subtype() == "html":
        text = html_text(text, enough)
    return _SPACE.sub(" ", text).strip()


def _header(msg: EmailMessage, name: str) -> str:
    try:
        value = msg.get(name)
    except IndexError, ValueError:  # a malformed header the policy can't parse: take it raw
        value = next((v for k, v in msg.raw_items() if k.lower() == name.lower()), None)
    return _SPACE.sub(" ", str(value)).strip() if value is not None else ""


def sender(msg: EmailMessage) -> tuple[str, str | None]:
    """The From header's display name and domain; never the local part."""
    pairs = getaddresses([_header(msg, "From")])
    name, address = pairs[0] if pairs else ("", "")
    domain = address.rpartition("@")[2].strip().lower() if "@" in address else None
    return name.strip(), domain or None


def utc_date(msg: EmailMessage) -> datetime | None:
    value = _header(msg, "Date")
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except TypeError, ValueError, IndexError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def message_id(msg: EmailMessage, fallback: str) -> str:
    raw = _header(msg, "Message-ID").strip("<> ")
    return hashlib.sha256((raw or fallback).encode()).hexdigest()[:16]


def model_text(
    name: str, domain: str | None, subject: str, unsubscribe: bool, body: str, header_lines: bool
) -> str:
    if not header_lines:
        return body
    who = f"{name} ({domain})" if name and domain else (name or domain or "")
    lines = [
        f"From: {who}",
        f"Subject: {subject}",
        f"List-Unsubscribe: {'yes' if unsubscribe else 'no'}",
    ]
    return "\n".join(lines) + "\n\n" + body


def to_record(
    raw: bytes,
    labels: frozenset[str] | None,
    body_chars: int = DEFAULT_BODY_CHARS,
    header_lines: bool = True,
) -> Record | None:
    """The record for one message, or None for a chat."""
    msg = _PARSER.parsebytes(raw)
    if labels is None:
        labels = header_labels(_header(msg, "X-Gmail-Labels"))
    if is_chat(labels):
        return None
    name, domain = sender(msg)
    subject = _header(msg, "Subject")
    unsubscribe = bool(_header(msg, "List-Unsubscribe"))
    body = visible_body(msg, body_chars)[:body_chars].rstrip()
    date = utc_date(msg)
    fallback = "\x00".join([date.isoformat() if date else "", name, domain or "", subject, body])
    return Record(
        text=model_text(name, domain, subject, unsubscribe, body, header_lines),
        id=message_id(msg, fallback),
        date=date.strftime("%Y-%m-%dT%H:%M:%SZ") if date else None,
        year=date.year if date else None,
        from_domain=domain,
        list_unsubscribe=unsubscribe,
        gmail_category=gmail_category(labels),
        sent=is_sent(labels),
        lang=guess_language(body),
    )


def convert(
    messages: Iterable[tuple[bytes, frozenset[str] | None]],
    body_chars: int = DEFAULT_BODY_CHARS,
    header_lines: bool = True,
) -> tuple[list[Record], Counts]:
    """Every message's record, deduplicated by id and sorted by date then id, with counts."""
    by_id: dict[str, Record] = {}
    read = chats = duplicates = unreadable = 0
    for raw, labels in messages:
        read += 1
        try:
            record = to_record(raw, labels, body_chars, header_lines)
        except Exception:  # one bad message shouldn't stop an archive
            unreadable += 1
            continue
        if record is None:
            chats += 1
        elif record.id in by_id:
            duplicates += 1
        else:
            by_id[record.id] = record
    records = sorted(by_id.values(), key=lambda r: (r.date or "", r.id))
    return records, Counts(read, len(records), chats, duplicates, unreadable)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("source", type=Path, help="mbox file, folder of .eml files, or gyb backup")
    parser.add_argument("-o", "--output", type=Path, help="JSONL file to write (default: stdout)")
    parser.add_argument("--body-chars", type=int, default=DEFAULT_BODY_CHARS)
    parser.add_argument("--no-header-lines", dest="header_lines", action="store_false")
    args = parser.parse_args(argv)

    records, counts = convert(read_source(args.source), args.body_chars, args.header_lines)
    lines = "".join(record.to_json() + "\n" for record in records)
    if args.output:
        args.output.write_text(lines, encoding="utf-8")
    else:
        sys.stdout.write(lines)
    print(
        f"read {counts.read}, wrote {counts.written}, skipped {counts.chats} chats, "
        f"{counts.duplicates} duplicates, {counts.unreadable} unreadable",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
