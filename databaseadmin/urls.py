from django.urls import path
from .views import (
    home,
    product_view,
    attribute_view,
    timeseries_view,
    timestamp_view,
    TimeSeriesHierarchyView,
    delete_object,
    timeseries_tree_json,
    time_series_tree_view,
    export_all_database,
)
from .views.base_views import export_single_table

urlpatterns = [
    path('', home, name='home'),
    path('products/', product_view, name='product_view'),
    path('attributes/', attribute_view, name='attribute_view'),
    path('timeseries/', timeseries_view, name='timeseries_view'),
    path('timestamps/', timestamp_view, name='timestamp_view'),

    path('timeseries/hierarchy/', TimeSeriesHierarchyView.as_view(), name='time_series_hierarchy'),
    path('timeseries/tree/', time_series_tree_view, name='time_series_tree'),
    path('api/timeseries/tree/', timeseries_tree_json, name='timeseries_tree_json'),

    path('export/all/', export_all_database, name='export_all_database'),
    path('export-table/<str:model_name>/', export_single_table, name='export_single_table'),

    path('<str:model_name>/<int:pk>/delete/', delete_object, name='delete_object'),
]
