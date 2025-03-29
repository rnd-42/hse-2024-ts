from django.http import StreamingHttpResponse
from django.db.models import IntegerField, FloatField, DecimalField, Q
import csv
from datetime import datetime, date

class Echo:
    """Фейковый файловый объект, который просто возвращает строку."""
    def write(self, value):
        return value


def get_field_types(model):
    """
    Возвращает словарь типов полей модели для использования в интерфейсе.
    Определяет числовые и текстовые поля.
    """
    field_types = {}
    for field in model._meta.fields:
        if isinstance(field, (IntegerField, FloatField, DecimalField)):
            field_types[field.name] = 'number'
        else:
            field_types[field.name] = 'text'
    return field_types


def apply_filters(qs, model, request):
    """
    Применяет фильтры к запросу QuerySet на основе параметров GET запроса.
    Поддерживает как старый формат параметров, так и новый (с массивами).
    """
    fields = {field.name: type(field) for field in model._meta.fields}
    # Поддержка как старых так и новых параметров
    filter_fields = request.GET.getlist('filter_field[]') or request.GET.getlist('filter_field')
    filter_operators = request.GET.getlist('filter_operator[]') or request.GET.getlist('filter_operator')
    filter_values = request.GET.getlist('filter_value[]') or request.GET.getlist('filter_value')
    filters = Q()
    
    for field, operator, value in zip(filter_fields, filter_operators, filter_values):
        if field and field in fields and value:
            field_type = fields[field]
            is_numeric = field_type in [IntegerField, FloatField, DecimalField]
            
            if is_numeric and operator in ["gt", "gte", "lt", "lte"]:
                try:
                    value = float(value)
                    filters &= Q(**{f"{field}__{operator}": value})
                except ValueError:
                    continue
            else:
                filters &= Q(**{f"{field}__{operator}": value})
    
    return qs.filter(filters)


def apply_sorting(qs, request, allowed_sort_fields, prefix):
    """
    Применяет сортировку к QuerySet на основе параметров GET запроса.
    Поддерживает множественную сортировку по нескольким полям.
    """
    # Поддержка как старых так и новых параметров сортировки
    sort_fields = request.GET.getlist('sort_by[]') or [request.GET.get('sort_by')]
    sort_orders = request.GET.getlist('order[]') or [request.GET.get('order', 'asc')]
    
    # Если нет полей сортировки, используем id по умолчанию
    if not sort_fields or not sort_fields[0]:
        sort_fields = [prefix + 'id']
        sort_orders = ['asc']
    
    # Формируем список полей сортировки для order_by
    order_by_fields = []
    for field, order in zip(sort_fields, sort_orders):
        if field in allowed_sort_fields:
            order_by_fields.append(("-" if order == "desc" else "") + field)
    
    # Если нет валидных полей, используем id
    if not order_by_fields:
        order_by_fields = ['id']
    
    # Применяем сортировку
    qs = qs.order_by(*order_by_fields)
    
    # Возвращаем первое поле сортировки и порядок для обратной совместимости
    primary_sort = sort_fields[0] if sort_fields else prefix + 'id'
    primary_order = sort_orders[0] if sort_orders else 'asc'
    
    return qs, primary_sort, primary_order


def handle_csv_upload(file, model):
    """
    Загружает данные из CSV файла в указанную модель.
    """
    decoded_file = file.read().decode('utf-8').splitlines()
    reader = csv.reader(decoded_file)
    next(reader)  # Пропускаем заголовок
    for row in reader:
        model.objects.create(**dict(zip([field.name for field in model._meta.fields if field.name != 'id'], row)))


def export_to_csv(queryset, model=None):
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
    field_names = [field.name for field in model._meta.fields]
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    filename = f"{model_name}_export_{timestamp}.csv"
    
    # Используем Echo для создания псевдо-буфера, который запишет строки в StreamingHttpResponse
    pseudo_buffer = Echo()
    writer = csv.writer(pseudo_buffer)
    
    # Создаем генератор CSV строк для потоковой передачи
    def rows_generator():
        nonlocal queryset
        
        # Заголовок CSV
        yield writer.writerow(field_names)
        
        # Получаем имя поля для фильтрации (обычно это primary key)
        pk_field = model._meta.pk.name
        
        # Проверяем и инициализируем queryset если он не был передан
        if queryset is None:
            queryset = model.objects.all()
        
        # Оптимизируем запросы для связанных полей
        for field in model._meta.fields:
            if field.is_relation and field.many_to_one and hasattr(queryset, 'select_related'):
                queryset = queryset.select_related(field.name)
        
        # Обрабатываем данные частями (chunks) для экономии памяти
        chunk_size = 1000
        last_pk = 0
        has_more = True
        
        # Обрабатываем данные поэтапно
        while has_more:
            # Берем только следующий кусок данных
            chunk = list(queryset.filter(**{f"{pk_field}__gt": last_pk}).order_by(pk_field)[:chunk_size])
            
            # Если нет данных, завершаем обработку
            if not chunk:
                break
                
            # Обновляем last_pk для следующей итерации
            last_pk = getattr(chunk[-1], pk_field)
            
            # Генерируем CSV-строки для текущего набора данных
            for obj in chunk:
                row = []
                for field in field_names:
                    value = getattr(obj, field)
                    # Форматирование дат для CSV
                    if isinstance(value, (datetime, date)):
                        value = value.strftime('%Y-%m-%d %H:%M:%S')
                    elif value is None:
                        value = ''
                    row.append(value)
                yield writer.writerow(row)
            
            # Проверяем, есть ли еще данные
            has_more = len(chunk) == chunk_size
    
    # Создаем и возвращаем StreamingHttpResponse для эффективной потоковой передачи
    response = StreamingHttpResponse(
        rows_generator(),
        content_type='text/csv',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'
    return response 