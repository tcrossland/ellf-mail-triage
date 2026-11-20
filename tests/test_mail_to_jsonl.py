"""Tests for scripts/mail_to_jsonl.py, on synthetic mail with fictional senders."""

import csv
import io
import json
import mailbox
import sqlite3
from email.message import EmailMessage
from email.utils import format_datetime, parsedate_to_datetime
from pathlib import Path

import pytest
from conftest import load_script

m2j = load_script("mail_to_jsonl")


def _message(
    sender: str,
    subject: str,
    date: str,
    plain: str | None = None,
    html: str | None = None,
    message_id: str | None = None,
    unsubscribe: bool = False,
    charset: str = "utf-8",
) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = "Reader <reader@example.net>"
    msg["Subject"] = subject
    msg["Date"] = date
    if message_id:
        msg["Message-ID"] = message_id
    if unsubscribe:
        msg["List-Unsubscribe"] = "<mailto:leave@example.org>"
    if plain is not None:
        msg.set_content(plain, charset=charset)
    if html is not None:
        if plain is None:
            msg.set_content(html, subtype="html")
        else:
            msg.add_alternative(html, subtype="html")
    return msg


# (message, Gmail label IDs as gyb records them)
ARCHIVE = [
    (
        _message(
            "Ada Lovelace <ada@example.com>",
            "Lunch on Friday?",
            "Fri, 06 Mar 2015 09:15:00 +0000",
            plain="Hi,\n\nare you free for lunch on Friday?\n\nAda",
            message_id="<lunch.1@example.com>",
        ),
        ["INBOX", "CATEGORY_PERSONAL"],
    ),
    (
        _message(
            "Example Deals <news@shop.example.org>",
            "50% off everything this weekend",
            "Sat, 07 Mar 2015 10:00:00 +0200",
            html=(
                "<html><head><title>Deals</title><style>p {color: red}</style></head>"
                "<body><p>Big   sale</p><script>track()</script><p>Shop now &amp; save</p>"
                "</body></html>"
            ),
            message_id="<deal.42@shop.example.org>",
            unsubscribe=True,
        ),
        ["INBOX", "CATEGORY_PROMOTIONS"],
    ),
    (
        _message(
            "Example Rail <tickets@example.org>",
            "Your booking is confirmed",
            "Mon, 09 Mar 2015 18:30:00 -0500",
            plain="Booking reference ABC123. Seat 42.",
            html="<p>Booking reference <b>ABC123</b>. Seat 42.</p>",
            message_id="<booking.7@example.org>",
        ),
        ["CATEGORY_UPDATES", "Receipts, 2015"],
    ),
    (
        _message(
            "Café Example <hello@example.com>",
            "Merci",
            "Tue, 10 Mar 2015 08:00:00 +0100",
            plain="Merci beaucoup, à bientôt.",
            charset="latin-1",
        ),
        ["SENT"],
    ),
    (
        _message(
            "Old Friend <friend@example.net>",
            "Photos from the trip",
            "Sun, 12 Jul 2009 20:00:00 +0000",
            plain="Here are the photos.",
            message_id="<photos@example.net>",
        ),
        ["INBOX"],
    ),
    (
        _message(
            "Ada Lovelace <ada@example.com>",
            "chat",
            "Wed, 11 Mar 2015 12:00:00 +0000",
            plain="ok",
            message_id="<chat.1@example.com>",
        ),
        ["CHAT"],
    ),
]


def _takeout_name(label: str) -> str:
    """A Gmail label ID as Takeout names it (unverified: see docs/facts.md)."""
    if label.startswith("CATEGORY_"):
        return "Category " + label.removeprefix("CATEGORY_").title()
    return {"INBOX": "Inbox", "CHAT": "Chat", "SENT": "Sent"}.get(label, label)


def _labels_header(labels: list[str]) -> str:
    out = io.StringIO()
    csv.writer(out, lineterminator="").writerow([_takeout_name(x) for x in labels])
    return out.getvalue()


def _with_labels_header(msg: EmailMessage, labels: list[str]) -> bytes:
    """The message with Takeout's X-Gmail-Labels header first, as Takeout writes it."""
    return f"X-Gmail-Labels: {_labels_header(labels)}\n".encode() + msg.as_bytes()


def write_mbox(path: Path) -> Path:
    box = mailbox.mbox(path)
    for msg, labels in ARCHIVE:
        box.add(_with_labels_header(msg, labels))
    box.flush()
    box.close()
    return path


