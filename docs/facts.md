# Facts

Every behaviour of Ellf, its recipes or an LLM service that this template
relies on, with its source and the date it was checked. Anything not checked
is **unverified**.

| Fact | Source | Checked |
| --- | --- | --- |
| explosion/ellf-templates is MIT-licensed. | Its `LICENSE` file | 2026-11-20 |
| A template is one directory with a `README.md` that documents every resource, plus `plans/`, `recipes/`, `config/` and `assets/` as needed, in the layout `/ellf-template` exports. Some also have `scripts/`. | ellf-templates `AGENTS.md` and its tree | 2026-11-20 |
| A template's entry in `templates.json` has `name`, `title`, `description`, `tags`, `counts`, `url`, `author`, `gpu`, `sample_data`, `api_keys`, with tags from a fixed list. | ellf-templates `AGENTS.md` | 2026-11-20 |
| Contributed templates go to Explosion by email with a link to the repo. | Ellf docs | **unverified** |
| `hf_llm_agent`'s supported models and the hardware they need. | | **unverified** |
| How a trained model leaves the cluster (`ellf files`, `hf_model_push`, private by default). | | **unverified** |
| Whether a task can start on a dataset that already holds answers, for Gmail's categories as an annotator. llm-classifier-eval may do it with an action. | | **unverified** |
| Whether Google may use what is sent to the Gemini API, and whether that differs between the free and paid tiers. | | **unverified** |
| spaCy runs on Python 3.14 (matters for use in mailcellar, which requires it). | | **unverified** |
| Ellf's terms forbid using it "to develop competing products"; read in full before the mailcellar step. | | **unverified** |
