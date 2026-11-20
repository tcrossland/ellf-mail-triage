# Facts

Every behaviour of Ellf, its recipes or an LLM service that this template
relies on, with its source and the date it was checked. Anything not checked
is **unverified**.

| Fact | Source | Checked |
| --- | --- | --- |
| explosion/ellf-templates is MIT-licensed. | Its `LICENSE` file | 2026-11-20 |
| A template is one directory with a `README.md` that documents every resource, plus `plans/`, `recipes/`, `config/` and `assets/` as needed, in the layout `/ellf-template` exports. Some also have `scripts/`. | ellf-templates `AGENTS.md` and its tree | 2026-11-20 |
| A template's entry in `templates.json` has `name`, `title`, `description`, `tags`, `counts`, `url`, `author`, `gpu`, `sample_data`, `api_keys`, with tags from a fixed list. | ellf-templates `AGENTS.md` | 2026-11-20 |
| Contributed templates go to Explosion by email with a link to the repo. | ellf.ai/docs/templates | 2026-11-20 |
| The Solo plan is free for one person with no time limit: one account, a single-user annotation platform and a local cluster. | ellf.ai/pricing | 2026-11-20 |
| `ellf-cli` is proprietary ("All rights reserved"), installed with pip, Python 3.10 or later. Keep it out of this repo's dependencies. | Its PyPI metadata; ellf.ai/docs/install | 2026-11-20 |
| A Solo cluster runs on Linux with K3s, at least 4 GB RAM and 20 GB disk. On a Mac that means a Linux VM; Lima's `k3s` template works. | ellf.ai/docs/cluster#install-local; tried with ellf-cli 24.0.0 | 2026-11-20 |
| `ellf init` and `ellf login --agent claude` install the Ellf skills in the enclosing git repository, found by any `.git` entry above the current folder, and `login --agent` also allows `Bash(ellf kb:*)` in the global Claude Code settings. Run them in a folder that is its own git repository. | Tried with ellf-cli 24.0.0 | 2026-11-20 |
| Ellf's Helm chart installs its own Traefik; K3s's bundled Traefik then fails to install, which does no harm. | Tried with chart ellf-0.1.169 | 2026-11-20 |
| A cluster's address can't carry a port: the chart uses it as the Ingress host. `http://` works only for `localhost` on port 80; any other address needs `https://` and the certificate Ellf issues (`ellf infra tls --trust`), whose CA is limited to the cluster's address and localhost. | Chart ellf-0.1.169 manifest; ellf.ai/docs/cluster#install-local-deploy | 2026-11-20 |
| On macOS, a process without root can bind a port below 1024 only on every interface, so Lima forwards a VM's port 80 to the whole network. A Lima `vzNAT` address with https keeps the cluster on the Mac. | Tried on macOS with Lima 2.3.0 | 2026-11-20 |
| Firefox needs the cluster's CA imported into its own certificate store; Chrome and the macOS keychain share trust. | Tried | 2026-11-20 |
| After `ellf clusters update --address`, the CLI keeps the old address until `ellf login --cluster <name>`, and logging in again can clear the default project (`ellf config project`). | Tried with ellf-cli 24.0.0 | 2026-11-20 |
| `ellf publish data` without a destination stores the file as `<name>-<version>`, without its extension, and a recipe then can't choose a loader. Pass a destination path that keeps the extension, and `--loader jsonl` for JSONL. | Tried with ellf-cli 24.0.0 | 2026-11-20 |
| Existing answers load into a new dataset with the `db_actions` recipe (`--copy.in-asset`), from a JSONL asset with `text`, `label`, `answer` and `_view_id`. | Tried with ellf-recipes on 2026-11-20 | 2026-11-20 |
| `hf_llm_agent`'s supported models and the hardware they need. | | **unverified** |
| How a trained model leaves the cluster. The docs list `ellf files cp` and `ellf export`; `hf_model_push` is not read. | ellf.ai/docs/assets-files, ellf.ai/docs/cli | **unverified** |
| Whether a task can start on a dataset that already holds answers, for Gmail's categories as an annotator. `db_actions` can load them into a dataset (above); llm-classifier-eval may do the rest with an action. | | **unverified** |
| Gmail has no categories on mail that arrived before its tabs launched in 2013; it did not go back and categorise older mail. The pre-2013 comparison rests on this. | | **unverified** |
| A Google Takeout mbox gives each message's Gmail category, in its `X-Gmail-Labels` header. | | **unverified** |
| A Got Your Back backup records each message's Gmail category in `msg-db.sqlite`. | | **unverified** |
| Whether Google may use what is sent to the Gemini API, and whether that differs between the free and paid tiers. | | **unverified** |
| spaCy runs on Python 3.14 (matters for use in mailcellar, which requires it). | | **unverified** |
| Ellf's terms forbid using it "to develop competing products"; read in full before the mailcellar step. | | **unverified** |
