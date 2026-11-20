from pathlib import Path
import sqlite3
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency
from statsmodels.stats.proportion import proportion_confint

ROOT = Path(__file__).resolve().parent
CSV = ROOT / "ml_project1_data.csv"
OUT = ROOT / "outputs"
OUT.mkdir(exist_ok=True)
CAMPAIGNS = [f"AcceptedCmp{i}" for i in range(1, 6)] + ["Response"]
SPEND = ["MntWines", "MntFruits", "MntMeatProducts", "MntFishProducts", "MntSweetProducts", "MntGoldProds"]


def clean_data(raw):
    df = raw.copy()
    log = []

    def record(issue, rows, action, why):
        log.append({"Issue": issue, "Rows affected": int(rows), "Action": action, "Reason": why})

    date = pd.to_datetime(df["Dt_Customer"], errors="coerce")
    bad_date = date.isna()
    record("Missing or invalid Dt_Customer", bad_date.sum(), "Drop rows with invalid enrollment date", "Required for the reference year and tenure.")
    df = df.loc[~bad_date].copy()
    df["Dt_Customer"] = date.loc[~bad_date]
    reference_year = int(df["Dt_Customer"].dt.year.max())

    income = pd.to_numeric(df["Income"], errors="coerce")
    bad_income = income.isna() | (income <= 0) | (income > 200000)
    median_income = income.loc[~bad_income].median()
    record("Missing, nonpositive, or implausible Income (>200,000)", bad_income.sum(), f"Replace with valid-income median ({median_income:.0f})", "A robust median preserves customers while removing an extreme value.")
    df["Income"] = income.mask(bad_income, median_income)

    birth = pd.to_numeric(df["Year_Birth"], errors="coerce")
    age = reference_year - birth
    bad_birth = birth.isna() | (age < 18) | (age > 100)
    birth_median = birth.loc[~bad_birth].median()
    record("Missing or impossible age (<18 or >100 at reference year)", bad_birth.sum(), f"Replace Year_Birth with valid-birth median ({birth_median:.0f})", "Age bands require a plausible adult age.")
    df["Year_Birth"] = birth.mask(bad_birth, birth_median).astype(int)

    edu = df["Education"].fillna("Unknown").astype(str).str.strip()
    edu_map = {"2n Cycle": "2nd Cycle", "2nd cycle": "2nd Cycle", "Graduation": "Graduation", "Master": "Master", "PhD": "PhD", "Basic": "Basic"}
    bad_edu = ~edu.isin(edu_map)
    record("Missing or inconsistent Education labels", bad_edu.sum(), "Normalize 2n Cycle and map missing/unrecognized labels to Other", "Keeps category values consistent without discarding rows.")
    df["Education"] = edu.map(edu_map).fillna("Other")

    marital = df["Marital_Status"].fillna("Unknown").astype(str).str.strip()
    marital_map = {"Single": "Single", "Married": "Married", "Together": "Together", "Divorced": "Divorced", "Widow": "Widowed", "Widowed": "Widowed", "YOLO": "Other", "Absurd": "Other", "Alone": "Single"}
    bad_mar = ~marital.isin(marital_map)
    record("Missing or inconsistent Marital_Status labels", bad_mar.sum(), "Map Alone to Single; YOLO, Absurd, and unknown labels to Other", "Standardizes equivalent and invalid category labels.")
    df["Marital_Status"] = marital.map(marital_map).fillna("Other")

    for col in ["Kidhome", "Teenhome"]:
        x = pd.to_numeric(df[col], errors="coerce")
        bad = x.isna() | (x < 0) | (x > 5) | (x % 1 != 0)
        med = x.loc[~bad].median()
        record(f"Missing or impossible {col}", bad.sum(), f"Replace with valid-value median ({med:g})", "Household child counts must be nonnegative whole numbers.")
        df[col] = x.mask(bad, med).round().astype(int)

    for col in CAMPAIGNS:
        x = pd.to_numeric(df[col], errors="coerce")
        bad = x.isna() | ~x.isin([0, 1])
        record(f"Missing or invalid campaign flag {col}", bad.sum(), "Set missing or invalid flag to 0", "Campaign outcomes are binary; absent acceptance is treated as no conversion.")
        df[col] = x.mask(bad, 0).astype(int)

    for col in SPEND:
        x = pd.to_numeric(df[col], errors="coerce")
        bad = x.isna() | (x < 0)
        record(f"Missing or negative {col}", bad.sum(), "Replace with median nonnegative spend (or zero if none)", "Spend cannot be negative.")
        df[col] = x.mask(bad, x.loc[~bad].median() if (~bad).any() else 0)

    # Contact cost and conversion revenue are fixed by the supplied case definitions.
    df["Z_CostContact"] = 3
    df["Z_Revenue"] = 11
    df["TotalSpend"] = df[SPEND].sum(axis=1)
    df["ReferenceYear"] = reference_year
    df["Age"] = reference_year - df["Year_Birth"]
    df["AgeBand"] = pd.cut(df["Age"], [17, 34, 49, 64, 101], labels=["18–34", "35–49", "50–64", "65+"]).astype(str)
    df["IncomeQuartile"] = pd.qcut(df["Income"].rank(method="first"), 4, labels=["Q1 lowest", "Q2", "Q3", "Q4 highest"])
    df["Children"] = np.where(df["Kidhome"] + df["Teenhome"] == 0, "0", "1+")
    days = (df["Dt_Customer"].max() - df["Dt_Customer"]).dt.days
    df["TenureBand"] = pd.cut(days, [-1, 365, 730, 20000], labels=["Under 1 year", "1–2 years", "Over 2 years"]).astype(str)
    return df, pd.DataFrame(log)


