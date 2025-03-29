"""
Инициализация пакета представлений для приложения databaseadmin.
Импортирует и объединяет все представления из подмодулей.
"""
from .base_views import (
    home,
    delete_object,
    timeseries_tree_json,
    time_series_tree_view,
    export_all_database
)

from .data_views import (
    product_view,
    attribute_view,
    timeseries_view,
    timestamp_view
)

from .hierarchy_views import (
    TimeSeriesHierarchyView
)

from .utils import (
    apply_filters,
    apply_sorting,
    export_to_csv,
    get_field_types,
    handle_csv_upload,
    Echo
)

# Экспортируем все представления для использования в URLs
__all__ = [
    'home',
    'delete_object',
    'timeseries_tree_json',
    'time_series_tree_view',
    'export_all_database',
    'product_view',
    'attribute_view',
    'timeseries_view',
    'timestamp_view',
    'TimeSeriesHierarchyView',
    'apply_filters',
    'apply_sorting',
    'export_to_csv',
    'get_field_types',
    'handle_csv_upload',
    'Echo'
] 