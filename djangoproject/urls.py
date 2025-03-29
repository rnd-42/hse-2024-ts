from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('django.contrib.auth.urls')),  # Страницы авторизации: вход, выход, восстановление пароля
    path('', include('databaseadmin.urls')),  # URL-приложения
]
