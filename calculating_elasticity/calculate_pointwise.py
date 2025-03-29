import pandas as pd
import numpy as np
from datetime import timedelta


def compute_pointwise_elasticity(df, window_days=7, min_price_change=0.05):
    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df["date"] = df["date"].dt.floor("D")

    df_daily = df.groupby(["date", "product_id", "attribute_id"], as_index=False).agg({
        "attribute": "mean",
        "trips": "sum"
    })

    df_daily["attribute_shifted"] = df_daily.groupby(["product_id", "attribute_id"])["attribute"].shift(1)
    df_daily["attribute_diff"] = (df_daily["attribute"] - df_daily["attribute_shifted"]).abs()
    df_daily["attribute_change"] = df_daily["attribute_diff"] > min_price_change * df_daily["attribute"]

    change_dates = df_daily[df_daily["attribute_change"]][["date", "product_id", "attribute_id"]]

    window = timedelta(days=window_days)
    elasticity_points = []

    for _, row in change_dates.iterrows():
        change_date = row["date"]
        product_id = row["product_id"]
        attribute_id = row["attribute_id"]

        before_start = change_date - window
        before_end = change_date
        after_start = change_date
        after_end = change_date + window

        df_before = df_daily[
            (df_daily["date"] >= before_start) & (df_daily["date"] < before_end) &
            (df_daily["product_id"] == product_id) & (df_daily["attribute_id"] == attribute_id)
        ]
        df_after = df_daily[
            (df_daily["date"] >= after_start) & (df_daily["date"] < after_end) &
            (df_daily["product_id"] == product_id) & (df_daily["attribute_id"] == attribute_id)
        ]

        if df_before.empty or df_after.empty:
            continue

        avg_q1 = df_before["trips"].mean()
        avg_q2 = df_after["trips"].mean()
        avg_p1 = df_before["attribute"].mean()
        avg_p2 = df_after["attribute"].mean()

        if min(avg_q1, avg_q2, avg_p1, avg_p2) <= 0:
            continue

        ln_q = np.log(avg_q2 / avg_q1)
        ln_p = np.log(avg_p2 / avg_p1)
        elasticity = ln_q / ln_p if ln_p != 0 else 0

        elasticity_points.append({
            "product_id": product_id,
            "attribute_id": attribute_id,
            "method": f"point_change_{window_days}d",
            "date": change_date,
            "elasticity": elasticity
        })

    df_elasticity = pd.DataFrame(elasticity_points)
    print("Подсчитана поточечная эластичность")
    return df_elasticity
