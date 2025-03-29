from django import forms
from .models import Product, Attribute, TimeSeries, Timestamp

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ['name', 'category', 'parameters']

class AttributeForm(forms.ModelForm):
    class Meta:
        model = Attribute
        fields = ['name', 'data_type']

class TimeSeriesForm(forms.ModelForm):
    class Meta:
        model = TimeSeries
        fields = ['parent_time_series', 'name', 'product']

class TimestampForm(forms.ModelForm):
    class Meta:
        model = Timestamp
        fields = ['time_series', 'attribute', 'value', 'start_dt', 'end_dt']
