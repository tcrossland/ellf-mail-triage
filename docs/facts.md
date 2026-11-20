# Facts

Every behaviour of Ellf, its recipes or an LLM service that this template
relies on, with its source. All were checked on 2026-11-20 unless marked.
Anything not checked is **unverified**.

## Templates and Explosion

- explosion/ellf-templates is MIT-licensed.
  Source: its `LICENSE` file.
- A template is one directory with a `README.md` that documents every
  resource, plus `plans/`, `recipes/`, `config/` and `assets/` as needed,
  in the layout `/ellf-template` exports. Some also have `scripts/`.
  Source: ellf-templates `AGENTS.md` and its tree.
- A template's entry in `templates.json` has `name`, `title`,
  `description`, `tags`, `counts`, `url`, `author`, `gpu`, `sample_data`
  and `api_keys`, with tags from a fixed list.
  Source: ellf-templates `AGENTS.md`.
- Contributed templates go to Explosion by email with a link to the repo.
  Source: ellf.ai/docs/templates.

## Ellf plans and the service

- The Solo plan is free for one person with no time limit: one account, a
  single-user annotation platform and a local cluster.
  Source: ellf.ai/pricing.
- The Solo plan runs a cluster only on your own machine or one on your
  home network. A cloud cluster needs a team plan (Starter or
  Professional), set up with `ellf infra init`, `provision` (Terraform,
  applied in your own cloud account) and `start`.
  Source: ellf.ai/docs/cluster#install-cloud, through `ellf kb read`.
- Ellf's servers keep records: names, IDs, paths, the arguments of tasks
  and actions, and account details. The cluster keeps the data, the
  Prodigy database, model files, recipe code and the annotation app; data
  shown in the web app or CLI comes straight from the cluster.
  Source: ellf.ai/docs#architecture, through `ellf kb read`.