def write_eml_folder(folder: Path) -> Path:
    for i, (msg, labels) in enumerate(ARCHIVE):
        path = folder / f"part{i % 2}" / f"{i}.eml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(_with_labels_header(msg, labels))
    return folder


def write_gyb(folder: Path) -> Path:
    """A Got Your Back backup (db_version 6): msg-db.sqlite and <y>/<m>/<d>/<id>.eml."""
    folder.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(folder / "msg-db.sqlite")
    con.executescript(
        """
        CREATE TABLE settings (name TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE messages(message_num INTEGER PRIMARY KEY,
                              message_filename TEXT,
                              message_internaldate TIMESTAMP);
        CREATE TABLE labels (message_num INTEGER, label TEXT);
        CREATE TABLE uids (message_num INTEGER, uid TEXT PRIMARY KEY);
        CREATE UNIQUE INDEX labelidx ON labels (message_num, label);
        INSERT INTO settings VALUES ('db_version', '6');
        """
    )
    for i, (msg, labels) in enumerate(ARCHIVE):
        if "CHAT" in labels:
            continue  # gyb doesn't back up chats
        when = parsedate_to_datetime(msg["Date"])
        gmail_id = f"18{i:014x}"
        rel = f"{when.year}/{when.month}/{when.day}/{gmail_id}.eml"
        (folder / rel).parent.mkdir(parents=True, exist_ok=True)
        raw = msg.as_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
        (folder / rel).write_bytes(raw)
        cur = con.execute(
            "INSERT INTO messages (message_filename, message_internaldate) VALUES (?, ?)",
            (rel, str(when.replace(tzinfo=None))),
        )
        con.execute("INSERT INTO uids VALUES (?, ?)", (cur.lastrowid, gmail_id))
        con.executemany(
            "INSERT INTO labels VALUES (?, ?)", [(cur.lastrowid, label) for label in labels]
        )
    con.commit()
    con.close()
    return folder


@pytest.fixture
def sources(tmp_path):
    return {
        "mbox": write_mbox(tmp_path / "takeout.mbox"),
        "eml": write_eml_folder(tmp_path / "eml"),
        "gyb": write_gyb(tmp_path / "gyb"),
    }


def _convert(source: Path, **kwargs):
    return m2j.convert(m2j.read_source(source), **kwargs)


def test_every_source_gives_the_same_records(sources):
    results = {kind: _convert(path) for kind, path in sources.items()}
    mbox_records = results["mbox"][0]
    assert len(mbox_records) == 5
    assert results["eml"][0] == mbox_records
    assert results["gyb"][0] == mbox_records
    assert results["mbox"][1].chats == 1
    assert results["eml"][1].chats == 1


def test_records_are_sorted_by_date(sources):
    records, _ = _convert(sources["mbox"])
    assert [r.date for r in records] == sorted(r.date for r in records)
    assert records[0].year == 2009


def test_newsletter_record(sources):
    records, _ = _convert(sources["gyb"])
    deal = next(r for r in records if r.from_domain == "shop.example.org")
    assert deal.text == (
        "From: Example Deals (shop.example.org)\n"
        "Subject: 50% off everything this weekend\n"
        "List-Unsubscribe: yes\n"
        "\n"
        "Big sale Shop now & save"
    )
    assert deal.list_unsubscribe is True
    assert deal.gmail_category == "promotions"
    assert deal.date == "2015-03-07T08:00:00Z"


def test_plain_text_is_preferred_to_html(sources):
    records, _ = _convert(sources["mbox"])
    booking = next(r for r in records if r.gmail_category == "updates")
    assert booking.text.endswith("\n\nBooking reference ABC123. Seat 42.")
    assert booking.date == "2015-03-09T23:30:00Z"


def test_non_utf8_body_and_missing_message_id(sources):
    records = {kind: _convert(path)[0] for kind, path in sources.items()}
    cafe = [next(r for r in rs if r.text.endswith("à bientôt.")) for rs in records.values()]
    assert len({r.id for r in cafe}) == 1
    assert cafe[0].from_domain == "example.com"
    assert cafe[0].gmail_category is None


def test_sent_mail_is_flagged_from_every_source(sources):
    for path in sources.values():
        records, _ = _convert(path)
        assert [r.text.endswith("à bientôt.") for r in records] == [r.sent for r in records]


@pytest.mark.parametrize(
    "labels, expected",
    [({"SENT", "INBOX"}, True), ({"Drafts"}, True), ({"DRAFT"}, True), ({"Inbox"}, False)],
)
def test_is_sent(labels, expected):
    assert m2j.is_sent(labels) is expected


