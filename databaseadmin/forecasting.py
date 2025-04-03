import pandas as pd
import numpy as np
from statsmodels.tsa.statespace.sarimax import SARIMAX
from statsmodels.tsa.statespace.sarimax import SARIMAXResultsWrapper
from typing import List, Optional, Tuple, Dict, Any
from django.db import transaction

class SARIMAXAutoForecaster:
    def __init__(self, arima_orders=[(1,1,1)], seasonal_orders=[(1,1,1,7)],
                 max_lags=30, top_k_features=10, train_ratio=0.8):
        self.arima_orders = arima_orders
        self.seasonal_orders = seasonal_orders
        self.max_lags = max_lags
        self.top_k = top_k_features
        self.train_ratio = train_ratio

        self.best_model_: Optional[SARIMAXResultsWrapper] = None
        self.best_order_ = None
        self.best_seasonal_order_ = None
        self.best_features_: Optional[List[str]] = None
        self.best_mape_ = np.inf

    def _make_exogs(self, ts_price: pd.Series) -> pd.DataFrame:
        exog = pd.DataFrame(index=ts_price.index)
        for lag in range(1, self.max_lags + 1):
            exog[f'lag_diff_{lag}'] = ts_price - ts_price.shift(lag)
        return exog.dropna()

    def _select_features(self, ts_traffic: pd.Series, exog: pd.DataFrame) -> List[str]:
        y = ts_traffic.loc[exog.index]
        corrs = exog.apply(lambda col: abs(col.corr(y)))
        return corrs.sort_values(ascending=False).index[:self.top_k].tolist()  # type: ignore

    def _split(self, ts: pd.Series, exog: pd.DataFrame) -> Tuple[pd.Series, pd.DataFrame, pd.Series, pd.DataFrame]:
        n = len(ts)
        train_n = int(self.train_ratio * n)
        return (ts.iloc[:train_n], exog.iloc[:train_n],
                ts.iloc[train_n:], exog.iloc[train_n:])

    def fit(self, ts_traffic: pd.Series, ts_price: pd.Series) -> 'SARIMAXAutoForecaster':
        full_exog = self._make_exogs(ts_price)
        full_traffic = ts_traffic.loc[full_exog.index]
        y_train, ex_train, y_val, ex_val = self._split(full_traffic, full_exog)

        for order in self.arima_orders:
            for seasonal in self.seasonal_orders:
                selected = self._select_features(y_train, ex_train)
                exog_train_sel = ex_train[selected]
                exog_val_sel   = ex_val[selected]
                try:
                    model = SARIMAX(y_train, order=order,
                                    seasonal_order=seasonal,
                                    exog=exog_train_sel)
                    model_fit = model.fit(disp=False)  # type: ignore
                except Exception:
                    continue

                try:
                    pred = model_fit.get_forecast(steps=len(y_val),  # type: ignore
                                         exog=exog_val_sel).predicted_mean
                    mape = np.mean(np.abs((y_val - pred) / y_val)) * 100
                except Exception:
                    continue

                if mape < self.best_mape_:
                    self.best_mape_ = mape
                    self.best_model_ = model_fit  # type: ignore
                    self.best_order_ = order
                    self.best_seasonal_order_ = seasonal
                    self.best_features_ = selected

        return self

    def predict(self, ts_price_full: pd.Series) -> pd.Series:
        if self.best_model_ is None or self.best_features_ is None:
            raise ValueError("Сначала вызовите fit().")
        
        exog_full = self._make_exogs(ts_price_full)
        exog_sel = exog_full[self.best_features_]
        
        try:
            forecast = self.best_model_.get_forecast(  # type: ignore
                steps=len(exog_sel),
                exog=exog_sel
            ).predicted_mean
            return forecast
        except Exception as e:
            raise ValueError(f"Ошибка при прогнозировании: {str(e)}")

    def get_mape(self, actual: pd.Series, predicted: pd.Series) -> float:
        return float(np.mean(np.abs((actual - predicted) / actual)) * 100)

    def summary(self) -> str:
        return (f"Best SARIMAX order: {self.best_order_}, "
                f"seasonal: {self.best_seasonal_order_}\n"
                f"Selected features (lags): {self.best_features_}\n"
                f"MAPE on validation: {self.best_mape_:.2f}%")