- A cloud cluster's default worker classes are `base`, `small`, `medium`
  and `gpu` (an NVIDIA T4 in the docs' Google Cloud example).
  Source: ellf.ai/docs/cluster#workers.
- `ellf-cli` is proprietary ("All rights reserved"), installed with pip,
  Python 3.10 or later. Keep it out of this repo's dependencies.
  Source: its PyPI metadata; ellf.ai/docs/install.

## The cluster on a Mac

- A Solo cluster runs on Linux with K3s, at least 4 GB RAM and 20 GB
  disk. On a Mac that means a Linux VM; Lima's `k3s` template works.
  Source: ellf.ai/docs/cluster#install-local; tried with ellf-cli 24.0.0.
- `ellf init` and `ellf login --agent claude` install the Ellf skills in
  the enclosing git repository, found by any `.git` entry above the
  current folder, and `login --agent` also allows `Bash(ellf kb:*)` in the
  global Claude Code settings. Run them in a folder that is its own git
  repository.
  Source: tried with ellf-cli 24.0.0.
- Ellf's Helm chart installs its own Traefik; K3s's bundled Traefik then
  fails to install, which does no harm.
  Source: tried with chart ellf-0.1.169.
- A cluster's address can't carry a port: the chart uses it as the
  Ingress host. `http://` works only for `localhost` on port 80; any other
  address needs `https://` and the certificate Ellf issues
  (`ellf infra tls --trust`), whose CA covers only the cluster's address
  and localhost.
  Source: chart ellf-0.1.169 manifest; ellf.ai/docs/cluster#install-local-deploy.
- On macOS, a process without root can bind a port below 1024 only on
  every interface, so Lima forwards a VM's port 80 to the whole network. A
  Lima `vzNAT` address with https keeps the cluster on the Mac.
  Source: tried on macOS with Lima 2.3.0.
- Firefox needs the cluster's CA imported into its own certificate store;
  Chrome and the macOS keychain share trust.
  Source: tried.
- After `ellf clusters update --address`, the CLI keeps the old address
  until `ellf login --cluster <name>`, and logging in again can clear the
  default project (`ellf config project`).
  Source: tried with ellf-cli 24.0.0.

## The CLI and assets

- `ellf publish data` without a destination stores the file as
  `<name>-<version>`, without its extension, and a recipe then can't
  choose a loader. Pass a destination path that keeps the extension, and
  `--loader jsonl` for JSONL.
  Source: tried with ellf-cli 24.0.0.
- `ellf publish data` with `--kind labels` and `--kind instructions`
  publishes a label scheme and guidelines. Assets belong to the cluster:
  the command takes a project only for `--render`.
  Source: tried with ellf-cli 24.0.0.
- Publishing under an existing name with a new `--version` adds a version
  to that asset; `ellf assets info` shows the latest.
  Source: tried with ellf-cli 24.0.0.
- When several versions of an asset share a name, a task or action given
  the name doesn't say which it uses. Given a version's asset ID it uses
  that version: `--label-scheme` with the 0.2.0 ID gave the task that
  version's six labels. `ellf tasks info` shows the name, not the version.
  Source: tried with ellf-cli 24.0.0.
- A task's `--input` takes an asset's ID as well as its name, which picks
  one asset when two share a name.
  Source: tried with ellf-cli 24.0.0.
- A label scheme is an asset of kind `labels`: a JSON object from each
  label, in order, to its `description`, `do_not_mark` (what not to give
  it) and `examples` (`text`, with `label` when the label applies).
  Guidelines are a markdown asset of kind `instructions`.
  Source: ellf.ai/docs/assets-files#labels.

## Recipes, tasks and actions

- The `textcat` task takes `--label-scheme` and `--settings.instructions`,
  with `--labels-exclusive` for one label per message. Annotators see a
  label's description on hover.
  Source: `ellf tasks create textcat --help` with ellf-recipes on the
  cluster; helpdesk-routing's README.
- Prodigy shows each example's meta on the card unless the config sets
  `"hide_meta": true` (a `StrictBool`, default false). With mail the meta
  can include Gmail's category, so a blind labelling task needs it set.
  Whether the cluster honours it is **unverified** until seen on a card.
  Source: `prodigy/types.py` in prodigy 2.0.0a18; the pilot cards.
- Existing answers load into a new dataset with the `db_actions` recipe
  (`--copy.in-asset`), from a JSONL asset with `text`, `label`, `answer`
  and `_view_id`.
  Source: tried with ellf-recipes.
- `gemini_agent` and `hf_llm_agent` use the label definitions and
  instructions of the task they are assigned to, and can add their own on
  top.
  Source: ellf.ai/docs/assets-files#labels; `ellf agents create --help`.
- `review` takes a typed `--label` list, or else the labels found in the
  answers.
  Source: `ellf tasks create review --help`.
- `train` takes its labels from the answers (`--textcat.train` for
  exclusive labels) and can draw a learning curve (`--train-curve`, with
  `--train-curve.n-samples` points; the default 1 draws none worth
  having). With `--textcat.eval` it evaluates on those datasets instead
  of holding back `--eval-split` of the training data.
  Source: `ellf actions create train --help`.
- `train` registers a Model asset (`--output.name`, at
  `{__nfs__}/models/<name>/<version>`) and a Results asset, and uploads
  `model-best`: the checkpoint that scored best on the evaluation data.
  So the evaluation data choose the model, and scores on them flatter it
  a little. `--output.skip` registers neither. On 998 messages from a
  blank pipeline it trained in about 2 minutes on the Lima VM's 4 CPUs.
  Source: `ellf_recipes/recipes/train.py` in ellf-recipes on the cluster;
  tried 2026-11-20.
- A recipe takes a trained model as a parameter typed `Model` from
  `ellf_recipes_sdk`, and `.load()` returns the spaCy pipeline, from a
  directory or a packaged wheel. The CLI takes the model asset's ID.
  Source: `ellf_recipes_sdk/sdk/assets.py`; `model_to_dataset` in
  `mail_recipes` 0.4.0, tried 2026-11-20.
- `ellf actions create` starts the action unless given `--no-start`.
  Running `ellf actions start` after it starts a second execution of the
  same action.
  Source: tried with ellf-cli 24.0.0.
- `ellf actions stop` leaves the action in state `not_found`; its name has
  to be deleted before it is reused. An action that saves only at the end
  saves nothing when stopped.
  Source: tried with ellf-cli 24.0.0.
- `ellf actions logs` shows what the action's pod prints while it runs,
  so `llm_to_dataset` from `mail_recipes` 0.2.0 shows its progress after
  each saved batch. `ellf actions info` shows only the state.
  Source: tried with ellf-cli 24.0.0.
- llm-classifier-eval's `llm_to_dataset` action (MIT, in its `recipes/`)
  saves an LLM's answer on every text of an input asset to a dataset,
  credited to its own annotator session, so review and the dashboard
  compare it with a person's. It calls any OpenAI-compatible endpoint
  (`--base-url`, `--model`, optional `--api-key`), or reads a label
  already in each record's meta (`--llm-label-key`). It sends the label
  scheme's definitions and `--instructions`, not the task's guidelines.
  It sends no `reasoning_effort` and waits 60 s for a reply; this
  template's copy sends `"none"` by default and waits 120 s.
  Source: its README and `llm_to_dataset.py` in explosion/ellf-templates.
- `hf_llm_agent` does not run a model on the cluster: it calls a chat
  model on Hugging Face Inference Providers (by default
  `meta-llama/Llama-3.3-70B-Instruct`), billed to your Hugging Face token,
  so the mail goes to Hugging Face and the provider it routes to. No
  built-in agent runs an LLM on the cluster; `hf_model_agent` (in
  `ellf-recipes-gpu`) runs a fine-tuned transformers text classifier.
  Source: `ellf agents create hf_llm_agent --help` and
  `hf_model_agent --help`; `ellf recipes list`.

## Building and testing recipes

- `ellf publish code DIR` builds the package with whatever `python` is on
  PATH and then imports it, so it needs a Python with setuptools, Prodigy
  and `ellf-recipes-sdk` (`pip install prodigy ellf-recipes-sdk
  ellf-recipes`). Without them it stops with no module named setuptools,
  or no module named ellf_recipes_sdk.
  Source: ellf.ai/docs/recipe-development#setup; tried with ellf-cli 24.0.0.
- Prodigy comes from Ellf's private package index. `ellf login`, run with
  the virtualenv active, writes `$VIRTUAL_ENV/pip.conf` pointing pip at
  it through a keyring backend (no secret on disk), but only if the
  venv's pip is 26.2.2 or later. With an older pip, or none (a uv venv),
  it skips this with a warning. `python -m ensurepip` installs a pip too
  old for it (25.0.1 with Python 3.12).
  Source: tried with ellf-cli 24.0.0.
- On the index, `ellf-recipes-sdk` 1.3.211 calls
  `Database.count_legacy_examples`, which the latest stable Prodigy
  (1.18.29) lacks, so recipe tests that save examples fail with an
  `AttributeError`. They pass with the pre-release `prodigy==2.0.0a18`
  (`pip install --pre`).
  Source: tried with the github-docs-issues venv, Python 3.12.
- A recipe test that saves examples without the tests' `database`
  fixture writes to Prodigy's default database, `~/.prodigy/prodigy.db`,
  and a rerun then finds its own earlier answers there.
  Source: tried 2026-11-20 with `mail_recipes`' tests.

## LLMs and Ollama

- Ollama is MIT-licensed and serves an OpenAI-compatible API on
  `127.0.0.1:11434`. On a Mac the Lima VM reaches it at
  `host.lima.internal`, which is `192.168.5.2`; a pod in the cluster
  reaches `192.168.5.2` but can't resolve the name. So a local model needs
  no port open to the network.
  Source: Ollama's `LICENSE`; tried with Ollama 0.40.16 and Lima 2.3.0.
- Ollama 0.40.16 calls ollama.com when the server starts:
  `GET /api/tags` and `/api/experimental/model-recommendations`, both
  with only a timestamp in the query. Both timed out here, and local
  requests were served as usual. Nothing in the log shows prompts going
  out, but what else these calls send isn't read.
  Source: the server's own log (`model show cloud cache hydration`,
  `model recommendations`).
