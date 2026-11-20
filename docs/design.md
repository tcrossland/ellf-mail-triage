# Design

What the template does and why each part is as it is. What it has found
so far is in [results.md](results.md); the facts the design relies on,
with sources, are in [facts.md](facts.md).

## Why

Gmail's categories say little about an old archive: in one account,
Primary and Updates hold 99% of categorised mail, and mail from before
late 2010 or from other providers has none. An LLM can sort into any
categories, but slowly, and a cloud LLM sees the mail. A small classifier
trained on the archive itself runs fast and locally; what it costs is
labels. The template measures whether that trade pays.

[mailcellar](https://github.com/mailcellar/mailcellar), which offloads old
mail out of Gmail by rule, is the first intended user: it could filter on
a message's kind. Its scheme is the template's default and worked example.

[Ellf](https://ellf.ai), from Explosion (spaCy, Prodigy), fits. It plugs
into Claude Code, runs annotation and training on a cluster on your own
machine (the free Solo plan; on a Mac, in a Linux VM), and is built around
replacing LLM calls with small private models. None of the public
templates in [explosion/ellf-templates](https://github.com/explosion/ellf-templates)
is about mail.

## What the template does

It sorts the messages in a mail archive into categories you define, one
per message, with a small spaCy text classifier trained on a local LLM's
labels. It measures the classifier against the LLM, and against a person
on the pilot.

The headline question: on your own archive and categories, how close does
a small local model get to an LLM, and what does each cost? Cost here is
machine time per 1,000 messages and the person's hours. The write-up
answers it for the default scheme on one archive; other schemes are
supported but not tested.

## Decisions

- **The categories are an input**, in two assets: a label scheme
  (`assets/mail_kinds.json`), with each label's description, what not to
  give it and examples, and guidelines for the person
  (`assets/mail_kinds_guidelines.md`). The labelling task shows both. The
  LLM gets the scheme's descriptions and its own instructions, not the
  guidelines. Training takes its labels from the answers. To change the
  scheme, edit the two files and the label list of the `review` tasks.
  Labels are exclusive, one per message.
- **The pilot is where a scheme is settled.** Start from the default or
  your own draft, label 100 messages by hand with the LLM's answers to
  compare, and change the labels, descriptions and guidelines where the
  two disagree.
- **The sample is drawn by a script**, `scripts/make_splits.py`, from the
  importer's JSONL with a fixed seed. It spreads the sample over the
  years, takes a minimum from each Gmail category (some are nearly
  empty), and takes enough from each five-year period for the eval set to
  hold about 30 of it. Your own mail is left out, since the model sorts
  mail you receive. It writes the pilot, eval set and training pool,
  disjoint, and the rest.
- **Results are given by age of mail**, per five-year period, with the
  number of eval messages behind each score. Old mail comes from other
  senders and services, and it is what an archive is sorted to clear out,
  so a model that does well overall but badly on it is no use. Old periods
  are oversampled, so the overall score weights each period by its share
  of the archive.
- **Results are given by language too.** An archive is often in more than
  one language, and the kind can go with the language: in the archive
  checked, most mail in one language was work. A model can then learn the
  language instead of the kind. Scores are given per language, from the
  importer's guess, and so is the LLM's agreement with the person, since
  its instructions are in English.
- **The default scheme sorts by what to keep.** Work, personal mail and
  your own records are kept; automated and bulk mail can go. It maps onto
  Gmail's categories only roughly.
  - `WORK`: mail about your job, from people and the job's own paperwork.
  - `PERSONAL`: a person you know writing about your life outside work.
  - `ADMIN`: your own affairs with organisations: receipts, bookings,
    statements, contracts, tax, health, school, housing, insurance.
  - `AUTOMATED`: mail a system sends about your account or activity:
    codes, alerts, shipping updates, reminders, notices from work systems.
  - `BULK`: the same message sent to many people: newsletters, marketing,
    announcements and mailing lists.
- **A kind is advice, not a decision to delete.** What is kept or
  offloaded is up to the tool that acts on the kinds, such as mailcellar.
  A predicted kind knows nothing of legal holds, duties to keep records or
  a work account's retention policy, so those rules have to check them.
  The README says so.
- **The bar is set around the costly mistake.** Mail to keep given a kind
  that can go may be offloaded; the reverse only takes up space. So the
  bar limits the costly mistake as well as setting overall agreement. It
  is written down in the pilot, before anything is scored. With your own
  scheme, you name the costly mistakes. For the default scheme:

  | Test | Limit | Applies to |
  |---|---|---|
  | Mail to keep given a kind that can go | at most 2% | overall, and each language with 50+ eval messages |
  | Agreement, weighted by period | at least 85% | overall |
  | Gap between languages | at most 10 points | languages with 50+ eval messages |

  It is measured twice. Against the LLM on the eval set of 300: did the
  model learn what it was taught? Against the person on the pilot's 100:
  is what it learnt right? The pilot is small, so each figure there comes
  with its 95% interval, and the language tests don't apply.
- **The LLM labels; the person labels only the pilot.** Solo allows one
  annotator. The LLM labels the eval set and the training pool alone, and
  its labels are used as they are; checking them would have cost the
  person about two hours more. So the headline measures distillation: how
  close the small model gets to the LLM it learns from. The LLM's own
  errors pass into the training labels, and only the pilot shows them, so
  the LLM is scored there too. The person's consistency is their first
  pilot labels against the ones they settled on after review, which
  overstates how often they would agree with themselves a week later.
- **One local LLM, served by Ollama** (by default Qwen3 14B with thinking
  off, Apache-2.0), so no mail leaves the machine and there is no fee per
  message. It is called by `llm_to_dataset`, the action llm-classifier-eval
  ships (MIT), copied into `recipes/` and changed to turn thinking off,
  save in batches and retry. Its instructions are in
  `config/llm_instructions.txt`, generic for any archive. Cloud LLMs aren't
  used: Gemini's free tier may read what it is sent, its paid tier keeps
  it for a while, and Hugging Face doesn't state its providers' data
  policies. The cost is a weaker teacher than a leading model. Any
  OpenAI-compatible endpoint works, for a user who accepts a service's
  terms.
- **Gmail's categories are a side comparison**, scored as one more
  annotator where a scheme maps onto them, and only on messages that have
  one. For the default scheme: Primary to `WORK`, `PERSONAL` or `ADMIN`,
  Updates to `ADMIN` or `AUTOMATED`, Social to `AUTOMATED`, Promotions and
  Forums to `BULK`.
- **The text the model sees** is the sender's name and domain, the
  subject, whether there's a `List-Unsubscribe` header, and the start of
  the visible body. Whether the header lines help is measured too.
- **Costs are measured on one machine**: time per 1,000 messages for the
  small model and the LLM, training time, the LLM's labelling time and
  the person's hours. Energy isn't measured; time stands in for it.
- **Train from a blank pipeline**, so no base model's licence needs
  checking and CPU is enough. English (`en`) or spaCy's multi-language
  pipeline (`xx`) is chosen on the eval set.
- **The importer is a script run on the host**, `scripts/mail_to_jsonl.py`,
  standard library only. It reads an mbox (Google Takeout), a folder of
  `.eml` files or a Got Your Back backup, and writes JSONL for
  `ellf publish data`. The meta keeps a hash of the Message-ID, the date,
  the sender's domain, the `List-Unsubscribe` flag, Gmail's category,
  whether it is your own mail, and a guess at the language. No address,
  recipient or user label is kept, and chats are dropped.
  `--no-header-lines` writes the body alone.
- **Nothing from real mail is published.** The template ships synthetic
  mail with fictional senders. The write-up gives only figures, and the
  model trained on real mail stays private. The Enron corpus isn't used:
  CMU's page states no licence and asks users to respect the privacy of
  the people in it.

Borrowed from other Ellf templates: the scheme as assets and the pilot
(helpdesk-routing), JSONL input and synthetic sample data
(support-insights), a `scripts/` folder (llm-to-jev), and the
`llm_to_dataset` action and the LLM as one more annotator
(llm-classifier-eval).
