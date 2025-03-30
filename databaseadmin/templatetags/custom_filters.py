from django import template
from django.utils.dateformat import format
from django.utils.safestring import mark_safe
import datetime

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