- Qwen3-8B and Qwen3-14B are Apache-2.0. Ollama's library page for qwen3
  states no licence. Gemma 3 is under Google's own Gemma terms, which are
  not read.
  Source: huggingface.co/Qwen/Qwen3-8B and /Qwen3-14B and their `LICENSE`
  files; ollama.com/library/qwen3; huggingface.co/google/gemma-3-12b-it.
- Qwen3 through Ollama's OpenAI-compatible endpoint thinks first by
  default: the reasoning comes back in a separate `reasoning` field and
  the answer alone in `content`, but a reply takes 15 to 70 s on an M2
  with 24 GB, for 8B and 14B. `/no_think` in the prompt does not turn it
  off; `"reasoning_effort": "none"` in the request does, and a reply then
  takes about 0.5 s (8B) or 1 s (14B) on short messages, after a first
  call of 5 to 9 s that loads the model.
  Source: tried with Ollama 0.40.16, qwen3:8b and qwen3:14b, with
  `llm_to_dataset`'s prompt.
- With thinking off and the prompt asking for one label, Qwen3 8B often
  names two (`WORK,ADMIN`), which an exclusive scheme rejects; 14B names
  one. On scheme 0.4.0's 15 synthetic examples 8B named two 4 times; told
  to reply with one word it named one each time.
  Source: tried with Ollama 0.40.16 and `llm_to_dataset`'s prompt.
