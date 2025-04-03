"""
Главный модуль представлений, импортирующий все представления из подмодулей.
Этот файл служит только для обеспечения обратной совместимости.
Новый код следует добавлять в соответствующие файлы в директории views/.
"""
from databaseadmin.views.base_views import (
    home,
    delete_object,
    timeseries_tree_json,
    time_series_tree_view,
    export_single_table
)

from databaseadmin.views.data_views import (
    product_view,
    attribute_view,
    timeseries_view,
    timestamp_view
)

from databaseadmin.views.hierarchy_views import TimeSeriesHierarchyView

from databaseadmin.views.utils import (
    apply_filters,
    apply_sorting,
    export_to_csv,
    get_field_types
)

__all__ = [
    'home',
    'delete_object',
    'timeseries_tree_json',
    'time_series_tree_view',
    'product_view',
    'attribute_view',
    'timeseries_view',
    'timestamp_view',
    'TimeSeriesHierarchyView',
    'apply_filters',
    'apply_sorting',
    'export_to_csv',
    'get_field_types',
    'export_single_table'
]
