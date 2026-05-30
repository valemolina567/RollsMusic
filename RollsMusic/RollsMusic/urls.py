from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('registros.urls')),
    # Dashboards de roles
    path('dashboard/usuario/', views.dashboard_usuario, name='dashboard_usuario'),
    path('dashboard/artista/', views.dashboard_artista, name='dashboard_artista'),
]