- On an M2 MacBook Air, Qwen3 14B through Ollama keeps the GPU fully busy
  with one request at a time, so `OLLAMA_NUM_PARALLEL=4` with four
  requests at once was no faster (4.5 to 4.7 s a message, against 4.1 to
  4.4 s). Each request is about 800 tokens of prompt and two of answer,
  and the fixed start of the prompt is served from Ollama's cache.
  Source: tried with Ollama 0.40.16; the server's log and `ioreg`.

## LLM services' terms

- Hugging Face does not store the request or response it routes through
  Inference Providers, and keeps debugging logs without user data for up
  to 30 days; it does not train on them. Each provider's own data policy
  applies, and HF does not say what those are; for language models
  OpenRouter picks the provider. There is no zero-retention option; you
  can turn providers off in your account settings, and a pinned provider
  is never swapped. The providers' own policies are **unverified**.
  Source: huggingface.co/docs/inference-providers/security, /routing and
  /providers.
- Gemini API, terms effective 2026-03-23. Free tier (Unpaid Services):
  Google uses prompts and responses to improve its products, human
  reviewers may read them, and the terms say not to submit personal
  information. Paid (a Cloud project with active billing): not used to
  improve products, but logged for a limited period to detect abuse;
  optional request logs are kept up to 55 days by default. In the EEA,
  Switzerland or the UK the paid data-use terms apply to every tier. No
  zero-retention option is described.
  Source: aistudio.google.com/docs/terms and /docs/logs-policy.

## Gmail data

- Gmail's categories are lopsided in a real archive. Of a Gmail account's
  categorised mail, Personal (Primary) holds 72%, Updates 27%, Forums
  0.4%, Promotions 0.3% and Social 3 messages. Of a Google Workspace
  account's: Updates 50%, Forums 22%, Personal 21%, Promotions 7% and
  Social 1 message. Whether bulk mail sits in Personal or Updates is not
  checked.
  Source: count-only queries on two real backups.
- Gmail's categories do not stop at 2013, when its tabs launched. In a
  real Gmail backup, received mail carries a category from October 2010
  (a few from July to September 2010) and none before; from then on, mail
  without one is almost all sent mail or drafts. A second account shows
  the same. So the slice without categories is mail from before late
  2010.
  Source: count-only queries per year and month on two real backups.
- A Got Your Back backup (db_version 6) keeps each message's labels in
  the `labels` table of `msg-db.sqlite`, system labels by Gmail ID, so a
  category is `CATEGORY_PROMOTIONS` and so on. Messages are
  `<year>/<month>/<day>/<gmail_id>.eml`, and chats aren't backed up.
  Source: mailcellar's `backup/gyb.py`, from gyb 1.97's code.
- In two real Gmail backups all five `CATEGORY_` labels occur, 77% and
  89% of messages carry one, and almost always exactly one (one message in
  about 7,500 had two; the importer then takes the first of personal,
  social, promotions, updates, forums). Sent mail carries `SENT`, drafts
  `DRAFT` and deleted mail `TRASH`: in one backup 12% of messages are sent
  mail, three quarters of it without a category, and 32% are in the
  trash. Backups of non-Gmail accounts have no categories.
  Source: count-only queries on four real backups.
- **Unverified:** a Google Takeout mbox gives each message's Gmail
  category in its `X-Gmail-Labels` header: comma-separated labels, a
  category named like `Category Promotions`, chats labelled `Chat`, sent
  mail `Sent` and drafts `Drafts`. The importer accepts this and the
  `CATEGORY_PROMOTIONS` form.
  Source: third-party guides to Takeout mbox files; no real export
  checked.

## Not yet checked

- How a trained model leaves the cluster. The docs list `ellf files cp`
  and `ellf export`; `hf_model_push` is not read.
  Source: ellf.ai/docs/assets-files, ellf.ai/docs/cli.
- Whether spaCy runs on Python 3.14 (matters for use in mailcellar, which
  requires it).
- Ellf's terms forbid using it "to develop competing products"; read
  them in full before the mailcellar step.
