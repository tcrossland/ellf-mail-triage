# Ellf Template: Mail Triage

An [Ellf](https://ellf.ai) template that sorts the messages in a mail archive
into a few kinds that matter for what to keep: personal, transactional,
notification, bulk and mailing list. It trains a small spaCy text classifier
on labels that an LLM drafts and a person settles, and it runs on your own
machine, so no mail has to leave it once the model is trained.

The question it answers: on your own archive, how close does a model that
runs locally and costs nothing per message get to an LLM, and how does it do
on mail older than Gmail's categories? It scores the model against a cloud
LLM, a local LLM, Gmail's own categories and the person who labelled the
evaluation set.

**Status:** nothing built yet. [docs/design.md](docs/design.md) says how it
will work and [docs/backlog.md](docs/backlog.md) what comes next.

## Privacy

The template ships synthetic sample mail with fictional senders. Nothing from
real mail is published: no messages, no quotes, and no model trained on real
mail. The write-up reports figures only.

## Licence

[MIT](LICENSE).
