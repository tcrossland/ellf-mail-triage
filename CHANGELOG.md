# Changelog

## [Unreleased]

### Added

- Importer `scripts/mail_to_jsonl.py`: mbox, `.eml` folders and Got Your
  Back backups to JSONL.
- Sampler `scripts/make_splits.py`: pilot, eval set and training pool,
  spread by period.
- Default label scheme `assets/mail_kinds.json` (`WORK`, `PERSONAL`,
  `ADMIN`, `AUTOMATED`, `BULK`) and guidelines for the person.
- `mail_recipes`: `llm_to_dataset` (saves in batches, retries,
  `--label-details`) and `model_to_dataset` (a trained model's answers as
  an annotator's, with `meta.score`).
- `scripts/score.py`: agreement and costly mistakes against a reference,
  with intervals and the bar.
