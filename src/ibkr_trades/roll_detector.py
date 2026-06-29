from __future__ import annotations

import uuid

import pandas as pd


def detect_and_tag_rolls(df: pd.DataFrame) -> pd.DataFrame:
    """Detect same-day close+open pairs on same underlying+option_type, assign shared roll_id.

    A roll = same-day C trade + O trade on same underlying and option_type with different expiration.
    Modifies a copy; returns it.
    """
    df = df.copy()
    if "roll_id" not in df.columns:
        df["roll_id"] = None

    opts = df[df["asset_type"] == "OPT"].copy()
    if opts.empty:
        return df

    opts["date"] = pd.to_datetime(opts["date"]).dt.date

    for trade_date, group in opts.groupby("date"):
        closes = group[group["open_close"].str.contains("C", na=False)]
        opens = group[group["open_close"] == "O"]

        for _, close_row in closes.iterrows():
            match = opens[
                (opens["underlying"] == close_row["underlying"])
                & (opens["option_type"] == close_row["option_type"])
                & (opens["expiration"] != close_row["expiration"])
                & (df.loc[opens.index, "roll_id"].isna())
            ]
            if match.empty:
                continue

            roll_id = str(uuid.uuid4())
            df.loc[close_row.name, "roll_id"] = roll_id
            df.loc[match.index[0], "roll_id"] = roll_id

    return df
