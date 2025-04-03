from django.http import StreamingHttpResponse, HttpRequest
from django.db.models import IntegerField, FloatField, DecimalField, Q, Model, QuerySet
from django.db import models
import csv
from datetime import datetime
from typing import Dict, List, Any, Optional, Type, Tuple, Generator

def get_field_types(model: Type[Model]) -> Dict[str, str]:
    """
    Возвращает словарь типов полей модели для использования в интерфейсе.
    Определяет числовые и текстовые поля.
    """
    field_types: Dict[str, str] = {}
    for field in model._meta.fields:
        if isinstance(field, (IntegerField, FloatField, DecimalField)):
            field_types[field.name] = 'number'
        else:
            field_types[field.name] = 'text'
    return field_types


def apply_filters(qs: QuerySet, model: Type[Model], request: HttpRequest) -> QuerySet:
    """
    Применяет фильтры к запросу QuerySet на основе параметров GET запроса.
    Поддерживает как старый формат параметров, так и новый (с массивами).
    """
    fields: Dict[str, Type[models.Field]] = {
        field.name: type(field) for field in model._meta.fields}
    filter_fields: List[str] = request.GET.getlist(
        'filter_field[]') or request.GET.getlist('filter_field')
    filter_operators: List[str] = request.GET.getlist(
        'filter_operator[]') or request.GET.getlist('filter_operator')
    filter_values: List[str] = request.GET.getlist(
        'filter_value[]') or request.GET.getlist('filter_value')
    filters: Q = Q()

    for field, operator, value in zip(filter_fields, filter_operators, filter_values):
        if not field or not operator or not value:
            continue
            
        db_field = field
        if field.endswith('_id') and field[:-3] in fields:
            db_field = field[:-3] + '_id'
            field_type = fields[field[:-3]]
            is_numeric = True  # ID всегда числовые
        elif field in fields:
            db_field = field
            field_type = fields[field]
            is_numeric = field_type in [IntegerField, FloatField, DecimalField]
        else:
            continue

        if is_numeric and operator in ["gt", "gte", "lt", "lte", "exact"]:
            try:
                value = float(value)
                filters &= Q(**{f"{db_field}__{operator}": value})
            except ValueError:
                continue
        else:
            filters &= Q(**{f"{db_field}__{operator}": value})

    return qs.filter(filters)


def apply_sorting(qs: QuerySet, request: HttpRequest, allowed_sort_fields: List[str], prefix: str, primary_key: str = 'id') -> Tuple[QuerySet, str, str]:
    """
    Применяет сортировку к QuerySet на основе параметров запроса.
    
    Args:
        qs: QuerySet для сортировки
        request: HTTP-запрос
        allowed_sort_fields: Список разрешенных полей для сортировки
        prefix: Префикс для полей сортировки
        primary_key: Имя первичного ключа (должно быть указано для каждой модели)
    
    Returns:
        Кортеж (отсортированный QuerySet, поле сортировки, порядок сортировки)
    """
    sort_fields_raw = request.GET.getlist(
        'sort_by[]') or [request.GET.get('sort_by', '')]
    sort_orders_raw = request.GET.getlist(
        'order[]') or [request.GET.get('order', 'asc')]

    sort_fields: List[str] = [str(f) for f in sort_fields_raw if f]
    sort_orders: List[str] = [str(o) for o in sort_orders_raw if o]

    if not sort_fields or not sort_fields[0]:
        sort_fields = [primary_key]  # Используем переданный primary_key без префикса
        sort_orders = ['asc']

    order_by_fields: List[str] = []
    for field, order in zip(sort_fields, sort_orders):
        db_field = field
        if field.endswith('_id') and field[:-3] in allowed_sort_fields:
            db_field = field
        elif field in allowed_sort_fields:
            db_field = field
        else:
            continue
            
        order_by_fields.append(("-" if order == "desc" else "") + db_field)

    if not order_by_fields:
        order_by_fields = [primary_key]

    qs = qs.order_by(*order_by_fields)

    primary_sort: str = sort_fields[0] if sort_fields else primary_key
    primary_order: str = sort_orders[0] if sort_orders else 'asc'

    return qs, primary_sort, primary_order


