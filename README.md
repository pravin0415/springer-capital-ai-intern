# Marketing Campaign Analysis

This project analyzes the six campaign response flags in the iFood marketing dataset and creates the SQL checks, cleaning log, charts, segment tables, and a manager-facing PDF report.

## Run it

1. The original `ml_project1_data.csv` is included in this repository next to `analyze_campaigns.py`. It is also available from the [source dataset](https://raw.githubusercontent.com/nailson/ifood-data-business-analyst-test/master/ml_project1_data.csv). The notebook reads the raw file and cleans it during the analysis.
2. Install the packages in `requirements.txt`.
3. Open `marketing_campaign_analysis.ipynb` and run all cells from top to bottom, or run `python analyze_campaigns.py`.

The notebook executes the same analysis script. It writes `cleaning_log.csv` and `marketing_campaign_report.pdf` beside the notebook, and writes the cleaned SQLite database, campaign and segment result tables, and four PNG charts to `outputs/`. The script asserts that campaign conversion rates, segment conversion rates, and campaign 6 profit agree between SQLite and Pandas.

`queries.sql` contains the matching SQL queries. The case defines cost per contact as 3 and revenue per conversion as 11; only campaign 6 has profit results. Age is calculated using the latest enrollment year in the data. High-performing segments must have at least 50 customers and a chi-square p-value below 0.05 versus everyone outside that segment.

## Outputs and assumptions

The targeting scenario uses only qualifying `IncomeQuartile × Children` groups. Each group's observed campaign 6 response rate is applied to its customer count, and expected profit is calculated as 11 per expected conversion minus 3 per contact. The qualifying groups in this dataset do not overlap. This is a scenario based on historical rates, not a causal estimate.
