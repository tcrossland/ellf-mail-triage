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
- The package is `mail_recipes`, version 0.1.0.

## `llm_to_dataset`

Saves an LLM's answers on an input asset of texts to a dataset, credited to
their own session (`LLM` by default), the way the built-in text classification
task saves a person's. So the built-in review shows the LLM's answer and a
person's on the same text as versions of one example, and the annotation
dashboard compares them like two annotators.

`classify` is called once per text: it sends the instructions, the label
definitions and the text to an OpenAI-compatible chat endpoint and reads label
names from the reply, or returns `None` for no usable answer. Texts with no
usable answer are left out and counted in the log. A failed request stops the
action. The action can also read labels already in each record's `meta`
(`--llm-label-key`), and draw a sample by the LLM's label (`--sample-size`,
`--min-per-label`, `--blind`); see the original README.

```bash
ellf actions create llm_to_dataset --name mail-pilot-llm --input "Mail (pilot)" --label-scheme "Mail kinds" --labels-exclusive --output mail_pilot_llm --instructions "..." --no-start
```

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
