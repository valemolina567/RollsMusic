from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from datetime import date
from django.db.models import Q

# Se añade 'Rol' a las importaciones
from .models import Usuario, Discografica, Artista, Album, Cancion, Genero, PlanEntity, Rol
from django.db import connection
from django.db import DatabaseError
from functools import wraps
from django.http import JsonResponse

from bson.objectid import ObjectId # Para manejar los IDs alfanuméricos de Mongo
from datetime import datetime # Fundamental para las fechas automáticas
from .db import db # Tu conexión de PyMongo

import os
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django.shortcuts import redirect

def verificar_rol(roles_permitidos):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # 1. Obtener el rol guardado en la sesión NoSQL de MongoDB
            rol_usuario = request.session.get('usuario_rol')
            
            # Si no ha iniciado sesión, al login
            if not request.session.get('usuario_id') or not rol_usuario:
                messages.error(request, "Debes iniciar sesión para acceder a esta sección.")
                return redirect('login')
            
            # 2. Normalizar strings (quitar espacios y capitalizar) para evitar fallos de tipeo en la BD
            rol_usuario_limpio = str(rol_usuario).strip().capitalize()
            roles_permitidos_limpios = [str(r).strip().capitalize() for r in roles_permitidos]
            
            # 3. Validar si el rol actual está dentro de los permitidos para esta vista
            if rol_usuario_limpio in roles_permitidos_limpios:
                return view_func(request, *args, **kwargs)
            else:
                messages.error(request, f"No tienes permisos para acceder a esta sección con tu rol de {rol_usuario}.")
                # Si es un artista queriendo entrar a una zona prohibida o viceversa, lo mandamos a su raíz correspondiente
                if rol_usuario_limpio == 'Artista':
                    return redirect('dashboard_artista')
                elif rol_usuario_limpio == 'Admin':
                    return redirect('index')
                else:
                    return redirect('dashboard_usuario')
        return _wrapped_view
    return decorator

@verificar_rol(['Admin'])
def listar_usuarios(request):
    query = request.GET.get('q', '').strip()
    
    if query:
        # Busca coincidencias tanto en el nombre como en el apellido
        usuarios = Usuario.objects.filter(Q(nombre__icontains=query) | Q(apellido__icontains=query))
    else:
        usuarios = Usuario.objects.all()
        
    return render(request, 'usuarios/listar.html', {'usuarios': usuarios})

# PANEL DE INICIO GENERAL
@verificar_rol(['Admin'])
def index(request):
    return render(request, 'index.html')

# ==========================================
# CRUD: DISCOGRAFICAS
# ==========================================
@verificar_rol(['Admin'])
def listar_discograficas(request):
    query = request.GET.get('q', '').strip()
    
    if query:
        items = Discografica.objects.filter(nombre__icontains=query)
    else:
        items = Discografica.objects.all()
        
    return render(request, 'discograficas/listar.html', {'items': items})

