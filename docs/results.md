# Results

What the template has found so far on one real archive, with the default
scheme. Figures only; no message is quoted. Measured on an M2 MacBook Air
with 24 GB. How each figure is produced is in [design.md](design.md);
`scripts/score.py` computes the scores from dataset exports.

## Settling the scheme

The pilot ran three times before the scheme held:

1. Scheme 0.1.0 had no kind for work mail, the largest share of received
   mail.
2. Scheme 0.2.0 split records and dealings with organisations across three
   kinds, while mailing lists were too rare to need their own.
3. Scheme 0.3.0 has the five kinds now in use. Version 0.4.0 keeps them
   and adds the cases the round's disagreements settled.

In the third round the person labelled the 100 in 8.5 minutes and
reviewed the 25 disagreements with the LLM in 5.2 minutes. Their first
labels agree with their reviewed ones on 94 of 100.

## The LLM against the person

Qwen3 14B without thinking, scored against the person's reviewed labels
on the pilot's 100:

| | Earlier instructions | Final instructions |
|---|---|---|
| Agreement | 77/100 | 79/100 (70% to 86%) |
| Weighted by period | 80.0% | 83.0% |
| Mail to keep given a kind that can go | 5/86 | 5/86 (3% to 13%) |

Ranges are 95% intervals. The final instructions were written from this
pilot, so their score here flatters them a little.

By language, with the final instructions:

| | Agreement | Costly mistakes |
|---|---|---|
| The archive's main language | 46/49 | 0/48 |
| English, the instructions' language | 29/45 | 5/32 |

The commonest disagreements are `ADMIN` given `WORK` (8) and `PERSONAL`
given `WORK` (4). The costly ones are all mail to keep given `BULK`.

Against the bar, the LLM itself fails on the pilot: 5.8% costly mistakes
against a limit of 2%, and 83% agreement against 85%. The small model,
which learns from it, fails too (see below).

### The full label definitions

With `--label-details` the prompt also carries each kind's list of what
not to give it and the scheme's examples, about 2,150 tokens instead of
800, at the same speed since the added part is cached. On the pilot:

| | Descriptions only | Full definitions |
|---|---|---|
| Agreement | 79/100 | 71/99 |
| Weighted by period | 83.0% | 73.8% |
| Mail to keep given a kind that can go | 5/86 | 2/85 (1% to 8%) |
| The archive's main language | 46/49 | 39/48 |
| English | 29/45 | 29/45 |

The answer changed on 18 messages. The fuller prompt fixed 3 costly
mistakes and made none, but `PERSONAL` given `WORK` rose from 4 to 9.
Neither change is clear on 100 messages (exact tests on the changed
answers: p = 0.25 for costly mistakes, p = 0.14 for agreement), and both
versions miss the bar. The eval set and training pool were labelled with
the descriptions only.

### A smaller LLM

Qwen3 8B, same prompt, on the same pilot: twice as fast, but only 49 of
its 100 replies were usable; the other 51 named two labels where one was
asked for. On those 49 it agreed with the person on 29, and put 17 of the
35 messages to keep in a kind that can go. It is not used.

## Machine time

| Step | Time |
|---|---|
| The LLM (14B) labelling the eval set, 300 messages | 23 min 31 s (4.7 s each) |
| The LLM (14B) labelling the pilot, 100 messages | 6 to 9 min |
| The LLM (8B) labelling the pilot, 100 messages | 4 min 21 s |
| The LLM (14B) labelling the training pool, 998 messages | about 70 min (4.2 s each) |
| Training the small model on 998 messages, in the cluster | about 2 min |
| The small model labelling 1,000 messages, in the cluster | about 1 s |
| The learning curve: four trainings, on 25% to 100% of the pool | about 4 min |

Sending four requests at once was no faster than one at a time: the
Mac's GPU is already fully used by one.

## The LLM's labels

The labels the small model learns from and is scored against, by kind:

| Kind | Training pool | Eval set |
|---|---|---|
| WORK | 446 | 134 |
| PERSONAL | 196 | 56 |
| ADMIN | 152 | 41 |
| BULK | 121 | 49 |
| AUTOMATED | 83 | 20 |
| All | 998 | 300 |

## Other models

Tried outside the template, in Python on the Mac, on the same splits:

- **Zero-shot**: `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7`
  given each kind's description, with no training.
- **Embeddings and logistic regression**: sentence embeddings from
  `sentence-transformers/paraphrase-multilingual-mpnet-base-v2` and a
  logistic regression on top.
- **SetFit**: the same sentence model fine-tuned on pairs of labelled
  messages, then a logistic regression on top.

Each trained model was trained twice: on the LLM's labels for the
training pool, and on the person's labels for the pilot. Trained on the
person's labels, it is scored on the pilot by five-fold cross-validation:
each fifth is predicted by a model trained on the other 80.

