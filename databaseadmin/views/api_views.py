from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
import json
import pandas as pd
from ..models import TimeSeries, Attribute, Timestamp, ForecastingModel
import os
import traceback
import logging
from ..forecasting import SARIMAXAutoForecaster

@login_required
@require_GET
def get_time_series_attributes(request, time_series_id: int) -> JsonResponse:
    """
    API-эндпоинт для получения всех уникальных атрибутов временного ряда
    """
    try:
        if not TimeSeries.objects.filter(time_series_id=time_series_id).exists():
            return JsonResponse({'error': 'Временной ряд не найден'}, status=404)
        
        attributes = Attribute.objects.filter(
            timestamp__time_series_id=time_series_id
        ).distinct()
        
        attributes_data = [
            {
                'id': attr.attribute_id,
                'name': attr.name,
                'data_type': attr.data_type
            }
            for attr in attributes
        ]
        
        return JsonResponse(attributes_data, safe=False)
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_POST
@csrf_exempt
def create_forecasting_model(request) -> JsonResponse:
    """
    API-эндпоинт для создания модели прогнозирования
    """
    try:
        data = json.loads(request.body)
        time_series_id = data.get('time_series_id')
        feature_attribute_id = data.get('feature_attribute_id')
        target_attribute_id = data.get('target_attribute_id')
        
        if not all([time_series_id, feature_attribute_id, target_attribute_id]):
            return JsonResponse({'error': 'Не все обязательные параметры указаны'}, status=400)
        
        try:
            time_series = TimeSeries.objects.get(time_series_id=time_series_id)
            feature_attribute = Attribute.objects.get(attribute_id=feature_attribute_id)
            target_attribute = Attribute.objects.get(attribute_id=target_attribute_id)
        except (TimeSeries.DoesNotExist, Attribute.DoesNotExist):
            return JsonResponse({'error': 'Временной ряд или атрибут не найден'}, status=404)
        
        if feature_attribute_id == target_attribute_id:
            return JsonResponse({'error': 'Атрибуты должны быть разными'}, status=400)
        
        feature_data_exists = Timestamp.objects.filter(
            time_series=time_series,
            attribute=feature_attribute
        ).exists()
        
        target_data_exists = Timestamp.objects.filter(
            time_series=time_series,
            attribute=target_attribute
        ).exists()
        
        if not feature_data_exists or not target_data_exists:
            return JsonResponse({'error': 'Недостаточно данных для указанных атрибутов'}, status=400)
        
        existing_model = ForecastingModel.objects.filter(time_series=time_series).first()
        
        if existing_model:
            existing_model.feature_attribute = feature_attribute
            existing_model.target_attribute = target_attribute
            existing_model.save()
            model = existing_model
            message = 'Модель обновлена'
        else:
            model = ForecastingModel(
                time_series=time_series,
                feature_attribute=feature_attribute,
                target_attribute=target_attribute
            )
            model.save()
            message = 'Модель создана'
        
        return JsonResponse({
            'status': 'success',
            'message': message,
            'model_id': model.model_id
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Некорректный формат JSON'}, status=400)
    
    except Exception as e:
        error_msg = f"Ошибка при создании модели: {str(e)}"
        logging.error(error_msg)
        logging.error(traceback.format_exc())
        return JsonResponse({'error': error_msg}, status=500)

@login_required
@require_POST
@csrf_exempt
def train_forecasting_model(request) -> JsonResponse:
    """
    API-эндпоинт для обучения модели прогнозирования
    Использует SARIMAXAutoForecaster
    """
    try:
        data = json.loads(request.body)
        model_id = data.get('model_id')
        
        if not model_id:
            return JsonResponse({'error': 'Не указан ID модели'}, status=400)
        
        try:
            forecasting_model = ForecastingModel.objects.get(model_id=model_id)
        except ForecastingModel.DoesNotExist:
            return JsonResponse({'error': 'Модель не найдена'}, status=404)
        
        time_series = forecasting_model.time_series
        feature_attribute = forecasting_model.feature_attribute
        target_attribute = forecasting_model.target_attribute
        
        feature_timestamps = Timestamp.objects.filter(
            time_series=time_series,
            attribute=feature_attribute
        ).order_by('start_dt')
        
        target_timestamps = Timestamp.objects.filter(
            time_series=time_series, 
            attribute=target_attribute
        ).order_by('start_dt')
        
        if not feature_timestamps.exists() or not target_timestamps.exists():
            return JsonResponse({'error': 'Недостаточно данных для обучения модели'}, status=400)
            
        try:
            feature_data = {
                ts.start_dt.date(): float(ts.value) 
                for ts in feature_timestamps 
                if ts.value and ts.value.strip()
            }
            
            target_data = {
                ts.start_dt.date(): float(ts.value) 
                for ts in target_timestamps 
                if ts.value and ts.value.strip()
            }
        except ValueError as e:
            error_msg = f"Ошибка при преобразовании данных: {str(e)}"
            logging.error(error_msg)
            return JsonResponse({'error': error_msg}, status=400)
        
        common_dates = sorted(set(feature_data.keys()) & set(target_data.keys()))
        
        if not common_dates:
            return JsonResponse({'error': 'Нет общих дат между атрибутами'}, status=400)
            
        if len(common_dates) < 30:  
            return JsonResponse(
                {'error': f'Недостаточно данных для обучения модели (нужно минимум 30 точек, найдено {len(common_dates)})'},
                status=400
            )
            
        common_dates_ts = pd.to_datetime(common_dates)
        all_price = pd.Series({pd.Timestamp(date): float(feature_data[date]) for date in common_dates})
        all_traffic = pd.Series({pd.Timestamp(date): float(target_data[date]) for date in common_dates})
        
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
            
            temp_dir = os.path.join(project_root, 'models')
            os.makedirs(temp_dir, exist_ok=True)
            
            model_dir = os.path.join(temp_dir, f'model_dir_{model_id}')
            os.makedirs(model_dir, exist_ok=True)
                        
            all_data_filename = os.path.join(model_dir, f'model_{model_id}_all_data.csv')
            
            df_all = pd.DataFrame({
                'date': [date.strftime('%Y-%m-%d') for date in common_dates_ts],
                f'{feature_attribute.name}': all_price.values,
                f'{target_attribute.name}': all_traffic.values
            })
            
            df_all.to_csv(all_data_filename, index=False)
            
            logging.info(f"Данные для модели {model_id} сохранены в директории {model_dir}")
        except Exception as e:
            logging.error(f"Ошибка при сохранении данных: {str(e)}")
            logging.error(traceback.format_exc())
            model_dir = None
                
        try:
            forecaster = SARIMAXAutoForecaster(
                arima_orders=[(1,1,1), (2,1,2), (1,1,0), (0,1,1)], 
                seasonal_orders=[(1,1,1,7), (0,1,1,7)],            
                max_lags=30,
                top_k_features=10,
                train_ratio=0.8
            )
            
            train_size = int(len(common_dates) * 0.8)
            train_dates = common_dates[:train_size]
            test_dates = common_dates[train_size:]
            
            train_dates_ts = pd.to_datetime(train_dates)
            test_dates_ts = pd.to_datetime(test_dates)
            
            train_price = all_price.loc[train_dates_ts]
            train_traffic = all_traffic.loc[train_dates_ts]
            
            test_price = all_price.loc[test_dates_ts]
            test_traffic = all_traffic.loc[test_dates_ts]
            
            logging.info(f"Начало обучения модели ID {model_id} с помощью SARIMAXAutoForecaster")
            forecaster.fit(train_traffic, train_price)
            logging.info(f"Модель ID {model_id} успешно обучена")
            
            try:
                logging.info("Начинаем оценку качества прогнозирования на тестовой выборке")
                
                combined_price = pd.concat([train_price, test_price])
                
                predictions = forecaster.predict(combined_price)
                
                test_predictions = predictions.loc[test_dates_ts] if test_dates_ts[0] in predictions.index else None
                
                if test_predictions is None or len(test_predictions) != len(test_traffic):
                    logging.warning(f"Прогнозные даты не совпадают с тестовыми! Корректируем индексы.")
                    logging.warning(f"Прогнозные даты: {predictions.index}")
                    logging.warning(f"Тестовые даты: {test_traffic.index}")
                    
                    common_idx = pd.DatetimeIndex(
                        predictions.index.intersection(test_traffic.index.to_list())
                    )
                    if len(common_idx) > 0:
                        test_predictions = predictions.loc[common_idx]
                        test_traffic_adj = test_traffic.loc[common_idx]
                        mape = forecaster.get_mape(test_traffic_adj, test_predictions)
                    else:
                        if len(predictions) >= len(test_traffic):
                            adjusted_predictions = pd.Series(
                                predictions.values[-len(test_traffic):], 
                                index=test_traffic.index
                            )
                            mape = forecaster.get_mape(test_traffic, adjusted_predictions)
                        else:
                            raise ValueError("Не удалось сопоставить прогнозные и тестовые данные")
                else:
                    mape = forecaster.get_mape(test_traffic, test_predictions)
                
                logging.info(f"MAPE на тестовой выборке: {mape:.2f}%")
                
                logging.info("Обучаем финальную модель на всех данных")
                final_forecaster = SARIMAXAutoForecaster(
                    arima_orders=forecaster.arima_orders,
                    seasonal_orders=forecaster.seasonal_orders,
                    max_lags=forecaster.max_lags,
                    top_k_features=forecaster.top_k,
                    train_ratio=0.8
                )
                final_forecaster.fit(all_traffic, all_price)
                
                forecasting_model.save_model_object(final_forecaster)
                
            except Exception as eval_error:
                logging.error(f"Ошибка при оценке качества модели: {str(eval_error)}")
                logging.error(traceback.format_exc())
                mape = None
                
                forecasting_model.save_model_object(forecaster)
            
            best_order = forecaster.best_order_
            best_seasonal_order = forecaster.best_seasonal_order_
            
            model_info = forecaster.summary()
            logging.info(f"Дополнительная информация о модели: {model_info}")
            
        except Exception as e:
            error_msg = f"Ошибка при обучении модели: {str(e)}"
            logging.error(error_msg)
            logging.error(traceback.format_exc())
            return JsonResponse({'error': error_msg}, status=500)
        
        result = {
            'status': 'success',
            'message': 'Модель успешно обучена',
            'model_id': model_id,
            'model_type': 'sarimax',
            'model_params': {
                'order': str(best_order) if best_order else "неизвестно",
                'seasonal_order': str(best_seasonal_order) if best_seasonal_order else "неизвестно"
            }
        }
        
        if mape is not None:
            result['mape'] = round(mape, 2)
            result['training_points'] = len(train_dates)
            result['test_points'] = len(test_dates)
        
        try:
            if model_dir and os.path.exists(model_dir):
                result['data_storage'] = {
                    'model_dir': model_dir,
                    'files': {
                        'all_data': f'model_{model_id}_all_data.csv',
                        'model_file': f'model_{model_id}.pkl'
                    }
                }
        except Exception:
            pass
            
        return JsonResponse(result)
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Некорректный формат JSON'}, status=400)
    
    except Exception as e:
        error_msg = f"Ошибка при обучении модели: {str(e)}"
        logging.error(error_msg)
        logging.error(traceback.format_exc())
        return JsonResponse({'error': error_msg}, status=500)

@login_required
@require_POST
@csrf_exempt
def delete_forecasting_model(request) -> JsonResponse:
    """
    API-эндпоинт для удаления модели прогнозирования
    """
    try:
        data = json.loads(request.body)
        model_id = data.get('model_id')
        time_series_id = data.get('time_series_id')
        
        if not model_id and not time_series_id:
            return JsonResponse({'error': 'Не указан ID модели или временного ряда'}, status=400)
        
        try:
            if model_id:
                forecasting_model = ForecastingModel.objects.get(model_id=model_id)
            elif time_series_id:
                forecasting_model = ForecastingModel.objects.get(time_series__time_series_id=time_series_id)
            else:
                return JsonResponse({'error': 'Не указан ID модели или временного ряда'}, status=400)
        except ForecastingModel.DoesNotExist:
            return JsonResponse({'error': 'Модель не найдена'}, status=404)
        except ForecastingModel.MultipleObjectsReturned:
            if time_series_id:
                models = ForecastingModel.objects.filter(time_series__time_series_id=time_series_id)
                for model in models:
                    _delete_model_files(model)
                models.delete()
                
                return JsonResponse({
                    'status': 'success',
                    'message': f'Удалено моделей: {models.count()}'
                })
            else:
                return JsonResponse({'error': 'Найдено несколько моделей, уточните запрос'}, status=400)
        
        _delete_model_files(forecasting_model)
        
        model_id = forecasting_model.model_id  # Сохраняем id перед удалением
        forecasting_model.delete()
        
        return JsonResponse({
            'status': 'success',
            'message': f'Модель {model_id} успешно удалена'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Некорректный формат JSON'}, status=400)
    
    except Exception as e:
        error_msg = f"Ошибка при удалении модели: {str(e)}"
        logging.error(error_msg)
        logging.error(traceback.format_exc())
        return JsonResponse({'error': error_msg}, status=500)

def _delete_model_files(forecasting_model):
    """
    Вспомогательная функция для удаления файлов модели
    """
    try:
        if forecasting_model.model_file_path and os.path.exists(forecasting_model.model_file_path):
            model_dir = os.path.dirname(forecasting_model.model_file_path)
            
            os.remove(forecasting_model.model_file_path)
            
            csv_files = [f for f in os.listdir(model_dir) if f.endswith('.csv')]
            for csv_file in csv_files:
                os.remove(os.path.join(model_dir, csv_file))
            
            try:
                os.rmdir(model_dir)
            except OSError:
                logging.warning(f"Не удалось удалить директорию модели {forecasting_model.model_id}: директория не пуста")
    except Exception as e:
        logging.error(f"Ошибка при удалении файлов модели {forecasting_model.model_id}: {str(e)}")
        logging.error(traceback.format_exc())

@require_POST
@login_required
def forecast_child_series(request):
    """
    API-представление для выполнения прогнозирования для дочернего ряда на основе модели родительского ряда.
    Создает прогнозы для всех точек в дочернем ряду, основываясь на имеющихся данных о признаках.
    """
    try:
        data = json.loads(request.body)
        parent_model_id = data.get('parent_model_id')
        child_series_id = data.get('child_series_id')
        
        if not parent_model_id or not child_series_id:
            return JsonResponse({'error': 'Не указаны обязательные параметры'}, status=400)
        
        # Проверяем существование дочернего ряда
        try:
            child_series = TimeSeries.objects.get(time_series_id=child_series_id)
        except TimeSeries.DoesNotExist:
            return JsonResponse({'error': 'Дочерний ряд не найден'}, status=404)
        
        # Проверяем существование модели прогнозирования
        try:
            forecasting_model = ForecastingModel.objects.get(model_id=parent_model_id)
        except ForecastingModel.DoesNotExist:
            return JsonResponse({'error': 'Модель прогнозирования не найдена'}, status=404)
        
        # Получаем атрибуты модели
        feature_attribute = forecasting_model.feature_attribute
        
        # Получаем количество записей в дочернем ряду для атрибута признака (feature)
        child_feature_count = Timestamp.objects.filter(
            time_series=child_series,
            attribute=feature_attribute
        ).count()
        
        # Используем количество признаков как количество периодов для прогноза
        forecast_periods = child_feature_count
        
        # Выполняем прогнозирование, передавая количество периодов, равное количеству признаков
        from databaseadmin.forecasting import make_forecast_for_child_series
        result = make_forecast_for_child_series(
            parent_model_id=parent_model_id,
            child_series_id=child_series_id,
            forecast_periods=forecast_periods
        )
        
        if result['success']:
            # Добавляем информацию о количестве периодов в ответ
            result['feature_count'] = child_feature_count
            return JsonResponse(result, status=200)
        else:
            return JsonResponse(result, status=400)
            
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Неверный формат JSON'}, status=400)
    except Exception as e:
        return JsonResponse({'error': f'Произошла ошибка: {str(e)}'}, status=500) 