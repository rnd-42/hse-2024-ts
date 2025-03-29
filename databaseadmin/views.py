"""
Главный модуль представлений, импортирующий все представления из подмодулей.
"""
from databaseadmin.views.base_views import (
    home, 
    delete_object, 
    timeseries_tree_json, 
    time_series_tree_view
)
from databaseadmin.views.data_views import (
    product_view, 
    attribute_view, 
    timeseries_view, 
    timestamp_view
)
from databaseadmin.views.hierarchy_views import (
    TimeSeriesHierarchyView
)
from databaseadmin.views.utils import (
    apply_filters,
    apply_sorting,
    export_to_csv,
    get_field_types,
    handle_csv_upload,
    Echo
)
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
import csv
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import IntegerField, FloatField, DecimalField, Q
from .models import Product, Attribute, TimeSeries, Timestamp
from .forms import ProductForm, AttributeForm, TimeSeriesForm, TimestampForm
from django.views.generic import TemplateView
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.http import StreamingHttpResponse, JsonResponse
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
import json
import io
from datetime import datetime

# Экспортируем все представления для использования в URLs
__all__ = [
    'home',
    'delete_object',
    'timeseries_tree_json',
    'time_series_tree_view',
    'product_view',
    'attribute_view',
    'timeseries_view',
    'timestamp_view',
    'TimeSeriesHierarchyView',
    'apply_filters',
    'apply_sorting',
    'export_to_csv',
    'get_field_types',
    'handle_csv_upload',
    'Echo'
]

def home(request):  
    return render(request, 'home.html')

def get_field_types(model):
    field_types = {}
    for field in model._meta.fields:
        if isinstance(field, (IntegerField, FloatField, DecimalField)):
            field_types[field.name] = 'number'
        else:
            field_types[field.name] = 'text'
    return field_types


def apply_filters(qs, model, request):
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

def timeseries_tree_json(request):
    parent_id = request.GET.get('parent_id')

    if parent_id in (None, '', 'null', 'None'):  # <-- Добавили эти проверки
        children = TimeSeries.objects.filter(parent_time_series__isnull=True)
    else:
        children = TimeSeries.objects.filter(parent_time_series_id=parent_id)

    data = []
    for ts in children:
        has_children = TimeSeries.objects.filter(parent_time_series=ts).exists()
        data.append({
            "id": ts.time_series_id,
            "text": ts.name,
            "children": has_children,
        })

    return JsonResponse(data, safe=False)


def handle_csv_upload(file, model):
    decoded_file = file.read().decode('utf-8').splitlines()
    reader = csv.reader(decoded_file)
    next(reader)
    for row in reader:
        model.objects.create(**dict(zip([field.name for field in model._meta.fields if field.name != 'id'], row)))

def delete_object(request, model_name, pk):
    if request.method == 'POST':
        model_map = {
            'product': Product,
            'timeseries': TimeSeries,
        }
        model = model_map.get(model_name.lower())
        if not model:
            messages.error(request, "Неверная модель для удаления.")
            return redirect('home')

        instance = get_object_or_404(model, pk=pk)
        instance.delete()
        messages.success(request, f"{model_name.capitalize()} успешно удалён(а).")
        return redirect(f'/{model_name}/')  # или используй reverse()
    else:
        messages.error(request, "Удаление возможно только методом POST.")
        return redirect('home')

class Echo:
    """Фейковый файловый объект, который просто возвращает строку."""
    def write(self, value):
        return value

def export_to_csv(queryset, model):
    """
    Оптимизированная функция экспорта в CSV с использованием chunked iteration
    и потоковой передачи для обработки больших наборов данных.
    """
    if model is None:
        raise ValueError("Model должна быть указана для export_to_csv")
        
    meta = model._meta
    field_names = [field.name for field in meta.fields]
    
    # Создаем имя файла с временной меткой
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    filename = f"{meta.model_name}_export_{timestamp}.csv"

    pseudo_buffer = Echo()
    writer = csv.writer(pseudo_buffer)
    
    # Префетч для оптимизации
    if hasattr(queryset, 'select_related'):
        for field in model._meta.fields:
            if field.is_relation and field.many_to_one:
                queryset = queryset.select_related(field.name)
    
    # Оптимизированный генератор строк
    def row_generator():
        # Записываем заголовок
        yield writer.writerow([field for field in field_names]).encode('utf-8')
        
        # Итерация по пакетам без вызова count()
        chunk_size = 1000  # Меньший размер чанка для более быстрого начала потока
        
        # Используем более эффективную технику итерации
        start_pk = 0
        has_more = True
        pk_field = model._meta.pk.name
        
        while has_more:
            # Запрашиваем данные с фильтрацией по первичному ключу для эффективности
            chunk = list(queryset.filter(**{f"{pk_field}__gt": start_pk}).order_by(pk_field)[:chunk_size])
            if not chunk:
                break
                
            # Обновляем начальное значение PK для следующего чанка
            start_pk = getattr(chunk[-1], pk_field)
            
            # Обработка текущего чанка
            for obj in chunk:
                row_data = []
                for field in field_names:
                    value = getattr(obj, field)
                    # Форматирование даты/времени для CSV
                    if hasattr(value, 'strftime'):
                        value = value.strftime('%Y-%m-%d %H:%M:%S')
                    row_data.append(value)
                yield writer.writerow(row_data).encode('utf-8')
            
            # Отправляем heartbeat после каждого чанка
            yield b''
            
            # Если получили меньше записей, чем размер чанка, значит это последний чанк
            has_more = len(chunk) == chunk_size
    
    # Создаем потоковый ответ
    response = StreamingHttpResponse(
        row_generator(),
        content_type='text/csv; charset=utf-8',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        },
    )
    return response


