# Runtime data

This directory is populated by the crawlers and analysis pipeline. It is intentionally
empty in a fresh source distribution.

## Generated inputs

- `VNTRIP/rawdata.csv`
- `VIETNAM_TRAVEL/rawdata.csv`
- `PROVINCIAL_PORTALS/rawdata.csv`

These files are crawler-managed. Do not rename, edit, or merge them manually; each
crawler deduplicates by `source_url` and writes a crawl manifest for provenance.

## Optional review input

To enable rating and factor analysis, create `reviews.csv` using UTF-8 CSV with the
following required columns:

```text
review_id,destination,rating,review_text
```

`rating` must be numeric from 1 to 5. Optional columns are `review_date`, `platform`,
`source_url`, and `collected_at`. Use only data that you are authorised to collect and
process. Do not include personal data beyond what is necessary for the research.

## Analysis output

`analysis/` is recreated by `analysis_pipeline.py`; `docs/data/` is recreated by
`dashboard.py`. Commit generated output only when publishing a reviewed dashboard.
