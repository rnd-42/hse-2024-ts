from django.views.generic import TemplateView
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from ..models import TimeSeries
from datetime import datetime


class TimeSeriesHierarchyView(TemplateView):
    """
    Представление для отображения иерархии временных рядов.
    Позволяет просматривать все таймстемпы в иерархии одного временного ряда.
    """
    template_name = 'time_series_hierarchy.html'

    def _apply_filter(self, data, field, operator, value):
        """Применяет один фильтр к списку данных."""
        filtered_data = []
        for item in data:
            field_value = str(item.get(field, '')).lower()
            filter_value = str(value).lower()
            
            if operator == 'exact':
                if field_value == filter_value:
                    filtered_data.append(item)
            elif operator == 'iexact':
                if field_value == filter_value:
                    filtered_data.append(item)
            elif operator == 'contains':
                if filter_value in field_value:
                    filtered_data.append(item)
            elif operator == 'icontains':
                if filter_value in field_value:
                    filtered_data.append(item)
            elif operator == 'startswith':
                if field_value.startswith(filter_value):
                    filtered_data.append(item)
            elif operator == 'endswith':
                if field_value.endswith(filter_value):
                    filtered_data.append(item)
            elif operator == 'gt':
                try:
                    if float(field_value) > float(filter_value):
                        filtered_data.append(item)
                except ValueError:
                    continue
            elif operator == 'gte':
                try:
                    if float(field_value) >= float(filter_value):
                        filtered_data.append(item)
                except ValueError:
                    continue
            elif operator == 'lt':
                try:
                    if float(field_value) < float(filter_value):
                        filtered_data.append(item)
                except ValueError:
                    continue
            elif operator == 'lte':
                try:
                    if float(field_value) <= float(filter_value):
                        filtered_data.append(item)
                except ValueError:
                    continue
        
        return filtered_data
        
    def _apply_filters(self, data, filter_fields, filter_operators, filter_values):
        """Применяет множественные фильтры к данным иерархии."""
        if not filter_fields or not filter_operators or not filter_values:
            return data
            
        if len(filter_fields) == 1 and filter_fields[0] and filter_values[0]:
            return self._apply_filter(data, filter_fields[0], filter_operators[0], filter_values[0])
            
        filtered_data = data
        for field, operator, value in zip(filter_fields, filter_operators, filter_values):
            if field and value:
                filtered_data = self._apply_filter(filtered_data, field, operator, value)
                
        return filtered_data
        
    def _get_sort_key(self, item, field):
        """Получает ключ для сортировки с учетом типа данных."""
        value = item.get(field, '')
        if isinstance(value, (int, float)):
            return value
        try:
            return float(value)
        except (ValueError, TypeError):
            if field in ['start_dt', 'end_dt'] and value:
                try:
                    if isinstance(value, str):
                        return datetime.fromisoformat(value.replace('Z', '+00:00'))
                    return value
                except (ValueError, TypeError):
                    pass
            return str(value).lower()
            
    def _apply_sorting(self, data, sort_fields, sort_orders):
        """Применяет множественные сортировки к данным иерархии."""
        if not sort_fields or not sort_fields[0]:
            return data
        
        sorted_data = data.copy()
        
        for field, order in reversed(list(zip(sort_fields, sort_orders))):
            if field:
                reverse = order == 'desc'
                sorted_data = sorted(sorted_data, key=lambda x: self._get_sort_key(x, field), reverse=reverse)
                
        return sorted_data

    def get_context_data(self, **kwargs):
        """
        Готовит данные для шаблона.
        Загружает выбранный временной ряд, получает его иерархию,
        применяет фильтры и сортировку, подготавливает контекст для шаблона.
        """
        context = super().get_context_data(**kwargs)
        
        series_id = self.request.GET.get('series_id')
        selected_series = None
        hierarchy_data = []
        error = None

        if series_id:
            try:
                selected_series = TimeSeries.objects.get(time_series_id=series_id)
                hierarchy_data = selected_series.get_hierarchy_data()
            except TimeSeries.DoesNotExist:
                error = "Временной ряд не найден"
            except Exception as e:
                error = f"Ошибка при получении данных: {str(e)}"

        available_series = TimeSeries.objects.all().order_by('name')

        filter_fields = self.request.GET.getlist('filter_field[]') or [self.request.GET.get('filter_field')]
        filter_operators = self.request.GET.getlist('filter_operator[]') or [self.request.GET.get('filter_operator')]
        filter_values = self.request.GET.getlist('filter_value[]') or [self.request.GET.get('filter_value')]

        hierarchy_data = self._apply_filters(hierarchy_data, filter_fields, filter_operators, filter_values)

        sort_fields = self.request.GET.getlist('sort_by[]') or [self.request.GET.get('sort_by')]
        sort_orders = self.request.GET.getlist('order[]') or [self.request.GET.get('order', 'asc')]

        hierarchy_data = self._apply_sorting(hierarchy_data, sort_fields, sort_orders)

        paginator = Paginator(hierarchy_data, 50)
        page = self.request.GET.get('page', 1)
        try:
            hierarchy_data = paginator.page(page)
        except PageNotAnInteger:
            hierarchy_data = paginator.page(1)
        except EmptyPage:
            hierarchy_data = paginator.page(paginator.num_pages)

        fields = [
            ('depth', 'depth'),
            ('initial_time_series_id', 'initial_time_series_id'),
            ('attribute_id', 'attribute_id'),
            ('value', 'value'),
            ('start_dt', 'start_dt'),
            ('end_dt', 'end_dt'),
        ]

        hidden_fields = {}
        if selected_series:
            hidden_fields['series_id'] = selected_series.time_series_id

        context.update({
            'title': 'Сбор таймстемпов иерархически',
            'table_name': 'hierarchy',
            'available_series': available_series,
            'selected_series': selected_series,
            'hierarchy_data': hierarchy_data,
            'object_list': hierarchy_data,
            'page_obj': hierarchy_data,   
            'error': error,
            'fields': fields,
            'filter_field': filter_fields[0] if filter_fields else None,
            'filter_operator': filter_operators[0] if filter_operators else None,
            'filter_value': filter_values[0] if filter_values else None,
            'sort_by': sort_fields[0] if sort_fields else None,  
            'order': sort_orders[0] if sort_orders else 'asc',
            'show_add_form': False,         
            'show_actions': False,          
            'show_export_button': False,   
            'hidden_fields': hidden_fields,
        })
        return context 