| | Agreement with the person | Costly, against the person | Agreement with the LLM | Costly, against the LLM |
|---|---|---|---|---|
| The LLM (14B) | 79/100 | 5/86 | | |
| Zero-shot | 28/100 | 9/86 | 86/300 | 17/231 |
| Embeddings, the LLM's labels | 70/100 | 6/86 | 225/300 | 11/231 |
| SetFit, the LLM's labels | 68/100 | 11/86 | 258/300 | 7/231 |
| Embeddings, the person's labels | 69/100 | 0/86 | | |
| SetFit, the person's labels | 73/100 (64% to 81%) | 0/86 | 209/300 | 5/231 |

"Costly" is mail to keep given a kind that can go. Against the person,
SetFit trained on the LLM's labels agrees on 40 of 49 in the archive's
main language and 25 of 45 in English; trained on the person's labels,
on 40 and 30.

- **Zero-shot** is far behind and is ruled out.
- **SetFit copies the LLM best** (86% on the eval set, 87.6% and 2.0%
  costly weighted by period) but comes no closer to the person than the
  plain embeddings. A model that learns from the LLM can't do much better
  than the LLM's 79.
- **Trained on the person's 100**, SetFit agrees most often, but the
  intervals overlap. Its 0 costly mistakes mean little: it almost never
  gives a kind that can go (7 answers of 100), and of the person's 14
  `AUTOMATED` and `BULK` messages it found 2. The pilot has 7 of each,
  too few to learn them from.

Machine time:

| Model | Training | Labelling 1,000 messages |
|---|---|---|
| Zero-shot | none | about 12.5 min |
| Embeddings, on 998 | 19 s | 17 s |
| SetFit, on 998 (600 steps) | 33 min | 25 s |
| SetFit, on 80 (100 steps) | about 5.5 min | 25 s |

## The small model

spaCy's text classifier, trained by the built-in `train` action from a
blank pipeline on the LLM's labels for the training pool, with the LLM's
labels for the eval set as its evaluation data. `model_to_dataset` then
saved its answers on the pilot and the eval set. It was trained twice:
from a blank `en` pipeline and from a blank `xx` one, which has no rules
for any one language.

| | The LLM | spaCy, `en` | spaCy, `xx` |
|---|---|---|---|
| Agreement with the person | 79/100 | 78/100 | 79/100 (70% to 86%) |
| Weighted by period | 83.0% | 80.0% | 82.8% |
| Costly, against the person | 5/86 | 5/86 | 4/86 (2% to 11%) |
| The archive's main language | 46/49 | 40/49 | 41/49 |
| English | 29/45 | 34/45 | 34/45 |
| Agreement with the LLM, eval set | | 245/300 | 244/300 (77% to 85%) |
| Costly against the LLM, eval set | | 12/231 | 7/231 (1% to 6%) |

- **The small model is as good as the LLM** against the person, and
  labels 1,000 messages in about a second instead of about 70 minutes.
  The two pipelines are level; `xx` is a little ahead on each measure,
  none of it clear on 100 messages.
- **It is not a copy of the LLM.** On the pilot, `xx` gives the LLM's
  label on 78 of 100. It is right on 9 messages where the LLM is wrong,
  and wrong on 9 where the LLM is right; 2 of its 4 costly mistakes are
  the LLM's too.
- **It does better than the sentence-embedding models** in "Other
  models", which agree with the person on 68 to 70 of 100.
- **By language** the gap is smaller than the LLM's: worse in the
  archive's main language, better in English.
- **The learning curve still rises.** Against the LLM on the eval set,
  the score (macro F) is 0.60, 0.71, 0.73 and 0.77 with 25%, 50%, 75%
  and all of the pool. More of the LLM's labels would bring the model
  closer to the LLM; whether also closer to the person is not known.

The eval set chose which checkpoint of training to keep, so the scores
against the LLM there flatter the model a little. The pilot played no
part in training.

**Against the bar the model fails, as the LLM does:** `xx` makes 4.7%
costly mistakes against a limit of 2%, and agrees 82.8% weighted by
period against 85%.

### Gmail's categories

Scored through the default scheme's mapping, on the messages that have a
category: 73 of the pilot and 216 of the eval set. A category counts as
consistent when the reference's kind is one it maps to. Primary maps to
three kinds and Updates to two, so this is far easier than agreement and
can't be compared with it.

| | Pilot, against the person | Eval set, against the LLM |
|---|---|---|
| Consistent | 64/73 | 180/216 |
| Mail to keep in a category that maps only to kinds that can go | 2/63 | 3/167 |

The 27 of 100 pilot messages with no category get no answer at all.

## Costs

| | The LLM (14B) | The small model |
|---|---|---|
| Labelling 1,000 messages | about 70 min | about 1 s |
| Training | none | about 2 min |
| Labels it needs | none | the LLM's on the pool: about 70 min |

The person's time is the pilot: in its third round, 8.5 minutes to label
100 and 5.2 minutes to review 25 disagreements.
