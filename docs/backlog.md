# Backlog

In order. Each item says when it is done.

2. **Importer.** `scripts/mail_to_jsonl.py`, standard library only: mbox,
   a folder of `.eml` files, or a Got Your Back backup, to JSONL (`text`,
   `meta`), with tests on synthetic mail.
   Done when: all three inputs produce the same records for the same
   messages, and `ellf publish data` accepts the output.
3. **Sample and pilot.** Export about 1,500 messages, spread over the
   years and over Gmail's categories, with a fixed seed: a pilot of 100,
   an eval set of 300 and a training pool of about 1,000, all disjoint,
   and the rest as backlog. Label the pilot by hand, with both LLM agents
   as second opinions, and settle the labels and guidelines from the
   disagreements (as helpdesk-routing's pilot does).
   Done when: the label scheme and guidelines are settled, one LLM is
   chosen to draft the training pool, and the bar the model has to reach
   is written down before anything is scored.
4. **Eval set.** Label the 300 blind, with no model or LLM in the loop. A
   week later, label 50 of them again blind.
   Done when: the eval set is labelled and the self-agreement figure is
   recorded.
5. **Training pool.** The chosen LLM drafts labels; the person curates them
   (support-insights' `curate` task).
   Done when: the pool is curated.
6. **Train and score.** Train the text classifier, with a learning curve
   to see whether more labels still help. Score the model, both LLMs and
   Gmail's categories against the eval set, overall, per label, and on the
   pre-2013 slice. Record time and cost per 1,000 messages for the model
   and each LLM.
   Done when: the scores and costs are in a results table, and the model
   is judged against the bar from step 3.
7. **Export and publish.** Export with `/ellf-template`, swap in synthetic
   sample mail, and fill the fields ellf-templates' AGENTS.md lists for
   `templates.json`. Tags: Text Classification, LLM Distillation,
   Evaluation, Data Import & Export, spaCy, and the chosen LLM.
   Done when: this repo is public with the template and the write-up, and
   nothing in it comes from real mail.
8. **Offer it to Explosion.** By their documented route for contributed
   templates.
   Done when: sent.
9. **Use it in mailcellar.** Planned in mailcellar once step 6 says the
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
