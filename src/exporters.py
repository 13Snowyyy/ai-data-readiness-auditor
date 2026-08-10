"""Export helpers: Markdown report, cleaned CSV, column profile, issue log."""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd

from . import config
from .audit_engine import is_text_like
from .utils import clean_text, human_readable_timestamp


# ---------------------------------------------------------------------------
# Markdown audit report
# ---------------------------------------------------------------------------
def _md_list(items: List[str]) -> str:
    return "\n".join(f"- {item}" for item in items) if items else "- None"


def _md_table(rows: List[Dict[str, Any]], columns: List[str]) -> str:
    if not rows:
        return "_No records._"
    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = []
    for row in rows:
        body.append("| " + " | ".join(str(row.get(c, "")) for c in columns) + " |")
    return "\n".join([header, sep, *body])


def build_markdown_report(
    inputs: Dict[str, Any],
    audit: Dict[str, Any],
    quality: Dict[str, Any],
    dashboard: Dict[str, Any],
    package: Dict[str, Any],
) -> str:
    """Build a complete Markdown audit report with all 18 sections."""
    name = inputs.get("dataset_name") or "Untitled dataset"
    lines: List[str] = []

    lines.append(f"# {config.APP_NAME} — Data Readiness Report")
    lines.append("")
    lines.append(f"_{config.APP_TAGLINE}_")
    lines.append("")
    lines.append(f"**Dataset:** {name}  ")
    lines.append(f"**Owner:** {inputs.get('dataset_owner') or 'N/A'}  ")
    lines.append(f"**Generated:** {human_readable_timestamp()}  ")
    lines.append(f"**Generation Mode:** {package.get('generation_mode', config.MODE_TEMPLATE)}  ")
    lines.append("")

    # 1. Executive Summary
    lines.append("## 1. Executive Summary")
    lines.append(package["executive_summary"])
    lines.append("")

    # 2. Dataset Overview
    lines.append("## 2. Dataset Overview")
    lines.append(f"- Rows: {audit['shape']['rows']:,}")
    lines.append(f"- Columns: {audit['shape']['columns']}")
    lines.append(f"- Business question: {inputs.get('business_question') or 'N/A'}")
    lines.append(f"- Intended audience: {inputs.get('intended_audience') or 'N/A'}")
    lines.append(f"- Intended use: {inputs.get('intended_use') or 'N/A'}")
    lines.append("")

    # 3. Data Quality Score
    lines.append("## 3. Data Quality Score")
    lines.append(f"**{quality['score']}/100 — {quality['status']}**")
    lines.append("")
    lines.append(_md_table(
        [{"Component": c["name"], "Score": f"{c['score']}/{c['weight']}", "Detail": c["detail"]}
         for c in quality["components"]],
        ["Component", "Score", "Detail"],
    ))
    lines.append("")

    # 4. Dashboard Readiness Score
    lines.append("## 4. Dashboard Readiness Score")
    lines.append(f"**{dashboard['score']}/100 — {dashboard['status']}**")
    lines.append("")
    lines.append(_md_table(
        [{"Check": c["name"], "Score": f"{c['score']}/{c['weight']}", "Status": c["detail"]}
         for c in dashboard["components"]],
        ["Check", "Score", "Status"],
    ))
    lines.append("")

    # 5. Column Profile
    lines.append("## 5. Column Profile")
    lines.append(_md_table(
        [{"Column": p["column"], "Type": p["semantic_type"], "Missing %": p["missing_pct"],
          "Unique": p["unique"], "Samples": clean_text(p["sample_values"])[:60]}
         for p in audit["profiles"]],
        ["Column", "Type", "Missing %", "Unique", "Samples"],
    ))
    lines.append("")

    # 6. Missing Value Report
    lines.append("## 6. Missing Value Report")
    lines.append(f"- Overall missing (true nulls): {audit['missing']['overall_missing_pct']}%")
    lines.append(f"- Effective missing (incl. blank-like): {audit['missing']['effective_missing_pct']}%")
    lines.append(f"- Blank-like placeholders: {audit['missing']['total_blank_like']}")
    lines.append(f"- Columns above threshold: {', '.join(audit['missing']['flagged_columns']) or 'None'}")
    lines.append(f"- Rows with many missing fields: {audit['missing']['rows_many_missing']}")
    lines.append("")

    # 7. Duplicate Record Report
    lines.append("## 7. Duplicate Record Report")
    lines.append(f"- Exact duplicate rows: {audit['duplicates']['exact_duplicate_rows']} "
                 f"({audit['duplicates']['exact_duplicate_pct']}%)")
    if audit["duplicates"]["key_columns_used"]:
        lines.append(f"- Key-based duplicates ({audit['duplicates']['key_columns_used']}): "
                     f"{audit['duplicates']['key_duplicate_rows']}")
    lines.append("")

    # 8. Category Consistency Report
    lines.append("## 8. Category Consistency Report")
    lines.append(_md_table(
        [{"Column": i["column"], "Case conflicts": i["case_conflicts"],
          "Example": clean_text(i.get("example_conflict", ""))[:40],
          "Whitespace": i["whitespace_values"], "Blank-like": i["blank_like_values"],
          "High cardinality": i["high_cardinality"]}
         for i in audit["categories"]["issues"]],
        ["Column", "Case conflicts", "Example", "Whitespace", "Blank-like", "High cardinality"],
    ))
    lines.append("")

    # 9. Date Quality Report
    lines.append("## 9. Date Quality Report")
    lines.append(_md_table(
        [{"Column": r["column"], "Parse %": r["parse_success_rate"],
          "Invalid": r["invalid_dates"], "Future": r["future_dates"],
          "Very old": r["very_old_dates"]}
         for r in audit["dates"]["reports"]],
        ["Column", "Parse %", "Invalid", "Future", "Very old"],
    ))
    lines.append("")

    # 10. Numeric Outlier Report
    lines.append("## 10. Numeric Outlier Report")
    lines.append(_md_table(
        [{"Column": r["column"], "Min": r["min"], "Max": r["max"], "Mean": r["mean"],
          "Median": r["median"], "Std": r["std"], "Outliers": r["outliers"]}
         for r in audit["numeric"]["reports"]],
        ["Column", "Min", "Max", "Mean", "Median", "Std", "Outliers"],
    ))
    lines.append("")

    # 11. Business Readiness Assessment
    b = audit["business"]
    lines.append("## 11. Business Readiness Assessment")
    lines.append(f"- Owner column: {b['owner_column'] or 'Not found'}")
    lines.append(f"- Status column: {b['status_column'] or 'Not found'}")
    lines.append(f"- Date column: {b['date_column'] or 'Not found'}")
    lines.append(f"- Numeric metrics available: {b['has_numeric_metrics']}")
    lines.append(f"- Grouping fields available: {b['has_grouping_fields']}")
    lines.append(f"- Likely ID columns: {', '.join(b['id_columns']) or 'None'}")
    lines.append(f"- Enough records for analysis: {b['enough_records']} ({b['record_count']} rows)")
    lines.append("")

    # 12. Dashboard Readiness Assessment
    d = audit["dashboard"]
    lines.append("## 12. Dashboard Readiness Assessment")
    for label, key in [
        ("Has date column", "has_date_column"),
        ("Has category column", "has_category_column"),
        ("Has numeric column", "has_numeric_column"),
        ("Manageable missing values", "manageable_missing"),
        ("Low duplicate risk", "low_duplicate_risk"),
        ("Has grouping fields", "has_grouping_fields"),
        ("Has summarizable metrics", "has_summarizable_metrics"),
        ("Audit metadata complete", "metadata_complete"),
    ]:
        lines.append(f"- {label}: {'Yes' if d[key] else 'No'}")
    lines.append("")

    # 13. Data Dictionary Draft
    lines.append("## 13. Data Dictionary Draft")
    lines.append(_md_table(
        [{"Column": e["column"], "Type": e["type"], "Dashboard role": e["dashboard_role"],
          "Missing %": e["missing_pct"], "Unique": e["unique_values"],
          "Suggested use": e["suggested_use"],
          "Example values": clean_text(e["example_values"])[:50]}
         for e in package["data_dictionary"]],
        ["Column", "Type", "Dashboard role", "Missing %", "Unique",
         "Suggested use", "Example values"],
    ))
    lines.append("")

    # 14. Data Quality Issue Log
    lines.append("## 14. Data Quality Issue Log")
    lines.append(_md_table(
        [{"Issue Type": i["category"], "Column": i["column"], "Severity": i["severity"],
          "Description": clean_text(i["detail"])[:70],
          "Recommended Fix": clean_text(i.get("recommended_fix", ""))[:70],
          "Business Impact": clean_text(i.get("business_impact", ""))[:70]}
         for i in audit["issue_log"]],
        ["Issue Type", "Column", "Severity", "Description", "Recommended Fix", "Business Impact"],
    ))
    lines.append("")

    # 15. Cleanup Recommendations
    lines.append("## 15. Cleanup Recommendations")
    lines.append(_md_list(package["cleanup_recommendations"]))
    lines.append("")

    # 16. Suggested Chart Gallery
    lines.append("## 16. Suggested Chart Gallery")
    lines.append(_md_table(
        [{"Chart": c["chart"], "Fields": clean_text(c["fields"]),
          "Why": clean_text(c["why"])}
         for c in package.get("chart_gallery", [])],
        ["Chart", "Fields", "Why"],
    ))
    lines.append("")

    # 17. Recommended Dashboard Pages
    lines.append("## 17. Recommended Dashboard Pages")
    lines.append(_md_table(
        [{"Page": p["page"], "Why": clean_text(p["why"]),
          "Requires": p["requires"], "Available": p["available"]}
         for p in package.get("dashboard_pages", [])],
        ["Page", "Why", "Requires", "Available"],
    ))
    lines.append("")

    # 18. Suggested Business Questions
    lines.append("## 18. Suggested Business Questions")
    lines.append(_md_list(package["suggested_business_questions"]))
    lines.append("")

    # 19. Suggested Next Steps
    lines.append("## 19. Suggested Next Steps")
    lines.append(_md_list(package["suggested_next_steps"]))
    lines.append("")

    # 20. Final Data Readiness Summary
    lines.append("## 20. Final Data Readiness Summary")
    lines.append(package["final_summary"])
    lines.append("")
    lines.append("---")
    lines.append(f"_Generated by {config.APP_NAME} v{config.APP_VERSION}._")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Cleaned CSV
