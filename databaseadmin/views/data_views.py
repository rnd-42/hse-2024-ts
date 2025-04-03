from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpRequest, HttpResponse, StreamingHttpResponse
from django.db import transaction
import csv
import io
from ..models import Product, Attribute, TimeSeries, Timestamp
from ..forms import ProductForm, AttributeForm, TimeSeriesForm, TimestampForm
from .utils import apply_filters, apply_sorting, export_to_csv, get_field_types, get_field_info, convert_fields_to_tuple, split_foreign_keys_to_fields
from typing import Dict, List, Any, Type
from django.db.models import Model, QuerySet
from django.forms import ModelForm
from django.db import models


def handle_csv_upload(request: HttpRequest, model: Type[Model]) -> JsonResponse | StreamingHttpResponse:
    """
    Обрабатывает загрузку CSV файла.
    """
    if 'file' not in request.FILES:
        return JsonResponse({'error': 'Файл не найден'}, status=400)

    file = request.FILES['file']
    if file.size > 10 * 1024 * 1024:  # 10MB
        return JsonResponse({'error': 'Файл слишком большой (макс. 10MB)'}, status=400)

    try:
        content = file.read().decode('utf-8-sig')
        reader = csv.DictReader(io.StringIO(content))

        # Получаем имя первичного ключа модели, если есть
        pk_name = model._meta.pk.name if model._meta.pk is not None else 'id'
        
        required_fields = [
            f.name for f in model._meta.fields if not f.auto_created and f.name != pk_name and not f.blank]
        missing_fields = [
            field for field in required_fields if field not in reader.fieldnames]

        if missing_fields:
            return JsonResponse({
                'error': 'Отсутствуют обязательные поля',
                'missing_fields': missing_fields
            }, status=400)

        # Получаем информацию о всех полях модели
        model_fields = {}
        for field in model._meta.fields:
            model_fields[field.name] = field

        with transaction.atomic():
            success_count = 0
            error_count = 0
            errors = []

            for row in reader:
                try:
                    # Преобразуем ключи словаря в строки и удаляем пустые значения
                    cleaned_row = {}
                    for k, v in row.items():
                        if v and k is not None:
                            key = str(k).strip()
                            if isinstance(v, str):
                                cleaned_row[key] = v.strip()
                            else:
                                cleaned_row[key] = v
                    
                    # Обрабатываем внешние ключи (ForeignKey)
                    for field_name, value in list(cleaned_row.items()):
                        if field_name in model_fields and hasattr(model_fields[field_name], 'related_model'):
                            field = model_fields[field_name]
                            related_model = field.related_model
                            
                            # Проверяем, что related_model не является None
                            if related_model is None:
                                continue
                                
                            # Пробуем найти объект по ID
                            if isinstance(value, str) and value.isdigit():
                                try:
                                    related_obj = related_model.objects.get(pk=int(value))
                                    cleaned_row[field_name] = related_obj
                                    continue
                                except Exception:
                                    # В случае любой ошибки продолжаем и пробуем другие способы поиска
                                    pass
                                
                            # Если не удалось найти по ID, пробуем найти по имени (если есть поле name)
                            if isinstance(value, str):
                                try:
                                    if hasattr(related_model, 'name'):
                                        related_obj = related_model.objects.get(name=value)
                                        cleaned_row[field_name] = related_obj
                                    else:
                                        raise ValueError(f"Не удалось найти объект {related_model.__name__} с именем '{value}'")
                                except Exception as e:
                                    error_msg = f"Не удалось найти объект {related_model.__name__} с ID или именем '{value}'"
                                    raise ValueError(error_msg)
                    
                    model.objects.create(**cleaned_row)
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    errors.append(str(e))

            return JsonResponse({
                'success': True,
                'processed': success_count + error_count,
                'success_count': success_count,
                'error_count': error_count,
                'errors': errors[:10]  
            })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def product_view(request: HttpRequest) -> HttpResponse | StreamingHttpResponse:
    """
    Представление для работы с продуктами.
    """
    if request.method == 'POST':
        if 'file' in request.FILES:
            return handle_csv_upload(request, Product)

        product_form = ProductForm(request.POST)
        if product_form.is_valid():
            product_form.save()
            messages.success(request, 'Продукт успешно добавлен')
            return redirect('product_view')
        else:
            messages.error(request, 'Ошибка при добавлении продукта')
            errors = [
                f'{field}: {", ".join(errors)}' for field, errors in product_form.errors.items()]
            messages.error(request, '\n'.join(errors))
    else:
        product_form = ProductForm()

    products = Product.objects.all()
    fields_tuple = split_foreign_keys_to_fields(Product)

    products = apply_filters(products, Product, request)
    allowed_fields = [field.name for field in Product._meta.fields]
    products, sort_by, order = apply_sorting(products, request, allowed_fields, "products_", primary_key='product_id')
    
    # Получаем список обязательных полей (за исключением auto_created и primary key)
    pk_name = Product._meta.pk.name if Product._meta.pk is not None else 'id'
    required_fields = [
        f.name for f in Product._meta.fields 
        if not f.auto_created and f.name != pk_name and not f.blank]
    
    paginator = Paginator(products, 50)
    page_number = request.GET.get('page', '1')
    page_obj = paginator.get_page(page_number)

    return render(request, 'data_view.html', {
        'title': 'Продукты',
        'table_name': 'products',
        'object_list': page_obj,
        'manual_form': product_form,
        'fields': fields_tuple,
        'field_types': get_field_types(Product),
        'page_obj': page_obj,
        'sort_by': sort_by,
        'order': order,
        'hidden_fields': {},
        'show_export_button': True,
        'show_add_form': True,
        'required_fields': required_fields
    })


