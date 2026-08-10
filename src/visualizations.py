"""Plotly Express visualizations for the audit dashboard."""

from __future__ import annotations

from typing import Any, Dict, List

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from .audit_engine import coerce_numeric

_QUALITY_COLORS = {"good": "#2e7d32", "warn": "#ed6c02", "bad": "#c62828"}


def _score_color(score: float) -> str:
    if score >= 80:
        return _QUALITY_COLORS["good"]
    if score >= 50:
        return _QUALITY_COLORS["warn"]
    return _QUALITY_COLORS["bad"]


def score_gauge(score: float, title: str):
    """Gauge chart for a 0-100 score with colored quality bands."""
    color = _score_color(score)
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        number={"suffix": " / 100"},
        title={"text": title, "font": {"size": 16}},
        gauge={
            "axis": {"range": [0, 100]},
            "bar": {"color": color},
            "steps": [
                {"range": [0, 50], "color": "#fdecea"},
                {"range": [50, 80], "color": "#fff4e5"},
                {"range": [80, 100], "color": "#edf7ed"},
            ],
            "threshold": {
                "line": {"color": color, "width": 4},
                "thickness": 0.8,
                "value": score,
            },
        },
    ))
    fig.update_layout(height=260, margin=dict(l=20, r=20, t=50, b=10))
    return fig


def missing_values_chart(audit: Dict[str, Any]):
    """Bar chart of effective missing percentage (nulls + blank-like) by column."""
    data = [
        {"column": col, "missing_pct": info["effective_missing_pct"]}
        for col, info in audit["missing"]["per_column"].items()
    ]
    df = pd.DataFrame(data).sort_values("missing_pct", ascending=False)
    fig = px.bar(
        df, x="missing_pct", y="column", orientation="h",
        labels={"missing_pct": "Missing / blank-like %", "column": "Column"},
        title="Missing & Blank-like Values by Column",
        color="missing_pct", color_continuous_scale="Reds",
        range_color=[0, 100],
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=max(300, 32 * len(df)))
    return fig


def type_distribution_chart(audit: Dict[str, Any]):
    """Bar chart of column counts by inferred data type."""
    counts = audit["types"]["type_counts"]
    df = pd.DataFrame({"type": list(counts.keys()), "count": list(counts.values())})
    df = df[df["count"] > 0]
    fig = px.bar(
        df, x="type", y="count", color="type", text="count",
        title="Data Type Distribution",
        labels={"type": "Data Type", "count": "Column Count"},
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(showlegend=False)
    return fig


def duplicate_indicator_chart(audit: Dict[str, Any]):
    """Gauge-style indicator for exact duplicate percentage."""
    pct = audit["duplicates"]["exact_duplicate_pct"]
    bar_color = (
        _QUALITY_COLORS["bad"] if pct >= 10
        else _QUALITY_COLORS["warn"] if pct > 0
        else _QUALITY_COLORS["good"]
    )
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=pct,
        number={"suffix": " %"},
        title={"text": "Exact Duplicate Rows (%)"},
        gauge={
            "axis": {"range": [0, max(20, pct + 5)]},
            "bar": {"color": bar_color},
        },
    ))
    fig.update_layout(height=280, margin=dict(l=20, r=20, t=50, b=10))
    return fig


def numeric_distribution_chart(df: pd.DataFrame, column: str):
    """Histogram for a selected numeric column."""
    series = coerce_numeric(df[column]).dropna()
    fig = go.Figure(go.Histogram(x=series, nbinsx=30, marker_color="#1565c0"))
    fig.update_layout(title=f"Distribution of {column}", xaxis_title=column,
                      yaxis_title="Count", height=350)
    return fig


def top_categories_chart(df: pd.DataFrame, column: str, top_n: int = 10):
    """Bar chart of the most frequent values in a categorical column."""
    counts = df[column].astype(str).value_counts().head(top_n).reset_index()
    counts.columns = [column, "count"]
    fig = px.bar(
        counts, x="count", y=column, orientation="h",
        title=f"Top {top_n} Values in {column}",
        color="count", color_continuous_scale="Blues",
    )
    fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=350)
    return fig


