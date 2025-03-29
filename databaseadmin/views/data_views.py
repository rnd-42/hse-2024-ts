from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from ..models import Product, Attribute, TimeSeries, Timestamp
from ..forms import ProductForm, AttributeForm, TimeSeriesForm, TimestampForm
from .utils import apply_filters, apply_sorting, export_to_csv, get_field_types


@login_required
def product_view(request):
    """
    Представление для просмотра, добавления и редактирования продуктов.
    """
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
            from .utils import handle_csv_upload
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
    """
    Представление для просмотра, добавления и редактирования атрибутов.
    """
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
            from .utils import handle_csv_upload
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
        'field_types': get_field_types(Attribute),
        'page_obj': page_obj,
        'sort_by': sort_by,
        'order': order,
    })


@login_required
def timeseries_view(request):
    """
    Представление для просмотра, добавления и редактирования временных рядов.
    """
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
            from .utils import handle_csv_upload
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
        'field_types': get_field_types(TimeSeries),
        'page_obj': page_obj,
        'sort_by': sort_by,
        'order': order,
    })


@login_required
def timestamp_view(request):
    """
    Представление для просмотра, добавления и редактирования таймстемпов.
    """
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
            from .utils import handle_csv_upload
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
        'field_types': get_field_types(Timestamp),
        'page_obj': page_obj,
        'sort_by': sort_by,
        'order': order,
    }) 