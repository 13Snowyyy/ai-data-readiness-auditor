"""AI Data Readiness Auditor -- Streamlit application.

Run with:  streamlit run app.py
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src import config, db, exporters, visualizations
from src.audit_engine import run_audit
from src.providers import get_provider
from src.sample_data import generate_messy_dataframe
from src.scoring import score_dashboard_readiness, score_data_quality
from src.utils import safe_file_name, timestamp_slug
from src.validators import load_dataframe, validate_column_names, validate_dataframe

# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title=config.APP_NAME,
    page_icon="🧹",
    layout="wide",
    initial_sidebar_state="expanded",
)

config.ensure_folders()
db.init_db()

# Session state defaults.
for key, default in {
    "df": None,
    "audit": None,
    "quality": None,
    "dashboard": None,
    "package": None,
    "inputs": {},
    "source_name": "",
}.items():
    st.session_state.setdefault(key, default)


# ---------------------------------------------------------------------------
# Sidebar: mode + metadata inputs
# ---------------------------------------------------------------------------
def render_sidebar() -> dict:
    st.sidebar.title(config.APP_NAME)
    st.sidebar.caption(config.APP_TAGLINE)
    st.sidebar.divider()

    st.sidebar.subheader("Generation Mode")
    mode = st.sidebar.radio(
        "Choose how narratives are generated:",
        [config.MODE_TEMPLATE, config.MODE_LLM],
        index=0,
        help="Template Engine Mode works fully offline with no API key.",
    )

    if mode == config.MODE_LLM and not config.llm_mode_available():
        st.sidebar.warning(
            "LLM Enhanced Mode is not configured. The app will use "
            "Template Engine Mode instead."
        )
        active_mode = config.MODE_TEMPLATE
    else:
        active_mode = mode
    st.sidebar.info(f"Active mode: **{active_mode}**")

    if active_mode == config.MODE_LLM:
        provider = config.get_active_provider() or "unknown"
        model = config.get_model(provider) or "(default)"
        st.sidebar.caption(f"Provider: `{provider}` · Model: `{model}`")
        st.sidebar.caption(
            "Keys are read from environment variables only and are never stored."
        )

    st.sidebar.divider()
    st.sidebar.subheader("Audit Configuration")
    inputs = {
        "dataset_name": st.sidebar.text_input("Dataset name"),
        "dataset_owner": st.sidebar.text_input("Dataset owner"),
        "business_question": st.sidebar.text_area("Business question", height=70),
        "intended_audience": st.sidebar.text_input("Intended audience"),
        "intended_use": st.sidebar.selectbox(
            "Intended use",
            ["", "Dashboard", "Report", "Analysis", "AI/LLM input",
             "Executive summary", "Operational tracker", "Other"],
        ),
        "expected_key_columns": st.sidebar.text_input(
            "Expected key columns (comma-separated)"
        ),
        "expected_date_column": st.sidebar.text_input("Expected date column"),
        "expected_owner_column": st.sidebar.text_input("Expected owner column"),
        "expected_status_column": st.sidebar.text_input("Expected status column"),
        "notes": st.sidebar.text_area("Notes", height=70),
    }
    inputs["_active_mode"] = active_mode
    return inputs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def score_card(label: str, score: float, status: str, color: str, emoji: str) -> None:
    st.markdown(
        f"""
        <div style="border:1px solid #e0e0e0;border-radius:12px;padding:16px;
                    text-align:center;background:#fafafa;">
            <div style="font-size:0.9rem;color:#555;">{label}</div>
            <div style="font-size:2.4rem;font-weight:700;color:{color};">
                {score}<span style="font-size:1rem;color:#999;">/100</span>
            </div>
            <div style="font-size:1rem;font-weight:600;color:{color};">{emoji} {status}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_component_breakdown(components: list) -> None:
    """Show each scoring component as a labeled progress bar for transparency."""
    for c in components:
        earned, total = c["score"], c["weight"]
        st.write(f"**{c['name']}** — {earned}/{total} pts · {c['detail']}")
        st.progress(earned / total if total else 0.0)


def render_score_warnings(quality: dict, dashboard: dict) -> None:
    """Show the required decision-safety warnings based on the scores."""
    if quality["score"] < 50:
        st.error(
            "⚠️ Do not rely on this dataset for decision-making until the "
            "critical data quality issues are resolved."
        )
    if dashboard["score"] < 50:
        st.error(
            "⚠️ Do not build a dashboard from this dataset yet. Clean and "
            "standardize the data first."
        )
    if quality["score"] >= 80 and dashboard["score"] >= 80:
        st.success("✅ This dataset looks trustworthy and dashboard-ready.")


