# Ellf Template: Mail Triage

An [Ellf](https://ellf.ai) template that sorts the messages in a mail archive
into categories you define. It trains a small spaCy text classifier on labels
that an LLM drafts and a person settles, and it runs on your own machine, so
no mail has to leave it once the model is trained. The default categories
sort by what to keep: personal, transactional, notification, bulk and
mailing list.

The question it answers: on your own archive and your own categories, how
close does a model that runs locally and costs nothing per message get to an
LLM? It scores the model against the LLMs that labelled alongside it and the
person who labelled the evaluation set, and, for the default categories,
against Gmail's own.

**Status:** the importer is built: `scripts/mail_to_jsonl.py` turns an mbox,
a folder of `.eml` files or a Got Your Back backup into JSONL for Ellf.
[docs/design.md](docs/design.md) says how the rest will work and
[docs/backlog.md](docs/backlog.md) what comes next.

## Privacy

The template ships synthetic sample mail with fictional senders. Nothing from
real mail is published: no messages, no quotes, and no model trained on real
mail. The write-up reports figures only.

## Licence

[MIT](LICENSE).
