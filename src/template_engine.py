"""Template Engine Mode narrative generation.

This module turns raw audit results and scores into readable, business-friendly
narrative sections without requiring any external API. It is the default
generation engine for the app and the fallback for LLM Enhanced Mode.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _dataset_label(inputs: Dict[str, Any]) -> str:
    return inputs.get("dataset_name") or "This dataset"


# ---------------------------------------------------------------------------
# 1. Executive summary
# ---------------------------------------------------------------------------
def executive_summary(audit, quality, dashboard, inputs) -> str:
    name = _dataset_label(inputs)
    rows = audit["shape"]["rows"]
    cols = audit["shape"]["columns"]

    lines = [
        f"{name} contains {rows:,} rows and {cols} columns.",
        f"The overall data quality score is {quality['score']}/100 "
        f"({quality['status']}), and the dashboard readiness score is "
        f"{dashboard['score']}/100 ({dashboard['status']}).",
    ]

    if quality["score"] < 50:
        lines.append(
            "**Warning:** Do not rely on this dataset for decision-making until "
            "the critical data quality issues are resolved."
        )
    elif quality["score"] < 80:
        lines.append(
            "The dataset is usable but needs cleanup before it can be fully trusted."
        )
    else:
        lines.append("The dataset is in good shape and ready for deeper analysis.")

    if dashboard["score"] < 50:
        lines.append(
            "**Warning:** Do not build a dashboard from this dataset yet. Clean and "
            "standardize the data first."
        )

    return " ".join(lines)


# ---------------------------------------------------------------------------
# 2. Biggest risks
# ---------------------------------------------------------------------------
def biggest_risks(audit) -> List[str]:
    risks: List[str] = []

    if audit["missing"]["flagged_columns"]:
        cols = ", ".join(audit["missing"]["flagged_columns"][:5])
        risks.append(f"High missing values in: {cols}.")
    if audit["duplicates"]["exact_duplicate_rows"] > 0:
        risks.append(
            f"{audit['duplicates']['exact_duplicate_rows']} exact duplicate rows "
            f"({audit['duplicates']['exact_duplicate_pct']}%)."
        )
    if audit["categories"]["columns_with_issues"]:
        cols = ", ".join(audit["categories"]["columns_with_issues"][:5])
        risks.append(f"Inconsistent category values in: {cols}.")
    if audit["types"]["mixed_type_columns"]:
        cols = ", ".join(audit["types"]["mixed_type_columns"][:5])
        risks.append(f"Mixed data types in: {cols}.")
    weak_dates = [r["column"] for r in audit["dates"]["reports"] if r["parse_success_rate"] < 95]
    if weak_dates:
        risks.append(f"Date parsing problems in: {', '.join(weak_dates[:5])}.")
    outlier_cols = [r["column"] for r in audit["numeric"]["reports"] if r["outliers"] > 0]
    if outlier_cols:
        risks.append(f"Potential outliers in: {', '.join(outlier_cols[:5])}.")

    if not risks:
        risks.append("No major data quality risks detected.")
    return risks


# ---------------------------------------------------------------------------
# 3. Cleanup recommendations
# ---------------------------------------------------------------------------
def cleanup_recommendations(audit) -> List[str]:
    recs: List[str] = []

    for col in audit["missing"]["flagged_columns"]:
        pct = audit["missing"]["per_column"][col]["missing_pct"]
        recs.append(
            f"Address missing values in `{col}` ({pct}%): impute, backfill, or "
            f"remove the column if it is not needed."
        )
    if audit["duplicates"]["exact_duplicate_rows"] > 0:
        recs.append(
            "Remove or investigate exact duplicate rows before aggregating metrics."
        )
    if audit["duplicates"]["key_duplicate_rows"] > 0:
        recs.append(
            f"Review {audit['duplicates']['key_duplicate_rows']} records that repeat "
            f"on key columns {audit['duplicates']['key_columns_used']} -- these may be "
            f"unintended duplicates."
        )
    for item in audit["categories"]["issues"]:
        parts = []
        if item["case_conflicts"]:
            parts.append("standardize capitalization")
        if item["whitespace_values"]:
            parts.append("trim leading/trailing spaces")
        if item["blank_like_values"]:
            parts.append("replace blank-like placeholders (N/A, TBD, unknown) with true nulls")
        if item["high_cardinality"]:
            parts.append("consider whether this column works as a dimension (high cardinality)")
        if parts:
            recs.append(f"In `{item['column']}`: " + "; ".join(parts) + ".")
    for rep in audit["dates"]["reports"]:
        if rep["parse_success_rate"] < 95 or rep["invalid_dates"] > 0:
            recs.append(
                f"Standardize date formats in `{rep['column']}` and fix "
                f"{rep['invalid_dates']} unparseable value(s)."
            )
        if rep["future_dates"] > 0:
            recs.append(f"Verify {rep['future_dates']} future date(s) in `{rep['column']}`.")
    for col in audit["types"]["mixed_type_columns"]:
        recs.append(f"Resolve mixed data types in `{col}` so it holds a single, consistent type.")
    for rep in audit["numeric"]["reports"]:
        if rep["negative_values"] > 0:
            recs.append(
                f"Confirm whether {rep['negative_values']} negative value(s) in "
                f"`{rep['column']}` are valid."
            )

    if not recs:
        recs.append("No cleanup actions required. The dataset is analysis-ready.")
    return recs


# ---------------------------------------------------------------------------
# 4. Suggested charts
# ---------------------------------------------------------------------------
def suggested_charts(audit) -> List[str]:
    charts: List[str] = ["Missing values by column (bar chart).",
                          "Data type distribution (bar chart)."]
    numeric = audit["types"]["numeric_columns"]
    category = audit["types"]["category_columns"]
    date = audit["types"]["date_columns"]

    if numeric:
        charts.append(f"Distribution histogram for numeric column `{numeric[0]}`.")
    if category:
        charts.append(f"Top categories bar chart for `{category[0]}`.")
    if date and numeric:
        charts.append(f"Trend of `{numeric[0]}` over `{date[0]}` (line chart).")
    if category and numeric:
        charts.append(f"`{numeric[0]}` grouped by `{category[0]}` (bar chart).")
    charts.append("Data quality and dashboard readiness score breakdowns.")
    return charts


# ---------------------------------------------------------------------------
# 5. Suggested business questions
# ---------------------------------------------------------------------------
def suggested_business_questions(audit, inputs) -> List[str]:
    questions: List[str] = []
    if inputs.get("business_question"):
        questions.append(f"Primary question provided: {inputs['business_question']}")

    numeric = audit["types"]["numeric_columns"]
    category = audit["types"]["category_columns"]
    date = audit["types"]["date_columns"]

    if numeric and category:
        questions.append(f"How does `{numeric[0]}` differ across `{category[0]}`?")
    if numeric and date:
        questions.append(f"How is `{numeric[0]}` trending over time?")
    if category:
        questions.append(f"Which `{category[0]}` values are most and least common?")
    if audit["business"]["has_status_column"]:
        questions.append(
            f"What is the distribution of records across `{audit['business']['status_column']}`?"
        )
    if audit["business"]["has_owner_column"]:
        questions.append(
            f"How is workload distributed across `{audit['business']['owner_column']}`?"
        )
    if not questions:
        questions.append("What patterns exist across the available categorical fields?")
    return questions


# ---------------------------------------------------------------------------
# 6. Suggested next steps
# ---------------------------------------------------------------------------
def suggested_next_steps(audit, quality, dashboard) -> List[str]:
    steps: List[str] = []

    if quality["score"] < 50:
        steps.append("Resolve critical data quality issues before any analysis.")
    elif quality["score"] < 80:
        steps.append("Clean up flagged columns, then re-run the audit to confirm improvement.")
    else:
        steps.append("Proceed to exploratory analysis and metric definition.")

    has_date = audit["dashboard"]["has_date_column"]
    has_numeric = audit["dashboard"]["has_numeric_column"]

    if not has_date and not has_numeric:
        steps.append(
            "This dataset has no date or numeric columns. Focus on categorical analysis: "
            "frequency counts, cross-tabs, and distribution summaries rather than trends or KPIs."
        )
    elif not has_date:
        steps.append("No date column detected -- time-based trend analysis is not yet possible.")
    elif not has_numeric:
        steps.append("No numeric column detected -- focus on counts and categorical breakdowns.")

    if dashboard["score"] >= 80:
        steps.append("Define KPIs and prototype a dashboard with the suggested charts.")
    elif dashboard["score"] >= 50:
        steps.append("Prepare and standardize the data before building a dashboard.")
    else:
        steps.append("Do not build a dashboard yet -- prioritize cleanup and structure first.")

    steps.append("Save this audit to history so you can track improvement over time.")
    return steps


# ---------------------------------------------------------------------------
# 7. Final data readiness summary
# ---------------------------------------------------------------------------
def final_summary(audit, quality, dashboard, inputs) -> str:
    name = _dataset_label(inputs)
    verdict = (
        "ready for trusted analysis"
        if quality["score"] >= 80
        else "usable with cleanup"
        if quality["score"] >= 50
        else "not yet reliable"
    )
    dash_verdict = (
        "ready for dashboarding"
        if dashboard["score"] >= 80
        else "not yet dashboard-ready"
    )
    return (
        f"{name} is currently **{verdict}** (quality {quality['score']}/100) and "
        f"**{dash_verdict}** (readiness {dashboard['score']}/100). "
        f"Follow the cleanup recommendations and re-audit to raise both scores before "
        f"making decisions or publishing dashboards."
    )


# ---------------------------------------------------------------------------
# Dashboard readiness advisor (recommended pages)
# ---------------------------------------------------------------------------
def recommended_dashboard_pages(audit) -> List[Dict[str, str]]:
    """Recommend dashboard pages/tabs based on the fields that are available."""
    numeric = audit["types"]["numeric_columns"]
    category = audit["types"]["category_columns"]
    date = audit["types"]["date_columns"]
    business = audit["business"]
    pages: List[Dict[str, str]] = []

    # Executive summary is always useful as a landing page.
    pages.append({
        "page": "Executive Summary",
        "why": "High-level KPIs and headline numbers for a quick overview.",
        "requires": "At least one metric or record count",
        "available": "Yes" if numeric or audit["shape"]["rows"] else "Partial",
    })

    if date and numeric:
        pages.append({
            "page": "Trend Analysis",
            "why": f"Track `{numeric[0]}` over `{date[0]}` to reveal patterns and seasonality.",
            "requires": "A date column + a numeric metric",
            "available": "Yes",
        })

    if category:
        pages.append({
            "page": "Category Breakdown",
            "why": f"Compare performance across `{category[0]}` and other dimensions.",
            "requires": "At least one categorical dimension",
            "available": "Yes",
        })

    if business.get("has_owner_column") or business.get("has_status_column"):
        cols = ", ".join(c for c in [business.get("owner_column"), business.get("status_column")] if c)
        pages.append({
            "page": "Owner / Status Tracking",
            "why": f"Monitor workload and progress using {cols}.",
            "requires": "An owner and/or status column",
            "available": "Yes",
        })

    # Data quality monitoring is always recommended for a trustworthy dashboard.
    pages.append({
        "page": "Data Quality Monitoring",
        "why": "Surface missing values, duplicates, and freshness so consumers can trust the numbers.",
        "requires": "The audit results (always available)",
        "available": "Yes",
    })

    return pages


# ---------------------------------------------------------------------------
# Suggested chart gallery
# ---------------------------------------------------------------------------
def chart_gallery(audit) -> List[Dict[str, str]]:
    """Suggest concrete charts based only on the fields that exist."""
    numeric = audit["types"]["numeric_columns"]
    category = audit["types"]["category_columns"]
    date = audit["types"]["date_columns"]
    gallery: List[Dict[str, str]] = []

    if category and numeric:
        gallery.append({
            "chart": "Bar chart",
            "fields": f"`{numeric[0]}` by `{category[0]}`",
            "why": "Compare a metric across categories.",
        })
    if date and numeric:
        gallery.append({
            "chart": "Line chart",
            "fields": f"`{numeric[0]}` over `{date[0]}`",
            "why": "Show how a metric changes over time.",
        })
    if numeric:
        gallery.append({
            "chart": "Histogram",
            "fields": f"`{numeric[0]}`",
            "why": "Reveal the distribution and skew of a numeric field.",
        })
        gallery.append({
            "chart": "Box plot",
            "fields": f"`{numeric[0]}`" + (f" by `{category[0]}`" if category else ""),
            "why": "Spot spread and outliers at a glance.",
        })

    # Pie/donut only when a category is genuinely low-cardinality.
    for item in audit["profiles"]:
        if item["column"] in category and 2 <= item["unique"] <= 6:
            gallery.append({
                "chart": "Pie / donut chart",
                "fields": f"share of `{item['column']}`",
                "why": "Show part-to-whole for a small number of categories.",
            })
            break

    # Scatter only when at least two numeric columns exist.
    if len(numeric) >= 2:
        gallery.append({
            "chart": "Scatter plot",
            "fields": f"`{numeric[0]}` vs `{numeric[1]}`",
            "why": "Explore the relationship between two numeric fields.",
        })

    if not gallery:
        gallery.append({
            "chart": "Frequency table / bar chart",
            "fields": "categorical columns",
            "why": "No numeric or date fields detected; focus on counts.",
        })
    return gallery


# ---------------------------------------------------------------------------
# Data dictionary draft
# ---------------------------------------------------------------------------
def _dashboard_role(column: str, semantic_type: str, unique: int, total_rows: int) -> str:
    """Map a column to a dashboard role: Metric, Dimension, Date, ID, Text, Unknown."""
    name = column.lower()
    looks_like_id = (
        any(tok in name for tok in ("id", "key", "code", "number", "no."))
        and total_rows and unique >= total_rows * 0.8
    )
    if looks_like_id:
        return "ID"
    if semantic_type == "date":
        return "Date"
    if semantic_type == "numeric":
        return "Metric"
    if semantic_type in ("category", "boolean"):
        return "Dimension"
    if semantic_type == "text":
        return "Text"
    return "Unknown"


def _suggested_use(role: str) -> str:
    """Plain-language suggestion for how to use a column on a dashboard."""
    return {
        "Metric": "Aggregate as a KPI (sum, average, min/max) and trend over time.",
        "Dimension": "Use as a filter, group-by, or breakdown axis.",
        "Date": "Drive time-series trends, date filters, and period comparisons.",
        "ID": "Use as a unique key for joins and record counts, not as a chart axis.",
        "Text": "Use for context, tooltips, or search; not ideal for aggregation.",
        "Unknown": "Inspect and classify before using in a dashboard.",
    }.get(role, "Inspect and classify before using in a dashboard.")


def _description_draft(column: str, role: str) -> str:
    """A best-guess description starter derived from the column name and role."""
    readable = column.replace("_", " ").replace("-", " ").strip().lower()
    role_hint = {
        "Metric": "numeric measure",
        "Dimension": "categorical attribute",
        "Date": "date/time field",
        "ID": "unique identifier",
        "Text": "free-text field",
        "Unknown": "field",
    }.get(role, "field")
    return f"{role_hint.capitalize()} representing {readable} (edit to confirm)."


def data_dictionary(audit) -> List[Dict[str, Any]]:
    """Build a draft data dictionary from column profiles."""
    total_rows = audit["shape"]["rows"]
    dictionary: List[Dict[str, Any]] = []
    for p in audit["profiles"]:
        role = _dashboard_role(p["column"], p["semantic_type"], p["unique"], total_rows)
        dictionary.append({
            "column": p["column"],
            "type": p["semantic_type"],
            "dashboard_role": role,
            "description": _description_draft(p["column"], role),
            "example_values": p["sample_values"],
            "missing_pct": p["missing_pct"],
            "completeness": f"{round(100 - p['missing_pct'], 1)}%",
            "unique_values": p["unique"],
            "suggested_use": _suggested_use(role),
        })
    return dictionary


# ---------------------------------------------------------------------------
# Full package
# ---------------------------------------------------------------------------
def generate_package(audit, quality, dashboard, inputs) -> Dict[str, Any]:
    """Assemble every narrative section into a single package dictionary."""
    return {
        "executive_summary": executive_summary(audit, quality, dashboard, inputs),
        "biggest_risks": biggest_risks(audit),
        "cleanup_recommendations": cleanup_recommendations(audit),
        "suggested_charts": suggested_charts(audit),
        "chart_gallery": chart_gallery(audit),
        "dashboard_pages": recommended_dashboard_pages(audit),
        "suggested_business_questions": suggested_business_questions(audit, inputs),
        "suggested_next_steps": suggested_next_steps(audit, quality, dashboard),
        "final_summary": final_summary(audit, quality, dashboard, inputs),
        "data_dictionary": data_dictionary(audit),
    }