def campaign_summary(df):
    rows = []
    for i, col in enumerate(CAMPAIGNS, 1):
        n, k = len(df), int(df[col].sum())
        lo, hi = proportion_confint(k, n, method="wilson")
        means = df.groupby(col, observed=False)["TotalSpend"].mean()
        rows.append({"Campaign": i, "Flag": col, "Customers": n, "Conversions": k, "Rate": k/n, "CI low": lo, "CI high": hi,
                     "Avg spend converted": means.get(1, np.nan), "Avg spend not converted": means.get(0, np.nan)})
    return pd.DataFrame(rows)


def segment_tables(df):
    dims = ["AgeBand", "IncomeQuartile", "Education", "Marital_Status", "Children", "TenureBand"]
    tables = {}
    overall = df["Response"].mean()
    for dim in dims:
        grouped = df.groupby(dim, observed=True).agg(Customers=("Response", "size"), Conversions=("Response", "sum"), Rate=("Response", "mean"), AvgSpend=("TotalSpend", "mean")).reset_index()
        pvals = []
        high = []
        for _, row in grouped.iterrows():
            subset = df[dim].eq(row[dim])
            rest = df.loc[~subset, "Response"]
            try:
                p = chi2_contingency([[int(df.loc[subset, "Response"].sum()), int(subset.sum()-df.loc[subset, "Response"].sum())], [int(rest.sum()), int(len(rest)-rest.sum())]], correction=False)[1]
            except ValueError:
                p = 1.0
            pvals.append(p)
            high.append(bool(row["Customers"] >= 50 and row["Rate"] > df.loc[~subset, "Response"].mean() and p < .05))
        grouped["p-value vs rest"] = pvals
        grouped["High-performing"] = high
        grouped["Overall rate"] = overall
        intervals = [proportion_confint(int(row.Conversions), int(row.Customers), method="wilson") for row in grouped.itertuples()]
        grouped["CI low"] = [x[0] for x in intervals]
        grouped["CI high"] = [x[1] for x in intervals]
        tables[dim] = grouped
    combo = df.groupby(["IncomeQuartile", "Children"], observed=True).agg(Customers=("Response", "size"), Conversions=("Response", "sum"), Rate=("Response", "mean"), AvgSpend=("TotalSpend", "mean")).reset_index()
    combo["Segment"] = combo["IncomeQuartile"].astype(str) + " × " + combo["Children"].astype(str) + " children"
    combo["p-value vs rest"] = [chi2_contingency([[int(df.loc[(df.IncomeQuartile.eq(r.IncomeQuartile)) & (df.Children.eq(r.Children)), "Response"].sum()), int(((df.IncomeQuartile.eq(r.IncomeQuartile)) & (df.Children.eq(r.Children))).sum()-df.loc[(df.IncomeQuartile.eq(r.IncomeQuartile)) & (df.Children.eq(r.Children)), "Response"].sum())], [int(df.loc[~((df.IncomeQuartile.eq(r.IncomeQuartile)) & (df.Children.eq(r.Children))), "Response"].sum()), int((~((df.IncomeQuartile.eq(r.IncomeQuartile)) & (df.Children.eq(r.Children)))).sum()-df.loc[~((df.IncomeQuartile.eq(r.IncomeQuartile)) & (df.Children.eq(r.Children))), "Response"].sum())]], correction=False)[1] for r in combo.itertuples()]
    combo["High-performing"] = [bool(r.Customers >= 50 and r.Rate > (df.loc[~((df.IncomeQuartile.eq(r.IncomeQuartile)) & (df.Children.eq(r.Children))), "Response"].mean()) and p < .05) for r, p in zip(combo.itertuples(), combo["p-value vs rest"])]
    combo["Overall rate"] = overall
    intervals = [proportion_confint(int(row.Conversions), int(row.Customers), method="wilson") for row in combo.itertuples()]
    combo["CI low"] = [x[0] for x in intervals]
    combo["CI high"] = [x[1] for x in intervals]
    tables["IncomeQuartile × Children"] = combo
    return tables


