"""
Главный модуль представлений, импортирующий все представления из подмодулей.
Этот файл служит только для обеспечения обратной совместимости.
Новый код следует добавлять в соответствующие файлы в директории views/.
"""
# Импорт из базовых представлений
from databaseadmin.views.base_views import (
    home, 
    delete_object, 
    timeseries_tree_json, 
    time_series_tree_view,
    export_all_database,
    export_single_table
)

# Импорт из представлений данных
from databaseadmin.views.data_views import (
    product_view, 
    attribute_view, 
    timeseries_view, 
    timestamp_view
)

# Импорт из иерархических представлений
from databaseadmin.views.hierarchy_views import TimeSeriesHierarchyView

# Импорт утилитарных функций
from databaseadmin.views.utils import (
    apply_filters,
    apply_sorting,
    export_to_csv,
    get_field_types,
    Echo
)

# Экспортируем все представления для использования в URLs
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
    'Echo',
    'export_all_database',
    'export_single_table'
]