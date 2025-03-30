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
    # Поддержка как старых так и новых параметров
    filter_fields: List[str] = request.GET.getlist(
        'filter_field[]') or request.GET.getlist('filter_field')
    filter_operators: List[str] = request.GET.getlist(
        'filter_operator[]') or request.GET.getlist('filter_operator')
    filter_values: List[str] = request.GET.getlist(
        'filter_value[]') or request.GET.getlist('filter_value')
    filters: Q = Q()

    for field, operator, value in zip(filter_fields, filter_operators, filter_values):
        if field and field in fields and value:
            field_type: Type[models.Field] = fields[field]
            is_numeric: bool = field_type in [
                IntegerField, FloatField, DecimalField]

            if is_numeric and operator in ["gt", "gte", "lt", "lte"]:
                try:
                    value = float(value)
                    filters &= Q(**{f"{field}__{operator}": value})
                except ValueError:
                    continue
            else:
                filters &= Q(**{f"{field}__{operator}": value})

    return qs.filter(filters)


def apply_sorting(qs: QuerySet, request: HttpRequest, allowed_sort_fields: List[str], prefix: str, primary_key: str = 'id') -> Tuple[QuerySet, str, str]:
    """
    Применяет сортировку к QuerySet на основе параметров запроса.
    
    Args:
        qs: QuerySet для сортировки
        request: HTTP-запрос
        allowed_sort_fields: Список разрешенных полей для сортировки
        prefix: Префикс для полей сортировки
        primary_key: Имя первичного ключа (по умолчанию 'id')
    
    Returns:
        Кортеж (отсортированный QuerySet, поле сортировки, порядок сортировки)
    """
    # Поддержка как старых так и новых параметров сортировки
    sort_fields_raw = request.GET.getlist(
        'sort_by[]') or [request.GET.get('sort_by', '')]
    sort_orders_raw = request.GET.getlist(
        'order[]') or [request.GET.get('order', 'asc')]

    sort_fields: List[str] = [str(f) for f in sort_fields_raw if f]
    sort_orders: List[str] = [str(o) for o in sort_orders_raw if o]

    # Если нет полей сортировки, используем primary_key по умолчанию
    if not sort_fields or not sort_fields[0]:
        sort_fields = [prefix + primary_key]
        sort_orders = ['asc']

    # Формируем список полей сортировки для order_by
    order_by_fields: List[str] = []
    for field, order in zip(sort_fields, sort_orders):
        if field in allowed_sort_fields:
            order_by_fields.append(("-" if order == "desc" else "") + field)

    # Если нет валидных полей, используем primary_key
    if not order_by_fields:
        order_by_fields = [primary_key]

    # Применяем сортировку
    qs = qs.order_by(*order_by_fields)

    # Возвращаем первое поле сортировки и порядок для обратной совместимости
    primary_sort: str = sort_fields[0] if sort_fields else prefix + primary_key
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

    # Подготовка данных о полях
    fields: List[Dict[str, str]] = []
    for field in model._meta.fields:
        # Для ForeignKey используем field_id
        if field.get_internal_type() == 'ForeignKey':
            field_export_name = f"{field.name}_id"
        else:
            field_export_name = field.name

        fields.append({
            'name': field.name,
            'export_name': field_export_name
        })

    # Получаем имена полей для экспорта
    header_names: List[str] = [field['export_name'] for field in fields]

    timestamp: str = datetime.now().strftime('%Y%m%d%H%M%S')
    filename: str = f"{model_name}_export_{timestamp}.csv"

    # Используем Echo для создания псевдо-буфера для записи в ответ
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

    # Функция для преобразования данных в строки CSV
    def get_csv_data() -> Generator[bytes, None, None]:
        # Заголовок - используем имена полей для экспорта
        yield writer.writerow(header_names).encode('utf-8')

        # Получаем имя поля для фильтрации (обычно это primary key)
        pk_field: str = model._meta.pk.name if model._meta.pk else 'id'  # Используем правильное имя первичного ключа модели

        # Инициализируем queryset, если не передан
        nonlocal queryset
        if queryset is None:
            queryset = model.objects.all()

        # Оптимизируем запросы для связанных полей
        for field in model._meta.fields:
            if field.is_relation and field.many_to_one and hasattr(queryset, 'select_related'):
                queryset = queryset.select_related(field.name)

        # Обрабатываем данные частями для экономии памяти
        chunk_size: int = 1000
        last_pk: int = 0
        has_more: bool = True

        while has_more:
            # Фильтруем по первичному ключу для эффективности
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

                    # Для ForeignKey полей извлекаем ID
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
        # Используем оригинальное имя поля вместо verbose_name
        display_name = field.name
        # Если есть verbose_name, используем его, но сохраняем подчеркивания
        if hasattr(field, 'verbose_name') and field.verbose_name != field.name:
            display_name = str(field.verbose_name)

        # Делаем первую букву заглавной
        display_name = display_name[0].upper() + display_name[1:]

        result.append((field.name, display_name))

    return result