def sql_checks(df, tables, campaign):
    con = sqlite3.connect(OUT / "campaigns.sqlite")
    df.to_sql("customers", con, if_exists="replace", index=False)
    campaign_sql = pd.read_sql_query("SELECT flag AS Campaign, COUNT(*) AS Customers, SUM(converted) AS Conversions, AVG(converted * 1.0) AS Rate FROM (SELECT 'AcceptedCmp1' flag, AcceptedCmp1 converted FROM customers UNION ALL SELECT 'AcceptedCmp2', AcceptedCmp2 FROM customers UNION ALL SELECT 'AcceptedCmp3', AcceptedCmp3 FROM customers UNION ALL SELECT 'AcceptedCmp4', AcceptedCmp4 FROM customers UNION ALL SELECT 'AcceptedCmp5', AcceptedCmp5 FROM customers UNION ALL SELECT 'Response', Response FROM customers) GROUP BY flag", con)
    profit_sql = pd.read_sql_query("SELECT SUM(Response * Z_Revenue - Z_CostContact) AS Profit FROM customers", con).iloc[0, 0]
    segment_sql = pd.read_sql_query("SELECT IncomeQuartile, Children, COUNT(*) Customers, SUM(Response) Conversions, AVG(Response * 1.0) Rate, AVG(TotalSpend) AvgSpend FROM customers GROUP BY IncomeQuartile, Children", con)
    cdict = campaign.set_index("Flag")
    for r in campaign_sql.itertuples():
        assert np.isclose(r.Rate, cdict.loc[r.Campaign, "Rate"])
        assert int(r.Conversions) == int(cdict.loc[r.Campaign, "Conversions"])
    expected = int((df.Response * df.Z_Revenue - df.Z_CostContact).sum())
    assert int(profit_sql) == expected
    pandas_seg = tables["IncomeQuartile × Children"].set_index(["IncomeQuartile", "Children"])
    sql_seg = segment_sql.set_index(["IncomeQuartile", "Children"])
    assert np.allclose(pandas_seg.loc[sql_seg.index, "Rate"], sql_seg.Rate)
    con.close()
    return campaign_sql, segment_sql, profit_sql


def make_charts(df, campaign, tables, target_count, profit_all, profit_target):
    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.errorbar(campaign.Campaign, campaign.Rate*100, yerr=[(campaign.Rate-campaign["CI low"])*100, (campaign["CI high"]-campaign.Rate)*100], fmt="o", capsize=4)
    ax.set(xticks=campaign.Campaign, xlabel="Campaign", ylabel="Conversion rate (%)", title=f"Campaign 6 leads at {campaign.iloc[-1].Rate:.1%}; intervals show uncertainty")
    fig.tight_layout(); fig.savefig(OUT/"campaign_rates.png", dpi=180); plt.close(fig)
    chart = tables["IncomeQuartile × Children"].sort_values("Rate")
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.barh(chart.Segment, chart.Rate*100, color=np.where(chart["High-performing"], "#168a72", "#9aa6b2"))
    ax.axvline(df.Response.mean()*100, color="#c34a36", linestyle="--", label=f"Overall {df.Response.mean():.1%}")
    ax.set(xlabel="Campaign 6 conversion rate (%)", title="Income and household size separate response rates")
    ax.legend(); fig.tight_layout(); fig.savefig(OUT/"segment_rates.png", dpi=180); plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 4.5)); x=np.arange(6); width=.36
    ax.bar(x-width/2, campaign["Avg spend converted"], width, label="Converted"); ax.bar(x+width/2, campaign["Avg spend not converted"], width, label="Did not convert")
    ax.set(xticks=x, xticklabels=[f"Campaign {i}" for i in range(1,7)], ylabel="Average total spend", title="Responders spend more in some campaigns, but not all"); ax.legend()
    fig.tight_layout(); fig.savefig(OUT/"spend_by_campaign.png", dpi=180); plt.close(fig)
    fig, ax = plt.subplots(figsize=(7,4.5)); labels=["Contact everyone", "Target high-performing"]
    ax.bar(labels, [profit_all, profit_target], color=["#8793a1", "#168a72"])
    ax.axhline(0, color="black", linewidth=.8); ax.set(ylabel="Estimated campaign profit", title=f"Targeting {target_count:,} customers changes expected profit")
    fig.tight_layout(); fig.savefig(OUT/"profit_scenarios.png", dpi=180); plt.close(fig)