@login_required
def attribute_view(request: HttpRequest) -> HttpResponse | StreamingHttpResponse:
    """
    Представление для работы с атрибутами.
    """
    if request.method == 'POST':
        if 'file' in request.FILES:
            return handle_csv_upload(request, Attribute)

        attribute_form = AttributeForm(request.POST)
        if attribute_form.is_valid():
            attribute_form.save()
            messages.success(request, 'Атрибут успешно добавлен')
            return redirect('attribute_view')
        else:
            messages.error(request, 'Ошибка при добавлении атрибута')
            errors = [
                f'{field}: {", ".join(errors)}' for field, errors in attribute_form.errors.items()]
            messages.error(request, '\n'.join(errors))
    else:
        attribute_form = AttributeForm()

    attributes = Attribute.objects.all()
    fields_tuple = split_foreign_keys_to_fields(Attribute)

    attributes = apply_filters(attributes, Attribute, request)
    allowed_fields = [field.name for field in Attribute._meta.fields]
    attributes, sort_by, order = apply_sorting(attributes, request, allowed_fields, "attributes_", primary_key='attribute_id')
    
    # Получаем список обязательных полей (за исключением auto_created и primary key)
    pk_name = Attribute._meta.pk.name if Attribute._meta.pk is not None else 'id'
    required_fields = [
        f.name for f in Attribute._meta.fields 
        if not f.auto_created and f.name != pk_name and not f.blank]
    
    paginator = Paginator(attributes, 50)
    page_number = request.GET.get('page', '1')
    page_obj = paginator.get_page(page_number)

    return render(request, 'data_view.html', {
        'title': 'Атрибуты',
        'table_name': 'attributes',
        'object_list': page_obj,
        'manual_form': attribute_form,
        'fields': fields_tuple,
        'field_types': get_field_types(Attribute),
        'page_obj': page_obj,
        'sort_by': sort_by,
        'order': order,
        'hidden_fields': {},
        'show_export_button': True,
        'show_add_form': True,
        'required_fields': required_fields
    })


