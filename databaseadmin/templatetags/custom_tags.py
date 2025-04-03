from django import template
from django.db import models
from ..models import Product, Attribute, TimeSeries, Timestamp

register = template.Library()

@register.filter
def get_attr(obj, attr_name):
    """
    Получение атрибута объекта или значения из словаря.
    Для foreign key полей возвращает имя с ID через метод display_name.
    """
    if isinstance(obj, dict):
        return obj.get(attr_name)
    
    value = getattr(obj, attr_name, None)
    
    if isinstance(value, (Product, Attribute, TimeSeries, Timestamp)):
        return value.display_name()
    
    return value
