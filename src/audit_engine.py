"""Core data auditing engine using pandas and numpy.

The ``run_audit`` function returns a plain dictionary of audit results that
the scoring, template, export, and visualization layers all consume. Keeping
the output as simple Python types keeps the rest of the app decoupled from
pandas internals and makes the results easy to serialize.
"""

from __future__ import annotations

import warnings
from typing import Any, Dict, List

import numpy as np
import pandas as pd

from . import config
from .utils import clean_text


def _to_datetime(values: pd.Series) -> pd.Series:
    """Parse a series to datetimes, quietly coercing unparseable values."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return pd.to_datetime(values, errors="coerce")


def coerce_numeric(series: pd.Series) -> pd.Series:
    """Return a numeric version of a series, handling numbers stored as text.

    Already-numeric columns are returned unchanged. Object columns have thousands
    separators and surrounding spaces stripped before coercion so values like
    "1,200" or " 45 " parse correctly. Unparseable values become NaN.
    """
    if pd.api.types.is_numeric_dtype(series):
        return series
    cleaned = (
        series.astype(str)
        .str.strip()
        .str.replace(",", "", regex=False)
    )
    return pd.to_numeric(cleaned, errors="coerce")


def is_blank_like(series: pd.Series) -> pd.Series:
    """Boolean mask marking placeholder values such as 'N/A', 'TBD', '-'."""
    lowered = series.astype(str).str.strip().str.lower()
    return lowered.isin(config.BLANK_LIKE_VALUES)


def is_text_like(series: pd.Series) -> bool:
    """True for text columns (object or pandas/Arrow string dtypes).

    Newer pandas may back string columns with a dedicated ``str``/``string``
    dtype instead of ``object``, so a plain ``dtype == object`` check misses
    them.
    """
    if series.dtype == object:
        return True
    return pd.api.types.is_string_dtype(series) and not pd.api.types.is_numeric_dtype(series)


# ---------------------------------------------------------------------------
# Type inference helpers
# ---------------------------------------------------------------------------
def _is_date_like(series: pd.Series, sample_size: int = 200) -> bool:
    """Heuristically decide whether a text/object column holds dates."""
    non_null = series.dropna()
    if non_null.empty:
        return False
    sample = non_null.astype(str).head(sample_size)
    # Skip pure numeric-looking values so plain integers are not read as dates.
    if sample.str.fullmatch(r"-?\d+(\.\d+)?").mean() > 0.8:
        return False
    parsed = _to_datetime(sample)
    return parsed.notna().mean() >= 0.7


def _is_boolean_like(series: pd.Series) -> bool:
    """Detect columns that only contain boolean-style values."""
    values = {
        clean_text(v).lower()
        for v in series.dropna().unique()
    }
    if not values:
        return False
    boolean_sets = [
        {"true", "false"},
        {"yes", "no"},
        {"y", "n"},
        {"0", "1"},
        {"t", "f"},
    ]
    return any(values.issubset(bset) for bset in boolean_sets)


def _infer_semantic_type(series: pd.Series) -> str:
    """Return one of: numeric, date, boolean, category, text."""
    if pd.api.types.is_bool_dtype(series):
        return "boolean"
    if pd.api.types.is_numeric_dtype(series):
        return "numeric"
    if pd.api.types.is_datetime64_any_dtype(series):
        return "date"

    non_null = series.dropna()
    if non_null.empty:
        return "text"

    if _is_boolean_like(series):
        return "boolean"
    if _is_date_like(series):
        return "date"

    # Try numeric coercion for object columns holding numbers stored as text.
    coerced = coerce_numeric(non_null)
    if coerced.notna().mean() >= 0.9:
        return "numeric"

    n_unique = non_null.nunique()
    ratio = n_unique / max(len(non_null), 1)
    if ratio <= config.HIGH_CARDINALITY_RATIO or n_unique <= 50:
        return "category"
    return "text"


def _has_mixed_types(series: pd.Series, sample_size: int = 500) -> bool:
    """Detect object columns whose values mix numbers and non-numbers."""
    non_null = series.dropna().head(sample_size)
    if non_null.empty or pd.api.types.is_numeric_dtype(series):
        return False
    numeric_flags = []
    for value in non_null:
        text = clean_text(value).replace(",", "")
        if text == "":
            continue
        try:
            float(text)
            numeric_flags.append(True)
        except ValueError:
            numeric_flags.append(False)
    if not numeric_flags:
        return False
    numeric_share = sum(numeric_flags) / len(numeric_flags)
    return 0.1 < numeric_share < 0.9


# ---------------------------------------------------------------------------
# Column profiling
# ---------------------------------------------------------------------------
def profile_columns(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """Build a per-column profile with types, missing counts and samples."""
    total_rows = len(df)
    profiles: List[Dict[str, Any]] = []

    for col in df.columns:
        series = df[col]
        missing = int(series.isna().sum())
        non_null = total_rows - missing
        unique = int(series.nunique(dropna=True))
        blank_like = int(is_blank_like(series.dropna()).sum()) if is_text_like(series) else 0
        samples = [
            clean_text(v)
            for v in series.dropna().unique()[:5]
        ]
        profiles.append(
            {
                "column": str(col),
                "dtype": str(series.dtype),
                "semantic_type": _infer_semantic_type(series),
                "non_null": non_null,
                "missing": missing,
                "missing_pct": round((missing / total_rows) * 100, 2) if total_rows else 0.0,
                "blank_like": blank_like,
                "unique": unique,
                "sample_values": ", ".join(samples) if samples else "",
                "mixed_types": _has_mixed_types(series),
            }
        )
    return profiles


# ---------------------------------------------------------------------------
# Missing value analysis
# ---------------------------------------------------------------------------
def analyze_missing(df: pd.DataFrame) -> Dict[str, Any]:
    total_rows = len(df)
    per_column = {}
    flagged_columns = []
    total_blank_like = 0
    for col in df.columns:
        series = df[col]
        missing = int(series.isna().sum())
        # Blank-like placeholders count as "effectively missing".
        blank_like = int(is_blank_like(series.dropna()).sum()) if is_text_like(series) else 0
        total_blank_like += blank_like
        effective_missing = missing + blank_like
        pct = (missing / total_rows) * 100 if total_rows else 0.0
        effective_pct = (effective_missing / total_rows) * 100 if total_rows else 0.0
        per_column[str(col)] = {
            "missing": missing,
            "missing_pct": round(pct, 2),
            "blank_like": blank_like,
            "effective_missing_pct": round(effective_pct, 2),
        }
        if effective_pct >= config.MISSING_COLUMN_THRESHOLD * 100:
            flagged_columns.append(str(col))

    row_missing_counts = df.isna().sum(axis=1)
    threshold = max(1, int(df.shape[1] * config.ROW_MISSING_THRESHOLD))
    rows_many_missing = int((row_missing_counts >= threshold).sum())

    total_cells = total_rows * df.shape[1]
    total_missing = int(df.isna().sum().sum())
    overall_pct = (total_missing / total_cells) * 100 if total_cells else 0.0
    effective_overall_pct = (
        ((total_missing + total_blank_like) / total_cells) * 100 if total_cells else 0.0
    )

    return {
        "per_column": per_column,
        "flagged_columns": flagged_columns,
        "rows_many_missing": rows_many_missing,
        "total_missing": total_missing,
        "total_blank_like": total_blank_like,
        "overall_missing_pct": round(overall_pct, 2),
        "effective_missing_pct": round(effective_overall_pct, 2),
    }


# ---------------------------------------------------------------------------
# Duplicate analysis
# ---------------------------------------------------------------------------
def analyze_duplicates(df: pd.DataFrame, key_columns: List[str] | None = None) -> Dict[str, Any]:
    total_rows = len(df)
    exact_dupes = int(df.duplicated(keep="first").sum())
    result = {
        "exact_duplicate_rows": exact_dupes,
        "exact_duplicate_pct": round((exact_dupes / total_rows) * 100, 2) if total_rows else 0.0,
        "key_duplicate_rows": 0,
        "key_columns_used": [],
    }

    if key_columns:
        valid_keys = [c for c in key_columns if c in df.columns]
        if valid_keys:
            key_dupes = int(df.duplicated(subset=valid_keys, keep="first").sum())
            result["key_duplicate_rows"] = key_dupes
            result["key_columns_used"] = valid_keys
    return result


# ---------------------------------------------------------------------------
# Data type analysis
# ---------------------------------------------------------------------------
def analyze_types(profiles: List[Dict[str, Any]]) -> Dict[str, Any]:
    buckets = {"numeric": [], "date": [], "category": [], "text": [], "boolean": []}
    mixed = []
    for p in profiles:
        buckets.setdefault(p["semantic_type"], []).append(p["column"])
        if p["mixed_types"]:
            mixed.append(p["column"])
    return {
        "numeric_columns": buckets["numeric"],
        "date_columns": buckets["date"],
        "category_columns": buckets["category"],
        "text_columns": buckets["text"],
        "boolean_columns": buckets["boolean"],
        "mixed_type_columns": mixed,
        "type_counts": {k: len(v) for k, v in buckets.items()},
    }


# ---------------------------------------------------------------------------
# Category consistency analysis
# ---------------------------------------------------------------------------
def analyze_categories(df: pd.DataFrame, category_columns: List[str]) -> Dict[str, Any]:
    issues: List[Dict[str, Any]] = []
    total_rows = len(df)

    for col in category_columns:
        series = df[col].dropna().astype(str)
        if series.empty:
            continue

        # Inconsistent capitalization: same value after lower/strip but different raw.
        lowered = series.str.strip().str.lower()
        raw_by_norm = series.groupby(lowered).unique()
        case_conflicts = int(sum(len(v) > 1 for v in raw_by_norm))
        # Capture one concrete example to make the issue tangible.
        example = ""
        for variants in raw_by_norm:
            if len(variants) > 1:
                example = " / ".join(map(str, variants[:3]))
                break

        # Leading/trailing whitespace.
        whitespace_hits = int((series != series.str.strip()).sum())

        # Blank-like placeholder values.
        blank_hits = int(lowered.isin(config.BLANK_LIKE_VALUES).sum())

        # High cardinality relative to row count.
        n_unique = series.nunique()
        cardinality_ratio = n_unique / max(total_rows, 1)
        high_cardinality = cardinality_ratio >= config.HIGH_CARDINALITY_RATIO

        if case_conflicts or whitespace_hits or blank_hits or high_cardinality:
            issues.append(
                {
                    "column": col,
                    "case_conflicts": case_conflicts,
                    "example_conflict": example,
                    "whitespace_values": whitespace_hits,
                    "blank_like_values": blank_hits,
                    "unique_values": n_unique,
                    "high_cardinality": high_cardinality,
                }
            )

    return {
        "issues": issues,
        "columns_with_issues": [i["column"] for i in issues],
    }


# ---------------------------------------------------------------------------
# Date quality analysis
# ---------------------------------------------------------------------------
def analyze_dates(df: pd.DataFrame, date_columns: List[str]) -> Dict[str, Any]:
    reports: List[Dict[str, Any]] = []
    now = pd.Timestamp.now()
    old_cutoff = pd.Timestamp("1990-01-01")

    for col in date_columns:
        series = df[col]
        non_null = series.dropna()
        parsed = _to_datetime(non_null.astype(str))
        total = len(non_null)
        valid = int(parsed.notna().sum())
        invalid = total - valid
        success_rate = (valid / total) * 100 if total else 0.0

        valid_dates = parsed.dropna()
        future_dates = int((valid_dates > now).sum())
        very_old = int((valid_dates < old_cutoff).sum())

        reports.append(
            {
                "column": col,
                "parse_success_rate": round(success_rate, 2),
                "invalid_dates": invalid,
                "missing_dates": int(series.isna().sum()),
                "future_dates": future_dates,
                "very_old_dates": very_old,
                "min_date": str(valid_dates.min()) if not valid_dates.empty else "",
                "max_date": str(valid_dates.max()) if not valid_dates.empty else "",
            }
        )
    return {"reports": reports}


# ---------------------------------------------------------------------------
# Numeric quality analysis
# ---------------------------------------------------------------------------
def analyze_numeric(df: pd.DataFrame, numeric_columns: List[str]) -> Dict[str, Any]:
    reports: List[Dict[str, Any]] = []

    for col in numeric_columns:
        # Coerce object columns that hold numbers stored as text.
        series = coerce_numeric(df[col]).dropna()
        if series.empty:
            continue

        q1 = series.quantile(0.25)
        q3 = series.quantile(0.75)
        iqr = q3 - q1
        lower = q1 - config.OUTLIER_IQR_MULTIPLIER * iqr
        upper = q3 + config.OUTLIER_IQR_MULTIPLIER * iqr
        outliers = int(((series < lower) | (series > upper)).sum())
        negatives = int((series < 0).sum())

        reports.append(
            {
                "column": col,
                "min": round(float(series.min()), 4),
                "max": round(float(series.max()), 4),
                "mean": round(float(series.mean()), 4),
                "median": round(float(series.median()), 4),
                "std": round(float(series.std(ddof=0)), 4),
                "outliers": outliers,
                "outlier_pct": round((outliers / len(series)) * 100, 2),
                "negative_values": negatives,
            }
        )
    return {"reports": reports}


# ---------------------------------------------------------------------------
# Business & dashboard readiness checks
# ---------------------------------------------------------------------------
def _looks_like_id(column: str, profile: Dict[str, Any], total_rows: int) -> bool:
    name = column.lower()
    if any(tok in name for tok in ("id", "key", "code", "number", "no.")):
        # ID columns are usually highly unique.
        if profile["unique"] >= total_rows * 0.8:
            return True
    return False


def check_business_readiness(df: pd.DataFrame, profiles, types, inputs) -> Dict[str, Any]:
    total_rows = len(df)
    columns_lower = {str(c).lower(): str(c) for c in df.columns}

    def find_column(keywords):
        for low, original in columns_lower.items():
            if any(k in low for k in keywords):
                return original
        return None

    owner_col = inputs.get("expected_owner_column") or find_column(["owner", "assignee", "responsible"])
    status_col = inputs.get("expected_status_column") or find_column(["status", "state", "stage"])
    date_col = inputs.get("expected_date_column") or (types["date_columns"][0] if types["date_columns"] else None)

    id_columns = [
        p["column"] for p in profiles if _looks_like_id(p["column"], p, total_rows)
    ]

    return {
        "has_owner_column": bool(owner_col),
        "owner_column": owner_col,
        "has_status_column": bool(status_col),
        "status_column": status_col,
        "has_date_column": bool(date_col),
        "date_column": date_col,
        "has_numeric_metrics": len(types["numeric_columns"]) > 0,
        "has_grouping_fields": len(types["category_columns"]) > 0,
        "id_columns": id_columns,
        "enough_records": total_rows >= config.MIN_RECORDS_FOR_ANALYSIS,
        "record_count": total_rows,
        "key_fields_present": bool(inputs.get("expected_key_columns"))
        and all(
            k.strip() in df.columns
            for k in str(inputs.get("expected_key_columns", "")).split(",")
            if k.strip()
        ),
    }


def check_dashboard_readiness(df, types, missing, duplicates, inputs) -> Dict[str, Any]:
    total_rows = len(df)
    has_date = len(types["date_columns"]) > 0
    has_category = len(types["category_columns"]) > 0 or len(types["boolean_columns"]) > 0
    has_numeric = len(types["numeric_columns"]) > 0
    manageable_missing = missing["effective_missing_pct"] < 20
    low_duplicates = duplicates["exact_duplicate_pct"] < 10
    metadata_fields = ["dataset_name", "dataset_owner", "business_question", "intended_use"]
    metadata_complete = sum(1 for f in metadata_fields if inputs.get(f)) >= 2

    return {
        "has_date_column": has_date,
        "has_category_column": has_category,
        "has_numeric_column": has_numeric,
        "manageable_missing": manageable_missing,
        "low_duplicate_risk": low_duplicates,
        "has_grouping_fields": has_category,
        "has_summarizable_metrics": has_numeric,
        "metadata_complete": metadata_complete,
        "enough_records": total_rows >= config.MIN_RECORDS_FOR_ANALYSIS,
    }


# ---------------------------------------------------------------------------
# Issue log builder
# ---------------------------------------------------------------------------
def build_issue_log(audit: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Flatten audit findings into a list of issue records for export.

    Each record carries a business-friendly recommended fix and a plain-language
    business impact so the log is ready for a stakeholder or portfolio review.
    """
    issues: List[Dict[str, Any]] = []

    for col in audit["missing"]["flagged_columns"]:
        info = audit["missing"]["per_column"][col]
        pct = info["effective_missing_pct"]
        blank_note = (
            f" (includes {info['blank_like']} blank-like value(s))"
            if info["blank_like"] else ""
        )
        issues.append({
            "category": "Missing Values",
            "column": col,
            "severity": "High" if pct >= 50 else "Medium",
            "detail": f"{pct}% of values are missing or blank-like{blank_note}.",
            "recommended_fix": (
                f"Impute, backfill, or source the missing values in `{col}`; "
                "drop the column if it is not needed."
            ),
            "business_impact": (
                "Metrics and filters built on this column will be incomplete or "
                "misleading, understating totals and skewing breakdowns."
            ),
        })

    if audit["duplicates"]["exact_duplicate_rows"] > 0:
        issues.append({
            "category": "Duplicates",
            "column": "(entire row)",
            "severity": "High" if audit["duplicates"]["exact_duplicate_pct"] >= 10 else "Medium",
            "detail": f"{audit['duplicates']['exact_duplicate_rows']} exact duplicate rows.",
            "recommended_fix": "Remove exact duplicate rows or confirm they are legitimate repeats.",
            "business_impact": "Duplicates inflate counts, sums, and averages, overstating performance.",
        })

    for item in audit["categories"]["issues"]:
        details = []
        fixes = []
        if item["case_conflicts"]:
            variant = f" (e.g. {item['example_conflict']})" if item.get("example_conflict") else ""
            details.append(f"{item['case_conflicts']} inconsistent capitalization group(s){variant}")
            fixes.append("standardize capitalization")
        if item["whitespace_values"]:
            details.append(f"{item['whitespace_values']} value(s) with extra spaces")
            fixes.append("trim surrounding whitespace")
        if item["blank_like_values"]:
            details.append(f"{item['blank_like_values']} blank-like value(s)")
            fixes.append("convert blank-like placeholders to true nulls")
        if item["high_cardinality"]:
            details.append(f"high cardinality ({item['unique_values']} unique values)")
            fixes.append("group rare values or treat as an identifier rather than a dimension")
        if details:
            issues.append({
                "category": "Category Consistency",
                "column": item["column"],
                "severity": "Medium",
                "detail": "; ".join(details) + ".",
                "recommended_fix": ("In `%s`: " % item["column"]) + "; ".join(fixes) + ".",
                "business_impact": (
                    "The same category will split into multiple groups, fragmenting "
                    "charts and double-counting segments."
                ),
            })

    for rep in audit["dates"]["reports"]:
        problems = []
        if rep["parse_success_rate"] < 95:
            problems.append(f"{rep['parse_success_rate']}% parse success")
        if rep["invalid_dates"]:
            problems.append(f"{rep['invalid_dates']} invalid dates")
        if rep["future_dates"]:
            problems.append(f"{rep['future_dates']} future dates")
        if rep["very_old_dates"]:
            problems.append(f"{rep['very_old_dates']} very old dates")
        if problems:
            issues.append({
                "category": "Date Quality",
                "column": rep["column"],
                "severity": "Medium",
                "detail": "; ".join(problems) + ".",
                "recommended_fix": (
                    f"Standardize `{rep['column']}` to a single date format and "
                    "correct invalid or out-of-range values."
                ),
                "business_impact": (
                    "Time-series trends, date filters, and period comparisons will be "
                    "unreliable or break entirely."
                ),
            })

    for rep in audit["numeric"]["reports"]:
        if rep["outliers"] > 0:
            issues.append({
                "category": "Numeric Outliers",
                "column": rep["column"],
                "severity": "Low" if rep["outlier_pct"] < 5 else "Medium",
                "detail": f"{rep['outliers']} potential outliers ({rep['outlier_pct']}%).",
                "recommended_fix": (
                    f"Review extreme values in `{rep['column']}`; correct data-entry "
                    "errors or cap/flag genuine outliers."
                ),
                "business_impact": "Outliers distort averages and totals, misrepresenting typical values.",
            })

    for col in audit["types"]["mixed_type_columns"]:
        issues.append({
            "category": "Mixed Data Types",
            "column": col,
            "severity": "Medium",
            "detail": "Column mixes numeric and non-numeric values.",
            "recommended_fix": f"Separate or convert values in `{col}` so it holds one consistent type.",
            "business_impact": "Aggregations and sorting behave unpredictably, and charts may fail to render.",
        })

    return issues


