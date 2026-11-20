# Design

## Why

People sort an archive for their own reasons: what to keep, which client
or project a message belongs to, what still needs a reply. Gmail offers
one fixed set of categories, and in a real archive they say little: in one
Gmail account, Primary and Updates hold 99% of categorised mail,
Promotions 0.3% and Social almost none (see [facts.md](facts.md)). They
are also missing from older mail and from mail that came from another
provider. An LLM can sort mail into any categories, but each message takes
a second or more of a large model's time, on a paid service or on your own
hardware, and a cloud LLM sees the mail. A small classifier trained on the
archive itself, on categories its owner chose, should sort every message,
old mail included, far faster on the same machine, without sending it
anywhere. What it costs instead is labelling: a person's hours in the
pilot, the eval set and the training pool. Whether that trade pays is
measured, not assumed.

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
and your own categories, how close does a small model that runs locally
get to an LLM, and what does each cost: machine time per 1,000 messages,
and the person's hours the small model takes to train? The write-up
answers it for the default scheme on one archive; other schemes are
supported but not tested.

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
  from each, since Promotions, Social and Forums can be nearly empty, and
  with enough from each five-year period for the eval set to hold about 30
  of it. Your own mail is left out: the model sorts the mail you receive.
  It writes the pilot, eval set and training pool, disjoint, and the rest.
- **Results are given by age of mail** as well as overall and per label:
  for each five-year period of the archive, with the number of eval
  messages behind each score. Old mail comes from other senders, services
  and formats than recent mail, so a model can do well overall and badly
  on it, and old mail is what an archive is sorted to clear out. Old
  periods are oversampled for this, so the overall score weights each
  period by its share of the archive.
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
- **A kind is advice, not a decision to delete.** The template labels
  mail; what is kept or offloaded is decided by rules in the tool that
  acts on the labels, such as mailcellar's. Legal holds, duties to keep
  records for a number of years, and the retention policies of a work
  account are out of scope: a predicted label can't know about them, so
  those rules have to check them. The template's README says so.
- **The bar is set per label, around the costly mistake.** Errors aren't
  equal: mail to keep given a kind that is dropped may be offloaded,
  while mail to drop given a kind that is kept only takes up space. So
  the bar the model has to reach names the costly mistakes and limits
  them, as well as setting overall agreement; for the default scheme,
  `PERSONAL` or `TRANSACTIONAL` mail labelled `NOTIFICATION` or `BULK`.
  With your own scheme, you name the costly mistakes. The bar is written
  down in the pilot, before anything is scored.
- **Gmail's categories are an optional comparison**, not part of the
  headline. Where a scheme maps onto them, they are scored as one more
  annotator, at the coarser level, as llm-classifier-eval treats an LLM.
  For the default scheme the mapping is Primary to `PERSONAL`, Promotions
  to `BULK`, Forums to `LIST`, Social to `NOTIFICATION`, and Updates to
  `TRANSACTIONAL` or `NOTIFICATION`; in the archive checked this mostly
  measures Primary against Updates. It is scored only on the messages
  that have a category.
- **Text the model sees**: the sender's name and domain, the subject,
  whether there's a `List-Unsubscribe` header, then the first part of the
  visible body text. Whether the header lines help is measured, not
  assumed.
- **One local LLM, served by Ollama on your own machine** (by default Qwen3
  14B with thinking off, Apache-2.0), labels the pilot, the eval set and the
  training pool, so no mail leaves the machine and there is no fee per
  message; it costs machine time and power instead. It is called by
  `llm_to_dataset`, the action llm-classifier-eval ships (MIT), copied into
  `recipes/`: it sends the label definitions, the instructions and the
  message to an OpenAI-compatible endpoint and saves the answers as an
  annotator of their own; the copy asks for no thinking, which takes a reply
  from half a minute to about a second (see [facts.md](facts.md)). On a Mac
  the cluster reaches Ollama on the Mac's localhost through Lima, so no port
  is opened to the network. Cloud LLMs aren't used: Gemini's free tier may
  use and read what it is sent, its paid tier still keeps it for a while to
  check for abuse, and Hugging Face hands requests to providers whose data
  policies it doesn't state (see [facts.md](facts.md)). The cost is a weaker
  comparison: the write-up measures the small model against a 14B LLM, not a
  leading one, and the drafts need more curating. Any OpenAI-compatible
  endpoint works, so a user who accepts a cloud service's terms can point
  the action at one.
- **Costs are measured on one machine.** The write-up gives the time per
  1,000 messages for the small model and the local LLM, run on the same
  machine, the time training takes, and the person's hours labelling and
  curating in the pilot, eval set and training pool. Energy is not
  measured; time on one machine stands in for it. A cloud LLM's fee isn't
  measured either, since none is used.
- **Train from a blank English pipeline**, so there is no base model whose
  licence needs checking, and CPU is enough.
- **The importer is a script run on the host**, not a recipe on the
  cluster: `scripts/mail_to_jsonl.py`, standard library only, reading an
  mbox (Google Takeout), a folder of `.eml` files, or a Got Your Back
  backup (its `msg-db.sqlite` for labels). It writes JSONL (`text`, `meta`)
  for `ellf publish data`, as support-insights' input is. The meta keeps
  only a hash of the Message-ID, the date and year, the sender's domain,
  whether there's a `List-Unsubscribe` header, Gmail's category and
  whether it is your own mail (Gmail's Sent or Drafts); no address,
  recipient or user label is kept, and chats are dropped.
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