# ---------------------------------------------------------------------------
def build_cleaned_dataframe(
    df: pd.DataFrame,
    audit: Dict[str, Any],
    trim_text: bool = True,
    standardize_blanks: bool = True,
    remove_duplicates: bool = True,
    standardize_capitalization: bool = True,
) -> pd.DataFrame:
    """Return a lightly cleaned copy of the dataset.

    Each cleaning step is optional so the UI can offer safe, reversible toggles:
    trim whitespace, normalize blank-like values to NaN, standardize category
    capitalization, and drop exact duplicate rows.
    """
    cleaned = df.copy()

    # Trim whitespace on text columns and replace blank-like tokens with NaN.
    for col in cleaned.columns:
        if not is_text_like(cleaned[col]):
            continue
        if trim_text:
            cleaned[col] = cleaned[col].map(
                lambda v: clean_text(v) if isinstance(v, str) else v
            )
        if standardize_blanks:
            lowered = cleaned[col].astype(str).str.strip().str.lower()
            mask = lowered.isin(config.BLANK_LIKE_VALUES)
            cleaned.loc[mask, col] = pd.NA

    # Standardize capitalization for detected category columns (title case).
    if standardize_capitalization:
        for col in audit["types"]["category_columns"]:
            if col in cleaned.columns and is_text_like(cleaned[col]):
                cleaned[col] = cleaned[col].map(
                    lambda v: str(v).strip().title() if isinstance(v, str) and v else v
                )

    # Drop exact duplicate rows.
    if remove_duplicates:
        cleaned = cleaned.drop_duplicates().reset_index(drop=True)
    return cleaned


def build_column_profile_df(audit: Dict[str, Any]) -> pd.DataFrame:
    return pd.DataFrame(audit["profiles"])


def build_issue_log_df(audit: Dict[str, Any]) -> pd.DataFrame:
    """Return the issue log as a stakeholder-friendly, well-labeled table."""
    columns = {
        "category": "Issue Type",
        "column": "Column Affected",
        "severity": "Severity",
        "detail": "Description",
        "recommended_fix": "Recommended Fix",
        "business_impact": "Business Impact",
    }
    log = audit["issue_log"]
    if not log:
        return pd.DataFrame(columns=list(columns.values()))
    return pd.DataFrame(log).reindex(columns=list(columns.keys())).rename(columns=columns)
