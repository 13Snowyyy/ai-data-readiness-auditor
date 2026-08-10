# AI Data Readiness Auditor

[![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-App-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)
[![pandas](https://img.shields.io/badge/pandas-Data-150458?logo=pandas&logoColor=white)](https://pandas.pydata.org/)
[![Plotly](https://img.shields.io/badge/Plotly-Charts-3F4F75?logo=plotly&logoColor=white)](https://plotly.com/python/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Local-first](https://img.shields.io/badge/Local--first-No%20API%20key%20required-success)](#10-how-template-engine-mode-works)
[![Optional AI](https://img.shields.io/badge/Optional-LLM%20Enhanced%20Mode-8A2BE2)](#11-how-llm-enhanced-mode-works)

> **Clean the data before trusting the dashboard.**

A local-first web application that helps anyone upload a CSV or Excel file and
quickly understand whether the dataset is ready for analysis, dashboarding,
reporting, or AI-assisted insights. It profiles the data, detects quality
issues, produces a **Data Quality Score** and a **Dashboard Readiness Score**,
drafts a data dictionary, and generates an executive-ready audit report — all
without needing an API key or internet connection.

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/Sviless/ai-data-readiness-auditor.git
cd ai-data-readiness-auditor

# 2. Install dependencies
python -m pip install -r requirements.txt

# 3. Run
python -m streamlit run app.py
```

Then open the URL it prints (usually http://localhost:8501), click
**Load sample dataset**, and press **Run Data Readiness Audit**. No API key or
internet connection is required.

> On Windows you can instead double-click **`run_app.bat`**; on macOS/Linux run
> **`./run_app.sh`** — both create a virtual environment and launch the app for you.

---

## 1. Project Overview

Teams constantly want dashboards, reports, and AI insights, but their source
data is often incomplete, duplicated, inconsistent, poorly structured, or simply
not ready for trusted analysis. The **AI Data Readiness Auditor** catches these
problems early. Upload a messy file, click **Run Audit**, and get a clear,
practical readiness assessment with recommendations before you build anything.

## 2. The Problem This Tool Solves

- Dashboards built on dirty data lead to wrong decisions.
- Messy CSV/Excel trackers hide missing values, duplicates, and inconsistent
  categories.
- Analysts waste hours discovering data problems *after* starting the work.
- Non-technical stakeholders can't easily judge whether data is trustworthy.

This tool surfaces those issues in minutes and tells you what to fix first.

## 3. Why Data Readiness Matters

"Garbage in, garbage out." A dashboard is only as trustworthy as the data behind
it. Data readiness means the dataset is complete enough, consistent enough, and
structured enough that metrics, trends, and groupings can be trusted. Checking
readiness *before* building saves rework and protects decision quality.

## 4. Key Features

- Upload **CSV** or **Excel (.xlsx)** files (Excel via `openpyxl`).
- Instant dataset preview and column-name validation.
- Comprehensive audit engine (pandas + numpy):
  - Column profiling and type inference
  - Missing-value analysis (true nulls + blank-like placeholders)
  - Duplicate detection (exact + key-based)
  - Category consistency checks (capitalization, whitespace, blank-like values, cardinality)
  - Date quality checks (parse rate, invalid/future/very-old dates)
  - Numeric quality checks (min/max/mean/median/std, IQR outliers, negatives)
  - Business and dashboard readiness checks
- **Data Quality Score** and **Dashboard Readiness Score** (0–100) with transparent, component-level breakdowns.
- **Data Quality Issue Log** — a structured table of issue type, column affected,
  severity, description, **recommended fix**, and **business impact**.
- **Data Dictionary Builder** — inferred type, description draft, example values,
  missing %, suggested use, and a **dashboard role** for each column
  (Metric, Dimension, Date, ID, Text, or Unknown).
- **Dashboard Readiness Advisor** — recommends dashboard pages (Executive Summary,
  Trend Analysis, Category Breakdown, Owner/Status Tracking, Data Quality Monitoring)
  based on the fields your data actually contains.
- **Suggested Chart Gallery** — field-aware chart suggestions (bar, line, histogram,
  box plot, pie/donut only when appropriate, scatter when numeric pairs exist).
- **Cleaned Dataset Preview** — apply safe, reversible cleaning toggles (trim text,
  standardize blank-like values, remove exact duplicates, standardize capitalization)
  with a live before/after preview and download.
- **Data Quality Score Breakdown** — see exactly how many points were lost in each issue area.
- **Audit History Dashboard** — score trends, per-audit score comparison, and issue-count trend from local **SQLite** history.
- Interactive **Plotly** charts and score gauges.
- Export a **Markdown** report (20 sections), a **cleaned CSV**, a **column profile CSV**, and an **issue log CSV**.
- **Template Engine Mode** (default, offline) plus an optional, fully implemented
  **LLM Enhanced Mode** (OpenAI, Groq, OpenRouter, Gemini, Azure OpenAI, Claude)
  that adds AI-written narratives when an API key is provided and falls back
  automatically when it isn't.

## 5. Technology Stack

- **Python**
- **Streamlit** (UI)
- **pandas** / **numpy** (analysis)
- **SQLite** (`sqlite3`, standard library) for audit history
- **openpyxl** (Excel support)
- **Plotly Express** (charts)
- **GitHub Copilot** + **Claude Opus 4.8** (AI-assisted development)
- **Template Engine Mode** + **LLM Enhanced Mode** architecture

## 6. Folder Structure

```
ai-data-readiness-auditor/
├── app.py                     # Streamlit UI
├── requirements.txt
├── README.md
├── LICENSE                    # MIT License
├── run_app.bat                # One-click Windows launcher
├── run_app.sh                 # One-click macOS/Linux launcher
├── .env.example               # Copy to .env to enable optional LLM mode
├── .gitignore
├── data/
│   └── data_readiness.db      # SQLite history (created on first run)
├── outputs/                   # Optional export destination
├── sample_files/
│   └── sample_messy_dataset.csv
└── src/
    ├── __init__.py
    ├── audit_engine.py        # Core pandas/numpy auditing logic
    ├── template_engine.py     # Template Engine Mode narratives
    ├── scoring.py             # Quality + dashboard readiness scoring
    ├── db.py                  # SQLite persistence
    ├── exporters.py           # Markdown / CSV exports
    ├── validators.py          # File + dataset validation
    ├── visualizations.py      # Plotly Express charts
    ├── sample_data.py         # Generic messy sample dataset generator
    ├── config.py              # Settings + .env loading + provider detection
    ├── utils.py               # Helper functions
    └── providers/
        ├── __init__.py
        ├── base_provider.py   # Provider interface
        ├── template_provider.py
        └── llm_provider.py    # LLM Enhanced Mode (real API calls)
```

## 7. Setup Instructions

**Prerequisites:** Python 3.9+ installed and on your PATH.

```powershell
# 1. (Optional) create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt
```

## 8. How to Run the App

**Option A — one click:**

- **Windows:** double-click **`run_app.bat`**.
- **macOS / Linux:** run **`./run_app.sh`** (you may first need `chmod +x run_app.sh`).

Each script creates a virtual environment, installs dependencies, and launches
the app automatically.

**Option B — manual:**

```bash
python -m streamlit run app.py
```

The app opens in your browser (usually at http://localhost:8501).

## 9. How to Use the Sample Dataset

- In the **Upload & Preview** tab, click **Load sample dataset** to instantly
  load a synthetic messy dataset, then click **Run Data Readiness Audit**.
- A CSV copy also lives at `sample_files/sample_messy_dataset.csv`. To regenerate
  it: `python -m src.sample_data`.

The sample intentionally includes missing values, duplicates, inconsistent
capitalization, date issues, numeric outliers, and blank-like placeholders.

## 10. How Template Engine Mode Works

Template Engine Mode is the **default** generation engine and runs **fully
offline**. It converts the raw audit results and scores into readable,
business-friendly deliverables (executive summary, biggest risks, issue log with
recommended fixes and business impact, data dictionary with dashboard roles,
chart gallery, recommended dashboard pages, cleanup recommendations, suggested
questions/next steps, and a final summary) using deterministic local templates in
`src/template_engine.py`. No API key, account, or internet connection is required.

## 11. How LLM Enhanced Mode Works

The app is architected around a **provider interface** (`src/providers/`).
**LLM Enhanced Mode** is fully implemented in `src/providers/llm_provider.py` and:

- Is selected entirely by **environment variables** — no keys are ever hardcoded.
- Reads keys from `os.environ` only and never logs or stores their values.
- Uses only the Python **standard library** (`urllib`) for the API call, so it adds
  **no extra dependencies**.
- Builds a structured, fact-grounded prompt from the audit results and asks the
  model for JSON, then overlays the AI narrative on top of the deterministic,
  field-derived sections (data dictionary, chart gallery, dashboard pages) so
  those stay grounded.
- **Falls back to Template Engine Mode automatically** — cleanly when no key is
  configured, and with a clear on-screen reason if a call fails (bad key, network
  error, non-JSON response, etc.). The app never crashes and never requires a key.

Supported providers (choose one via `LLM_PROVIDER`):

| Provider | `LLM_PROVIDER` | API key variable | Default model |
| --- | --- | --- | --- |
| OpenAI | `openai` | `OPENAI_API_KEY` | `gpt-4o-mini` |
| Groq | `groq` | `GROQ_API_KEY` | `llama-3.3-70b-versatile` |
| OpenRouter | `openrouter` | `OPENROUTER_API_KEY` | `openai/gpt-4o-mini` |
| Google Gemini | `gemini` | `GEMINI_API_KEY` | `gemini-2.0-flash` |
| Azure OpenAI | `azure_openai` | `AZURE_OPENAI_API_KEY` | (deployment name) |
| Anthropic Claude | `claude` | `ANTHROPIC_API_KEY` | `claude-3-5-sonnet-latest` |

Optional overrides (all optional; none required to run):

```
LLM_PROVIDER            # which provider to use (e.g. groq)
LLM_MODEL               # override the default model
LLM_API_KEY             # generic key (defaults provider to openai if set alone)
LLM_BASE_URL            # override the OpenAI-compatible base URL
AZURE_OPENAI_ENDPOINT   # required for Azure OpenAI
AZURE_OPENAI_DEPLOYMENT # Azure deployment name (or set via LLM_MODEL)
AZURE_OPENAI_API_VERSION# defaults to 2024-06-01
```

### Where to put your API key (easiest way — a `.env` file)

You do **not** need to touch any code. The app automatically reads a file named
`.env` in the project folder.

1. In the project folder you'll see a file called **`.env.example`**.
   Make a **copy** of it and rename the copy to **`.env`** (just `.env`, with the
   dot and nothing after it).
2. Open your new `.env` file. It lists six providers, each commented out.
3. Pick **one** provider, delete the `#` in front of its two lines, and paste
   your real key after the `=` sign. For example, for Groq:
   ```
   LLM_PROVIDER=groq
   GROQ_API_KEY=your-real-key-here
   ```
4. **Save** the file and start the app. In the sidebar, choose
   **LLM Enhanced Mode**.

Your `.env` file is automatically ignored by git, so your key never gets
committed or shared. If you leave the key out, the app simply keeps using the
offline **Template Engine Mode** — nothing breaks.

### Alternative: set it just for the current terminal session

If you'd rather not create a file, set the variables in your terminal before
launching (they disappear when you close the terminal):

```powershell
$env:LLM_PROVIDER = "groq"
$env:GROQ_API_KEY = "your-key-here"
python -m streamlit run app.py
```

Select **LLM Enhanced Mode** in the sidebar. If the key is missing or the call
fails, the app quietly uses Template Engine Mode and tells you why.

## 12. Example Use Case

An operations analyst inherits a messy issue-tracker export. Before building a
status dashboard, they load it into the auditor. The tool reports a **Data
Quality Score of 58 (Needs Cleanup)** and a **Dashboard Readiness Score of 61
(Needs Preparation)**, flags a 42%-missing `Satisfaction_Score` column, 8
duplicate rows, inconsistent `Region` capitalization, and unparseable dates.
The analyst exports the cleaned CSV and the Markdown report, fixes the flagged
issues, re-audits to confirm improvement, and only then builds the dashboard.

## 13. Portfolio Value

This project demonstrates beginner-to-intermediate **data analytics**,
**data quality thinking**, **BI readiness**, **AI-assisted development**, and
clean, modular software design — a practical, real-world tool rather than a toy
example.

## 14. Possible Future Enhancements

- Provider-native SDKs and streaming responses for LLM Enhanced Mode
- **Great Expectations** integration
- **ydata-profiling** integration
- Data lineage tracking
- KPI definition checker
- Automated column mapping
- Power BI readiness checklist
- SQL database connection
- Multiple file comparison
- Scheduled recurring audits
- Cloud deployment

## 15. Resume Bullets

- Built a local-first **AI Data Readiness Auditor** (Python, Streamlit, pandas,
  numpy, SQLite, openpyxl, Plotly) that profiles CSV/Excel datasets and detects
  missing values, duplicates, inconsistent categories, outliers, and date-quality
  issues, producing 0–100 **Data Quality** and **Dashboard Readiness** scores with
  transparent, component-level breakdowns.
- Engineered a structured **Data Quality Issue Log** (issue type, severity,
  recommended fix, and business impact) and an automated **Data Dictionary Builder**
  that infers each column's dashboard role (Metric, Dimension, Date, ID, Text),
  turning raw data profiling into stakeholder-ready deliverables.
- Designed a **Dashboard Readiness Advisor** and field-aware **Chart Gallery** that
  recommend BI dashboard pages and appropriate visualizations (bar, line, histogram,
  box, pie, scatter) based on the columns actually present in the data.
- Implemented a safe, reversible **data cleaning preview** (whitespace trimming,
  blank-like normalization, duplicate removal, category standardization) with live
  before/after metrics and one-click cleaned-CSV export.
- Delivered an **Audit History Dashboard** backed by SQLite that tracks data
  quality trends, per-audit score comparisons, and issue counts over time, plus
  20-section Markdown and CSV exports.
- Architected the app around a pluggable **provider interface** with an offline
  **Template Engine Mode** (no API key required) and an optional, fully implemented
  **LLM Enhanced Mode** supporting six providers (OpenAI, Groq, OpenRouter, Gemini,
  Azure OpenAI, Claude) via environment variables, with automatic, graceful
  fallback — demonstrating clean, modular, extensible software design.

---

## Author

**Gustavo Angulo**
GitHub: [@Sviless](https://github.com/Sviless)

Built as a data analytics / business intelligence portfolio project.

## License

Released under the **MIT License** — see [LICENSE](LICENSE) for details.

---

_Built with Python, Streamlit, pandas, numpy, SQLite, openpyxl, and Plotly Express._
