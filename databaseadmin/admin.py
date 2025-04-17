from django.contrib import admin
from .models import Product, Attribute, TimeSeries, Timestamp

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_id', 'name', 'category')

@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    list_display = ('attribute_id', 'name', 'data_type')

@admin.register(TimeSeries)
class TimeSeriesAdmin(admin.ModelAdmin):
    list_display = ('time_series_id', 'name', 'product', 'parent_time_series')

@admin.register(Timestamp)
class TimestampAdmin(admin.ModelAdmin):
    list_display = ('timestamp_id', 'time_series', 'attribute', 'value', 'start_dt', 'end_dt')
