import pandas as pd


def load_csv(path):
    df = pd.read_csv(path, parse_dates=["Date"])
    df.sort_values("Date", inplace=True)
    df.set_index("Date", inplace=True)
    return df
