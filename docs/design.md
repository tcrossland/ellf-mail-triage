# Design

## Why

People sort an archive for their own reasons: what to keep, which client or
project a message belongs to, what still needs a reply. Gmail offers one
fixed set of categories, and in a real archive they say little: in one
Gmail account, Primary and Updates hold 99% of categorised mail, Promotions
0.3% and Social almost none (see [facts.md](facts.md)). They are also
missing from mail before late 2010, when Gmail began to categorise mail,
and from mail that came from another provider. An LLM can sort mail into
any categories, but per message it costs money and time, and a cloud LLM
sees the mail. A small classifier trained on the archive itself, on
categories its owner chose, sorts every message, old mail included,
without sending it anywhere once it is trained.

[mailcellar](https://github.com/mailcellar/mailcellar), which offloads old
mail out of Gmail by rule, is the first intended user: a `kind` it could
filter on. Its scheme is the template's default and worked example.

[Ellf](https://ellf.ai), from Explosion (spaCy, Prodigy), fits: it plugs into
Claude Code, runs annotation and training on a cluster on your own machine
(the free Solo plan; on a Mac, in a Linux VM), and is built around
replacing LLM calls with small private models. None of the public templates
in [explosion/ellf-templates](https://github.com/explosion/ellf-templates)
is about mail.

## What the template does

Sorts the messages in a mail archive into categories you define, one per
message, using a small spaCy text classifier trained on labels that an LLM
drafts and a person settles, and measures it against the LLM and against
the person.

The question it answers, and the write-up's headline: on your own archive
and your own categories, how close does a model that runs locally and
costs nothing per message get to an LLM? The write-up answers it for the
default scheme on one archive; other schemes are supported but not tested.

## Decisions

- **The categories are an input**, in two assets, as helpdesk-routing
  keeps its problem areas: a label scheme (`assets/mail_kinds.json`), with
  each label's description, what not to give it and examples, and
  guidelines (`assets/mail_kinds_guidelines.md`). The labelling tasks read
  both, and an LLM agent assigned to a task reads them from the task;
  training takes its labels from the answers. Changing the scheme means
  editing the two files and the label list of the `review` tasks, which
  takes a typed list (see [facts.md](facts.md)). Labels are exclusive, one
  per message; a multi-label scheme is out of scope.
- **The pilot is where a scheme is settled.** You start from the default or
  your own draft, label 100 messages by hand with an LLM's answers to
  compare, and settle the labels, descriptions and guidelines from the
  disagreements, as helpdesk-routing's pilot does.
- **The sample is drawn by a script**, `scripts/make_splits.py`, standard
  library only, from the importer's JSONL with a fixed seed: spread over
  the years, then, where messages have a Gmail category, with a minimum
  from each, since Promotions, Social and Forums can be nearly empty. It
  writes the pilot, eval set and training pool, disjoint, and the rest.
- **The default scheme sorts by what to keep**, for mailcellar. It follows
  Gmail's categories where they serve retention and splits Updates, which
  mixes mail to keep with mail to drop:
  - `PERSONAL`: written by a person to you or a small group.
  - `TRANSACTIONAL`: receipts, invoices, orders, bookings, statements. Kept
    as records.
  - `NOTIFICATION`: automated alerts, shipping updates, social network
    mail, sign-in codes.
  - `BULK`: newsletters and marketing.
  - `LIST`: mailing lists and group discussions.
- **Gmail's categories are an optional comparison**, not part of the
  headline. Where a scheme maps onto them, they are scored as one more
  annotator, at the coarser level, as llm-classifier-eval treats an LLM.
  For the default scheme the mapping is Primary to `PERSONAL`, Promotions
  to `BULK`, Forums to `LIST`, Social to `NOTIFICATION`, and Updates to
  `TRANSACTIONAL` or `NOTIFICATION`; in the archive checked this mostly
  measures Primary against Updates. Mail from before late 2010 has no
  category, so the results are also given for that slice, where Gmail
  offers nothing.
- **Text the model sees**: the sender's name and domain, the subject,
  whether there's a `List-Unsubscribe` header, then the first part of the
  visible body text. Whether the header lines help is measured, not
  assumed.
- **Which LLMs: open.** Both built-in LLM agents send the mail to a
  service: `gemini_agent` to Google, `hf_llm_agent` to Hugging Face and an
  Inference Provider. None runs an LLM on the cluster, so a local LLM
  would need an agent recipe of our own in `recipes/` (see
  [facts.md](facts.md)). Whichever are used label the pilot as separate
  annotators; their agreement with the settled labels, their speed and
  their cost decide which one drafts the training pool, and each also
  labels the eval set. No mail goes to a service before its data-use
  terms are read, and mail you wouldn't send out stays out of the sample
  it sees.
- **Train from a blank English pipeline**, so there is no base model whose
  licence needs checking, and CPU is enough.
- **The importer is a script run on the host**, not a recipe on the
  cluster: `scripts/mail_to_jsonl.py`, standard library only, reading an
  mbox (Google Takeout), a folder of `.eml` files, or a Got Your Back
  backup (its `msg-db.sqlite` for labels). It writes JSONL (`text`, `meta`)
  for `ellf publish data`, as support-insights' input is. The meta keeps
  only a hash of the Message-ID, the date and year, the sender's domain,
  whether there's a `List-Unsubscribe` header and Gmail's category; no
  address, recipient or user label is kept, and chats are dropped.
  `--no-header-lines` writes the body alone, for measuring whether the
  header lines help. The llm-to-jev template ships a `scripts/` folder too.
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
