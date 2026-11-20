# Backlog

In order. Each item says when it is done.

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
   Done 2026-11-20: `recipes/mail_recipes` published; scheme 0.4.0 with
   five kinds (WORK, PERSONAL, ADMIN, AUTOMATED, BULK), settled over three
   rounds of the pilot: 0.1.0 had no kind for work mail, and 0.2.0 split
   records and dealings across three kinds while lists were rare. On 0.3.0
   the person labelled the 100 in 8.5 min and reviewed the 25
   disagreements in 5.2 min; their first labels agree with the reviewed
   ones on 94, the local LLM's on 77 (6 min 50 s for 100), with 5 costly
   mistakes. Its instructions are in `config/llm_instructions.txt`. The
   bar is in [design.md](design.md).
   Over half the pilot is in one language and the kind went with it, so
   results are given by language and the importer guesses it.
6. **Eval set.** Re-import and republish the splits so their meta has
   the language guess. The local LLM labels the 300, and the pilot's 100
   again with the final instructions, to score them against the person's
   reviewed labels.
   Done when: the eval set is labelled and the LLM's pilot score with the
   final instructions is recorded.
   Done 2026-11-20: the archive re-imported with the language guess and
   the same splits published as version 1.2.0. The person chose not to
   label the eval set or check the pool, about two hours more, so the
   LLM's labels are used as they are. The LLM labelled the 300 in 23.5
   min; with the final instructions it agrees with the person on 79 of
   the pilot's 100 (see [results.md](results.md)).
7. **Training pool.** The local LLM labels the 1,000 with the same
   instructions, and its labels are used as they are; the time is
   recorded.
   Done when: the pool is labelled.
   Done 2026-11-20: 998 messages (two duplicates dropped) labelled by
   Qwen3 14B, every one with a usable answer, in about 70 minutes of
   machine time over two runs. Qwen3 8B was tried on the pilot first and
   ruled out (see [results.md](results.md)).
8. **Train and score.**
   - **Train** the text classifier from a blank `en` pipeline and from a
     blank `xx` one, with a learning curve (`train --train-curve`) to see
     whether more labels still help, and keep the better.
   - **Apply the model:** save its answer on each eval and pilot message
     as an annotator of its own, as `llm_to_dataset` does for the LLM.
     `train` reports only overall scores, and of the cluster's recipes only
     the GPU package's `apply_curated_transformer` applies a model (not
     read), so this probably needs an action of our own.
   - **Score** with `scripts/score.py` from dataset exports: the model
     against the LLM on the eval set, and the model and the LLM against
     the person's reviewed pilot labels, overall, per label, per period
     and per language, with intervals. Score Gmail's categories too,
     through the default scheme's mapping, as a side comparison.
   - **Costs:** the time per 1,000 messages for the model and the local
     LLM on the same machine, the training time, the LLM's time in steps 6
     and 7, and the person's hours in step 5.

   Done when: the scores and costs are in [results.md](results.md), and
   the model is judged against the bar in [design.md](design.md).
   Done 2026-11-20: spaCy's text classifier from blank `en` and `xx`
   pipelines, about 2 minutes to train and about 1 second per 1,000
   messages, applied by `model_to_dataset` in `mail_recipes` 0.4.0. `xx`
   agrees with the person on 79 of 100 with 4 of 86 costly, as the LLM
   does (79, 5), and fails the bar as the LLM does. The learning curve
   still rises. Whether the header lines help is not yet measured.
