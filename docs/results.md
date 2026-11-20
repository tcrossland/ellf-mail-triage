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
against a limit of 2%, and 83% agreement against 85%. Since the small
model learns from it, the small model will most likely fail too.

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
| Training and the small model's time per 1,000 | to be measured |

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

## The small model

To come: trained on the LLM's labels for the training pool, scored
against the LLM on the eval set and against the person on the pilot.