def export_to_csv(queryset: Optional[QuerySet], model: Optional[Type[Model]] = None) -> StreamingHttpResponse:
    """
    Оптимизированная функция для экспорта QuerySet в CSV-файл с использованием потоковой передачи.

    Оптимизации:
    - Использует chunked processing для экономии памяти
    - Использует StreamingHttpResponse для эффективной потоковой передачи
    - Избегает вызова count() для больших таблиц
    - Применяет фильтрацию по primary key для эффективного извлечения данных

    Args:
        queryset: Django QuerySet для экспорта
        model: Модель Django (опционально, если не указана, будет взята из queryset)
    """
    if model is None and queryset:
        model = queryset.model

    if model is None:
        raise ValueError("Модель должна быть указана для export_to_csv")

    model_name = model._meta.model_name

    fields: List[Dict[str, str]] = []
    for field in model._meta.fields:
        if field.get_internal_type() == 'ForeignKey':
            field_export_name = f"{field.name}_id"
        else:
            field_export_name = field.name

        fields.append({
            'name': field.name,
            'export_name': field_export_name
        })

    header_names: List[str] = [field['export_name'] for field in fields]

    timestamp: str = datetime.now().strftime('%Y%m%d%H%M%S')
    filename: str = f"{model_name}_export_{timestamp}.csv"

    class BOMEcho:
        """
        Класс, который имитирует файлоподобный объект, который пишет в дополнительный объект.
        Также автоматически добавляет BOM-маркер для поддержки Unicode.
        """

        def __init__(self) -> None:
            self.first_write: bool = True

        def write(self, value: str) -> str:
            if self.first_write:
                self.first_write = False
                return '\ufeff' + value
            return value

    pseudo_buffer: BOMEcho = BOMEcho()
    writer = csv.writer(pseudo_buffer)

    def get_csv_data() -> Generator[bytes, None, None]:
        yield writer.writerow(header_names).encode('utf-8')

        pk_field: str = model._meta.pk.name if model._meta.pk is not None else 'id'
        
        nonlocal queryset
        if queryset is None:
            queryset = model.objects.all()

        for field in model._meta.fields:
            if field.is_relation and field.many_to_one and hasattr(queryset, 'select_related'):
                queryset = queryset.select_related(field.name)

        chunk_size: int = 1000
        last_pk: int = 0
        has_more: bool = True

        while has_more:
            chunk: List[Model] = list(queryset.filter(
                **{f"{pk_field}__gt": last_pk}).order_by(pk_field)[:chunk_size])

            if not chunk:
                break

            last_pk = getattr(chunk[-1], pk_field)

            for obj in chunk:
                row: List[Any] = []
                for field_info in fields:
                    field_name: str = field_info['name']
                    value: Any = getattr(obj, field_name)

                    if isinstance(value, models.Model):
                        value = value.pk

                    row.append(value)
                yield writer.writerow(row).encode('utf-8')

    response = StreamingHttpResponse(
        get_csv_data(), content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def get_field_names_with_underscores(model):
    """
    Возвращает список кортежей (имя_поля, отображаемое_имя) для модели,
    сохраняя подчеркивания в именах полей.

    Args:
        model: Django модель

    Returns:
        Список кортежей [(name, display_name), ...]
    """
    result = []
    for field in model._meta.fields:
        display_name = field.name
        if hasattr(field, 'verbose_name') and field.verbose_name != field.name:
            display_name = str(field.verbose_name)

        display_name = display_name[0].upper() + display_name[1:]

        result.append((field.name, display_name))

    return result

def get_field_info(model: Type[Model]) -> List[Dict[str, Any]]:
    """
    Получает информацию о полях модели.
    """
    field_info = []
    for field in model._meta.fields:
        if field.auto_created:
            continue

        field_info.append({
            'name': field.name,
            'verbose_name': field.verbose_name,
            'help_text': field.help_text,
            'required': not field.null and not field.blank
        })
    return field_info

def convert_fields_to_tuple(fields_info: List[Dict[str, str]]) -> List[Tuple[str, str]]:
    """
    Преобразует список словарей с информацией о полях 
    в список кортежей (имя_поля, отображаемое_имя).
    
    Args:
        fields_info: Список словарей с информацией о полях
            [{'name': 'field_name', 'verbose_name': 'Field Name', ...}, ...]
    
    Returns:
        Список кортежей [(name, display_name), ...]
    """
    result = []
    for field in fields_info:
        name = field.get('name', '')
        verbose_name = field.get('verbose_name', name)
        result.append((name, verbose_name))
    
    return result

def split_foreign_keys_to_fields(model: Type[Model]) -> List[Tuple[str, str]]:
    """
    Создает список кортежей (имя_поля, отображаемое_имя) для модели,
    разделяя поля ForeignKey на два отдельных поля: 
    одно для ID (field_id), другое для связанного объекта (field).
    
    Args:
        model: Django модель
    
    Returns:
        Список кортежей [(name, display_name), ...]
    """
    result = []
    
    for field in model._meta.fields:
        if field.auto_created:
            continue
        
        field_name = field.name
        
        if field.get_internal_type() == 'ForeignKey':
            id_field_name = f"{field_name}_id"
            result.append((id_field_name, id_field_name))
            
            result.append((field_name, field_name))
        else:
            result.append((field_name, field_name))
    
    return result
