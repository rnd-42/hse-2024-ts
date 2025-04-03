from django import forms
from .models import Product, Attribute, TimeSeries, Timestamp

class FormWithTypeLabels(forms.ModelForm):
    """
    Базовый класс форм, который добавляет информацию о типе поля в его лейбл.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            field_type = self._get_field_type(field)
            if field.label:
                field.label = f"{field.label} [{field_type}]"
            else:
                field.label = f"{field_name.replace('_', ' ').title()} [{field_type}]"
            
            if hasattr(field.widget, 'attrs') and field_type:
                field.widget.attrs.update({
                    'placeholder': self._get_placeholder(field_type, field),
                    'class': 'form-control'
                })
    
    def _get_field_type(self, field):
        """Определяет тип поля формы для отображения"""
        if isinstance(field, forms.DateTimeField):
            return "Дата/время"
        elif isinstance(field, forms.DateField):
            return "Дата"
        elif isinstance(field, forms.IntegerField):
            return "Целое число"
        elif isinstance(field, forms.FloatField):
            return "Число"
        elif isinstance(field, forms.JSONField):
            return "JSON"
        elif isinstance(field, forms.ModelChoiceField):
            return "Выбор из списка"
        elif isinstance(field, forms.BooleanField):
            return "Да/Нет"
        elif isinstance(field, forms.CharField):
            return "Текст"
        else:
            return ""
    
    def _get_placeholder(self, field_type, field):
        """Возвращает подсказку в зависимости от типа поля"""
        if field_type == "Дата/время":
            return "YYYY-MM-DD HH:MM:SS"
        elif field_type == "Дата":
            return "YYYY-MM-DD"
        elif field_type == "Целое число":
            return "Например: 42"
        elif field_type == "Число":
            return "Например: 3.14"
        elif field_type == "JSON":
            return '{"key": "value"}'
        elif field_type == "Выбор из списка":
            return "Выберите значение"
        else:
            return ""


class ProductForm(FormWithTypeLabels):
    class Meta:
        model = Product
        fields = ['name', 'category', 'parameters']
        widgets = {
            'parameters': forms.Textarea(attrs={
                'rows': 4, 
                'placeholder': '{"key1": "value1", "key2": "value2"}'
            }),
        }
        labels = {
            'name': 'Название',
            'category': 'Категория',
            'parameters': 'Параметры',
        }
        help_texts = {
            'parameters': 'Введите параметры в формате JSON (необязательно)',
        }
        
    def clean_parameters(self):
        """
        Очищает и обрабатывает поле parameters.
        Если поле пустое, возвращает пустой словарь.
        """
        parameters = self.cleaned_data.get('parameters')
        if parameters is None or parameters == '':
            return {}
        return parameters


class AttributeForm(FormWithTypeLabels):
    class Meta:
        model = Attribute
        fields = ['name', 'data_type']
        labels = {
            'name': 'Название',
            'data_type': 'Тип данных',
        }
        help_texts = {
            'data_type': 'Например: string, integer, float, datetime',
        }


class TimeSeriesForm(FormWithTypeLabels):
    class Meta:
        model = TimeSeries
        fields = ['parent_time_series', 'name', 'product']
        labels = {
            'parent_time_series': 'Родительский временной ряд',
            'name': 'Название',
            'product': 'Продукт',
        }
        help_texts = {
            'parent_time_series': 'Оставьте пустым для корневого временного ряда',
        }


class TimestampForm(FormWithTypeLabels):
    class Meta:
        model = Timestamp
        fields = ['time_series', 'attribute', 'value', 'start_dt', 'end_dt']
        widgets = {
            'start_dt': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_dt': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        }
        labels = {
            'time_series': 'Временной ряд',
            'attribute': 'Атрибут',
            'value': 'Значение',
            'start_dt': 'Дата начала',
            'end_dt': 'Дата окончания',
        }
        help_texts = {
            'end_dt': 'Необязательное поле. Оставьте пустым для текущих данных',
        }