def run_full_audit(df: pd.DataFrame, inputs: dict) -> tuple[bool, str]:
    """Run the audit pipeline. Returns (success, error_message)."""
    try:
        audit = run_audit(df, inputs)
        quality = score_data_quality(audit)
        dashboard = score_dashboard_readiness(audit)
        provider = get_provider(inputs.get("_active_mode", config.MODE_TEMPLATE),
                                config.get_selected_provider())
        package = provider.generate_data_readiness_narrative(
            inputs, audit, quality, dashboard
        )
    except Exception as exc:  # surface any unexpected failure to the user
        return False, f"The audit could not be completed: {exc}"

    st.session_state.update(
        audit=audit, quality=quality, dashboard=dashboard,
        package=package, inputs=inputs,
    )
    return True, ""


# ---------------------------------------------------------------------------
# Tab 1: Upload & Preview
# ---------------------------------------------------------------------------
def tab_upload(inputs: dict) -> None:
    st.header("Upload & Preview")
    st.write(
        "Upload a **CSV** or **Excel (.xlsx)** file, or load the built-in sample "
        "dataset to try the tool. Add optional details in the sidebar to enrich the audit."
    )

    col1, col2 = st.columns([3, 1])
    with col1:
        uploaded = st.file_uploader(
            "Choose a file", type=["csv", "xlsx"],
            help="Supported formats: .csv and .xlsx (Excel).",
        )
    with col2:
        st.write("")
        st.write("")
        if st.button("Load sample dataset", use_container_width=True,
                     help="Load a synthetic messy dataset with common issues."):
            st.session_state.df = generate_messy_dataframe()
            st.session_state.source_name = "sample_messy_dataset.csv"
            # Clear any previous audit so results reflect the new data.
            st.session_state.audit = None
            st.success("Sample dataset loaded.")

    if uploaded is not None:
        with st.spinner("Reading file..."):
            df, error = load_dataframe(uploaded)
        if error:
            st.error(error)
        else:
            st.session_state.df = df
            st.session_state.source_name = uploaded.name
            st.session_state.audit = None
            st.success(f"Loaded '{uploaded.name}' successfully.")

    df = st.session_state.df
    if df is None:
        st.info("No dataset loaded yet.")
        return

    valid, message = validate_dataframe(df)
    if not valid:
        st.error(message)
        return

    st.subheader("Dataset Preview")
    c1, c2, c3 = st.columns(3)
    c1.metric("Rows", f"{df.shape[0]:,}")
    c2.metric("Columns", df.shape[1])
    c3.metric("Missing cells", f"{int(df.isna().sum().sum()):,}")

    warnings = validate_column_names(df)
    for warning in warnings:
        st.warning(warning)

    st.dataframe(df.head(50), use_container_width=True)
    st.caption(f"Showing the first {min(50, len(df))} of {len(df):,} rows.")

    st.divider()
    st.write("When ready, run the full data readiness audit below.")
    if st.button("▶ Run Data Readiness Audit", type="primary", use_container_width=True):
        with st.spinner("Auditing dataset..."):
            ok, error = run_full_audit(df, inputs)
        if ok:
            st.success("Audit complete. Open the 'Audit Results' tab to review.")
            render_score_warnings(st.session_state.quality, st.session_state.dashboard)
        else:
            st.error(error)