def main():
    if not CSV.exists():
        raise FileNotFoundError(f"Place the supplied raw CSV here: {CSV}")
    raw = pd.read_csv(CSV)
    df, log = clean_data(raw)
    log.to_csv(OUT/"cleaning_log.csv", index=False)
    df.to_csv(OUT/"cleaned_customers.csv", index=False)
    camp = campaign_summary(df)
    tables = segment_tables(df)
    camp.to_csv(OUT/"campaign_summary.csv", index=False)
    for name, table in tables.items():
        table.to_csv(OUT/(name.lower().replace(" × ", "_").replace(" ", "_")+"_segments.csv"), index=False)
    campaign_sql, segment_sql, sql_profit = sql_checks(df, tables, camp)
    campaign_sql.to_csv(OUT/"sql_campaign_results.csv", index=False)
    segment_sql.to_csv(OUT/"sql_segment_results.csv", index=False)
    target_ids = set()
    for dim, table in tables.items():
        selected = table.loc[table["High-performing"]]
        for r in selected.itertuples():
            if dim == "IncomeQuartile × Children":
                mask = df.IncomeQuartile.eq(r.IncomeQuartile) & df.Children.eq(r.Children)
            else:
                mask = df[dim].eq(getattr(r, dim.replace(" ", "_")))
            target_ids.update(df.loc[mask].index.tolist())
    target = df.loc[sorted(target_ids)] if target_ids else df.iloc[0:0]
    # Overlapping qualifying segment definitions are deduplicated at customer level.
    expected_target_conversions = df.Response.mean()*len(target)
    profit_target = expected_target_conversions*11-len(target)*3
    profit_all = int(sql_profit)
    scenarios = pd.DataFrame([{"Scenario":"Contact everyone","Customers contacted":len(df),"Expected conversions":int(df.Response.sum()),"Profit":profit_all}, {"Scenario":"Target union of qualifying segments","Customers contacted":len(target),"Expected conversions":expected_target_conversions,"Profit":profit_target}])
    scenarios.to_csv(OUT/"profit_scenarios.csv", index=False)
    make_charts(df, camp, tables, len(target), profit_all, profit_target)
    multi = int((df[CAMPAIGNS].sum(axis=1)>1).sum())
    print(f"Reference year: {df.ReferenceYear.iloc[0]}; customers: {len(df)}; multiple campaign conversions: {multi}; campaign 6 profit: {profit_all}; targeted customers: {len(target)}; targeted expected profit: {profit_target:.2f}")
    print(camp.to_string(index=False))
    print("\nQualified segments:\n", pd.concat([t.loc[t["High-performing"]].assign(SegmentType=name) for name,t in tables.items()], ignore_index=True).to_string(index=False))
    print("\nSQL and Pandas checks passed. See outputs/ and queries.sql.")

    # Produce the manager-facing PDF after all metrics and charts have been computed.
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
    report = SimpleDocTemplate(str(OUT/"marketing_campaign_report.pdf"), pagesize=letter, rightMargin=0.6*inch, leftMargin=0.6*inch, topMargin=0.55*inch, bottomMargin=0.55*inch)
    styles = getSampleStyleSheet(); story=[]
    best = camp.sort_values("Rate", ascending=False).iloc[0]
    high = pd.concat([t.loc[t["High-performing"]].assign(Type=n) for n,t in tables.items()], ignore_index=True)
    high_text = "; ".join(f"{r.Type}: {r.iloc[0]} ({int(r.Customers)} customers, {r.Rate:.1%}, p={r['p-value vs rest']:.3g})" for _,r in high.iterrows()) or "No segment met both the sample-size and significance rules."
    story += [Paragraph("Marketing campaign analysis", styles["Title"]), Paragraph("Decision brief for the marketing manager", styles["Normal"]), Spacer(1,10), Paragraph("Summary and recommendations", styles["Heading1"])]
    story.append(Paragraph(f"1. Prioritize learning from Campaign {int(best.Campaign)}, the highest observed response rate at {best.Rate:.1%} (95% CI {best['CI low']:.1%}–{best['CI high']:.1%}; n={int(best.Customers):,}). Confirm the offer and audience before scaling.", styles["BodyText"]))
    story.append(Paragraph(f"2. Pilot only statistically qualified audience groups: {high_text}", styles["BodyText"]))
    story.append(Paragraph(f"3. The observed campaign 6 profit was {profit_all:,.0f}; the modeled targeted scenario contacts {len(target):,} and yields expected profit {profit_target:,.0f} under the same per-customer conversion rate and case economics.", styles["BodyText"]))
    story += [Spacer(1,8), Paragraph("Campaign comparison", styles["Heading1"])]
    data=[["Campaign","Conversions","Rate (95% CI)","Spend: converted","Spend: no conversion"]]
    for _, r in camp.iterrows(): data.append([str(int(r.Campaign)),str(int(r.Conversions)),f"{r.Rate:.1%} ({r['CI low']:.1%}–{r['CI high']:.1%})",f"{r['Avg spend converted']:.0f}",f"{r['Avg spend not converted']:.0f}"])
    tbl=Table(data, repeatRows=1, colWidths=[.75*inch,.85*inch,1.35*inch,1.35*inch,1.45*inch]); tbl.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#17324d")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.3,colors.grey),("FONTSIZE",(0,0),(-1,-1),7),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#eef3f6")])]))
    story += [tbl, Paragraph(f"{multi:,} customers converted in more than one campaign. Campaign intervals overlap where the data do not clearly separate observed rates; overlapping intervals are descriptive and do not substitute for a formal pairwise test.", styles["BodyText"]), Spacer(1,8), Image(str(OUT/"campaign_rates.png"), width=6.9*inch, height=3.85*inch), PageBreak(), Paragraph("Segments and targeting", styles["Heading1"]), Paragraph("High-performing means at least 50 customers and a chi-square test against all other customers with p < 0.05 and a higher conversion rate. The targeted customer count deduplicates overlaps across qualifying segment definitions.", styles["BodyText"])]
    seg_data=[["Segment","Group","N","Rate (95% CI)","Avg spend","p vs rest","Qualified"]]
    for name, table in tables.items():
        for _,r in table.iterrows(): seg_data.append([name,str(r.get("Segment",r.get(name,""))),str(int(r.Customers)),f"{r.Rate:.1%} ({r['CI low']:.1%}–{r['CI high']:.1%})",f"{r.AvgSpend:.0f}",f"{r['p-value vs rest']:.3g}","Yes" if r["High-performing"] else "No"])
    st=Table(seg_data, repeatRows=1, colWidths=[1.25*inch,1.55*inch,.42*inch,.55*inch,.7*inch,.65*inch,.55*inch]); st.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#17324d")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.25,colors.grey),("FONTSIZE",(0,0),(-1,-1),6),("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#eef3f6")])]))
    story += [st, Spacer(1,6), Image(str(OUT/"segment_rates.png"), width=6.9*inch, height=3.7*inch), PageBreak(), Paragraph("Targeting scenario", styles["Heading1"])]
    pdata=[["Scenario","Contacted","Expected conversions","Profit"]]+[[r.Scenario,f"{int(r['Customers contacted']):,}",f"{r['Expected conversions']:.1f}",f"{r.Profit:,.0f}"] for _,r in scenarios.iterrows()]
    pt=Table(pdata, colWidths=[2.7*inch,1.2*inch,1.4*inch,1.3*inch]); pt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),colors.HexColor("#17324d")),("TEXTCOLOR",(0,0),(-1,0),colors.white),("GRID",(0,0),(-1,-1),.3,colors.grey),("FONTSIZE",(0,0),(-1,-1),9)]))
    story += [pt, Spacer(1,8), Paragraph("Profit uses the supplied case assumptions: 11 per conversion and 3 per contacted customer. The targeted scenario assumes every selected customer converts at the overall campaign 6 rate; it is a scenario, not a causal estimate.", styles["BodyText"]), Spacer(1,6), Image(str(OUT/"profit_scenarios.png"), width=6.4*inch, height=4.1*inch), Paragraph("Limitations", styles["Heading1"]), Paragraph("The data are observational and contain one historical response outcome. They cannot establish that targeting causes higher response, predict results under a changed offer, or capture campaign-specific contact costs beyond the supplied fixed values. Segment comparisons examine many groups, so some apparent differences may occur by chance. Historical spend is not profit.", styles["BodyText"])]
    report.build(story)


if __name__ == "__main__":
    main()
