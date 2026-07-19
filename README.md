# Vietnam Tourism Interest Analysis

Reproducible research pipeline for studying **online interest in Vietnamese destinations** from publicly available tourism content. It collects permitted pages, identifies destinations and travel themes, tracks content engagement, and publishes a static dashboard.

> **Scope.** Article views and comments are proxies for content interest and engagement. They are not visitor-arrival statistics, traveller ratings, satisfaction scores, or evidence of causality.

## What this project answers

- Which destinations and themes receive the most observable content attention?
- How does attention vary by publication season and across repeated VNTRIP snapshots?
- Which content-level signals may help prioritize destination marketing research?
- When permitted review data is supplied, which service factors are mentioned alongside ratings?

## Architecture

```text
public tourism pages
        │
        ├── VNTRIP/crawl_vntrip.py
        ├── VIETNAM_TRAVEL/crawl_vietnam_travel.py
        └── PROVINCIAL_PORTALS/crawl_portals.py
        │
        ▼
data/<SOURCE>/rawdata.csv ──► analysis_pipeline.py ──► data/analysis/*.csv
                                                        │
                                                        ▼
                                                   dashboard.py
                                                        │
                                                        ▼
                                                docs/index.html
```

| Path | Purpose |
| --- | --- |
| `common/` | Shared HTTP, configuration, CSV, and crawl-manifest utilities. |
| `VNTRIP/`, `VIETNAM_TRAVEL/`, `PROVINCIAL_PORTALS/` | Source-specific crawlers. |
| `analysis_pipeline.py` | Cleaning, deduplication, labelling, trend, review, and coverage analysis. |
| `dashboard.py`, `dashboard_assets/` | Static dashboard generator and assets. |
| `quality_gate.py` | Publish checks used by GitHub Actions. |
| `tests/` | Offline regression tests; no network access is required. |
| `data/` | Runtime data. Raw and analytical CSV files are generated locally. |
| `docs/` | Generated GitHub Pages output. |

## Quick start

### From a source archive

```bash
mkdir parseHtml
unzip icegozi_travel_analysis_source_YYYY-MM-DD.zip -d parseHtml
cd parseHtml
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
sh run_all.sh
```

### From a Git clone

```bash
git clone https://github.com/Icegozi/icegozi_travel_analysis.git
cd icegozi_travel_analysis
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
sh run_all.sh
```

Use Python 3.12 or a compatible Python 3 release. The first run requires Internet access; it creates `data/` files and regenerates `docs/index.html`.

## Configuration

Copy `.env.example` to `.env`. Do not commit `.env`.

| Variable group | Default | Meaning |
| --- | ---: | --- |
| `RUN_*_CRAWLER` | `1` | Enables VNTRIP, Vietnam.travel, or provincial-portal crawling. |
| `*_MAX_PAGES` | `200`, `200`, `1000` | Listing-page budget for VNTRIP, Vietnam.travel, and all portals respectively. |
| `*_MAX_NEW_ARTICLES` | `1000`, `1000`, `200` | New-article budget per run. |
| `*_DELAY_SECONDS` | `2` | Delay between requests for each source. |
| `HTTP_TIMEOUT_SECONDS` / `HTTP_RETRIES` | `3` / `2` | Request timeout and retry count. |
| `PYTHON_BIN` | empty | Optional Python executable; defaults to `.venv/bin/python`. |

For a fast local check, lower page/article budgets in `.env`. `PORTALS_MAX_PAGES` and `PORTALS_MAX_NEW_ARTICLES` are global budgets shared by all provincial portals, not per-portal limits.

## Running the pipeline

```bash
# Crawl enabled sources, analyse, and rebuild the dashboard
sh run_all.sh

# Rebuild analysis and dashboard from data already collected
# Set all RUN_*_CRAWLER values to 0 in .env, then run:
sh run_all.sh

# Run offline regression tests
.venv/bin/python -m unittest tests/test_refactor.py

# Validate generated data before publishing
.venv/bin/python quality_gate.py
```

Open `docs/index.html` locally after a successful run. The dashboard's CSV download links are generated into `docs/data/`.

## Data contract and outputs

The crawlers preserve each source URL to avoid duplicate records. Do not manually edit `rawdata.csv`; rerun the relevant crawler instead. See [`data/README.md`](data/README.md) for the review-data schema.

Important outputs in `data/analysis/` include:

- `normalized_articles.csv` — cleaned content with destination and theme labels.
- `destination_opportunity_scores.csv` — content-interest prioritisation score (70% views/day, 30% article count).
- `destination_season_stats.csv` and `destination_monthly_interest.csv` — seasonal and monthly interest signals.
- `article_snapshot_trends.csv` — VNTRIP view changes between crawl dates.
- `content_engagement_stats.csv` — public comment activity; not traveller reviews.
- `review_behavior_stats.csv` and `destination_factor_stats.csv` — produced only when valid review data is supplied.
- `analysis_coverage.csv` and `run_metadata.json` — limits, provenance, and crawl coverage.

To analyse authorised review data, create `data/reviews.csv` with these required columns:

```text
review_id,destination,rating,review_text
```

Optional fields are `review_date`, `platform`, `source_url`, and `collected_at`. Ratings must be 1–5. Use canonical destination names such as `Đà Nẵng`, `Đà Lạt`, and `Phú Quốc`.

## Responsible collection and interpretation

- Crawl only public pages allowed by the site's `robots.txt`.
- Do not bypass authentication, CAPTCHAs, rate limits, or technical protections.
- Do not collect or publish personal data.
- Keep request budgets modest and retain source URLs/manifests for provenance.
- Treat labels and scores as exploratory signals. Validate destination labels and use representative, authorised review data before making claims about traveller sentiment.

## Automation and publishing

`.github/workflows/update-dashboard.yml` runs on GitHub Actions at 02:00 ICT (checked daily; crawling occurs every three days) and can be run manually in `full`, `vntrip_only`, or `dashboard_only` mode. It runs the quality gate before committing generated data and `docs/` for GitHub Pages.

Enable **Settings → Actions → General → Workflow permissions → Read and write permissions** for the workflow to push updates.

## Development

Keep new source-specific parsing code inside the appropriate crawler, place reusable logic in `common/`, and add an offline test for parsing or normalization changes. Format code with four-space indentation and use descriptive `snake_case` names. Generated data, virtual environments, caches, and local configuration are excluded by `.gitignore`.

## License

See [LICENSE](LICENSE).
