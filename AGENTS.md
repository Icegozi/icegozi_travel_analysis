# Contributor guidance

## Project scope

This is a Python research pipeline for analysing observable online interest in
Vietnamese tourism destinations. The maintained execution path is:

`run_all.sh` → crawlers → `analysis_pipeline.py` → `dashboard.py`.

## Source layout

- Keep source-specific parsing inside `VNTRIP/`, `VIETNAM_TRAVEL/`, or
  `PROVINCIAL_PORTALS/`.
- Put shared configuration, HTTP behaviour, manifests, and CSV helpers in `common/`.
- Treat `dashboard_assets/` as the dashboard template; `docs/` is generated output.
- Treat `data/` as runtime data, not hand-maintained source code.

## Change rules

- Respect `robots.txt`; do not add login, CAPTCHA bypass, or personal-data collection.
- Preserve `source_url` deduplication and crawl manifests when changing a crawler.
- Keep `.env` local and update `.env.example`, README, and the GitHub workflow together
  when changing configuration defaults.
- Use Python 3 data tooling (`pandas`, `requests`, BeautifulSoup) and four-space
  indentation with descriptive `snake_case` identifiers.
- Do not change generated CSV or `docs/` by hand; rerun the relevant script.

## Validation

Run offline regression tests after parser, normalisation, or configuration changes:

```bash
.venv/bin/python -m unittest tests/test_refactor.py
```

Run `sh run_all.sh` when validating the full pipeline with permitted network access.