@login_required
def product_view(request):
    message = ''
    product_form = ProductForm(prefix='product')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'manual':
            product_form = ProductForm(request.POST, prefix='product')
            if product_form.is_valid():
                product_form.save()
                message = 'Продукт добавлен'
        elif action == 'csv' and (file := request.FILES.get('file')):
            handle_csv_upload(file, Product)
            message = 'Продукты загружены из CSV'
    
    qs = Product.objects.all()
    qs = apply_filters(qs, Product, request)
    qs, sort_by, order = apply_sorting(qs, request, [field.name for field in Product._meta.fields], "product_")
    
    if request.GET.get('export') == '1':
        return export_to_csv(qs, model=Product)  
    
    paginator = Paginator(qs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    print(str(page_obj.object_list.query))
    
    print(str(qs.query))

    return render(request, 'data_view.html', {
        'message': message,
        'object_list': page_obj,
        'manual_form': product_form,
        'table_name': 'product',
        'fields': [(f.name, f.verbose_name) for f in Product._meta.fields],
        'field_types': get_field_types(Product),
        'page_obj': page_obj,
        'sort_by': sort_by,
        'order': order,
    })

@login_required
def attribute_view(request):
    message = ''
    attribute_form = AttributeForm(prefix='attribute')
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'manual':
            attribute_form = AttributeForm(request.POST, prefix='attribute')
            if attribute_form.is_valid():
                attribute_form.save()
                message = 'Атрибут добавлен'
        elif action == 'csv' and (file := request.FILES.get('file')):
            handle_csv_upload(file, Attribute)
            message = 'Атрибуты загружены из CSV'
    qs = Attribute.objects.all()
    qs = apply_filters(qs, Attribute, request)
    qs, sort_by, order = apply_sorting(qs, request, [field.name for field in Attribute._meta.fields], "attribute_")
    
    if request.GET.get('export') == '1':
        return export_to_csv(qs, model=Attribute)  
    
    paginator = Paginator(qs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'data_view.html', {
        'message': message,
        'object_list': page_obj,
        'manual_form': attribute_form,
        'table_name': 'attribute',
        'fields': [(f.name, f.verbose_name) for f in Attribute._meta.fields],
        'field_types': get_field_types(Product),
        'page_obj': page_obj,
        'sort_by': sort_by,
        'order': order,
    })

@login_required
def timeseries_view(request):
    message = ''
    timeseries_form = TimeSeriesForm(prefix='timeseries')
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'manual':
            timeseries_form = TimeSeriesForm(request.POST, prefix='timeseries')
            if timeseries_form.is_valid():
                timeseries_form.save()
                message = 'Временной ряд добавлен'
        elif action == 'csv' and (file := request.FILES.get('file')):
            handle_csv_upload(file, TimeSeries)
            message = 'Временные ряды загружены из CSV'
    qs = TimeSeries.objects.all()
    qs = apply_filters(qs, TimeSeries, request)
    qs, sort_by, order = apply_sorting(qs, request, [field.name for field in TimeSeries._meta.fields], "time_series_")
    
    if request.GET.get('export') == '1':
        return export_to_csv(qs, model=TimeSeries)  
    
    paginator = Paginator(qs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'data_view.html', {
        'message': message,
        'object_list': page_obj,
        'manual_form': timeseries_form,
        'table_name': 'timeseries',
        'fields': [(f.name, f.verbose_name) for f in TimeSeries._meta.fields],
        'field_types': get_field_types(Product),
        'page_obj': page_obj,
        'sort_by': sort_by,
        'order': order,
    })

@login_required
def timestamp_view(request):
    message = ''
    timestamp_form = TimestampForm(prefix='timestamp')
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'manual':
            timestamp_form = TimestampForm(request.POST, prefix='timestamp')
            if timestamp_form.is_valid():
                timestamp_form.save()
                message = 'Таймстемп добавлен'
        elif action == 'csv' and (file := request.FILES.get('file')):
            handle_csv_upload(file, Timestamp)
            message = 'Таймстемпы загружены из CSV'
    qs = Timestamp.objects.all()
    qs = apply_filters(qs, Timestamp, request)
    qs, sort_by, order = apply_sorting(qs, request, [field.name for field in Timestamp._meta.fields], "timestamp_")
    
    if request.GET.get('export') == '1':
        return export_to_csv(qs, model=Timestamp)  
    
    paginator = Paginator(qs, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    return render(request, 'data_view.html', {
        'message': message,
        'object_list': page_obj,
        'manual_form': timestamp_form,
        'table_name': 'timestamp',
        'fields': [(f.name, f.verbose_name) for f in Timestamp._meta.fields],
        'field_types': get_field_types(Product),
        'page_obj': page_obj,
        'sort_by': sort_by,
        'order': order,
    })

@login_required
def time_series_tree_view(request):
    # Получаем корневые временные ряды
    root_series = TimeSeries.objects.filter(parent_time_series__isnull=True)

    # Рекурсивная функция для получения иерархии
    def get_children(parent_id):
        children = TimeSeries.objects.filter(parent_time_series_id=parent_id)
        data = []
        for child in children:
            child_data = {
                'id': child.time_series_id,
                'name': child.name,
                'product': child.product.name if child.product else 'Не указан',
            }
            
            # Получаем детей текущего узла
            child_children = get_children(child.time_series_id)
            child_data['children'] = child_children
            
            # Считаем общее количество потомков (включая потомков потомков)
            total_descendants = len(child_children)
            for descendant in child_children:
                total_descendants += descendant.get('total_descendants', 0)
            child_data['total_descendants'] = total_descendants
            
            data.append(child_data)
        return data

    # Строим дерево с корневыми элементами
    time_series = []
    for root in root_series:
        # Получаем детей корневого элемента
        children = get_children(root.time_series_id)
        
        # Считаем общее количество потомков
        total_descendants = len(children)
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



class TimeSeriesHierarchyView(TemplateView):
    template_name = 'time_series_hierarchy.html'

    def _apply_filter(self, data, field, operator, value):
        filtered_data = []
        for item in data:
            field_value = str(item.get(field, '')).lower()
            filter_value = str(value).lower()
            
            if operator == 'exact':
                if field_value == filter_value:
                    filtered_data.append(item)
            elif operator == 'iexact':
                if field_value == filter_value:
                    filtered_data.append(item)
            elif operator == 'contains':
                if filter_value in field_value:
                    filtered_data.append(item)
            elif operator == 'icontains':
                if filter_value in field_value:
                    filtered_data.append(item)
            elif operator == 'startswith':
                if field_value.startswith(filter_value):
                    filtered_data.append(item)
            elif operator == 'endswith':
                if field_value.endswith(filter_value):
                    filtered_data.append(item)
            elif operator == 'gt':
                try:
                    if float(field_value) > float(filter_value):
                        filtered_data.append(item)
                except ValueError:
                    continue
            elif operator == 'gte':
                try:
                    if float(field_value) >= float(filter_value):
                        filtered_data.append(item)
                except ValueError:
                    continue
            elif operator == 'lt':
                try:
                    if float(field_value) < float(filter_value):
                        filtered_data.append(item)
                except ValueError:
                    continue
            elif operator == 'lte':
                try:
                    if float(field_value) <= float(filter_value):
                        filtered_data.append(item)
                except ValueError:
                    continue
        
        return filtered_data
        
    def _apply_filters(self, data, filter_fields, filter_operators, filter_values):
        """Применяет множественные фильтры к данным иерархии."""
        if not filter_fields or not filter_operators or not filter_values:
            return data
            
        # Если только один фильтр и используется старый формат
        if len(filter_fields) == 1 and filter_fields[0] and filter_values[0]:
            return self._apply_filter(data, filter_fields[0], filter_operators[0], filter_values[0])
            
        # Применяем последовательно все фильтры
        filtered_data = data
        for field, operator, value in zip(filter_fields, filter_operators, filter_values):
            if field and value:
                filtered_data = self._apply_filter(filtered_data, field, operator, value)
                
        return filtered_data
        
    def _get_sort_key(self, item, field):
        """Получает ключ для сортировки с учетом типа данных."""
        value = item.get(field, '')
        # Пробуем преобразовать в число для числовой сортировки
        if isinstance(value, (int, float)):
            return value
        try:
            return float(value)
        except (ValueError, TypeError):
            # Для дат пытаемся сначала преобразовать в datetime
            if field in ['start_dt', 'end_dt'] and value:
                try:
                    if isinstance(value, str):
                        return datetime.fromisoformat(value.replace('Z', '+00:00'))
                    return value
                except (ValueError, TypeError):
                    pass
            # Для остальных случаев возвращаем строку в нижнем регистре
            return str(value).lower()
            
    def _apply_sorting(self, data, sort_fields, sort_orders):
        """Применяет множественные сортировки к данным иерархии."""
        if not sort_fields or not sort_fields[0]:
            return data
        
        # Копируем данные, чтобы не изменять оригинал
        sorted_data = data.copy()
        
        # Сортируем по нескольким полям в порядке их указания (от последнего к первому)
        for field, order in reversed(list(zip(sort_fields, sort_orders))):
            if field:
                reverse = order == 'desc'
                # Используем стабильную сортировку
                sorted_data = sorted(sorted_data, key=lambda x: self._get_sort_key(x, field), reverse=reverse)
                
        return sorted_data

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Получаем выбранный временной ряд
        series_id = self.request.GET.get('series_id')
        selected_series = None
        hierarchy_data = []
        error = None

        if series_id:
            try:
                selected_series = TimeSeries.objects.get(time_series_id=series_id)
                hierarchy_data = selected_series.get_hierarchy_data()
            except TimeSeries.DoesNotExist:
                error = "Временной ряд не найден"
            except Exception as e:
                error = f"Ошибка при получении данных: {str(e)}"

        # Получаем все доступные временные ряды
        available_series = TimeSeries.objects.all().order_by('name')

        # Получаем параметры фильтрации (поддержка обоих форматов)
        filter_fields = self.request.GET.getlist('filter_field[]') or [self.request.GET.get('filter_field')]
        filter_operators = self.request.GET.getlist('filter_operator[]') or [self.request.GET.get('filter_operator')]
        filter_values = self.request.GET.getlist('filter_value[]') or [self.request.GET.get('filter_value')]

        # Применяем фильтры
        hierarchy_data = self._apply_filters(hierarchy_data, filter_fields, filter_operators, filter_values)

        # Получаем параметры сортировки (поддержка обоих форматов)
        sort_fields = self.request.GET.getlist('sort_by[]') or [self.request.GET.get('sort_by')]
        sort_orders = self.request.GET.getlist('order[]') or [self.request.GET.get('order', 'asc')]

        # Применяем сортировку
        hierarchy_data = self._apply_sorting(hierarchy_data, sort_fields, sort_orders)

        # Сохраняем общее количество записей
        total_count = len(hierarchy_data)
        
        # Применяем пагинацию
        paginator = Paginator(hierarchy_data, 50)
        page = self.request.GET.get('page', 1)
        try:
            hierarchy_data = paginator.page(page)
        except PageNotAnInteger:
            hierarchy_data = paginator.page(1)
        except EmptyPage:
            hierarchy_data = paginator.page(paginator.num_pages)

        fields = [
            ('depth', 'Глубина'),
            ('initial_time_series_id', 'ID исходного ряда'),
            ('attribute_id', 'ID атрибута'),
            ('value', 'Значение'),
            ('start_dt', 'Начало'),
            ('end_dt', 'Конец'),
        ]

        # Скрытые поля для формы фильтрации и сортировки
        hidden_fields = {}
        if selected_series:
            hidden_fields['series_id'] = selected_series.time_series_id

        context.update({
            'title': 'Сбор таймстемпов иерархически',
            'table_name': 'hierarchy',
            'available_series': available_series,
            'selected_series': selected_series,
            'hierarchy_data': hierarchy_data,
            'object_list': hierarchy_data,  # Для совместимости с data_view.html
            'page_obj': hierarchy_data,     # Для совместимости с data_view.html
            'total_items': total_count,     # Для совместимости со старым кодом
            'error': error,
            'fields': fields,
            'filter_field': filter_fields[0] if filter_fields else None,  # Для обратной совместимости
            'filter_operator': filter_operators[0] if filter_operators else None,
            'filter_value': filter_values[0] if filter_values else None,
            'sort_by': sort_fields[0] if sort_fields else None,  # Для обратной совместимости
            'order': sort_orders[0] if sort_orders else 'asc',
            'show_add_form': False,         # Скрыть форму добавления
            'show_actions': False,          # Скрыть колонку действий
            'show_export_button': False,    # Скрыть кнопку экспорта
            'hidden_fields': hidden_fields, # Скрытые поля для формы фильтрации
        })
        return context