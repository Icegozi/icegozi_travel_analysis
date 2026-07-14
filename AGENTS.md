# Agent guidance for parseHtml

## Project overview

- This repository is a Vietnamese data science student project with two main parts:
  - `Chotot/`: HTML scraping and regression modeling for real estate prices from nha.chotot.com.
  - `Rating/`: Goodreads book rating data collection and machine learning modeling.
- The primary implementation is in Jupyter notebooks, not a conventional Python package.

## Key files

- `README.md` — project report and execution instructions in Vietnamese.
- `Chotot/Chotot_Scraping_Data.ipynb` — scraping workflow for Chotot real estate listings.
- `Chotot/Predict.ipynb` — cleaning, EDA, and regression modeling for real estate pricing.
- `Rating/Predict.ipynb` — data preprocessing and regression modeling for book ratings.
- `Chotot/dataset.csv`, `Chotot/rawdata.csv`, `Rating/X.csv`, `Rating/y.csv` — core datasets used by notebooks.

## How to assist effectively

- Use the notebooks as the source of truth for modeling, preprocessing, and scraping logic.
- Preserve dataset file paths and the notebook-driven workflow.
- If adding or updating code, prefer Python 3 data science idioms (`pandas`, `scikit-learn`, `numpy`) and keep changes compatible with Jupyter/Colab execution.
- Do not assume there is a package-level build/test system; this repository is organized around notebooks and CSV datasets.

## Special notes

- The repository is structured for exploration and reporting, not production deployment.
- Many filenames and documentation are in Vietnamese; translate only when needed for comprehension, but preserve original names in code and file references.
- There are no existing chat customization files in this workspace, so use this guidance for future agent behavior.
