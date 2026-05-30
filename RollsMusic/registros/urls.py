from django.urls import path
from . import views

urlpatterns = [
    # Panel Principal
    path('', views.index, name='index'),

   # Usuarios (Nombres específicos y claros)
   path('usuarios/', views.listar_usuarios, name='listar_usuarios'),
   path('usuarios/crear/', views.crear_usuario, name='crear_usuario'),
   path('usuarios/editar/<int:id>/', views.editar_usuario, name='editar_usuario'),
   path('usuarios/eliminar/<int:id>/', views.eliminar_usuario, name='eliminar_usuario'),

    # Discográficas
    path('discograficas/', views.listar_discograficas, name='listar_discograficas'),
    path('discograficas/crear/', views.crear_discografica, name='crear_discografica'),
    path('discograficas/editar/<int:id>/', views.editar_discografica, name='editar_discografica'),
    path('discograficas/eliminar/<int:id>/', views.eliminar_discografica, name='eliminar_discografica'),

    # Artistas
    path('artistas/', views.listar_artistas, name='listar_artistas'),
    path('artistas/crear/', views.crear_artista, name='crear_artista'),
    path('artistas/editar/<int:id>/', views.editar_artista, name='editar_artista'),
    path('artistas/eliminar/<int:id>/', views.eliminar_artista, name='eliminar_artista'),

    # Álbumes
    path('albumes/', views.listar_albumes, name='listar_albumes'),
    path('albumes/crear/', views.crear_album, name='crear_album'),
    path('albumes/editar/<int:id>/', views.editar_album, name='editar_album'),
    path('albumes/eliminar/<int:id>/', views.eliminar_album, name='eliminar_album'),

    # Canciones
    path('canciones/', views.listar_canciones, name='listar_canciones'),
    path('canciones/crear/', views.crear_cancion, name='crear_cancion'),
    path('canciones/editar/<int:id>/', views.editar_cancion, name='editar_cancion'),
    path('canciones/eliminar/<int:id>/', views.eliminar_cancion, name='eliminar_cancion'),

    # Géneros
    path('generos/', views.listar_generos, name='listar_generos'),
    path('generos/crear/', views.crear_genero, name='crear_genero'),
    path('generos/editar/<int:id>/', views.editar_genero, name='editar_genero'),
    path('generos/eliminar/<int:id>/', views.eliminar_genero, name='eliminar_genero'),

    # Planes
    path('planes/', views.listar_planes, name='listar_planes'),
    path('planes/crear/', views.crear_plan, name='crear_plan'),
    path('planes/editar/<int:id>/', views.editar_plan, name='editar_plan'),
    path('planes/eliminar/<int:id>/', views.eliminar_plan, name='eliminar_plan'),
    
    # Rutas de autenticación
    path('login/', views.login_view, name='login'),
    path('registro/', views.registro_view, name='registro'),
    path('logout/', views.logout_view, name='logout'),
    
    path('dashboard/usuario/', views.dashboard_usuario, name='dashboard_usuario'),
    path('dashboard/artista/', views.dashboard_artista, name='dashboard_artista'),
]