def test_no_address_local_part_is_kept(sources):
    records, _ = _convert(sources["mbox"])
    dumped = "\n".join(r.to_json() for r in records)
    for local in ("ada@", "news@", "tickets@", "hello@", "friend@", "reader@", "lunch.1@"):
        assert local not in dumped


def test_header_labels_handle_quoted_commas():
    assert m2j.header_labels('Inbox,"Receipts, 2015", Category Updates') == {
        "Inbox",
        "Receipts, 2015",
        "Category Updates",
    }
    assert m2j.header_labels(None) == frozenset()


@pytest.mark.parametrize(
    "labels, expected",
    [
        ({"INBOX", "CATEGORY_SOCIAL"}, "social"),
        ({"Inbox", "Category Forums"}, "forums"),
        ({"category personal"}, "personal"),
        ({"INBOX", "Receipts"}, None),
    ],
)
def test_gmail_category(labels, expected):
    assert m2j.gmail_category(labels) == expected


@pytest.mark.parametrize(
    "text, expected",
    [
        ("Thanks for the photos. We will refund the chair, you don't need to send it back.", "en"),
        (
            "Hola, gracias por las fotos. Te devolvemos el dinero y no hace falta enviar la silla.",
            "es",
        ),
        (
            "Bonjour, merci pour les photos. Nous vous remboursons, pas besoin de la chaise.",
            "fr",
        ),
        (
            "Hallo, danke für die Fotos. Wir erstatten den Betrag, Sie müssen nicht schicken.",
            "de",
        ),
        (
            "Olá, obrigado pelas fotos. Não é preciso devolver, você recebe o valor com isso.",
            "pt",
        ),
        (
            "Ciao, grazie per le foto. Non è necessario rispedire la sedia, è già fatto.",
            "it",
        ),
        ("OK, 10:30", None),
        ("Thanks and gracias y the plan el plan", None),
    ],
)
def test_guess_language(text, expected):
    assert m2j.guess_language(text) == expected


def test_language_is_guessed_from_the_body_only():
    msg = _message(
        "Ana Ruiz <ana@example.org>",
        "Please read: the plan for the year",
        "Mon, 02 Mar 2015 10:00:00 +0000",
        plain="Hola, te mando el plan para el año. Gracias por todo y saludos.",
        message_id="<plan.1@example.org>",
    )
    record = m2j.to_record(msg.as_bytes(), frozenset())
    assert record.lang == "es"
    assert json.loads(record.to_json())["meta"]["lang"] == "es"


def test_duplicates_are_written_once():
    raw = ARCHIVE[0][0].as_bytes()
    records, counts = m2j.convert([(raw, frozenset()), (raw, frozenset())])
    assert len(records) == 1
    assert counts.duplicates == 1


def test_body_chars_and_no_header_lines():
    msg = _message(
        "A <a@example.com>",
        "Long",
        format_datetime(parsedate_to_datetime("Fri, 06 Mar 2015 09:15:00 +0000")),
        plain="word " * 500,
    )
    record = m2j.to_record(msg.as_bytes(), frozenset(), body_chars=20, header_lines=False)
    assert record.text == "word word word word"


def test_unreadable_date_gives_none():
    msg = _message("A <a@example.com>", "No date", "not a date", plain="hi")
    record = m2j.to_record(msg.as_bytes(), frozenset())
    assert record.date is None and record.year is None


def test_gyb_paths_outside_the_folder_are_ignored(sources, tmp_path):
    outside = tmp_path / "outside.eml"
    outside.write_bytes(ARCHIVE[4][0].as_bytes())
    con = sqlite3.connect(sources["gyb"] / "msg-db.sqlite")
    con.execute(
        "INSERT INTO messages (message_filename, message_internaldate) VALUES (?, ?)",
        ("../outside.eml", "2009-07-12 20:00:00"),
    )
    con.commit()
    con.close()
    _, counts = _convert(sources["gyb"])
    assert counts.read == 5


def test_main_writes_jsonl(sources, tmp_path, capsys):
    out = tmp_path / "out.jsonl"
    assert m2j.main([str(sources["eml"]), "-o", str(out)]) == 0
    lines = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(lines) == 5
    assert all(set(line) == {"text", "meta"} for line in lines)
    assert sum(line["meta"]["sent"] for line in lines) == 1
    assert "wrote 5" in capsys.readouterr().err
