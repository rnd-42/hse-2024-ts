from django import template
from django.utils.dateformat import format
from django.utils.safestring import mark_safe
import datetime
from django.db import models

register = template.Library()

@register.filter
def range(value):
    """
    Возвращает диапазон чисел от 0 до value-1
    Используется для создания списка страниц в пагинации
    """
    return range(value) 

@register.filter
def format_date(value, fmt='j E Y H:i'):
    """
    Форматирует дату по указанному формату
    """
    if not value:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            try:
                value = datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M:%S.%fZ')
            except ValueError:
                return value
    return format(value, fmt)

@register.filter
def format_value(value, type_name=None):
    """
    Форматирует значение в зависимости от его типа
    """
    if value is None:
        return ""
    if isinstance(value, bool):
        return "Да" if value else "Нет"
    if isinstance(value, (datetime.date, datetime.datetime)):
        return format_date(value)
    if isinstance(value, (int, float)) and type_name != 'text':
        if float(value).is_integer():
            return str(int(value))
        return str(value)
    return str(value)

@register.filter
def as_badge(value, color="secondary"):
    """
    Обертывает значение в badge с указанным цветом
    """
    return mark_safe(f'<span class="badge bg-{color}">{value}</span>') 

@register.filter
def multiply(value, arg):
    """
    Умножает значение на аргумент
    """
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0
    
@register.filter
def divisibleby(value, arg):
    """
    Делит значение на аргумент
    """
    try:
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0 

@register.filter
def endswith(value, suffix):
    """
    Проверяет, заканчивается ли строка определенным суффиксом
    """
    if not value:
        return False
    return str(value).endswith(suffix) 

@register.filter
def get_attr(obj, attr):
    """
    Возвращает значение атрибута объекта по имени.
    Поддерживает доступ к вложенным атрибутам через точку (например, 'parent.name').
    
    Использование:
    {{ object|get_attr:"attribute_name" }}
    {{ object|get_attr:"parent.name" }}
    """
    if not obj or not attr:
        return ""
    
    if '.' in attr:
        parts = attr.split('.')
        for part in parts:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            elif hasattr(obj, 'get') and callable(getattr(obj, 'get')):
                try:
                    obj = obj.get(part)
                except (TypeError, KeyError):
                    return ""
            else:
                return ""
        return obj
    
    if hasattr(obj, attr):
        attr_value = getattr(obj, attr)
        
        if attr_value and isinstance(attr_value, models.Model):
            try:
                if hasattr(attr_value, 'name'):
                    return getattr(attr_value, 'name')
                return str(attr_value)
            except (AttributeError, TypeError):
                return str(attr_value)
            
        if callable(attr_value) and attr != 'pk' and not attr.startswith('_'):
            try:
                return attr_value()
            except:
                return attr_value
        return attr_value
    
    elif hasattr(obj, 'get') and callable(getattr(obj, 'get')):
        try:
            return obj.get(attr)
        except (TypeError, KeyError):
            return ""
            
    return ""

@register.filter
def get_related_id(obj, field_name):
    """
    Возвращает ID связанного объекта (ForeignKey).
    Обрабатывает специальный синтаксис field_id, извлекая поле field
    и получая ID связанного объекта.
    
    Использование:
    {{ object|get_related_id:"time_series_id" }}
    """
    if not obj or not field_name or not field_name.endswith('_id'):
        return ""
    
    related_field = field_name[:-3] 
    
    if hasattr(obj, related_field):
        related_obj = getattr(obj, related_field)
        if related_obj:
            return related_obj.pk
    
    if hasattr(obj, field_name):
        return getattr(obj, field_name)
    
    return "" 