def _score_breakdown_chart(components: List[Dict[str, Any]], title: str):
    df = pd.DataFrame(components)
    df["remaining"] = df["weight"] - df["score"]
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["name"], y=df["score"], name="Earned", marker_color="#2e7d32",
        customdata=df[["detail", "weight"]],
        hovertemplate="<b>%{x}</b><br>Earned: %{y} of %{customdata[1]}<br>%{customdata[0]}<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        x=df["name"], y=df["remaining"], name="Lost", marker_color="#e57373",
        hovertemplate="<b>%{x}</b><br>Lost: %{y}<extra></extra>",
    ))
    fig.update_layout(barmode="stack", title=title, yaxis_title="Points",
                      xaxis_title="Scoring Component", height=400,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
    return fig


def quality_breakdown_chart(quality: Dict[str, Any]):
    return _score_breakdown_chart(quality["components"], "Data Quality Score Breakdown")


def dashboard_breakdown_chart(dashboard: Dict[str, Any]):
    return _score_breakdown_chart(dashboard["components"], "Dashboard Readiness Score Breakdown")


def history_trend_chart(history: List[Dict[str, Any]]):
    """Line chart of quality and dashboard scores over saved audits."""
    if not history:
        return None
    df = pd.DataFrame(history).sort_values("id")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["created_at"], y=df["quality_score"],
                             mode="lines+markers", name="Data Quality"))
    fig.add_trace(go.Scatter(x=df["created_at"], y=df["dashboard_score"],
                             mode="lines+markers", name="Dashboard Readiness"))
    fig.update_layout(title="Audit History Trend", xaxis_title="Audit Time",
                      yaxis_title="Score", yaxis_range=[0, 100], height=380)
    return fig


def points_lost_chart(quality: Dict[str, Any], dashboard: Dict[str, Any]):
    """Horizontal bar of points lost per issue area across both scores."""
    rows = []
    for c in quality["components"]:
        if c["lost"] > 0:
            rows.append({"area": f"Quality · {c['name']}", "lost": c["lost"]})
    for c in dashboard["components"]:
        if c["lost"] > 0:
            rows.append({"area": f"Dashboard · {c['name']}", "lost": c["lost"]})
    if not rows:
        fig = go.Figure()
        fig.add_annotation(text="No points lost — full marks!", showarrow=False,
                           font=dict(size=16))
        fig.update_layout(height=300, title="Points Lost by Issue Area")
        return fig
    df = pd.DataFrame(rows).sort_values("lost", ascending=True)
    fig = px.bar(
        df, x="lost", y="area", orientation="h", text="lost",
        title="Points Lost by Issue Area",
        labels={"lost": "Points lost", "area": "Issue area"},
        color="lost", color_continuous_scale="Reds",
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(height=max(320, 30 * len(df)), coloraxis_showscale=False)
    return fig


def history_scores_bar(history: List[Dict[str, Any]]):
    """Grouped bar of quality vs dashboard score per saved audit."""
    if not history:
        return None
    df = pd.DataFrame(history).sort_values("id")
    label = df["dataset_name"].astype(str) + " (#" + df["id"].astype(str) + ")"
    fig = go.Figure()
    fig.add_trace(go.Bar(x=label, y=df["quality_score"], name="Data Quality",
                         marker_color="#1565c0"))
    fig.add_trace(go.Bar(x=label, y=df["dashboard_score"], name="Dashboard Readiness",
                         marker_color="#2e7d32"))
    fig.update_layout(barmode="group", title="Scores by Saved Audit",
                      xaxis_title="Audit", yaxis_title="Score",
                      yaxis_range=[0, 100], height=380)
    return fig


def history_issue_trend(history: List[Dict[str, Any]]):
    """Line chart of the number of logged issues over saved audits."""
    if not history:
        return None
    df = pd.DataFrame(history).sort_values("id")
    fig = go.Figure(go.Scatter(x=df["created_at"], y=df["issue_count"],
                               mode="lines+markers", name="Issues",
                               line=dict(color="#c62828")))
    fig.update_layout(title="Logged Issues Over Time", xaxis_title="Audit Time",
                      yaxis_title="Issue count", height=340)
    return fig
