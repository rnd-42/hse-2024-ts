import pandas as pd
import numpy as np
import statsmodels.api as sm


def compute_rolling_elasticity(df, window_size=30, step=1):
    df = df.copy()
    df["log_trips"] = np.log(df["trips"].clip(lower=1))
    df["log_attribute"] = np.log(df["attribute"].clip(lower=0.01))

    rolling_results = []

    for (time_series_id, attribute_id), group in df.groupby(["time_series_id", "attribute_id"]):
        rolling_dates = []
        rolling_elasticities = []

        for start in range(0, len(group) - window_size, step):
            end = start + window_size
            subset = group.iloc[start:end]

            if subset["log_attribute"].nunique() == 1:
                rolling_elasticities.append(0)
            else:
                X = sm.add_constant(subset["log_attribute"])
                model = sm.OLS(subset["log_trips"], X).fit()
                rolling_elasticities.append(model.params["log_attribute"])

            rolling_dates.append(subset["date"].iloc[-1])

        rolling_results.extend([
            {"time_series_id": time_series_id,
             "attribute_id": attribute_id,
             "method": f"rolling_{window_size}d",
             "date": date,
             "elasticity": elasticity}
            for date, elasticity in zip(rolling_dates, rolling_elasticities)
        ])

    print(f"Подсчитана эластичность с помощью регрессии с {window_size} дневным окном")

    return pd.DataFrame(rolling_results)

