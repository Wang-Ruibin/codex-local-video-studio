# Repository instructions

- Keep the plugin installable from the repo marketplace at `.agents/plugins/marketplace.json`.
- Keep Windows and Linux behavior aligned; platform-specific code belongs behind shared interfaces.
- Treat `README.md` as the English source and update `README.zh-CN.md` in the same change.
- Keep ordinary explanatory documentation paired by language. Do not translate `LICENSE` or this file.
- Never commit rendered media, voice models, credentials, virtual environments, caches, or temporary video jobs.
- Run `python scripts/validate_repository.py` and `python -m unittest discover -s tests -v` before committing.
- Preserve safe cleanup invariants: marker validation, quality hash binding, media QC binding, atomic delivery, and output-root containment.
