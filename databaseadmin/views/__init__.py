"""
Инициализация пакета представлений для приложения databaseadmin.
Импортирует и объединяет все представления из подмодулей.
"""
from .base_views import (
    home,
    timeseries_tree_json,
    time_series_tree_view,
    delete_object,
    export_single_table,
    download_csv_template,
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
)

# Экспортируем все представления для использования в URLs
__all__ = [
    'home',
    'product_view',
    'attribute_view',
    'timeseries_view',
    'timestamp_view',
    'timeseries_tree_json',
    'time_series_tree_view',
    'TimeSeriesHierarchyView',
    'delete_object',
    'export_single_table',
    'download_csv_template',
    'apply_filters',
    'apply_sorting',
    'export_to_csv',
    'get_field_types',
] 