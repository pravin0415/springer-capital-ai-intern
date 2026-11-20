-- Run against the cleaned customers table produced by analyze_campaigns.py.
-- Campaign flags: AcceptedCmp1–5 and Response (campaign 6).

-- Conversion count, contacted count, and rate by campaign (all customers contacted).
SELECT campaign, COUNT(*) AS customers_contacted,
       SUM(converted) AS conversions,
       1.0 * SUM(converted) / COUNT(*) AS conversion_rate
FROM (
    SELECT 'Campaign 1' AS campaign, AcceptedCmp1 AS converted FROM customers
    UNION ALL SELECT 'Campaign 2', AcceptedCmp2 FROM customers
    UNION ALL SELECT 'Campaign 3', AcceptedCmp3 FROM customers
    UNION ALL SELECT 'Campaign 4', AcceptedCmp4 FROM customers
    UNION ALL SELECT 'Campaign 5', AcceptedCmp5 FROM customers
    UNION ALL SELECT 'Campaign 6', Response FROM customers
)
GROUP BY campaign
ORDER BY campaign;

-- Campaign 6 rate by each required segment variable.
SELECT 'Age band' AS segment_type, AgeBand AS segment,
       COUNT(*) AS customers, SUM(Response) AS conversions,
       1.0 * SUM(Response) / COUNT(*) AS conversion_rate,
       AVG(TotalSpend) AS average_total_spend
FROM customers GROUP BY AgeBand
UNION ALL
SELECT 'Income quartile', IncomeQuartile, COUNT(*), SUM(Response),
       1.0 * SUM(Response) / COUNT(*), AVG(TotalSpend)
FROM customers GROUP BY IncomeQuartile
UNION ALL
SELECT 'Education', Education, COUNT(*), SUM(Response),
       1.0 * SUM(Response) / COUNT(*), AVG(TotalSpend)
FROM customers GROUP BY Education
UNION ALL
SELECT 'Marital status', Marital_Status, COUNT(*), SUM(Response),
       1.0 * SUM(Response) / COUNT(*), AVG(TotalSpend)
FROM customers GROUP BY Marital_Status
UNION ALL
SELECT 'Children', Children, COUNT(*), SUM(Response),
       1.0 * SUM(Response) / COUNT(*), AVG(TotalSpend)
FROM customers GROUP BY Children
UNION ALL
SELECT 'Tenure', TenureBand, COUNT(*), SUM(Response),
       1.0 * SUM(Response) / COUNT(*), AVG(TotalSpend)
FROM customers GROUP BY TenureBand
UNION ALL
SELECT 'Income quartile × children', IncomeQuartile || ' × ' || Children,
       COUNT(*), SUM(Response), 1.0 * SUM(Response) / COUNT(*), AVG(TotalSpend)
FROM customers GROUP BY IncomeQuartile, Children
ORDER BY segment_type, segment;

-- Campaign 6 profit under the supplied case economics.
SELECT SUM(Response * Z_Revenue - Z_CostContact) AS campaign_6_profit
FROM customers;