# ---------------------------------------------------------------------------
# Top-level orchestration
# ---------------------------------------------------------------------------
def run_audit(df: pd.DataFrame, inputs: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Run the full data readiness audit and return a results dictionary."""
    inputs = inputs or {}

    key_columns = [
        c.strip()
        for c in str(inputs.get("expected_key_columns", "")).split(",")
        if c.strip()
    ]

    profiles = profile_columns(df)
    types = analyze_types(profiles)
    missing = analyze_missing(df)
    duplicates = analyze_duplicates(df, key_columns)
    categories = analyze_categories(df, types["category_columns"])
    dates = analyze_dates(df, types["date_columns"])
    numeric = analyze_numeric(df, types["numeric_columns"])
    business = check_business_readiness(df, profiles, types, inputs)
    dashboard = check_dashboard_readiness(df, types, missing, duplicates, inputs)

    audit: Dict[str, Any] = {
        "shape": {"rows": int(df.shape[0]), "columns": int(df.shape[1])},
        "profiles": profiles,
        "types": types,
        "missing": missing,
        "duplicates": duplicates,
        "categories": categories,
        "dates": dates,
        "numeric": numeric,
        "business": business,
        "dashboard": dashboard,
        "inputs": inputs,
    }
    audit["issue_log"] = build_issue_log(audit)
    return audit