# ---------------------------------------------------------------------------
# Tab 2: Audit Results
# ---------------------------------------------------------------------------
def tab_results() -> None:
    st.header("Audit Results")
    audit = st.session_state.audit
    package = st.session_state.package
    quality = st.session_state.quality
    dashboard = st.session_state.dashboard

    if not audit:
        st.info("Run an audit first from the 'Upload & Preview' tab.")
        return

    st.caption(f"Generation mode: {package.get('generation_mode', config.MODE_TEMPLATE)}")

    # If LLM Enhanced Mode was requested but fell back, explain why.
    if package.get("llm_fallback") and package.get("llm_error"):
        st.warning(
            f"LLM Enhanced Mode was unavailable, so Template Engine Mode was used. "
            f"Reason: {package['llm_error']}"
        )
    elif not package.get("llm_fallback") and package.get("generation_mode") == config.MODE_LLM:
        st.success(
            f"Narrative generated by {package.get('llm_provider', 'LLM')} "
            f"(`{package.get('llm_model', '')}`)."
        )

    c1, c2 = st.columns(2)
    with c1:
        score_card("Data Quality Score", quality["score"], quality["status"],
                   quality["color"], quality["emoji"])
        st.plotly_chart(visualizations.score_gauge(quality["score"], "Data Quality"),
                        use_container_width=True)
    with c2:
        score_card("Dashboard Readiness", dashboard["score"], dashboard["status"],
                   dashboard["color"], dashboard["emoji"])
        st.plotly_chart(visualizations.score_gauge(dashboard["score"], "Dashboard Readiness"),
                        use_container_width=True)

    render_score_warnings(quality, dashboard)

    with st.expander("How these scores were calculated"):
        colq, cold = st.columns(2)
        with colq:
            st.markdown("**Data Quality (0–100)**")
            render_component_breakdown(quality["components"])
        with cold:
            st.markdown("**Dashboard Readiness (0–100)**")
            render_component_breakdown(dashboard["components"])

    st.subheader("Executive Summary")
    st.write(package["executive_summary"])

    st.subheader("Biggest Risks")
    for risk in package["biggest_risks"]:
        st.markdown(f"- {risk}")

    with st.expander("Column Profile", expanded=False):
        st.dataframe(pd.DataFrame(audit["profiles"]), use_container_width=True)

    with st.expander("Missing Value Report"):
        m = audit["missing"]
        st.write(f"Overall missing (true nulls): **{m['overall_missing_pct']}%**")
        st.write(f"Effective missing (incl. blank-like values): **{m['effective_missing_pct']}%**")
        st.write(f"Blank-like placeholders found: {m['total_blank_like']}")
        st.write(f"Columns above threshold: {m['flagged_columns'] or 'None'}")
        st.write(f"Rows with many missing fields: {m['rows_many_missing']}")

    with st.expander("Duplicate Record Report"):
        st.write(f"Exact duplicate rows: **{audit['duplicates']['exact_duplicate_rows']}** "
                 f"({audit['duplicates']['exact_duplicate_pct']}%)")
        if audit["duplicates"]["key_columns_used"]:
            st.write(f"Key-based duplicates: {audit['duplicates']['key_duplicate_rows']}")

    with st.expander("Category Consistency Report"):
        issues = audit["categories"]["issues"]
        st.dataframe(pd.DataFrame(issues), use_container_width=True) if issues else st.write("No issues detected.")

    with st.expander("Date Quality Report"):
        reports = audit["dates"]["reports"]
        st.dataframe(pd.DataFrame(reports), use_container_width=True) if reports else st.write("No date columns detected.")

    with st.expander("Numeric Outlier Report"):
        reports = audit["numeric"]["reports"]
        st.dataframe(pd.DataFrame(reports), use_container_width=True) if reports else st.write("No numeric columns detected.")

    with st.expander("Business Readiness Assessment"):
        st.json(audit["business"])

    with st.expander("Dashboard Readiness Assessment"):
        st.json(audit["dashboard"])

    st.subheader("Data Quality Issue Log")
    issue_df = exporters.build_issue_log_df(audit)
    if len(issue_df):
        st.caption(
            f"{len(issue_df)} issue(s) found. Each row includes a recommended fix "
            "and the business impact if left unresolved."
        )
        st.dataframe(issue_df, use_container_width=True, hide_index=True)
    else:
        st.success("No data quality issues were logged.")


# ---------------------------------------------------------------------------
# Tab 3: Data Quality Dashboard
# ---------------------------------------------------------------------------
def tab_dashboard() -> None:
    st.header("Data Quality Dashboard")
    audit = st.session_state.audit
    df = st.session_state.df
    quality = st.session_state.quality
    dashboard = st.session_state.dashboard

    if not audit:
        st.info("Run an audit first from the 'Upload & Preview' tab.")
        return

    c1, c2 = st.columns(2)
    with c1:
        st.plotly_chart(visualizations.missing_values_chart(audit), use_container_width=True)
    with c2:
        st.plotly_chart(visualizations.type_distribution_chart(audit), use_container_width=True)

    c3, c4 = st.columns(2)
    with c3:
        st.plotly_chart(visualizations.quality_breakdown_chart(quality), use_container_width=True)
    with c4:
        st.plotly_chart(visualizations.dashboard_breakdown_chart(dashboard), use_container_width=True)

    st.subheader("Where Points Were Lost")
    st.caption("Focus cleanup effort on the areas costing the most points.")
    st.plotly_chart(visualizations.points_lost_chart(quality, dashboard),
                    use_container_width=True)

    st.plotly_chart(visualizations.duplicate_indicator_chart(audit), use_container_width=True)

    numeric_cols = audit["types"]["numeric_columns"]
    category_cols = audit["types"]["category_columns"]

    c5, c6 = st.columns(2)
    with c5:
        if numeric_cols:
            col = st.selectbox("Numeric column", numeric_cols, key="num_sel")
            st.plotly_chart(visualizations.numeric_distribution_chart(df, col),
                            use_container_width=True)
        else:
            st.info("No numeric columns to chart.")
    with c6:
        if category_cols:
            col = st.selectbox("Categorical column", category_cols, key="cat_sel")
            st.plotly_chart(visualizations.top_categories_chart(df, col),
                            use_container_width=True)
        else:
            st.info("No categorical columns to chart.")


