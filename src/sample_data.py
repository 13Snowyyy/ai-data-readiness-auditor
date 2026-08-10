"""Generate a generic, messy sample dataset for demos and testing.

All data here is synthetic and generic. It contains no real company,
person, or proprietary information. The dataset intentionally includes common
data quality problems so the auditor has something meaningful to detect.
"""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import pandas as pd

from . import config


def generate_messy_dataframe(seed: int = 42) -> pd.DataFrame:
    """Create a synthetic messy operations dataset with realistic issues."""
    rng = random.Random(seed)
    np.random.seed(seed)

    n = 120
    regions = ["North", "north", "South", "SOUTH", "East", "west", "West "]
    statuses = ["Open", "open", "Closed", "In Progress", "in progress", "N/A", "TBD"]
    priorities = ["High", "Medium", "Low", "high", "unknown"]
    owners = ["Alex Rivera", "Jordan Lee", "Sam Patel", "Taylor Kim",
              "Morgan Diaz", "  Casey Fox", "Jamie Cruz", None]
    categories = ["Hardware", "Software", "Service", "hardware", "Facilities", "-"]

    rows = []
    for i in range(n):
        # Occasionally inject missing values and blank-like placeholders.
        cost = round(rng.uniform(50, 5000), 2)
        if rng.random() < 0.05:
            cost = round(rng.uniform(50000, 200000), 2)  # outliers
        if rng.random() < 0.04:
            cost = -abs(cost)  # suspicious negatives

        units = rng.randint(1, 40)
        if rng.random() < 0.06:
            units = rng.randint(500, 2000)  # outliers

        # Mixed date formats + some invalid/blank/future dates.
        date_choices = [
            f"2024-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
            f"{rng.randint(1,12):02d}/{rng.randint(1,28):02d}/2023",
            "not a date",
            "",
            "2035-01-15",   # future
            "1985-06-01",   # very old
        ]
        weights = [0.55, 0.28, 0.05, 0.05, 0.04, 0.03]
        created = rng.choices(date_choices, weights=weights)[0]

        rows.append({
            "Ticket_ID": f"TCK-{1000 + i}",
            "Region": rng.choice(regions),
            "Category": rng.choice(categories),
            "Priority": rng.choice(priorities),
            "Status": rng.choice(statuses),
            "Owner": rng.choice(owners),
            "Cost_USD": cost if rng.random() > 0.07 else np.nan,
            "Units": units if rng.random() > 0.05 else np.nan,
            "Satisfaction_Score": (
                round(rng.uniform(1, 5), 1) if rng.random() > 0.15 else np.nan
            ),
            "Created_Date": created,
            "Notes": rng.choice(["", "follow up", "N/A", "urgent", "unknown", "-"]),
        })

    df = pd.DataFrame(rows)

    # Inject exact duplicate rows.
    duplicates = df.sample(n=8, random_state=seed)
    df = pd.concat([df, duplicates], ignore_index=True)

    return df


def write_sample_csv(path: Path | None = None) -> Path:
    """Write the sample dataset to disk and return its path."""
    config.ensure_folders()
    target = Path(path) if path else config.SAMPLE_CSV
    target.parent.mkdir(parents=True, exist_ok=True)
    generate_messy_dataframe().to_csv(target, index=False)
    return target


if __name__ == "__main__":
    written = write_sample_csv()
    print(f"Sample dataset written to: {written}")