@login_required
def timeseries_view(request: HttpRequest) -> (HttpResponse | JsonResponse | StreamingHttpResponse):
    """
    Представление для просмотра, добавления и редактирования временных рядов.
    """
    message: str = ''
    error: str = ''
    timeseries_form: ModelForm = TimeSeriesForm(prefix='timeseries')

    if request.method == 'POST':
        if 'file' in request.FILES:
            return handle_csv_upload(request, TimeSeries)

        action: str = request.POST.get('action', '')
        if action == 'manual':
            timeseries_form = TimeSeriesForm(request.POST, prefix='timeseries')
            if timeseries_form.is_valid():
                timeseries_form.save()
                message = 'Временной ряд успешно добавлен'

    qs: QuerySet = TimeSeries.objects.all()
    qs = apply_filters(qs, TimeSeries, request)
    primary_key = 'time_series_id'
    allowed_fields = [field.name for field in TimeSeries._meta.fields]
    qs, sort_by, order = apply_sorting(qs, request, allowed_fields, "timeseries_", primary_key=primary_key)

    # Получаем список обязательных полей (за исключением auto_created и primary key)
    pk_name = TimeSeries._meta.pk.name if TimeSeries._meta.pk is not None else 'id'
    required_fields = [
        f.name for f in TimeSeries._meta.fields 
        if not f.auto_created and f.name != pk_name and not f.blank]

    if request.GET.get('export') == '1':
        return export_to_csv(qs, model=TimeSeries)

    paginator: Paginator = Paginator(qs, 50)
    page_number: str = request.GET.get('page', '1')
    page_obj = paginator.get_page(page_number)

    fields_tuple = split_foreign_keys_to_fields(TimeSeries)

    return render(request, 'data_view.html', {
        'message': message,
        'error': error,
        'object_list': page_obj,
        'manual_form': timeseries_form,
        'title': 'Временные ряды',
        'table_name': 'time_series',
        'fields': fields_tuple,
        'field_types': get_field_types(TimeSeries),
        'page_obj': page_obj,
        'sort_by': sort_by,
        'order': order,
        'hidden_fields': {},
        'show_export_button': True,
        'show_add_form': True,
        'required_fields': required_fields
    })


@login_required
def timestamp_view(request: HttpRequest) -> (HttpResponse | JsonResponse | StreamingHttpResponse):
    """
    Представление для просмотра, добавления и редактирования временных меток.
    """
    message: str = ''
    error: str = ''
    timestamp_form: ModelForm = TimestampForm(prefix='timestamp')

    if request.method == 'POST':
        if 'file' in request.FILES:
            return handle_csv_upload(request, Timestamp)

        action: str = request.POST.get('action', '')
        if action == 'manual':
            timestamp_form = TimestampForm(request.POST, prefix='timestamp')
            if timestamp_form.is_valid():
                timestamp_form.save()
                message = 'Временная метка успешно добавлена'

    qs: QuerySet = Timestamp.objects.all()
    qs = apply_filters(qs, Timestamp, request)
    allowed_fields = [field.name for field in Timestamp._meta.fields]
    qs, sort_by, order = apply_sorting(qs, request, allowed_fields, "timestamp_", primary_key='timestamp_id')

    # Получаем список обязательных полей (за исключением auto_created и primary key)
    pk_name = Timestamp._meta.pk.name if Timestamp._meta.pk is not None else 'id'
    required_fields = [
        f.name for f in Timestamp._meta.fields 
        if not f.auto_created and f.name != pk_name and not f.blank]

    if request.GET.get('export') == '1':
        return export_to_csv(qs, model=Timestamp)

    paginator: Paginator = Paginator(qs, 50)
    page_number: str = request.GET.get('page', '1')
    page_obj = paginator.get_page(page_number)

    fields_tuple = split_foreign_keys_to_fields(Timestamp)

    return render(request, 'data_view.html', {
        'message': message,
        'error': error,
        'title': 'Временные метки',
        'table_name': 'timestamps',
        'object_list': page_obj,
        'manual_form': timestamp_form,
        'fields': fields_tuple,
        'field_types': get_field_types(Timestamp),
        'page_obj': page_obj,
        'sort_by': sort_by,
        'order': order,
        'hidden_fields': {},
        'show_export_button': True,
        'show_add_form': True,
        'required_fields': required_fields
    })