@verificar_rol(['Admin'])
def crear_discografica(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        pais = request.POST.get('pais', '').strip()
        fecha = request.POST.get('fechaFundacion', '').strip()
        logo = request.POST.get('logo', '').strip() or 'default_logo.png'

        if not nombre or not pais or not fecha:
            messages.error(request, "Todos los campos obligatorios deben completarse.")
            return render(request, 'discograficas/crear.html')

        Discografica.objects.create(nombre=nombre, pais=pais, fechaFundacion=fecha, logo=logo)
        messages.success(request, "Discográfica agregada exitosamente.")
        return redirect('listar_discograficas')
    return render(request, 'discograficas/crear.html')

@verificar_rol(['Admin'])
def editar_discografica(request, id):
    item = get_object_or_404(Discografica, idDiscografica=id)
    if request.method == 'POST':
        item.nombre = request.POST.get('nombre')
        item.pais = request.POST.get('pais')
        item.fechaFundacion = request.POST.get('fechaFundacion')
        item.logo = request.POST.get('logo') or item.logo
        item.save()
        return redirect('listar_discograficas')
    return render(request, 'discograficas/editar.html', {'item': item})

@verificar_rol(['Admin'])
def eliminar_discografica(request, id):
    item = get_object_or_404(Discografica, idDiscografica=id)
    if request.method == 'POST':
        try:
            item.delete()
        except:
            messages.error(request, "No se puede eliminar: tiene artistas asociados.")
        return redirect('listar_discograficas')

# ==========================================
# CRUD: ARTISTAS (Con Géneros Dinámicos)
# ==========================================

@verificar_rol(['Admin'])
def listar_artistas(request):
    query = request.GET.get('q', '').strip()
    
    if query:
        items = list(Artista.objects.filter(nombreArtistico__icontains=query))
    else:
        items = list(Artista.objects.all())
        
    # Mapeo de columnas dinámicas crudas para inyectarlas de forma segura en la vista
    with connection.cursor() as cursor:
        cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'Catalogo' AND TABLE_NAME = 'Artista'")
        art_cols = [row[0] for row in cursor.fetchall()]
        
        col_art_genero = 'genero' if 'genero' in art_cols else ('generoPrincipal' if 'generoPrincipal' in art_cols else None)
        col_art_verificado = 'verificado' if 'verificado' in art_cols else None

        for item in items:
            item.genero_db = ""
            item.verificado_db = False
            
            query_extra = "SELECT idArtista"
            params_extra = []
            if col_art_genero: query_extra += f", {col_art_genero}"
            if col_art_verificado: query_extra += f", {col_art_verificado}"
            query_extra += " FROM Catalogo.Artista WHERE idArtista = %s"
            
            cursor.execute(query_extra, [item.idArtista])
            row = cursor.fetchone()
            if row:
                idx = 1
                if col_art_genero:
                    item.genero_db = row[idx] if row[idx] else ""
                    idx += 1
                if col_art_verificado:
                    item.verificado_db = bool(row[idx])

    return render(request, 'artistas/listar.html', {'items': items})


@verificar_rol(['Admin'])
@verificar_rol(['Admin'])
def crear_artista(request):
    discograficas = Discografica.objects.all()
    generos = Genero.objects.all()
    
    if request.method == 'POST':
        nombre_artistico = request.POST.get('nombreArtistico')
        biografia = request.POST.get('biografia', '')
        pais = request.POST.get('pais', 'Desconocido')
        fecha_creacion = request.POST.get('fechaCreacion') or date.today()
        disco_id = request.POST.get('discografica')
        id_usuario = request.POST.get('usuario')
        genero_form = request.POST.get('generoPrincipal')
        verificado_form = 1 if request.POST.get('verificado') else 0 
        
        # --- LÓGICA PARA LA IMAGEN ---
        nombre_imagen = 'default_artist.png'
        if request.FILES.get('imagen'):
            imagen_archivo = request.FILES['imagen']
            fs = FileSystemStorage(location=os.path.join('static', 'images', 'artistas'))
            # Guarda el archivo y previene duplicados renombrándolo si es necesario
            filename = fs.save(imagen_archivo.name, imagen_archivo)
            nombre_imagen = f"artistas/{filename}" # Se guardará como 'artistas/nombre.jpg'

        with connection.cursor() as cursor:
            try:
                cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'Catalogo' AND TABLE_NAME = 'Artista'")
                art_cols = [row[0] for row in cursor.fetchall()]
                
                col_art_usuario = 'Usuario_idUsuario' if 'Usuario_idUsuario' in art_cols else ('idUsuario' if 'idUsuario' in art_cols else ('Usuario_id' if 'Usuario_id' in art_cols else None))
                col_art_nombre = 'nombreArtistico' if 'nombreArtistico' in art_cols else ('nombre_artistico' if 'nombre_artistico' in art_cols else 'nombre')
                col_art_genero = 'genero' if 'genero' in art_cols else ('generoPrincipal' if 'generoPrincipal' in art_cols else None)
                col_art_verificado = 'verificado' if 'verificado' in art_cols else None
                
                cols = [col_art_nombre, 'pais', 'fechaCreacion', 'imagen', 'biografia', 'Discografica_idDiscografica']
                vals = [nombre_artistico, pais, fecha_creacion, nombre_imagen, biografia, disco_id]
                placeholders = ["%s"] * len(cols)
                
                if col_art_usuario and id_usuario:
                    cols.append(col_art_usuario)
                    vals.append(int(id_usuario))
                    placeholders.append("%s")
                
                if col_art_genero and genero_form:
                    cols.append(col_art_genero)
                    vals.append(genero_form)
                    placeholders.append("%s")
                    
                if col_art_verificado:
                    cols.append(col_art_verificado)
                    vals.append(verificado_form)
                    placeholders.append("%s")
                    
                sql_insert = f"INSERT INTO Catalogo.Artista ({', '.join(cols)}) VALUES ({', '.join(placeholders)})"
                cursor.execute(sql_insert, vals)
                
                messages.success(request, f"Perfil de '{nombre_artistico}' creado con imagen correctamente.")
                return redirect('listar_artistas')
            except Exception as e:
                messages.error(request, f"Error en SQL Server: {str(e)}")
                
    usuarios_artistas = Usuario.objects.filter(Rol_idRol__nombre='Artista')
    if not usuarios_artistas.exists():
        usuarios_artistas = Usuario.objects.all()
        
    return render(request, 'artistas/crear.html', {
        'discograficas': discograficas,
        'usuarios_artistas': usuarios_artistas,
        'generos': generos
    })


@verificar_rol(['Admin'])
def editar_artista(request, id):
    artista_obj = get_object_or_404(Artista, idArtista=id)
    discograficas = Discografica.objects.all()
    generos = Genero.objects.all()
    
    usuarios_artistas = Usuario.objects.filter(Rol_idRol__nombre='Artista')
    if not usuarios_artistas.exists():
        usuarios_artistas = Usuario.objects.all()

    artista_usuario_id = None
    genero_actual = ""
    es_verificado = False
    
    with connection.cursor() as cursor:
        cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'Catalogo' AND TABLE_NAME = 'Artista'")
        art_cols = [row[0] for row in cursor.fetchall()]
        
        col_art_usuario = 'Usuario_idUsuario' if 'Usuario_idUsuario' in art_cols else ('idUsuario' if 'idUsuario' in art_cols else ('Usuario_id' if 'Usuario_id' in art_cols else None))
        col_art_genero = 'genero' if 'genero' in art_cols else ('generoPrincipal' if 'generoPrincipal' in art_cols else None)
        col_art_verificado = 'verificado' if 'verificado' in art_cols else None
        
        query_extra = "SELECT idArtista"
        if col_art_usuario: query_extra += f", {col_art_usuario}"
        if col_art_genero: query_extra += f", {col_art_genero}"
        if col_art_verificado: query_extra += f", {col_art_verificado}"
        query_extra += " FROM Catalogo.Artista WHERE idArtista = %s"
        
        cursor.execute(query_extra, [id])
        row = cursor.fetchone()
        if row:
            idx = 1
            if col_art_usuario:
                artista_usuario_id = row[idx]
                idx += 1
            if col_art_genero:
                genero_actual = row[idx] if row[idx] else ""
                idx += 1
            if col_art_verificado:
                es_verificado = bool(row[idx])

    if request.method == 'POST':
        nombre_form = request.POST.get('nombreArtistico')
        biografia_form = request.POST.get('biografia', '')
        disco_id = request.POST.get('discografica')
        id_usuario = request.POST.get('usuario')
        genero_form = request.POST.get('generoPrincipal')
        verificado_form = 1 if request.POST.get('verificado') else 0

        # --- ACTUALIZACIÓN DE IMAGEN ---
        nombre_imagen = artista_obj.imagen # Por defecto mantiene la actual
        if request.FILES.get('imagen'):
            imagen_archivo = request.FILES['imagen']
            fs = FileSystemStorage(location=os.path.join('static', 'images', 'artistas'))
            filename = fs.save(imagen_archivo.name, imagen_archivo)
            nombre_imagen = f"artistas/{filename}"

        with connection.cursor() as cursor:
            try:
                col_art_nombre = 'nombre' if 'nombre' in art_cols else 'nombreArtistico'
                
                sql_update = f"UPDATE Catalogo.Artista SET {col_art_nombre} = %s, biografia = %s, Discografica_idDiscografica = %s, imagen = %s"
                params = [nombre_form, biografia_form, disco_id, nombre_imagen]
                
                if col_art_usuario:
                    sql_update += f", {col_art_usuario} = %s"
                    params.append(int(id_usuario) if id_usuario else None)
                if col_art_genero:
                    sql_update += f", {col_art_genero} = %s"
                    params.append(genero_form)
                if col_art_verificado:
                    sql_update += f", {col_art_verificado} = %s"
                    params.append(verificado_form)
                    
                sql_update += " WHERE idArtista = %s"
                params.append(id)
                
                cursor.execute(sql_update, params)
                messages.success(request, f"Perfil de '{nombre_form}' actualizado correctamente.")
                return redirect('listar_artistas')
            except Exception as e:
                messages.error(request, f"Error al guardar en SQL Server: {str(e)}")
    
    return render(request, 'artistas/editar.html', {
        'artista': artista_obj,
        'artista_usuario_id': artista_usuario_id,
        'genero_actual': genero_actual,
        'es_verificado': es_verificado,
        'discograficas': discograficas,
        'usuarios_artistas': usuarios_artistas,
        'generos': generos
    })

@verificar_rol(['Admin'])
def eliminar_artista(request, id):
    item = get_object_or_404(Artista, idArtista=id)
    if request.method == 'POST':
        item.delete()
        messages.success(request, "Artista eliminado con éxito.")
        return redirect('listar_artistas')

# ==========================================
# CRUD: ALBUMES
# ==========================================
@verificar_rol(['Admin'])
def listar_albumes(request):
    query = request.GET.get('q', '').strip()
    
    if query:
        items = Album.objects.filter(titulo__icontains=query)
    else:
        items = Album.objects.all()
        
    return render(request, 'albumes/listar.html', {'items': items})

@verificar_rol(['Admin'])
def crear_album(request):
    artistas = Artista.objects.all()
    if request.method == 'POST':
        titulo = request.POST.get('titulo')
        fecha = request.POST.get('fechaLanzamiento')
        artista_id = request.POST.get('artista')
        
        # CAPTURAR LA IMAGEN SUBIDA
        imagen = request.FILES.get('imagen') 
        
        artista = get_object_or_404(Artista, idArtista=artista_id)
        
        # SI NO SE SUBE IMAGEN, DJANGO ASIGNA AUTOMÁTICAMENTE EL DEFAULT SI ESTÁ CONFIGURADO EN EL MODELO.
        # SI NO TIENES DEFAULT EN EL MODELO, PASAMOS LA VARIABLE DIRECTAMENTE.
        Album.objects.create(
            titulo=titulo, 
            fechaLanzamiento=fecha, 
            Artista_idArtista=artista, 
            imagen=imagen if imagen else 'default_album.png' # Fallback manual
        )
        return redirect('listar_albumes')
    return render(request, 'albumes/crear.html', {'artistas': artistas})

@verificar_rol(['Admin'])
def editar_album(request, id):
    item = get_object_or_404(Album, idAlbum=id)
    artistas = Artista.objects.all()

    if request.method == 'POST':
        item.titulo = request.POST.get('titulo')
        item.fechaLanzamiento = request.POST.get('fechaLanzamiento')
        item.Artista_idArtista = get_object_or_404(Artista, idArtista=request.POST.get('artista'))
        
        # VALIDAR SI EL USUARIO SUBIÓ UNA NUEVA PORTADA
        nueva_imagen = request.FILES.get('imagen')
        if nueva_imagen:
            item.imagen = nueva_imagen  # Solo se reemplaza si viene un archivo nuevo
            
        item.save()
        return redirect('listar_albumes')

    return render(request, 'albumes/editar.html', {
        'item': item,
        'artistas': artistas
    })

@verificar_rol(['Admin'])
def eliminar_album(request, id):
    item = get_object_or_404(Album, idAlbum=id)
    if request.method == 'POST':
        item.delete()
        return redirect('listar_albumes')

# ==========================================
# CRUD: CANCIONES
# ==========================================

@verificar_rol(['Admin'])
def listar_canciones(request):
    query = request.GET.get('q', '').strip()

    if query:
        items = Cancion.objects.filter(titulo__icontains=query)
    else:
        items = Cancion.objects.all()

    return render(request, 'canciones/listar.html', {'items': items})


# ------------------------------------------
# CREAR CANCION (CON IMAGEN)
# ------------------------------------------
@verificar_rol(['Admin'])
def crear_cancion(request):
    albumes = Album.objects.all()

    if request.method == 'POST':
        titulo = request.POST.get('titulo')
        duracion = request.POST.get('duracion')
        pista = request.POST.get('numeroPista')
        fecha = request.POST.get('fechaLanzamiento')
        calidad = request.POST.get('calidadAudio')
        album_id = request.POST.get('album')

        # 👇 IMAGEN (IMPORTANTE)
        imagen = request.FILES.get('imagen')

        album = get_object_or_404(Album, idAlbum=album_id)

        Cancion.objects.create(
            titulo=titulo,
            duracion=duracion,
            numeroPista=pista,
            fechaLanzamiento=fecha,
            calidadAudio=calidad,
            Album_idAlbum=album,
            imagen=imagen if imagen else 'canciones/default.png'
        )

        return redirect('listar_canciones')

    return render(request, 'canciones/crear.html', {'albumes': albumes})


# ------------------------------------------
# EDITAR CANCION (CON IMAGEN)
# ------------------------------------------
@verificar_rol(['Admin'])
def editar_cancion(request, id):
    item = get_object_or_404(Cancion, idCancion=id)
    albumes = Album.objects.all()

    if request.method == 'POST':
        fecha = request.POST.get('fechaLanzamiento')

        item.titulo = request.POST.get('titulo')
        item.duracion = request.POST.get('duracion')
        item.numeroPista = request.POST.get('numeroPista')
        item.calidadAudio = request.POST.get('calidadAudio')
        item.Album_idAlbum = get_object_or_404(Album, idAlbum=request.POST.get('album'))

        # 🔥 protección contra NULL
        if fecha:
            item.fechaLanzamiento = fecha

        # imagen opcional (si la tienes)
        if request.FILES.get('imagen'):
            item.imagen = request.FILES['imagen']

        item.save()
        return redirect('listar_canciones')

    return render(request, 'canciones/editar.html', {
        'item': item,
        'albumes': albumes
    })


# ------------------------------------------
# ELIMINAR CANCION
# ------------------------------------------
@verificar_rol(['Admin'])
def eliminar_cancion(request, id):
    item = get_object_or_404(Cancion, idCancion=id)

    if request.method == 'POST':
        item.delete()
        return redirect('listar_canciones')

# ==========================================
# CRUD: GENEROS
# ==========================================
@verificar_rol(['Admin'])
def listar_generos(request):
    query = request.GET.get('q', '').strip()
    
    if query:
        items = Genero.objects.filter(nombre__icontains=query)
    else:
        items = Genero.objects.all()
        
    return render(request, 'generos/listar.html', {'items': items})

@verificar_rol(['Admin'])
def crear_genero(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        Genero.objects.create(nombre=nombre)
        return redirect('listar_generos')
    return render(request, 'generos/crear.html')

@verificar_rol(['Admin'])
def editar_genero(request, id):
    item = get_object_or_404(Genero, idGenero=id)
    if request.method == 'POST':
        item.nombre = request.POST.get('nombre')
        item.save()
        return redirect('listar_generos')
    return render(request, 'generos/editar.html', {'item': item})

@verificar_rol(['Admin'])
def eliminar_genero(request, id):
    item = get_object_or_404(Genero, idGenero=id)
    if request.method == 'POST':
        item.delete()
        return redirect('listar_generos')

# ==========================================
# CRUD: PLANES
# ==========================================
@verificar_rol(['Admin'])
def listar_planes(request):
    items = PlanEntity.objects.all()
    return render(request, 'planes/listar.html', {'items': items})

@verificar_rol(['Admin'])
def crear_plan(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        precio = request.POST.get('precio')
        duracion = request.POST.get('duracionDias')
        PlanEntity.objects.create(nombre=nombre, precio=precio, duracionDias=duracion)
        return redirect('listar_planes')
    return render(request, 'planes/crear.html')

@verificar_rol(['Admin'])
def editar_plan(request, id):
    item = get_object_or_404(PlanEntity, idPlan=id)
    if request.method == 'POST':
        item.nombre = request.POST.get('nombre')
        item.precio = request.POST.get('precio')
        item.duracionDias = request.POST.get('duracionDias')
        item.save()
        return redirect('listar_planes')
    return render(request, 'planes/editar.html', {'item': item})

@verificar_rol(['Admin'])
def eliminar_plan(request, id):
    item = get_object_or_404(PlanEntity, idPlan=id)
    if request.method == 'POST':
        item.delete()
        return redirect('listar_planes')

# ==========================================
# CRUD: USUARIOS
# ==========================================

@verificar_rol(['Admin'])
def crear_usuario(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        apellido = request.POST.get('apellido', '').strip()
        correo = request.POST.get('correo', '').strip()
        fecha_nacimiento = request.POST.get('fechaNacimiento', '').strip()
        contrasenia = request.POST.get('contrasenia', '').strip()
        rol_id = request.POST.get('rol', 2) 

        errores = []
        if not nombre: errores.append("El nombre es obligatorio")
        if not apellido: errores.append("El apellido es obligatorio")
        if not correo: errores.append("El correo es obligatorio")
        if not contrasenia: errores.append("La contraseña es obligatoria")
        
        fecha_nacimiento_dt = None
        if not fecha_nacimiento:
            errores.append("La fecha de nacimiento es obligatoria")
        else:
            try: fecha_nacimiento_dt = date.fromisoformat(fecha_nacimiento)
            except ValueError: errores.append("La fecha de nacimiento no tiene un formato válido (YYYY-MM-DD)")
        
        if errores:
            for e in errores: messages.error(request, e)
            return render(request, 'usuarios/crear.html')
        
        rol_obj = get_object_or_404(Rol, idRol=rol_id)

        Usuario.objects.create(
            nombre=nombre, apellido=apellido, correo=correo, contrasenia=contrasenia,
            fechaRegistro=date.today(), estado='Activo', imagen='default.png', 
            fechaNacimiento=fecha_nacimiento_dt,
            Rol_idRol=rol_obj 
        )
        messages.success(request, "Usuario creado correctamente")
        return redirect('listar_usuarios') # Corregido: apuntaba a 'listar' y tu vista se llama 'listar_usuarios'
    
    roles = Rol.objects.all()
    return render(request, 'usuarios/crear.html', {'roles': roles})

@verificar_rol(['Admin'])
def editar_usuario(request, id):
    usuario = get_object_or_404(Usuario, idUsuario=id)
    roles = Rol.objects.all() 
    
    if request.method == 'POST':
        usuario.nombre = request.POST.get('nombre', '').strip()
        usuario.apellido = request.POST.get('apellido', '').strip()
        usuario.correo = request.POST.get('correo', '').strip()
        usuario.estado = request.POST.get('estado', '').strip()
        
        if request.POST.get('fechaNacimiento'):
            usuario.fechaNacimiento = request.POST.get('fechaNacimiento')
            
        id_rol = request.POST.get('rol')
        if id_rol:
            usuario.Rol_idRol_id = int(id_rol)
            
        usuario.save()
        
        # CONFIRMACIÓN VISUAL: Agregamos una notificación de éxito
        messages.success(request, f"El perfil de '{usuario.nombre} {usuario.apellido}' ha sido actualizado exitosamente.")
        return redirect('listar_usuarios')
        
    return render(request, 'usuarios/editar.html', {
        'usuario': usuario,
        'roles': roles
    })

@verificar_rol(['Admin'])
def eliminar_usuario(request, id):
    usuario = get_object_or_404(Usuario, idUsuario=id)
    # Quitamos el "if request.method == 'POST'" para que acepte el viaje directo de SweetAlert2
    try:
        usuario.delete()
        messages.success(request, "Usuario eliminado correctamente de la plataforma.")
    except Exception as e:
        # SQL Server frenará el borrado si el usuario tiene playlists, reproducciones, etc.
        messages.error(request, "No se pudo eliminar el usuario debido a dependencias activas en la base de datos.")
    
    # Este return ahora sí se ejecuta siempre, sin importar si es GET o POST
    return redirect('listar_usuarios')
    
# ==========================================
# SISTEMA DE AUTENTICACIÓN (LOGIN / LOGOUT) - MIGRADO A MONGODB 
# ==========================================

def login_view(request):
    if request.method == 'POST':
        correo = request.POST.get('correo', '').strip()
        contrasenia = request.POST.get('contrasenia', '').strip()

        if not correo or not contrasenia:
            messages.error(request, "Por favor, completa todos los campos.")
            return render(request, 'auth/login.html')

        try:
            usuario = db.usuarios.find_one({"correo": correo})
            
            if usuario:
                if usuario.get('contrasenia') == contrasenia:
                    if usuario.get('estado') != 'Activo':
                        messages.error(request, f"Tu cuenta se encuentra: {usuario.get('estado')}. Contacta al administrador.")
                        return render(request, 'auth/login.html')
                    
                    # 1. Obtener el ID original migrado o el nuevo _id
                    user_id = usuario.get('idUsuarioSQL') or usuario.get('idUsuario') or str(usuario['_id']) 
                    request.session['usuario_id'] = str(user_id)
                    request.session['usuario_nombre'] = f"{usuario.get('nombre', '')} {usuario.get('apellido', '')}"
                    
                    # 2. Extraer rol explícito si lo hay
                    rol_db = str(usuario.get('rol', '')).strip().capitalize()
                    
                    # Si el rol es numérico o no existe, verificar los campos clásicos de SQL
                    id_rol = usuario.get('Rol_idRol') or usuario.get('idRol') or usuario.get('rol_id') or usuario.get('Rol_id')
                    
                    if not rol_db or rol_db == 'None':
                        if id_rol == 1:
                            rol_db = 'Admin'
                        elif id_rol == 2:
                            rol_db = 'Artista'
                        else:
                            rol_db = 'Cliente'
                            
                    # 3. VERIFICACIÓN EXPANSIVA: Búsqueda en la colección de artistas
                    # Convertimos el ID a número por si la migración lo guardó como Int
                    user_query_val = int(user_id) if str(user_id).isdigit() else str(user_id)
                    
                    es_artista = db.artistas.find_one({
                        "$or": [
                            {"idUsuario": user_query_val},
                            {"idUsuario": str(user_id)},
                            {"Usuario_idUsuario": user_query_val},
                            {"usuario_id": user_query_val},
                            {"Usuario_id": user_query_val},
                            {"idUsuarioSQL": user_query_val}
                        ]
                    })
                    
                    if es_artista:
                        rol_db = 'Artista'
                        
                    # ==========================================
                    # 🐞 DEBUG: Imprimir en el CMD para rastrear el error
                    # ==========================================
                    print("\n" + "="*50)
                    print(f"🔍 DEBUG LOGIN - USUARIO: {correo}")
                    print(f"1. ID detectado (user_id): {user_id}")
                    print(f"2. Rol numérico en BD (id_rol): {id_rol}")
                    print(f"3. Rol en texto (rol_db): {rol_db}")
                    print(f"4. ¿Se encontró en db.artistas?: {'SÍ ✅' if es_artista else 'NO ❌'}")
                    if not es_artista:
                        print("   -> El sistema te mandará al panel de usuario porque no halló tu perfil de artista.")
                    print("="*50 + "\n")
                    # ==========================================
                        
                    request.session['usuario_rol'] = rol_db
                    
                    # Redirección final
                    if rol_db == 'Admin':
                        return redirect('index')
                    elif rol_db == 'Artista':
                        return redirect('dashboard_artista')
                    else:
                        return redirect('dashboard_usuario')
                else:
                    messages.error(request, "Contraseña incorrecta.")
            else:
                messages.error(request, "El correo electrónico no está registrado.")
                
        except Exception as e:
            messages.error(request, f"Error al conectar con la base de datos: {str(e)}")

    return render(request, 'auth/login.html')

def registro_view(request):
    if request.method == 'POST':
        # 1. Capturar los datos enviados por el usuario
        nombre = request.POST.get('nombre', '').strip()
        apellido = request.POST.get('apellido', '').strip()
        correo = request.POST.get('correo', '').strip()
        contrasenia = request.POST.get('contrasenia', '').strip()
        fecha_nacimiento = request.POST.get('fecha_nacimiento', '').strip()
        
        # Validar que no existan campos vacíos
        if not all([nombre, apellido, correo, contrasenia, fecha_nacimiento]):
            messages.error(request, "Por favor, completa todos los campos obligatorios.")
            return render(request, 'auth/registro.html')

        try:
            # 2. Validar que el correo no exista ya en MongoDB
            if db.usuarios.find_one({"correo": correo}):
                messages.error(request, "Error: Este correo electrónico ya está en uso.")
                return render(request, 'auth/registro.html')
            
            # 3. Construir el documento JSON (Con la suscripción embebida como en el Avance 5)
            nuevo_usuario = {
                "nombre": nombre,
                "apellido": apellido,
                "correo": correo,
                "contrasenia": contrasenia,
                "fechaNacimiento": fecha_nacimiento,
                "fechaRegistro": datetime.now(),
                "estado": "Activo",
                "rol": "Cliente", # Rol por defecto
                "imagen": "usuario_nuevo.png",
                "suscripcion": {
                    "plan": "Free",
                    "estado": "Activa"
                }
            }
            
            # 4. Inserción directa en MongoDB (Reemplaza al SP de SQL)
            db.usuarios.insert_one(nuevo_usuario)
            
            messages.success(request, "¡Cuenta creada con éxito! Ahora puedes iniciar sesión.")
            return redirect('login')
            
        except Exception as e:
            messages.error(request, f"Ocurrió un error en el servidor NoSQL: {str(e)}")

    return render(request, 'auth/registro.html')

# ==========================================
# DASHBOARDS E INTEGRACIÓN DE OBJETOS SQL
# ==========================================

def dictfetchall(cursor):
    """Devuelve todas las filas de un cursor como un diccionario (clave-valor)."""
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]

@verificar_rol(['Cliente', 'Admin'])
def dashboard_usuario(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return redirect('login')
        
    top_canciones, playlists_usuario = [], []
    auto_open_id = request.session.pop('auto_open_playlist_id', None)
    
    # 1. Determinar el formato del ID (soporte para cuentas nuevas y migradas)
    try:
        user_query = {"_id": ObjectId(usuario_id)}
    except:
        user_query = {"idUsuarioSQL": int(usuario_id)}
        
    # 2. LECTURA DE PLAN: Extraer suscripción embebida en MongoDB
    usuario = db.usuarios.find_one(user_query)
    plan_info = {'plan_nombre': 'Free', 'suscripcion_estado': 'Inactiva'}
    if usuario and 'suscripcion' in usuario:
        plan_info = {
            'plan_nombre': usuario['suscripcion'].get('plan', 'Free'),
            'suscripcion_estado': usuario['suscripcion'].get('estado', 'Activa')
        }

    # 3. LECTURA MONGODB: Traer las playlists del usuario
    try:
        playlists_mongo = db.playlists.find({"$or": [{"idUsuarioSQL": usuario_id}, {"idUsuarioSQL": int(usuario_id) if str(usuario_id).isdigit() else usuario_id}]})
        for p in playlists_mongo:
            playlists_usuario.append((str(p['_id']), p.get('nombre', 'Sin nombre')))
    except Exception as e:
        print(f"Error al leer Playlists de Mongo: {e}")

    # 4. AGGREGATION PIPELINE: "Lo que más escuchas" (Reemplaza a EXEC sp_TopCancionesUsuario)
    try:
        pipeline_top = [
            {"$match": {"$or": [{"idUsuarioSQL": usuario_id}, {"idUsuarioSQL": int(usuario_id) if str(usuario_id).isdigit() else usuario_id}]}},
            {"$group": {"_id": "$idCancionSQL", "reproducciones": {"$sum": 1}}},
            {"$sort": {"reproducciones": -1}},
            {"$limit": 5},
            {"$lookup": {
                "from": "canciones",
                "localField": "_id",
                "foreignField": "idCancionSQL", 
                "as": "cancion_info"
            }},
            {"$unwind": "$cancion_info"}
        ]
        resultados_top = list(db.reproducciones.aggregate(pipeline_top))
        for r in resultados_top:
            c_info = r['cancion_info']
            top_canciones.append({
                'idCancion': c_info.get('idCancionSQL') or str(c_info['_id']),
                'Cancion': c_info.get('titulo', 'Desconocido'),
                'Artista': c_info.get('artista', {}).get('nombre', 'Desconocido'),
                'Album': c_info.get('album', {}).get('titulo', 'Sencillo')
            })
    except Exception as e:
        print(f"Error en Pipeline de Top Canciones: {e}")

    # 5. RECOMENDACIONES MONGODB: (Reemplaza a EXEC sp_RecomendacionesPersonalizadas)
    recomendaciones = request.session.get('recomendaciones_cache')
    if not recomendaciones:
        recomendaciones = []
        try:
            # Seleccionamos 5 pistas aleatorias del catálogo en Mongo con $sample
            recs_mongo = db.canciones.aggregate([{"$sample": {"size": 5}}])
            for c in recs_mongo:
                recomendaciones.append({
                    'idCancion': c.get('idCancionSQL') or str(c['_id']),
                    'Cancion': c.get('titulo', 'Desconocido'),
                    'Artista': c.get('artista', {}).get('nombre', 'Desconocido'),
                    'Album': c.get('album', {}).get('titulo', 'Sencillo')
                })
            request.session['recomendaciones_cache'] = recomendaciones
        except Exception:
            pass

    context = {
        'top_canciones': top_canciones,
        'recomendaciones': recomendaciones,
        'plan_info': plan_info,
        'playlists': playlists_usuario,
        'auto_open_playlist_id': auto_open_id,
    }
    return render(request, 'dashboards/usuario.html', context)

@verificar_rol(['Artista', 'Admin'])
def dashboard_artista(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return redirect('login')

    total_regalias = 0.0
    minutos_cancion_demo = 0.0 # ¡Ajustado para el HTML!
    albumes = []
    canciones_artista = []
    artista = None
    nombre_artista = request.session.get('usuario_nombre')

    try:
        user_query = ObjectId(usuario_id) if len(str(usuario_id)) == 24 else int(usuario_id)
        
        artista = db.artistas.find_one({
            "$or": [
                {"idUsuario": user_query},
                {"Usuario_idUsuario": user_query},
                {"idUsuario": str(usuario_id)},
                {"idUsuarioSQL": user_query}
            ]
        })
        
        if artista:
            artista_id = artista.get('idArtistaSQL') or artista.get('idArtista') or str(artista['_id'])
            nombre_artista = artista.get('nombreArtistico') or artista.get('nombre') or nombre_artista
            artista['nombre'] = nombre_artista  
        else:
            artista = {
                'nombreArtistico': nombre_artista,
                'nombre': nombre_artista,
                'pais': 'No especificado',
                'biografia': 'Sin biografía'
            }
            artista_id = usuario_id

        artista_query_val = int(artista_id) if str(artista_id).isdigit() else str(artista_id)

        # -------------------------------------------------------------------
        # 1. OBTENER ÁLBUMES
        # -------------------------------------------------------------------
        albumes = list(db.albumes.find({
            "$or": [
                {"idArtista": artista_query_val},
                {"idArtista": str(artista_id)},
                {"Artista_idArtista": artista_query_val},
                {"idArtistaSQL": artista_query_val}
            ]
        }))

        mapa_albumes = {}
        ids_albumes = []
        albums_artista_combo = [] # ¡Ajustado para el combo box del modal HTML!
        
        for a in albumes:
            id_alb = a.get('idAlbumSQL') or a.get('idAlbum') or a.get('Album_idAlbum') or str(a['_id'])
            if id_alb is not None:
                ids_albumes.append(id_alb)
                if str(id_alb).isdigit():
                    ids_albumes.append(int(id_alb))
                titulo_alb = a.get('titulo', 'Sencillo')
                mapa_albumes[str(id_alb)] = titulo_alb
                albums_artista_combo.append((str(id_alb), titulo_alb))

        # -------------------------------------------------------------------
        # 2. OBTENER CANCIONES
        # -------------------------------------------------------------------
        canciones_artista = list(db.canciones.find({
            "$or": [
                {"idArtista": artista_query_val},
                {"idArtista": str(artista_id)},
                {"Artista_idArtista": artista_query_val},
                {"idAlbum": {"$in": ids_albumes}},
                {"Album_idAlbum": {"$in": ids_albumes}},
                {"idAlbumSQL": {"$in": ids_albumes}}
            ]
        }))

        mapa_duraciones_safe = {}
        ids_canciones = []

        for cancion in canciones_artista:
            id_alb_cancion = str(cancion.get('idAlbum') or cancion.get('Album_idAlbum') or cancion.get('idAlbumSQL'))
            titulo_del_album = mapa_albumes.get(id_alb_cancion, "Sencillo")
            
            # --- Mapeos exactos para tu HTML ---
            cancion['Album_idAlbum'] = {'titulo': titulo_del_album} 
            
            segs = cancion.get('duracionSegundos') or cancion.get('duracion') or 0
            
            # El HTML espera la variable 'duracion' cruda o formateada. La formateamos aquí y la llamamos 'duracion'
            if isinstance(segs, int):
                mins = segs // 60
                rems = segs % 60
                cancion['duracion'] = f"{mins}:{rems:02d}"
            else:
                cancion['duracion'] = "0:00"

            idc = cancion.get('idCancionSQL') or cancion.get('idCancion') or cancion.get('Cancion_idCancion') or str(cancion['_id'])
            if idc is not None:
                ids_canciones.append(idc)
                if str(idc).isdigit():
                    ids_canciones.append(int(idc))
                mapa_duraciones_safe[str(idc)] = segs

        # -------------------------------------------------------------------
        # 3. MÉTRICA 100% SEGURA: MINUTOS REPRODUCIDOS
        # -------------------------------------------------------------------
        if ids_canciones:
            reproducciones = list(db.reproducciones.find({
                "$or": [
                    {"idCancionSQL": {"$in": ids_canciones}},
                    {"idCancion": {"$in": ids_canciones}},
                    {"Cancion_idCancion": {"$in": ids_canciones}}
                ]
            }))
            
            total_segs = 0
            for rep in reproducciones:
                id_c = rep.get('idCancionSQL') or rep.get('idCancion') or rep.get('Cancion_idCancion')
                if id_c is not None:
                    total_segs += mapa_duraciones_safe.get(str(id_c), 0)
            
            # ¡Se asigna a la variable que tu HTML espera!
            minutos_cancion_demo = round(total_segs / 60, 2)

        # -------------------------------------------------------------------
        # 4. MÉTRICA 100% SEGURA: REGALÍAS TOTALES
        # -------------------------------------------------------------------
        regalias = list(db.regalias.find({
            "$or": [
                {"idArtista": {"$in": [artista_query_val, str(artista_id)]}},
                {"Artista_idArtista": {"$in": [artista_query_val, str(artista_id)]}},
                {"idArtistaSQL": {"$in": [artista_query_val, str(artista_id)]}},
                {"artista.idArtista": {"$in": [artista_query_val, str(artista_id)]}}
            ]
        }))
        
        total_regalias = sum([float(r.get('monto', 0)) for r in regalias])
        total_regalias = round(total_regalias, 2)

    except Exception as e_general:
        print(f"🚨 ERROR EN DASHBOARD ARTISTA: {str(e_general)}")

    context = {
        'artista': artista,  
        'artista_nombre': nombre_artista,
        'total_regalias': total_regalias,
        'minutos_cancion_demo': minutos_cancion_demo, # ¡Variable ajustada!
        'albums_artista': albums_artista_combo, # ¡Variable ajustada para el select!
        'canciones_artista': canciones_artista
    }
    return render(request, 'dashboards/artista.html', context)

@verificar_rol(['Cliente', 'Admin'])
def procesar_pago(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return redirect('login')
        
    if request.method == 'POST':
        metodo = request.POST.get('metodo') 
        monto = 9.99 
        
        try:
            # Soportar IDs nuevos y heredados de la migración
            try:
                user_query = {"_id": ObjectId(usuario_id)}
            except:
                user_query = {"idUsuarioSQL": int(usuario_id)}
                
            # 1. Actualizamos el estado del usuario usando $set
            db.usuarios.update_one(
                user_query,
                {"$set": {
                    "suscripcion.plan": "Premium",
                    "suscripcion.estado": "Activa"
                }}
            )
            
            # 2. Insertamos el registro físico en MongoDB (Reemplaza al SP Facturacion.sp_RegistrarPago)
            nuevo_pago = {
                "idUsuario": usuario_id,
                "monto": monto,
                "metodo": metodo,
                "fechaGeneracion": datetime.now(),
                "estado": "Completado"
            }
            db.pagos.insert_one(nuevo_pago)
            
            messages.success(request, "¡Transacción completada! Tu cuenta ha sido actualizada a Premium 💎")
            return redirect('dashboard_usuario')
            
        except Exception as e:
            messages.error(request, f"Error al procesar el pago en MongoDB: {str(e)}")
            
    return render(request, 'dashboards/facturacion.html')

@verificar_rol(['Admin'])
def verificar_suscripciones(request):
    # Verificación de seguridad: Solo el Admin puede ejecutar esto
    if 'usuario_id' not in request.session or request.session.get('usuario_rol') != 'Admin':
        messages.error(request, "Acceso denegado. Esta acción es exclusiva para administradores.")
        return redirect('login')
        
    try:
        with connection.cursor() as cursor:
            # Consumo del Procedimiento Almacenado que contiene el Cursor
            cursor.execute("EXEC Facturacion.sp_VerificarSuscripcionesVencidas")
            
        messages.success(request, "⚙️ Mantenimiento completado: El cursor ha verificado y actualizado las suscripciones vencidas exitosamente.")
    except Exception as e:
        messages.error(request, f"Error al ejecutar el cursor de mantenimiento: {str(e)}")
        
    return redirect('index')

@verificar_rol(['Cliente', 'Admin'])
def registrar_reproduccion(request, id_cancion):
    usuario_id = request.session.get('usuario_id')
    
    try:
        # REGLA DE NEGOCIO: Validar que el usuario esté 'Activo'
        usuario_mongo = db.usuarios.find_one({"idUsuarioSQL": usuario_id})
        
        if not usuario_mongo:
            return JsonResponse({'status': 'error', 'message': 'Usuario no encontrado en MongoDB.'}, status=404)
            
        if usuario_mongo.get('estado') != 'Activo':
            return JsonResponse({'status': 'error', 'message': 'Operación denegada: Tu cuenta debe estar Activa para reproducir música.'}, status=403)

        # Inserción en MongoDB
        nueva_reproduccion = {
            "idUsuarioSQL": usuario_id,
            "idCancionSQL": int(id_cancion),
            "fechaHora": datetime.now(), 
            "dispositivo": "Navegador Web",
            "pais": "Ecuador", 
            "duracionEscuchada": 0, 
            "completada": True
        }

        db.reproducciones.insert_one(nueva_reproduccion)
        return JsonResponse({'status': 'success', 'message': 'Reproducción registrada en MongoDB.'})
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Fallo de BD NoSQL: {str(e)}'}, status=500)

@verificar_rol(['Artista', 'Admin'])
def crear_album_artista(request):
    usuario_id = request.session.get('usuario_id')
    if request.method == 'POST':
        # Capturamos exactamente las variables de tu modal HTML
        titulo = request.POST.get('titulo')
        fecha_lanzamiento = request.POST.get('fecha_lanzamiento')
        imagen = request.FILES.get('imagen')
        
        user_query = ObjectId(usuario_id) if len(str(usuario_id)) == 24 else int(usuario_id)
        artista = db.artistas.find_one({
            "$or": [{"idUsuario": user_query}, {"Usuario_idUsuario": user_query}, {"idUsuario": str(usuario_id)}]
        })
        
        artista_id = artista.get('idArtistaSQL') or artista.get('idArtista') or str(artista['_id']) if artista else usuario_id
        
        # Mantenemos la lógica de la imagen física intacta
        imagen_nombre = "default_album.jpg"
        if imagen:
            fs = FileSystemStorage(location='media/albumes/')
            filename = fs.save(imagen.name, imagen)
            imagen_nombre = filename

        # -------------------------------------------------------------------
        # ⚠️ ESTRUCTURA CORREGIDA (Formato Plano para match con Dashboard)
        # -------------------------------------------------------------------
        nuevo_album = {
            "titulo": titulo,
            "fechaLanzamiento": fecha_lanzamiento,
            "imagen": imagen_nombre,
            "idArtista": int(artista_id) if str(artista_id).isdigit() else artista_id
        }
        
        try:
            db.albumes.insert_one(nuevo_album)
            messages.success(request, f"El álbum '{titulo}' ha sido añadido a tu discografía.")
            return redirect('dashboard_artista')
        except Exception as e:
            messages.error(request, f"Error al registrar álbum: {e}")

    return redirect('dashboard_artista')

@verificar_rol(['Artista', 'Admin'])
def subir_cancion_artista(request):
    usuario_id = request.session.get('usuario_id')
    
    user_query = ObjectId(usuario_id) if len(str(usuario_id)) == 24 else int(usuario_id)
    artista = db.artistas.find_one({
        "$or": [{"idUsuario": user_query}, {"Usuario_idUsuario": user_query}, {"idUsuario": str(usuario_id)}]
    })
    
    artista_id = artista.get('idArtistaSQL') or artista.get('idArtista') or str(artista['_id']) if artista else usuario_id
    
    if request.method == 'POST':
        # Capturamos exactamente las variables del modal HTML
        titulo = request.POST.get('titulo')
        duracion = request.POST.get('duracion')
        # La variable de calidad se llama 'calidadAudio' en el HTML
        calidad = request.POST.get('calidadAudio', 'Estándar') 
        album_id = request.POST.get('album_id')
        
        try:
            # 1. Autocalcular el número de pista real
            num_pista = db.canciones.count_documents({
                "$or": [{"idAlbum": album_id}, {"idAlbum": int(album_id) if str(album_id).isdigit() else album_id}]
            }) + 1
            
            # -------------------------------------------------------------------
            # ⚠️ ESTRUCTURA CORREGIDA (Formato Plano para match con Dashboard)
            # -------------------------------------------------------------------
            nueva_cancion = {
                "titulo": titulo,
                "duracionSegundos": int(duracion) if duracion and duracion.isdigit() else 0, # Guardamos como duracionSegundos para los cálculos
                "calidadAudio": calidad,
                "numeroPista": num_pista,
                "idArtista": int(artista_id) if str(artista_id).isdigit() else str(artista_id),
                "idAlbum": int(album_id) if str(album_id).isdigit() else str(album_id)
            }
            
            db.canciones.insert_one(nueva_cancion)
            messages.success(request, f"¡La pista '{titulo}' se subió exitosamente!")
            return redirect('dashboard_artista')
            
        except Exception as e:
            messages.error(request, f"Error al subir canción: {e}")

    return redirect('dashboard_artista')
# ==========================================
# CRUD MONGODB: PLAYLISTS (MÓDULO COMPLETO)
# ==========================================

@verificar_rol(['Cliente', 'Admin'])
def crear_playlist_usuario(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        usuario_id = request.session.get('usuario_id')
        
        if not nombre or len(nombre) < 3:
            messages.error(request, "Error: El nombre de la playlist debe tener al menos 3 caracteres.")
            return redirect('dashboard_usuario')
            
        try:
            from datetime import datetime
            nueva_playlist = {
                "idUsuarioSQL": usuario_id,
                "nombre": nombre,
                "descripcion": "Playlist creada desde la nueva arquitectura NoSQL",
                "colaborativa": False,
                "fechaCreacion": datetime.now(),
                "canciones": [] 
            }
            
            db.playlists.insert_one(nueva_playlist)
            messages.success(request, f"Playlist '{nombre}' creada exitosamente en MongoDB 🍃")
        except Exception as e:
            messages.error(request, f"Error de validación en MongoDB: {str(e)}")
            
    return redirect('dashboard_usuario')


@verificar_rol(['Cliente', 'Admin'])
def obtener_detalles_playlist(request, id_playlist):
    try:
        # 1. Buscamos la playlist en MongoDB
        playlist_mongo = db.playlists.find_one({"_id": ObjectId(id_playlist)})
        if not playlist_mongo:
            return JsonResponse({'status': 'error', 'message': 'Playlist no encontrada en Mongo.'}, status=404)
        
        canciones_array = playlist_mongo.get('canciones', [])
        ids_guardadas = [c.get('idCancionSQL') for c in canciones_array]
        
        canciones_guardadas = []
        todas_canciones = []
        
        # 2. Reemplazo del SELECT SQL: Buscamos en db.canciones de Mongo
        catalogo = list(db.canciones.find({}, {"_id": 1, "idCancionSQL": 1, "titulo": 1}))
        
        for pista in catalogo:
            # Respaldo por si el idCancionSQL no existe en las nuevas canciones subidas
            pista_id = pista.get('idCancionSQL') or str(pista['_id'])
            pista_dict = {'id': pista_id, 'titulo': pista.get('titulo', 'Sin título')}
            
            todas_canciones.append(pista_dict)
            
            # Si el ID está en el array de la playlist, lo marcamos como guardado
            if pista_id in ids_guardadas or (isinstance(pista_id, int) and pista_id in ids_guardadas):
                canciones_guardadas.append(pista_dict)

        return JsonResponse({
            'status': 'success', 
            'id_playlist': str(id_playlist), 
            'guardadas': canciones_guardadas, 
            'disponibles': todas_canciones
        })
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@verificar_rol(['Cliente', 'Admin'])
def agregar_cancion_playlist(request, id_playlist, id_cancion):
    try:
        from datetime import datetime
        # Validación: Evitar duplicados
        playlist_actual = db.playlists.find_one({"_id": ObjectId(id_playlist)})
        if any(c.get("idCancionSQL") == int(id_cancion) for c in playlist_actual.get("canciones", [])):
            return JsonResponse({'status': 'error', 'message': 'Esta canción ya existe en la playlist.'}, status=400)

        # Operación UPDATE ($push a un arreglo en MongoDB)
        db.playlists.update_one(
            {"_id": ObjectId(id_playlist)},
            {"$push": {
                "canciones": {
                    "idCancionSQL": int(id_cancion),
                    "fechaAgregada": datetime.now() 
                }
            }}
        )
        return JsonResponse({'status': 'success', 'message': 'Pista agregada en MongoDB.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@verificar_rol(['Cliente', 'Admin'])
def eliminar_playlist_mongo(request, id_playlist):
    try:
        db.playlists.delete_one({"_id": ObjectId(id_playlist)})
        messages.success(request, "Playlist eliminada permanentemente de MongoDB.")
    except Exception as e:
        messages.error(request, f"Error al eliminar en MongoDB: {str(e)}")
    return redirect('dashboard_usuario')

def logout_view(request):
    # Limpiamos por completo la sesión del navegador
    request.session.flush()
    messages.success(request, "Sesión cerrada correctamente.")
    return redirect('login')