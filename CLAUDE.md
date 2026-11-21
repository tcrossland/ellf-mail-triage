# CLAUDE.md

ellf-mail-triage: an Ellf template that sorts archived mail into categories
the user defines in a label scheme (by default `WORK`, `PERSONAL`, `ADMIN`,
`AUTOMATED`, `BULK`) with a small spaCy text classifier, and measures it
against LLMs and a person. Read [docs/design.md](docs/design.md) first; what
to build next is in [docs/backlog.md](docs/backlog.md), in order.

## Layout

The repo root is the template, in the layout `/ellf-template` exports and
explosion/ellf-templates uses: `README.md`, `plans/`, `scripts/`, `assets/`,
`config/`, `recipes/`. Keep those names. The rest is ours and is left out
when the template is copied elsewhere: `CLAUDE.md`, `CHANGELOG.md`,
`docs/`, `tests/`, `pyproject.toml`, `uv.lock`, `.python-version`.

`docs/local/` holds personal notes. It is ignored by git; keep it that way.

## Commands

```bash
uv sync                                    # after any pyproject.toml change
uv run pytest                              # all tests; no network
uv run ruff format && uv run ruff check    # format, then lint; both must pass
```

## Rules

- Mail is personal data. Never write a real message, address, name, contact
  or anything from the user's setup into a committed file: code, tests,
  docs, commit messages. Use placeholders (`example.com`, `example.org`,
  invented names). Real exports live outside the repo; scratch output goes
  to the scratchpad. Figures from real mail are counts only.
- `assets/input/` holds synthetic mail only, with fictional senders.
- No mail goes to an LLM service (Gemini through `gemini_agent`, Hugging
  Face Inference Providers through `hf_llm_agent`, or any other) until
  that service's data-use question in [docs/facts.md](docs/facts.md) is
  settled.
- `scripts/` is standard library only: it runs on the host, outside Ellf.
- Before relying on a behaviour of Ellf, a recipe or an LLM service, check
  [docs/facts.md](docs/facts.md). A new fact goes there with its source and
  the date; anything not checked is marked **unverified**.
- Before adding a dependency, read its licence from its own metadata and
  record it in `pyproject.toml` next to it.

## Working agreement

- Commit on a branch; the user reviews it, then `main` is fast-forwarded.
  Stage explicit paths, never `git add -A`. Never push unless asked.
- Update the backlog in the same commit as the work it tracks. A done item
  moves to the Done section at the end.
- Commits: Conventional Commits, `type(scope): summary`, then a wrapped
  body saying what changed and why; end with the Co-Authored-By trailer.
- Writing: British English, no em-dashes, plain words.