# ---------------------------------------------------------------------------
# Tab 4: Recommendations
# ---------------------------------------------------------------------------
def tab_recommendations() -> None:
    st.header("Recommendations")
    package = st.session_state.package
    audit = st.session_state.audit

    if not package:
        st.info("Run an audit first from the 'Upload & Preview' tab.")
        return

    st.subheader("Cleanup Recommendations")
    for rec in package["cleanup_recommendations"]:
        st.markdown(f"- {rec}")

    st.subheader("Suggested Chart Gallery")
    st.caption("Charts are suggested only when the required field types are present.")
    gallery = package.get("chart_gallery", [])
    if gallery:
        gdf = pd.DataFrame(gallery).rename(
            columns={"chart": "Chart", "fields": "Fields", "why": "Why it helps"}
        )
        st.dataframe(gdf, use_container_width=True, hide_index=True)
    else:
        st.info("No chart suggestions available for this dataset.")

    st.subheader("Dashboard Readiness Advisor")
    st.caption("Recommended dashboard pages based on the fields available in your data.")
    pages = package.get("dashboard_pages", [])
    if pages:
        pdf = pd.DataFrame(pages).rename(
            columns={"page": "Page", "why": "Why", "requires": "Requires",
                     "available": "Available now"}
        )
        st.dataframe(pdf, use_container_width=True, hide_index=True)
    else:
        st.info("No dashboard page recommendations available.")

    st.subheader("Suggested Business Questions")
    for item in package["suggested_business_questions"]:
        st.markdown(f"- {item}")

    st.subheader("Suggested Next Steps")
    for item in package["suggested_next_steps"]:
        st.markdown(f"- {item}")

    st.subheader("Data Dictionary")
    st.caption(
        "A draft dictionary with an inferred dashboard role for each column "
        "(Metric, Dimension, Date, ID, Text, or Unknown). Edit descriptions to finalize."
    )
    dict_df = pd.DataFrame(package["data_dictionary"]).rename(columns={
        "column": "Column", "type": "Inferred type", "dashboard_role": "Dashboard role",
        "description": "Description draft", "example_values": "Example values",
        "missing_pct": "Missing %", "completeness": "Completeness",
        "unique_values": "Unique", "suggested_use": "Suggested use",
    })
    st.dataframe(dict_df, use_container_width=True, hide_index=True)

    st.subheader("Final Data Readiness Summary")
    st.success(package["final_summary"])


# ---------------------------------------------------------------------------
# Tab: Cleaned Dataset Preview
# ---------------------------------------------------------------------------
def tab_cleaned() -> None:
    st.header("Cleaned Dataset Preview")
    audit = st.session_state.audit
    df = st.session_state.df

    if not audit or df is None:
        st.info("Run an audit first from the 'Upload & Preview' tab.")
        return

    st.write(
        "Apply safe, reversible cleaning steps and preview the result. Your "
        "original file is never modified — you download a cleaned copy."
    )

    c1, c2 = st.columns(2)
    with c1:
        trim_text = st.checkbox("Trim text fields (remove extra spaces)", value=True)
        standardize_blanks = st.checkbox(
            "Standardize blank-like values (N/A, TBD, unknown → empty)", value=True
        )
    with c2:
        remove_duplicates = st.checkbox("Remove exact duplicate rows", value=True)
        standardize_capitalization = st.checkbox(
            "Standardize category capitalization (Title Case)", value=True
        )

    cleaned = exporters.build_cleaned_dataframe(
        df, audit,
        trim_text=trim_text,
        standardize_blanks=standardize_blanks,
        remove_duplicates=remove_duplicates,
        standardize_capitalization=standardize_capitalization,
    )

    m1, m2, m3 = st.columns(3)
    m1.metric("Original rows", f"{len(df):,}")
    m2.metric("Cleaned rows", f"{len(cleaned):,}", delta=f"{len(cleaned) - len(df):,}")
    m3.metric(
        "Missing cells now",
        f"{int(cleaned.isna().sum().sum()):,}",
        delta=f"{int(cleaned.isna().sum().sum() - df.isna().sum().sum()):,}",
        delta_color="inverse",
    )

    st.subheader("Preview (first 50 rows)")
    st.dataframe(cleaned.head(50), use_container_width=True)

    base = safe_file_name(st.session_state.inputs.get("dataset_name") or "audit")
    st.download_button(
        "⬇ Download Cleaned CSV",
        data=cleaned.to_csv(index=False),
        file_name=f"{base}_cleaned_{timestamp_slug()}.csv",
        mime="text/csv",
        use_container_width=True,
    )


