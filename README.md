# Marketing Campaign Analysis

This project analyzes the six campaign response flags in the iFood marketing dataset and creates the SQL checks, cleaning log, charts, segment tables, and a manager-facing PDF report.

## Run it

1. Download the original [`ml_project1_data.csv`](https://raw.githubusercontent.com/nailson/ifood-data-business-analyst-test/master/ml_project1_data.csv) into this folder (next to `analyze_campaigns.py`). The notebook reads that raw file; it does not require a pre-cleaned copy.
2. Install the packages in `requirements.txt`.
3. Open `marketing_campaign_analysis.ipynb` and run all cells from top to bottom, or run `python analyze_campaigns.py`.

The notebook executes the same analysis script. Outputs are written to `outputs/`, including `cleaning_log.csv`, the cleaned SQLite database, campaign and segment result tables, four PNG charts, and `marketing_campaign_report.pdf`. The script asserts that campaign conversion rates, segment conversion rates, and campaign 6 profit agree between SQLite and Pandas.

`queries.sql` contains the matching SQL queries. The case defines cost per contact as 3 and revenue per conversion as 11; only campaign 6 has profit results. Age is calculated using the latest enrollment year in the data. High-performing segments must have at least 50 customers and a chi-square p-value below 0.05 versus everyone outside that segment.

## Outputs and assumptions

The targeting scenario takes the union of customers in qualifying segments, so overlaps are not counted twice. Expected conversions use the overall campaign 6 response rate, as specified. This is a scenario based on historical rates, not a causal estimate.
