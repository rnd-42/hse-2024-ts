from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse, StreamingHttpResponse, HttpResponseNotFound, HttpResponse, HttpRequest
from django.contrib.auth.decorators import login_required
from ..models import TimeSeries, Product, Attribute, Timestamp, ForecastingModel
from .utils import export_to_csv
import io
import csv
from django.db import models
from typing import List, Dict, Any, Optional, Type, TypeVar, Union, Set
from django.db.models import Model, QuerySet

T = TypeVar('T', bound=Model)


def home(request: HttpRequest) -> HttpResponse:
    """
    Домашняя страница приложения.
    """
    return render(request, 'home.html')


def timeseries_tree_json(request: HttpRequest) -> JsonResponse:
    """
    Представление для получения данных о дереве временных рядов в формате JSON.
    Используется для построения динамического дерева на клиентской стороне.
    """
    parent_id: Optional[Union[str, None]] = request.GET.get('parent_id')

    if parent_id in (None, '', 'null', 'None'):
        children: QuerySet[TimeSeries] = TimeSeries.objects.filter(
            parent_time_series__isnull=True)
    else:
        children: QuerySet[TimeSeries] = TimeSeries.objects.filter(
            parent_time_series_id=parent_id)

    data: List[Dict[str, Any]] = []
    for ts in children:
        has_children: bool = TimeSeries.objects.filter(
            parent_time_series=ts).exists()
        data.append({
            "id": ts.time_series_id,
            "text": ts.name,
            "children": has_children,
        })

    return JsonResponse(data, safe=False)


@login_required
def delete_object(request: HttpRequest, model_name: str, pk: int) -> HttpResponse:
    """
    Общая функция для удаления объекта любой модели.
    """
    if request.method == 'POST':
        model_map: Dict[str, Type[Model]] = {
            'products': Product,
            'time_series': TimeSeries,
            'attributes': Attribute,
            'timestamps': Timestamp
        }

        url_map: Dict[str, str] = {
            'products': 'product_view',
            'time_series': 'timeseries_view',
            'attributes': 'attribute_view',
            'timestamps': 'timestamp_view',
        }

        model: Optional[Type[Model]] = model_map.get(model_name.lower())
        if not model:
            messages.error(
                request, f"Неверная модель для удаления: {model_name}")
            return redirect('home')

        instance: Model = get_object_or_404(model, pk=pk)
        instance.delete()
        messages.success(
            request, f"{model_name.capitalize()} успешно удалён(а).")

        url_name: str = url_map.get(model_name.lower(), model_name)
        return redirect(url_name)
    else:
        messages.error(request, "Удаление возможно только методом POST.")
        return redirect('home')


