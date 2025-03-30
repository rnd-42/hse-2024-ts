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
from .utils import apply_filters, apply_sorting, export_to_csv, get_field_types
from typing import Dict, List, Any, Type
from django.db.models import Model, QuerySet
from django.forms import ModelForm


def handle_csv_upload(request: HttpRequest, model: Type[Model]) -> JsonResponse | StreamingHttpResponse:
    """
    Обрабатывает загрузку CSV файла.
    """
    if 'csv_file' not in request.FILES:
        return JsonResponse({'error': 'Файл не найден'}, status=400)

    file = request.FILES['csv_file']
    if file.size > 5 * 1024 * 1024:  # 5MB
        return JsonResponse({'error': 'Файл слишком большой'}, status=400)

    try:
        content = file.read().decode('utf-8')
        reader = csv.DictReader(io.StringIO(content))

        required_fields = [
            f.name for f in model._meta.fields if not f.auto_created]
        missing_fields = [
            field for field in required_fields if field not in reader.fieldnames]

        if missing_fields:
            return JsonResponse({
                'error': 'Отсутствуют обязательные поля',
                'fields': missing_fields
            }, status=400)

        with transaction.atomic():
            success_count = 0
            error_count = 0
            errors = []

            for row in reader:
                try:
                    model.objects.create(**row)
                    success_count += 1
                except Exception as e:
                    error_count += 1
                    errors.append(str(e))

            return JsonResponse({
                'success': True,
                'processed': success_count + error_count,
                'success_count': success_count,
                'error_count': error_count,
                'errors': errors
            })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


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


@login_required
def product_view(request: HttpRequest) -> HttpResponse | StreamingHttpResponse:
    """
    Представление для работы с продуктами.
    """
    if request.method == 'POST':
        if 'csv_file' in request.FILES:
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
    field_info = get_field_info(Product)

    # Добавляем пагинацию
    paginator = Paginator(products, 50)
    page_number = request.GET.get('page', '1')
    page_obj = paginator.get_page(page_number)

    return render(request, 'data_view.html', {
        'title': 'Продукты',
        'table_name': 'products',
        'object_list': page_obj,
        'manual_form': product_form,
        'fields': field_info,
        'field_types': get_field_types(Product),
        'page_obj': page_obj
    })


@login_required
def attribute_view(request: HttpRequest) -> HttpResponse | StreamingHttpResponse:
    """
    Представление для работы с атрибутами.
    """
    if request.method == 'POST':
        if 'csv_file' in request.FILES:
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
    field_info = get_field_info(Attribute)

    # Добавляем пагинацию
    paginator = Paginator(attributes, 50)
    page_number = request.GET.get('page', '1')
    page_obj = paginator.get_page(page_number)

    return render(request, 'data_view.html', {
        'title': 'Атрибуты',
        'table_name': 'attributes',
        'object_list': page_obj,
        'manual_form': attribute_form,
        'fields': field_info,
        'field_types': get_field_types(Attribute),
        'page_obj': page_obj
    })


@login_required
def timeseries_view(request: HttpRequest) -> (HttpResponse | JsonResponse | StreamingHttpResponse):
    """
    Представление для просмотра, добавления и редактирования временных рядов.
    """
    message: str = ''
    errors: List[str] = []
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
    primary_key = 'time_series_id'  # Используем правильное имя первичного ключа для TimeSeries
    allowed_fields = [field.name for field in TimeSeries._meta.fields]
    qs, sort_by, order = apply_sorting(qs, request, allowed_fields, "timeseries_", primary_key=primary_key)

    if request.GET.get('export') == '1':
        return export_to_csv(qs, model=TimeSeries)

    paginator: Paginator = Paginator(qs, 50)
    page_number: str = request.GET.get('page', '1')
    page_obj = paginator.get_page(page_number)

    fields_info = get_field_info(TimeSeries)

    return render(request, 'data_view.html', {
        'message': message,
        'errors': errors,
        'object_list': page_obj,
        'manual_form': timeseries_form,
        'table_name': 'timeseries',
        'fields': fields_info,
        'field_types': get_field_types(TimeSeries),
        'page_obj': page_obj,
        'sort_by': sort_by,
        'order': order,
    })


@login_required
def timestamp_view(request: HttpRequest) -> (HttpResponse | JsonResponse | StreamingHttpResponse):
    """
    Представление для просмотра, добавления и редактирования временных меток.
    """
    message: str = ''
    errors: List[str] = []
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
    qs, sort_by, order = apply_sorting(qs, request, allowed_fields, "timestamp_")

    if request.GET.get('export') == '1':
        return export_to_csv(qs, model=Timestamp)

    paginator: Paginator = Paginator(qs, 50)
    page_number: str = request.GET.get('page', '1')
    page_obj = paginator.get_page(page_number)

    fields_info = get_field_info(Timestamp)

    return render(request, 'data_view.html', {
        'message': message,
        'errors': errors,
        'object_list': page_obj,
        'manual_form': timestamp_form,
        'table_name': 'timestamps',
        'fields': fields_info,
        'field_types': get_field_types(Timestamp),
        'page_obj': page_obj,
        'sort_by': sort_by,
        'order': order,
    })
