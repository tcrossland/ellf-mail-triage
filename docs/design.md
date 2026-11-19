# Design

## Why

Gmail's categories are the obvious key for sorting bulk mail out of an
archive, but they miss everything from before Gmail had tabs (2013), they
are missing from mail that came from another provider, and they file some
personal mail as promotions. A small classifier trained on the archive
itself gives every message a kind, old mail included, without sending it
anywhere once it is trained.

[mailcellar](https://github.com/mailcellar/mailcellar), which offloads old
mail out of Gmail by rule, is the first intended user: a `kind` it could
filter on.

[Ellf](https://ellf.ai), from Explosion (spaCy, Prodigy), fits: it plugs into
Claude Code, runs annotation and training on a cluster on your own machine
(the free Solo plan), and is built around replacing LLM calls with small
private models. None of the public templates in
[explosion/ellf-templates](https://github.com/explosion/ellf-templates) is
about mail.

## What the template does

Sorts the messages in a mail archive into a few kinds that matter for what
to keep, using a small spaCy text classifier trained on labels that an LLM
drafts and a person settles, and measures it against the LLM, against
Gmail's own categories and against the person.

The question it answers, and the write-up's headline: on your own archive,
how close does a model that runs locally and costs nothing per message get
to an LLM, and how does it do on mail older than Gmail's categories?

## Decisions

- **Labels**, one per message, settled in the pilot (backlog step 2). The
  starting scheme follows Gmail's tabs where they serve retention and
  splits Updates, which mixes mail to keep with mail to drop:
  - `PERSONAL`: written by a person to you or a small group.
  - `TRANSACTIONAL`: receipts, invoices, orders, bookings, statements. Kept
    as records.
  - `NOTIFICATION`: automated alerts, shipping updates, social network
    mail, sign-in codes.
  - `BULK`: newsletters and marketing.
  - `LIST`: mailing lists and group discussions.
- **Gmail's categories count as one more annotator**, mapped onto the
  scheme: Primary to `PERSONAL`, Promotions to `BULK`, Forums to `LIST`,
  Social to `NOTIFICATION`, Updates to either `TRANSACTIONAL` or
  `NOTIFICATION`, scored at the coarser level. The llm-classifier-eval
  template treats an LLM the same way.
- **Text the model sees**: the sender's name and domain, the subject,
  whether there's a `List-Unsubscribe` header, then the first part of the
  visible body text. Whether the header lines help is measured, not
  assumed.
- **Two LLMs in the pilot**: Gemini through `gemini_agent`, as the
  support-insights template uses, and a local model through
  `hf_llm_agent`, which keeps mail on the machine. Both label the 100
  pilot messages as separate annotators. Their agreement with the settled
  labels, their speed and their cost decide which one drafts the training
  pool; both also label the eval set, so the write-up compares a cloud
  LLM, a local LLM and the small model. No mail goes to Gemini before its
  data-use terms are read (see [facts.md](facts.md)), and mail you wouldn't
  send out stays out of the pilot sample.
- **Train from a blank English pipeline**, so there is no base model whose
  licence needs checking, and CPU is enough.
- **The importer is a script run on the host**, not a recipe on the
  cluster: `scripts/mail_to_jsonl.py`, standard library only, reading an
  mbox (Google Takeout), a folder of `.eml` files, or a Got Your Back
  backup (its `msg-db.sqlite` for labels). It writes JSONL (`text`, `meta`)
  for `ellf publish data`, as support-insights' input is. The llm-to-jev
  template ships a `scripts/` folder too.
- **Nothing from real mail is published.** The template ships synthetic
  sample mail with fictional senders, as support-insights ships generated
  tickets. The write-up gives only figures, never a quoted message, and
  the model trained on real mail stays private. The Enron corpus is not
  used: CMU's page states no licence and asks users to be sensitive to the
  privacy of the people in it.
- **One person labels.** Solo allows one annotator, so the two-annotator
  agreement check the Explosion templates use isn't available. Instead the
  person relabels part of the eval set a week later, blind, to measure
  their own consistency.