def make_forecast_for_child_series(parent_model_id: int, child_series_id: int, forecast_periods: int = 30) -> Dict[str, Any]:
    """
    Выполняет прогнозирование для дочернего временного ряда на основе обученной модели родительского ряда
    и сохраняет результаты прогноза в виде таймстемпов.
    
    Args:
        parent_model_id: ID модели прогнозирования родительского ряда
        child_series_id: ID дочернего временного ряда
        forecast_periods: Количество периодов для прогноза (используется только если нужно ограничить количество прогнозов)
        
    Returns:
        Словарь с результатами прогнозирования
    """
    from databaseadmin.models import ForecastingModel, TimeSeries, Timestamp
    
    try:
        forecasting_model = ForecastingModel.objects.get(model_id=parent_model_id)
        parent_series = forecasting_model.time_series
        child_series = TimeSeries.objects.get(time_series_id=child_series_id)
        
        if not child_series.parent_time_series or child_series.parent_time_series.time_series_id != parent_series.time_series_id:
            return {
                'success': False,
                'error': 'Выбранный ряд не является дочерним для ряда с моделью прогнозирования'
            }
        
        feature_attribute = forecasting_model.feature_attribute
        target_attribute = forecasting_model.target_attribute
        
        parent_feature_timestamps = Timestamp.objects.filter(
            time_series=parent_series,
            attribute=feature_attribute
        ).order_by('start_dt')
        
        child_feature_timestamps = Timestamp.objects.filter(
            time_series=child_series,
            attribute=feature_attribute
        ).order_by('start_dt')
        
        if not parent_feature_timestamps.exists() or not child_feature_timestamps.exists():
            return {
                'success': False,
                'error': 'Недостаточно данных для прогнозирования'
            }
        
        parent_features = {
            timestamp.start_dt: float(timestamp.value) 
            for timestamp in parent_feature_timestamps
        }
        parent_features_series = pd.Series(parent_features)
        parent_features_series.index = pd.DatetimeIndex(parent_features_series.index)
        
        child_features = {
            timestamp.start_dt: float(timestamp.value) 
            for timestamp in child_feature_timestamps
        }
        child_features_series = pd.Series(child_features)
        child_features_series.index = pd.DatetimeIndex(child_features_series.index)
        
        model_object = forecasting_model.load_model_object()
        if not model_object:
            return {
                'success': False,
                'error': 'Не удалось загрузить объект модели'
            }
            
        if isinstance(model_object, SARIMAXAutoForecaster):
            try:
                combined_features_series = pd.concat([parent_features_series, child_features_series]).sort_index()
                forecast_series = model_object.predict(combined_features_series)
                forecast_dates = child_features_series.index
                
                if len(forecast_series) < len(forecast_dates):
                    aligned_forecast = pd.Series(index=forecast_dates, dtype=float)
                    
                    common_dates = forecast_series.index.intersection(forecast_dates.tolist())
                    aligned_forecast.loc[common_dates] = forecast_series.loc[common_dates]
                    
                    last_value = forecast_series.iloc[-1] if len(forecast_series) > 0 else 0.0
                    missing_dates = forecast_dates.difference(common_dates)
                    aligned_forecast.loc[missing_dates] = last_value
                    
                    aligned_forecast = aligned_forecast.fillna(last_value)
                    
                    forecast_to_use = aligned_forecast
                else:
                    forecast_to_use = forecast_series.loc[forecast_dates.intersection(forecast_series.index.tolist())]
                    
                    if len(forecast_to_use) < len(forecast_dates):
                        missing_dates = forecast_dates.difference(forecast_to_use.index)
                        last_value = forecast_series.iloc[-1] if len(forecast_series) > 0 else 0.0
                        for date in missing_dates:
                            forecast_to_use[date] = last_value
                        
                        forecast_to_use = forecast_to_use.sort_index()
                
                if len(forecast_to_use) > forecast_periods:
                    forecast_to_use = forecast_to_use.iloc[:forecast_periods]
                
                with transaction.atomic():
                    existing_forecasts = Timestamp.objects.filter(
                        time_series=child_series,
                        attribute=target_attribute
                    )
                    existing_count = existing_forecasts.count()
                    existing_forecasts.delete()
                    
                    saved_timestamps = []
                    
                    for date, value in forecast_to_use.items():
                        new_timestamp = Timestamp.objects.create(
                            time_series=child_series,
                            attribute=target_attribute,
                            value=str(float(value)),
                            start_dt=date,
                            end_dt=None
                        )
                        saved_timestamps.append(new_timestamp)
                
                return {
                    'success': True,
                    'message': f'Прогноз успешно сохранен. Создано {len(saved_timestamps)} таймстемпов.',
                    'forecast_count': len(saved_timestamps),
                    'child_features_count': len(child_features_series),
                    'existing_deleted': existing_count,
                    'time_series_id': child_series_id,
                    'time_series_name': child_series.name
                }
                
            except Exception as e:
                return {
                    'success': False,
                    'error': f'Ошибка при прогнозировании: {str(e)}'
                }
        else:
            return {
                'success': False,
                'error': 'Неподдерживаемый тип модели прогнозирования'
            }
    
    except ForecastingModel.DoesNotExist:
        return {
            'success': False,
            'error': 'Модель прогнозирования не найдена'
        }
    except TimeSeries.DoesNotExist:
        return {
            'success': False,
            'error': 'Временной ряд не найден'
        }
    except Exception as e:
        return {
            'success': False,
            'error': f'Произошла ошибка: {str(e)}'
        }
