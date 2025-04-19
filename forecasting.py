import pandas as pd
import numpy as np
from pmdarima import auto_arima
from statsmodels.tsa.statespace.sarimax import SARIMAX, SARIMAXResultsWrapper
from typing import List, Optional, Tuple

class SARIMAXAutoForecaster:
    """
    Автоматический подбор параметров SARIMAX через auto_arima для ARIMA-части
    и использование всех 30 лагов экзогенов.
    """
    def __init__(
        self,
        seasonal_order: Tuple[int,int,int,int] = (1,1,1,7),
        max_lags: int = 30,
        train_ratio: float = 0.8
    ):
        self.seasonal_order = seasonal_order
        self.max_lags = max_lags
        self.train_ratio = train_ratio

        self.best_model_: Optional[SARIMAXResultsWrapper] = None
        self.best_order_: Optional[Tuple[int,int,int]] = None
        self.best_features_: Optional[List[str]] = None
        self.best_mape_: float = np.inf

    def _make_exogs(self, ts_price: pd.Series) -> pd.DataFrame:
        exog = pd.DataFrame(index=ts_price.index)
        for lag in range(1, self.max_lags + 1):
            exog[f'lag_diff_{lag}'] = ts_price - ts_price.shift(lag)
        return exog.dropna()

    def _split(
        self,
        ts: pd.Series,
        exog: pd.DataFrame
    ) -> Tuple[pd.Series,pd.DataFrame,pd.Series,pd.DataFrame]:
        n = len(ts)
        train_n = int(self.train_ratio * n)
        return (
            ts.iloc[:train_n], exog.iloc[:train_n],
            ts.iloc[train_n:], exog.iloc[train_n:]
        )

    def fit(
        self,
        ts_traffic: pd.Series,
        ts_price: pd.Series
    ) -> 'SARIMAXAutoForecaster':
        exog_full = self._make_exogs(ts_price)
        traffic_sync = ts_traffic.loc[exog_full.index]
        y_train, ex_train, y_val, ex_val = self._split(traffic_sync, exog_full)
        horizon = len(y_val)

        features = ex_train.columns.tolist()
        exog_train = ex_train[features]
        exog_val   = ex_val[features]

        arima = auto_arima(
            y_train,
            seasonal=True,
            m=self.seasonal_order[3],
            d=None, D=self.seasonal_order[1],
            max_p=5, max_q=5,
            max_P=2, max_Q=2,
            stepwise=True,
            error_action='ignore',
            suppress_warnings=True
        )
        self.best_order_ = (arima.order[0], arima.order[1], arima.order[2])

        model = SARIMAX(
            y_train,
            order=self.best_order_,
            seasonal_order=self.seasonal_order,
            exog=exog_train
        )
        fit_res = model.fit(disp=False)

        pred = fit_res.get_forecast(steps=horizon, exog=exog_val).predicted_mean
        mape = float(np.mean(np.abs((y_val - pred) / y_val)) * 100)

        self.best_model_    = fit_res
        self.best_features_ = features
        self.best_mape_     = mape
        return self

    def predict(
        self,
        ts_price_full: pd.Series
    ) -> pd.Series:
        if self.best_model_ is None or self.best_features_ is None:
            raise ValueError("Сначала вызовите fit().")

        exog_full = self._make_exogs(ts_price_full)
        exog_sel  = exog_full[self.best_features_]
        forecast  = self.best_model_.get_forecast(
            steps=len(exog_sel),
            exog=exog_sel
        ).predicted_mean
        return forecast

    def get_mape(
        self,
        actual: pd.Series,
        predicted: pd.Series
    ) -> float:
        return float(np.mean(np.abs((actual - predicted) / actual)) * 100)

    def summary(self) -> str:
        return (
            f"Best SARIMAX order: {self.best_order_}, "
            f"seasonal: {self.seasonal_order}\n"
            f"Validation MAPE: {self.best_mape_:.2f}%"
        )