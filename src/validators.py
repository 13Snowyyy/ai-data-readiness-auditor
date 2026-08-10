"""File and dataset validation helpers."""

from __future__ import annotations

from typing import Tuple

import pandas as pd

SUPPORTED_EXTENSIONS = (".csv", ".xlsx")


def validate_file_extension(file_name: str) -> Tuple[bool, str]:
    """Check that the uploaded file has a supported extension."""
    lower = str(file_name).lower()
    if lower.endswith(".csv"):
        return True, ""
    if lower.endswith(".xlsx"):
        return True, ""
    return (
        False,
        "Unsupported file type. Please upload a .csv or .xlsx file.",
    )


def load_dataframe(uploaded_file) -> Tuple[pd.DataFrame, str]:
    """Load a Streamlit uploaded file into a DataFrame.

    Returns (dataframe, error_message). On success error_message is "".
    """
    name = getattr(uploaded_file, "name", "uploaded_file")
    ok, message = validate_file_extension(name)
    if not ok:
        return pd.DataFrame(), message

    try:
        if name.lower().endswith(".csv"):
            try:
                df = pd.read_csv(uploaded_file)
            except UnicodeDecodeError:
                # Fall back to a forgiving encoding for non-UTF-8 files.
                uploaded_file.seek(0)
                df = pd.read_csv(uploaded_file, encoding="latin-1")
        else:
            # openpyxl is the engine for .xlsx files; read the first sheet.
            df = pd.read_excel(uploaded_file, engine="openpyxl")
    except pd.errors.EmptyDataError:
        return pd.DataFrame(), "The file appears to be empty. Please upload a file with data."
    except pd.errors.ParserError as exc:
        return pd.DataFrame(), f"The file could not be parsed. Check the formatting: {exc}"
    except Exception as exc:  # broad: surface any parse error to the user
        return pd.DataFrame(), f"Could not read the file: {exc}"

    # Drop fully-empty rows and columns that often come from spreadsheet exports.
    df = df.dropna(axis=0, how="all").dropna(axis=1, how="all")

    valid, message = validate_dataframe(df)
    if not valid:
        return pd.DataFrame(), message
    return df, ""


def validate_dataframe(df: pd.DataFrame) -> Tuple[bool, str]:
    """Ensure the dataset is non-empty and has usable columns."""
    if df is None or df.empty:
        return False, "The dataset is empty. Please upload a file with data."
    if df.shape[1] == 0:
        return False, "The dataset has no columns."
    if df.shape[0] == 0:
        return False, "The dataset has no rows."
    return True, ""


def validate_column_names(df: pd.DataFrame) -> list[str]:
    """Return a list of human-readable warnings about column names."""
    warnings: list[str] = []
    columns = list(df.columns)

    # Unnamed columns from bad CSV headers.
    unnamed = [c for c in columns if str(c).lower().startswith("unnamed")]
    if unnamed:
        warnings.append(
            f"{len(unnamed)} column(s) appear to be unnamed (missing headers)."
        )

    # Duplicate column names.
    seen = set()
    dupes = set()
    for c in columns:
        if c in seen:
            dupes.add(c)
        seen.add(c)
    if dupes:
        warnings.append(f"Duplicate column name(s): {', '.join(map(str, dupes))}.")

    # Whitespace in names.
    spaced = [c for c in columns if str(c) != str(c).strip()]
    if spaced:
        warnings.append("Some column names have leading/trailing spaces.")

    return warnings
