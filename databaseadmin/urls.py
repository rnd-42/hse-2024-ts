from django.urls import path
from .views import (
    home,
    product_view,
    attribute_view,
    timeseries_view,
    timestamp_view,
    timeseries_tree_json,
    time_series_tree_view,
    delete_object,
    export_single_table,
    download_csv_template,
)
from .views.api_views import (
    create_forecasting_model, 
    train_forecasting_model, 
    get_time_series_attributes, 
    delete_forecasting_model,
    forecast_child_series
)
from databaseadmin.views.hierarchy_views import TimeSeriesHierarchyView

urlpatterns = [
    path('', home, name='home'),
    path('products/', product_view, name='product_view'),
    path('attributes/', attribute_view, name='attribute_view'),
    path('timeseries/', timeseries_view, name='timeseries_view'),
    path('timestamps/', timestamp_view, name='timestamp_view'),
    path('timeseries/tree/json/', timeseries_tree_json, name='timeseries_tree_json'),
    path('timeseries/tree/', time_series_tree_view, name='time_series_tree'),
    path('delete/<str:model_name>/<int:pk>/', delete_object, name='delete_object'),
    path('export/<str:model_name>/', export_single_table, name='export_single_table'),
    path('download-template/<str:model_name>/', download_csv_template, name='download_csv_template'),

    path('timeseries/hierarchy/', TimeSeriesHierarchyView.as_view(), name='time_series_hierarchy'),
    
    # API-эндпоинты
    path('api/timeseries/<int:time_series_id>/attributes/', get_time_series_attributes, name='get_time_series_attributes'),
    path('api/forecasting/create/', create_forecasting_model, name='create_forecasting_model'),
    path('api/forecasting/train/', train_forecasting_model, name='train_forecasting_model'),
    path('api/forecasting/delete/', delete_forecasting_model, name='delete_forecasting_model'),
    path('api/forecasting/forecast-child/', forecast_child_series, name='forecast_child_series'),
]
