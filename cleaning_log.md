# Cleaning log

Row counts are calculated from the supplied raw CSV each time the notebook runs and saved in `outputs/cleaning_log.csv`. This keeps the log tied to the exact source data rather than hard-coding counts.

| Issue detected | Treatment | Reason |
|---|---|---|
| Missing or invalid enrollment date | Drop affected rows | Needed for tenure and reference year. |
| Missing, nonpositive, or income above 200,000 | Replace with median valid income | Prevents missing/extreme income from distorting quartiles while retaining customers. |
| Adult age below 18 or above 100 at latest enrollment year | Replace birth year with median valid birth year | Needed for meaningful age bands. |
| Missing/inconsistent education labels | Normalize `2n Cycle`; missing or unknown values become `Other` | Produces consistent categories. |
| Missing/inconsistent marital labels | `Alone` becomes `Single`; `YOLO`, `Absurd`, missing/unknown become `Other`; `Widow` becomes `Widowed` | Consolidates equivalent and unusable labels. |
| Missing, fractional, negative, or unusually high household child count (>5) | Replace with median valid whole number | Household counts must be plausible nonnegative integers. |
| Missing or nonbinary campaign response | Set to 0 | Campaign outcome is binary; absent acceptance is treated as no conversion. |
| Missing or negative product spend | Replace with median nonnegative amount (or zero if no valid values) | Spend cannot be negative. |
| Case constants | Set contact cost to 3 and revenue per conversion to 11 | These are specified by the assignment. |

The CSV log includes the number of affected rows for every rule. Multiple rules can affect the same row, so issue counts are not additive.
