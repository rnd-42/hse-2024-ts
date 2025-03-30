from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.http import JsonResponse, StreamingHttpResponse, HttpResponseNotFound, HttpResponse, HttpRequest
from django.contrib.auth.decorators import login_required
from ..models import TimeSeries, Product, Attribute, Timestamp
from .utils import export_to_csv
import io
import csv
from django.db import models
from typing import List, Dict, Any, Optional, Type, TypeVar, Union
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
        # Соответствие между именами таблиц и классами моделей
        model_map: Dict[str, Type[Model]] = {
            'products': Product,
            'time_series': TimeSeries,
            'attributes': Attribute,
            'timestamps': Timestamp
        }

        # Соответствие между именами таблиц и URL для перенаправления
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

        # Перенаправление на соответствующую страницу
        url_name: str = url_map.get(model_name.lower(), model_name)
        return redirect(url_name)
    else:
        messages.error(request, "Удаление возможно только методом POST.")
        return redirect('home')


@login_required
def time_series_tree_view(request: HttpRequest) -> HttpResponse:
    """
    Представление для страницы с древовидной структурой временных рядов.
    """
    # Получаем корневые временные ряды
    root_series: QuerySet[TimeSeries] = TimeSeries.objects.filter(
        parent_time_series__isnull=True)

    # Рекурсивная функция для получения иерархии
    def get_children(parent_id: int) -> List[Dict[str, Any]]:
        children: QuerySet[TimeSeries] = TimeSeries.objects.filter(
            parent_time_series_id=parent_id)
        data: List[Dict[str, Any]] = []
        for child in children:
            child_data: Dict[str, Any] = {
                'id': child.time_series_id,
                'name': child.name,
                'product': child.product.name if child.product else 'Не указан',
            }

            # Получаем детей текущего узла
            child_children: List[Dict[str, Any]
                                 ] = get_children(child.time_series_id)
            child_data['children'] = child_children

            # Считаем общее количество потомков (включая потомков потомков)
            total_descendants: int = len(child_children)
            for descendant in child_children:
                total_descendants += descendant.get('total_descendants', 0)
            child_data['total_descendants'] = total_descendants

            data.append(child_data)
        return data

    # Строим дерево с корневыми элементами
    time_series: List[Dict[str, Any]] = []
    for root in root_series:
        # Получаем детей корневого элемента
        children: List[Dict[str, Any]] = get_children(root.time_series_id)

        # Считаем общее количество потомков
        total_descendants: int = len(children)
        for child in children:
            total_descendants += child.get('total_descendants', 0)

        time_series.append({
            'id': root.time_series_id,
            'name': root.name,
            'product': root.product.name if root.product else 'Не указан',
            'children': children,
            'total_descendants': total_descendants
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
    
    # Получаем все записи модели
    queryset = model.objects.all()
    
    # Используем существующую функцию для экспорта в CSV
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
