# Ellf Template: Mail Triage

An [Ellf](https://ellf.ai) template that sorts the messages in a mail archive
into categories you define. It trains a small spaCy text classifier on labels
that an LLM drafts and a person settles, and it runs on your own machine, so
no mail has to leave it once the model is trained. The default categories
sort by what to keep: work, personal, admin (your own records), automated
and bulk.

The question it answers: on your own archive and your own categories, how
close does a small model that runs locally get to an LLM, and what does each
cost in machine time and in the hours a person spends labelling? It scores the
model against a local LLM that labelled alongside it, run through Ollama so no
mail leaves your machine, and against the person who labelled the evaluation
set, and, for the default categories, against Gmail's own.

An archive is often in more than one language, and the kinds of mail may
differ between them, so results are given per language as well as per age of
mail. The importer records a rough guess at each message's language.

**Status:** `scripts/mail_to_jsonl.py` turns an mbox, a folder of `.eml`
files or a Got Your Back backup into JSONL for Ellf, `scripts/make_splits.py`
draws the pilot, eval set and training pool from it, and `assets/` holds the
default categories. [docs/design.md](docs/design.md) says how the rest will
work and [docs/backlog.md](docs/backlog.md) what comes next.

## Privacy

The template ships synthetic sample mail with fictional senders. Nothing from
real mail is published: no messages, no quotes, and no model trained on real
mail. The write-up reports figures only.

## Licence

[MIT](LICENSE).