@login_required
def time_series_tree_view(request: HttpRequest) -> HttpResponse:
    """
    Отображает страницу с древовидным представлением временных рядов.
    """
    root_series: QuerySet[TimeSeries] = TimeSeries.objects.filter(
        parent_time_series__isnull=True).order_by('time_series_id')
    
    # Собираем информацию о моделях прогнозирования
    forecasting_models = ForecastingModel.objects.all()
    forecasting_model_ids = {model.time_series.time_series_id: model.model_id for model in forecasting_models}
    
    # Словарь для хранения количества атрибутов для каждого временного ряда
    timestamp_counts: Dict[int, int] = {}
    
    # Собираем информацию о доступных атрибутах для каждого временного ряда
    all_time_series_attributes: Dict[int, Set[int]] = {}
    
    all_timestamps = Timestamp.objects.values('time_series_id', 'attribute_id').distinct()
    for item in all_timestamps:
        ts_id = item['time_series_id']
        if ts_id not in all_time_series_attributes:
            all_time_series_attributes[ts_id] = set()
        all_time_series_attributes[ts_id].add(item['attribute_id'])
        
    for ts_id, attrs in all_time_series_attributes.items():
        timestamp_counts[ts_id] = len(attrs)

    def get_children(parent_id: int) -> List[Dict[str, Any]]:
        children: QuerySet[TimeSeries] = TimeSeries.objects.filter(
            parent_time_series_id=parent_id)
        data: List[Dict[str, Any]] = []
        for child in children:
            attribute_count = timestamp_counts.get(child.time_series_id, 0)
            
            has_forecasting_model = child.time_series_id in forecasting_model_ids
            
            # Проверяем, есть ли у родителя модель прогнозирования
            parent_has_forecasting_model = parent_id in forecasting_model_ids
            parent_forecasting_model_id = forecasting_model_ids.get(parent_id, None)
            
            child_data: Dict[str, Any] = {
                'id': child.time_series_id,
                'name': child.name,
                'product': child.product.name if child.product else 'Не указан',
                'attribute_count': attribute_count,
                'has_forecasting_model': has_forecasting_model,
                'parent_has_forecasting_model': parent_has_forecasting_model,
                'parent_forecasting_model_id': parent_forecasting_model_id,
            }

            child_children: List[Dict[str, Any]
                                 ] = get_children(child.time_series_id)
            child_data['children'] = child_children

            total_descendants: int = len(child_children)
            for descendant in child_children:
                total_descendants += descendant.get('total_descendants', 0)
            child_data['total_descendants'] = total_descendants

            data.append(child_data)
        return data

    time_series: List[Dict[str, Any]] = []
    for root in root_series:
        attribute_count = timestamp_counts.get(root.time_series_id, 0)
        
        has_forecasting_model = root.time_series_id in forecasting_model_ids
        
        children: List[Dict[str, Any]] = get_children(root.time_series_id)

        total_descendants: int = len(children)
        for child in children:
            total_descendants += child.get('total_descendants', 0)

        time_series.append({
            'id': root.time_series_id,
            'name': root.name,
            'product': root.product.name if root.product else 'Не указан',
            'children': children,
            'total_descendants': total_descendants,
            'attribute_count': attribute_count,
            'has_forecasting_model': has_forecasting_model,
            'parent_has_forecasting_model': False,  # У корневых узлов нет родителей
            'parent_forecasting_model_id': None,
        })

    return render(request, 'time_series_tree.html', {'time_series': time_series})


@login_required
def export_single_table(request: HttpRequest, model_name: str) -> StreamingHttpResponse | HttpResponseNotFound:
    """
    Экспортирует данные из отдельной таблицы в CSV-файл.
    
    Args:
        request: HTTP запрос
        model_name: Имя модели для экспорта
    """
    model_map = {
        'products': Product,
        'attributes': Attribute,
        'time_series': TimeSeries,
        'timestamps': Timestamp,
    }
    
    model = model_map.get(model_name.lower())
    if not model:
        return HttpResponseNotFound("Указанная модель не найдена")
    
    queryset = model.objects.all()
    
    return export_to_csv(queryset, model=model)


FIELD_EXAMPLES = {
    models.CharField: "example_charfield",
    models.TextField: "example_textfield",
    models.IntegerField: "123",
    models.FloatField: "123.45",
    models.DecimalField: "123.45",
    models.BooleanField: "true",
    models.DateField: "2024-01-01",
    models.DateTimeField: "2024-01-01 12:00:00",
    models.TimeField: "12:00:00",
    models.EmailField: "example@example.com",
    models.URLField: "https://example.com",
    models.JSONField: '{"key": "value"}',
    models.ForeignKey: "1",
}


@login_required
def download_csv_template(request: HttpRequest, model_name: str) -> HttpResponse:
    """
    Скачивание шаблона CSV для указанной модели.
    """
    model_map = {
        'products': Product,
        'time_series': TimeSeries,
        'attributes': Attribute,
        'timestamps': Timestamp
    }

    model = model_map.get(model_name.lower())
    if not model:
        return HttpResponseNotFound("Модель не найдена")

    output = io.StringIO()
    writer = csv.writer(output)

    fields = []
    for field in model._meta.fields:
        if isinstance(field, models.AutoField) or (hasattr(field, 'auto_created') and field.auto_created):
            continue

        field_info = {
            'name': field.name,
            'verbose_name': field.verbose_name,
            'help_text': field.help_text,
            'is_required': not field.blank,
            'field': field
        }
        fields.append(field_info)

    writer.writerow([field['name'] for field in fields])

    example_row = []
    for field_info in fields:
        field = field_info['field']

        example_value = None
        for field_class, example in FIELD_EXAMPLES.items():
            if isinstance(field, field_class):
                example_value = example
                break

        if example_value is None:
            example_value = "example_value"

        example_row.append(example_value)

    writer.writerow(example_row)

    content = output.getvalue()
    output.close()

    response = HttpResponse(content, content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{model_name}_template.csv"'

    return response
