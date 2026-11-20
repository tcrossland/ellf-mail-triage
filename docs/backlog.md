# Backlog

In order. Each item says when it is done.

5. **Pilot.** Copy `llm_to_dataset` from llm-classifier-eval into
   `recipes/`, change it to ask for no thinking (see [facts.md](facts.md)),
   and publish it. Label the 100 by hand, flagging every message you
   hesitate on, and save the local LLM's answers on the same messages as a
   separate annotator. Settle the labels, descriptions and guidelines in
   the two assets from the disagreements and flags (as helpdesk-routing's
   pilot does).
   Done when: the scheme is settled, the local LLM is judged good enough
   to draft the training pool (or a bigger local model is), and the bar
   the model has to reach is written down before anything is scored: per
   label, with a limit on the costly mistakes (mail to keep given a kind
   that is dropped).
   Progress (2026-11-20):
   - `recipes/mail_recipes` is published.
   - The pilot task `mail-pilot` is ready, using
     `config/prodigy_mail.json`.
   - Qwen3 14B's answers on the 100 are in `mail_pilot_llm` as annotator
     `qwen3-14b`. It took 7 min 15 s, about 4.3 s a message.
   - Left: your labels, then settling the scheme.
6. **Eval set.** Label the 300 blind, with no model or LLM in the loop. A
   week later, label 50 of them again blind.
   Done when: the eval set is labelled and the self-agreement figure is
   recorded.
7. **Training pool.** The local LLM drafts labels; the person curates them
   (support-insights' `curate` task).
   Done when: the pool is curated.
8. **Train and score.** Train the text classifier, with a learning curve
   (`train --train-curve`) to see whether more labels still help. Score
   the model and the local LLM against the eval set, overall, per label, and
   for each five-year period of the archive, with the number of eval
   messages behind each score; the overall score weights each period by
   its share of the archive. Score Gmail's categories too, through the
   default scheme's mapping and only on messages that have one, as a side
   comparison. Record the time per 1,000 messages for the model and the
   local LLM on the same machine, the training time, and the person's
   hours in steps 5 to 7.
   Done when: the scores and costs are in a results table, and the model
   is judged against the bar from step 5.
9. **Export and publish.** Export with `/ellf-template`, swap in synthetic
   sample mail, and fill the fields ellf-templates' AGENTS.md lists for
   `templates.json`. The README says how to use your own categories (the
   two assets and the `review` tasks' label lists), that only the default
   scheme is tested, and that a kind is advice: rules that act on it have
   to check legal holds and duties to keep records themselves. Tags: Text
   Classification, LLM Distillation, Evaluation, Data Import & Export,
   spaCy, and one for Ollama if the list has it.
   Done when: this repo is public with the template and the write-up, and
   nothing in it comes from real mail.
10. **Offer it to Explosion.** By their documented route for contributed
    templates.
    Done when: sent.
11. **Use it in mailcellar.** Planned in mailcellar once step 8 says the
    model is good enough: an optional extra, a command that stores each
    message's kind and score, and a `kind` scope key for offload rules.
    Done when: that plan exists in mailcellar.

## Done

1. **Learn the tools.** Install Ellf on the Solo plan and run the
   github-docs-issues template end to end; it is the closest single-label
   text classification template.
   Done when: that template has trained a model here, and anything learnt
   about Ellf that later steps rely on is in [facts.md](facts.md).
   Done 2026-11-20: a local K3s cluster in a Lima VM; 610 issues answered
   (179 accept, 378 reject, 53 ignore) by Claude rather than a person, as a
   tools run; the model scored ROC AUC 0.91 and F 78.7 on 20% held back.
2. **Importer.** `scripts/mail_to_jsonl.py`, standard library only: mbox,
   a folder of `.eml` files, or a Got Your Back backup, to JSONL (`text`,
   `meta`), with tests on synthetic mail.
   Done when: all three inputs produce the same records for the same
   messages, and `ellf publish data` accepts the output.
   Done 2026-11-20: identical JSONL from all three on synthetic mail, and
   `ellf publish data` took it. The gyb label format is checked on real
   backups; Takeout's is not yet (see [facts.md](facts.md)).
3. **Label scheme and splits.** Write the default scheme as
   `assets/mail_kinds.json` (each label's description, what not to give
   it, and examples from the synthetic mail) and
   `assets/mail_kinds_guidelines.md`. Write `scripts/make_splits.py`,
   standard library only, with tests on synthetic mail: about 1,500
   received messages (sent mail and drafts left out) from the importer's
   JSONL with a fixed seed, spread over the years first; within the years
   Gmail categorised, at least 30 from each category that has that many
   and all of any that has fewer. It splits them into a pilot of 100, an
   eval set of 300 and a training pool of about 1,000, all disjoint, each
   with the same spread, and the rest as backlog.
   Done when: both assets publish to the cluster, the script's tests pass,
   and the splits of the real archive are published.
   Done 2026-11-20: both assets published as version 0.1.0; the splits of
   one Gmail backup published as `Mail (pilot)`, `Mail (eval)` and
   `Mail (train)`. Version 1.1.0 draws enough from each five-year period
   for the eval set to hold about 30 of it, so step 8 can score by age.
4. **Choose the LLMs.** Between `gemini_agent`, `hf_llm_agent` and an
   agent recipe of our own that runs a model on the cluster, none of
   which is settled (see [facts.md](facts.md)). Read the data-use terms of
   each service considered before any mail goes to it.
   Done when: the choice and its reasons are in [design.md](design.md),
   and the terms it rests on are checked in facts.md.
   Done 2026-11-20: one local LLM, Qwen3 14B with thinking off, through
   Ollama, called by llm-classifier-eval's `llm_to_dataset` action rather
   than an agent of our own; no cloud LLM, after reading Gemini's and
   Hugging Face's terms.
