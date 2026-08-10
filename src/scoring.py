"""Scoring logic for data quality and dashboard readiness.

Both scores run from 0 to 100. Each returns a breakdown of the individual
components so the UI can render transparent, explainable score cards.
"""

from __future__ import annotations

from typing import Any, Dict, List


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def quality_status(score: float) -> Dict[str, str]:
    """Map a data quality score to a status label and color."""
    if score >= 80:
        return {"label": "High Quality", "color": "#2e7d32", "emoji": "🟢"}
    if score >= 50:
        return {"label": "Needs Cleanup", "color": "#ed6c02", "emoji": "🟡"}
    return {"label": "High Risk", "color": "#c62828", "emoji": "🔴"}


def dashboard_status(score: float) -> Dict[str, str]:
    """Map a dashboard readiness score to a status label and color."""
    if score >= 80:
        return {"label": "Dashboard Ready", "color": "#2e7d32", "emoji": "🟢"}
    if score >= 50:
        return {"label": "Needs Preparation", "color": "#ed6c02", "emoji": "🟡"}
    return {"label": "Not Ready for Dashboard", "color": "#c62828", "emoji": "🔴"}


# ---------------------------------------------------------------------------
# Data quality score
# ---------------------------------------------------------------------------
def score_data_quality(audit: Dict[str, Any]) -> Dict[str, Any]:
    """Compute a 0-100 data quality score with a component breakdown.

    Each component starts at its full weight and loses points as issues are
    found. Weights sum to 100. Every component reports the points earned, the
    maximum possible, and a plain-language reason so the score is transparent.
    """
    total_rows = max(audit["shape"]["rows"], 1)
    total_cols = max(audit["shape"]["columns"], 1)

    def component(name: str, weight: float, score: float, detail: str) -> Dict[str, Any]:
        score = round(_clamp(score, 0, weight), 1)
        return {
            "name": name,
            "weight": weight,
            "max": weight,
            "score": score,
            "lost": round(weight - score, 1),
            "detail": detail,
        }

    components: List[Dict[str, Any]] = []

    # 1. Missing values (weight 20) -- 50% effectively missing drives this to 0.
    missing_pct = audit["missing"]["effective_missing_pct"]
    components.append(component(
        "Missing Values", 20, 20 - (missing_pct / 100) * 20 * 2,
        f"{missing_pct}% of cells missing or blank-like",
    ))

    # 2. Duplicate rows (weight 15) -- ~33% duplicates drives this to 0.
    dupe_pct = audit["duplicates"]["exact_duplicate_pct"]
    components.append(component(
        "Duplicate Rows", 15, 15 - (dupe_pct / 100) * 15 * 3,
        f"{dupe_pct}% duplicate rows ({audit['duplicates']['exact_duplicate_rows']} rows)",
    ))

    # 3. Outlier risk (weight 10) -- based on average outlier share.
    outlier_cols = [r for r in audit["numeric"]["reports"] if r["outliers"] > 0]
    avg_outlier_pct = (
        sum(r["outlier_pct"] for r in outlier_cols) / len(outlier_cols)
        if outlier_cols else 0.0
    )
    components.append(component(
        "Outlier Risk", 10, 10 - (avg_outlier_pct / 100) * 10 * 2,
        f"{len(outlier_cols)} column(s) with outliers (avg {round(avg_outlier_pct, 1)}%)",
    ))

    # 4. Category consistency (weight 15) -- 4 points lost per affected column.
    cat_issue_cols = len(audit["categories"]["columns_with_issues"])
    components.append(component(
        "Category Consistency", 15, 15 - cat_issue_cols * 4,
        f"{cat_issue_cols} column(s) with consistency issues",
    ))

    # 5. Date parsing (weight 10) -- scaled by average parse success rate.
    date_reports = audit["dates"]["reports"]
    if date_reports:
        avg_success = sum(r["parse_success_rate"] for r in date_reports) / len(date_reports)
        components.append(component(
            "Date Quality", 10, (avg_success / 100) * 10,
            f"{round(avg_success, 1)}% average date parse success",
        ))
    else:
        components.append(component(
            "Date Quality", 10, 10, "no date columns (no date risk)",
        ))

    # 6. Mixed data types (weight 10) -- 4 points lost per mixed-type column.
    mixed_cols = len(audit["types"]["mixed_type_columns"])
    components.append(component(
        "Consistent Types", 10, 10 - mixed_cols * 4,
        f"{mixed_cols} mixed-type column(s)",
    ))

    # 7. Blank-like values (weight 10) -- counted across the whole dataset.
    blank_total = audit["missing"].get("total_blank_like", 0)
    blank_pct = (blank_total / (total_rows * total_cols)) * 100
    components.append(component(
        "Blank-like Values", 10, 10 - blank_pct * 5,
        f"{blank_total} placeholder value(s) (N/A, TBD, unknown, ...)",
    ))

    # 8. Key column completeness (weight 10) -- 2 points lost per flagged column.
    flagged = len(audit["missing"]["flagged_columns"])
    components.append(component(
        "Key Completeness", 10, 10 - flagged * 2,
        f"{flagged} column(s) above the missing-value threshold",
    ))

    total_score = round(sum(c["score"] for c in components), 1)
    status = quality_status(total_score)

    return {
        "score": total_score,
        "max_score": 100,
        "status": status["label"],
        "color": status["color"],
        "emoji": status["emoji"],
        "components": components,
    }


# ---------------------------------------------------------------------------
# Dashboard readiness score
# ---------------------------------------------------------------------------
def score_dashboard_readiness(audit: Dict[str, Any]) -> Dict[str, Any]:
    """Compute a 0-100 dashboard readiness score with a component breakdown."""
    d = audit["dashboard"]
    components: List[Dict[str, Any]] = []

    checks = [
        ("Numeric Metrics", d["has_numeric_column"], 18),
        ("Category Dimensions", d["has_category_column"], 15),
        ("Date/Time Column", d["has_date_column"], 15),
        ("Low Missing Risk", d["manageable_missing"], 12),
        ("Low Duplicate Risk", d["low_duplicate_risk"], 12),
        ("Grouping Fields", d["has_grouping_fields"], 8),
        ("Summarizable Metrics", d["has_summarizable_metrics"], 8),
        ("Enough Records", d["enough_records"], 6),
        ("Audit Metadata", d["metadata_complete"], 6),
    ]

    for name, passed, weight in checks:
        score = float(weight) if passed else 0.0
        components.append({
            "name": name,
            "weight": weight,
            "max": weight,
            "score": score,
            "lost": round(weight - score, 1),
            "detail": "Present" if passed else "Missing / weak",
        })

    total_score = round(sum(c["score"] for c in components), 1)
    status = dashboard_status(total_score)

    return {
        "score": total_score,
        "max_score": 100,
        "status": status["label"],
        "color": status["color"],
        "emoji": status["emoji"],
        "components": components,
    }
