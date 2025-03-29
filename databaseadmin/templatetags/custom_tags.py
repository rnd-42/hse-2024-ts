from django import template

register = template.Library()

@register.filter
def get_attr(obj, attr_name):
    """
    Получение атрибута объекта или значения из словаря.
    Работает как с обычными объектами Django, так и со словарями.
    """
    if isinstance(obj, dict):
        return obj.get(attr_name)
    return getattr(obj, attr_name, None)
