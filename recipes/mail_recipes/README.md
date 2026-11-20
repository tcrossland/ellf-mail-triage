# mail_recipes

The custom action of the ellf-mail-triage template: `llm_to_dataset`, copied
from the [llm-classifier-eval](https://github.com/explosion/ellf-templates)
template's `llm_recipes` (MIT, Copyright (c) 2026 ExplosionAI GmbH; see
[LICENSE](LICENSE)), with these changes:

- **`--reasoning-effort`** (default `none`) is sent as `reasoning_effort`, which
  turns off a model's thinking. Qwen3 through Ollama thinks by default and then
  takes 15 to 70 seconds a reply; with thinking off it takes about a second.
  Unset it for an endpoint that doesn't take the field.
- **The defaults point at a local model:** `qwen3:14b` on Ollama at
  `http://192.168.5.2:11434/v1`, the address a pod on a Lima cluster reaches the
  Mac's localhost by. So no mail goes to a cloud service unless you point the
  action at one.
- **Long runs are safe to stop.** Without a sample or a blind asset, answers
  are saved every `--batch-size` texts (default 50), and a rerun skips texts
  that already have the annotator's answer in the output dataset, so it
  carries on where a stopped or failed run left off. The original saves only
  at the end.
- **Failed requests are retried**, three times with a backoff of 2, 4 and 8
  seconds, for timeouts, lost connections and 5xx replies; a 4xx reply still
  stops the action at once. The timeout is 120 seconds, not 60, to leave room
  for a cold model load.
- **Replies are read leniently:** label names match whatever their case, and
  quotes, asterisks and a trailing full stop are ignored.
- **`--workers`** (default 1) sends that many requests at once. It helps only
  if the endpoint serves several at once (for Ollama, `OLLAMA_NUM_PARALLEL`)
  and isn't already busy with one; on an M2 Mac's GPU four at once were no
  faster.

## `llm_to_dataset`

Saves an LLM's answers on an input asset of texts to a dataset, credited to
their own session (`LLM` by default), the way the built-in text classification
task saves a person's. So the built-in review shows the LLM's answer and a
person's on the same text as versions of one example, and the annotation
dashboard compares them like two annotators.

`classify` is called once per text: it sends the instructions, the label
definitions and the text to an OpenAI-compatible chat endpoint and reads label
names from the reply, or returns `None` for no usable answer. Texts with no
usable answer are left out and counted in the log. A request that still fails
after its retries stops the action, keeping the answers saved so far.
`ellf actions logs` shows a line after each saved batch. The action can also
read labels already in each record's `meta` (`--llm-label-key`), and draw a
sample by the LLM's label (`--sample-size`, `--min-per-label`, `--blind`);
see the original README.

```bash
ellf actions create llm_to_dataset --name mail-pilot-llm \
  --input <pilot asset ID> --label-scheme <scheme asset ID> --labels-exclusive \
  --output mail_pilot_llm --instructions "$(cat config/llm_instructions.txt)"
```

Pass asset IDs (from `ellf assets list`) rather than names: once several
versions of an asset share a name, a name doesn't say which version is used.
`ellf actions create` starts the action unless given `--no-start`; don't run
`ellf actions start` after it, which starts a second copy.

## Publishing

```bash
ellf publish code recipes/mail_recipes
```

The version comes from `mail_recipes/about.py`: bump it there for each change.

## Tests

The tests need Prodigy and `ellf-recipes-sdk` installed, plus the dev
requirements, so they don't run in this repository's own environment:

```bash
pip install -e . -r requirements-dev.in
pytest tests
```