# ---------------------------------------------------------------------------
# Tab: Audit History Dashboard
# ---------------------------------------------------------------------------
def tab_saved() -> None:
    st.header("Saved Audits")
    audit = st.session_state.audit

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("💾 Save current audit to history", use_container_width=True,
                     disabled=not audit):
            if audit:
                db.save_audit(
                    st.session_state.inputs, audit, st.session_state.quality,
                    st.session_state.dashboard, st.session_state.package["final_summary"],
                )
                st.success("Audit saved to local history.")
    with col2:
        if st.button("🗑 Clear all history", use_container_width=True):
            db.delete_all()
            st.warning("Audit history cleared.")

    metrics = db.get_dashboard_metrics()
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total audits", metrics["total_audits"])
    m2.metric("Avg quality", metrics["avg_quality"])
    m3.metric("Avg dashboard", metrics["avg_dashboard"])
    m4.metric("Best quality", metrics["best_quality"])

    history = db.get_history()
    if history:
        st.subheader("Audit History")
        st.dataframe(pd.DataFrame(history), use_container_width=True, hide_index=True)

        trend = visualizations.history_trend_chart(history)
        if trend:
            st.plotly_chart(trend, use_container_width=True)

        c1, c2 = st.columns(2)
        with c1:
            bar = visualizations.history_scores_bar(history)
            if bar:
                st.plotly_chart(bar, use_container_width=True)
        with c2:
            issue_trend = visualizations.history_issue_trend(history)
            if issue_trend:
                st.plotly_chart(issue_trend, use_container_width=True)
    else:
        st.info("No saved audits yet. Save an audit above to start tracking trends.")


# ---------------------------------------------------------------------------
# Tab 6: Exports
# ---------------------------------------------------------------------------
def tab_exports() -> None:
    st.header("Exports")
    audit = st.session_state.audit
    df = st.session_state.df

    if not audit:
        st.info("Run an audit first from the 'Upload & Preview' tab.")
        return

    inputs = st.session_state.inputs
    quality = st.session_state.quality
    dashboard = st.session_state.dashboard
    package = st.session_state.package
    base = safe_file_name(inputs.get("dataset_name") or "audit")
    stamp = timestamp_slug()

    md_report = exporters.build_markdown_report(inputs, audit, quality, dashboard, package)
    st.download_button(
        "⬇ Export Markdown Audit Report",
        data=md_report,
        file_name=f"{base}_report_{stamp}.md",
        mime="text/markdown",
        use_container_width=True,
    )

    cleaned = exporters.build_cleaned_dataframe(df, audit)
    st.download_button(
        "⬇ Export Cleaned CSV",
        data=cleaned.to_csv(index=False),
        file_name=f"{base}_cleaned_{stamp}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    profile_df = exporters.build_column_profile_df(audit)
    st.download_button(
        "⬇ Export Column Profile CSV",
        data=profile_df.to_csv(index=False),
        file_name=f"{base}_column_profile_{stamp}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    issue_df = exporters.build_issue_log_df(audit)
    st.download_button(
        "⬇ Export Issue Log CSV",
        data=issue_df.to_csv(index=False),
        file_name=f"{base}_issue_log_{stamp}.csv",
        mime="text/csv",
        use_container_width=True,
    )

    with st.expander("Preview Markdown Report"):
        st.markdown(md_report)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    inputs = render_sidebar()
    st.title(f"🧹 {config.APP_NAME}")
    st.caption(config.APP_TAGLINE)

    tabs = st.tabs([
        "Upload & Preview",
        "Audit Results",
        "Data Quality Dashboard",
        "Recommendations",
        "Cleaned Data",
        "Saved Audits",
        "Exports",
    ])
    with tabs[0]:
        tab_upload(inputs)
    with tabs[1]:
        tab_results()
    with tabs[2]:
        tab_dashboard()
    with tabs[3]:
        tab_recommendations()
    with tabs[4]:
        tab_cleaned()
    with tabs[5]:
        tab_saved()
    with tabs[6]:
        tab_exports()


if __name__ == "__main__":
    main()
