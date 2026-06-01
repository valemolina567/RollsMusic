from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from datetime import date
# Se añade 'Rol' a las importaciones
from .models import Usuario, Discografica, Artista, Album, Cancion, Genero, PlanEntity, Rol
from django.db import connection
from django.db import DatabaseError
from functools import wraps
from django.http import JsonResponse

def verificar_rol(roles_permitidos):
    """Decorador para restringir el acceso a vistas según el rol de la sesión."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # 1. Validar si el usuario está autenticado en la sesión
            if 'usuario_id' not in request.session:
                messages.error(request, "Debes iniciar sesión para acceder a esta sección.")
                return redirect('login')
            
            # 2. Validar si su rol coincide con los permitidos
            rol_usuario = request.session.get('usuario_rol')
            if rol_usuario not in roles_permitidos:
                messages.error(request, f"Acceso denegado. Tu rol de '{rol_usuario}' no tiene permisos para esta acción.")
                
                # Redirección inteligente según su rol actual
                if rol_usuario == 'Artista':
                    return redirect('dashboard_artista')
                elif rol_usuario == 'Cliente':
                    return redirect('dashboard_usuario')
                else:
                    return redirect('login')
                    
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator    

@verificar_rol(['Admin'])
def listar_usuarios(request):
    # Si no existe la variable en sesión, lo mandamos directo al login
    if 'usuario_id' not in request.session:
        messages.error(request, "Debes iniciar sesión para acceder a esta sección.")
        return redirect('login')
        
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
    items = Artista.objects.all()
    return render(request, 'artistas/listar.html', {'items': items})

@verificar_rol(['Admin'])
def crear_artista(request):
    discograficas = Discografica.objects.all()
    generos = Genero.objects.all() # <-- 1. Recuperamos los géneros de la BD
    
    if request.method == 'POST':
        nombre_artistico = request.POST.get('nombreArtistico')
        biografia = request.POST.get('biografia', '')
        pais = request.POST.get('pais', 'Desconocido')
        fecha_creacion = request.POST.get('fechaCreacion') or date.today()
        disco_id = request.POST.get('discografica')
        id_usuario = request.POST.get('usuario')
        genero_form = request.POST.get('generoPrincipal') # <-- Capturamos el género seleccionado
        
        with connection.cursor() as cursor:
            try:
                # Localizar las columnas reales de tu base de datos
                cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'Catalogo' AND TABLE_NAME = 'Artista'")
                art_cols = [row[0] for row in cursor.fetchall()]
                col_art_usuario = 'Usuario_idUsuario' if 'Usuario_idUsuario' in art_cols else ('idUsuario' if 'idUsuario' in art_cols else ('Usuario_id' if 'Usuario_id' in art_cols else None))
                col_art_nombre = 'nombreArtistico' if 'nombreArtistico' in art_cols else ('nombre_artistico' if 'nombre_artistico' in art_cols else 'nombre')
                col_art_genero = 'genero' if 'genero' in art_cols else ('generoPrincipal' if 'generoPrincipal' in art_cols else None)
                
                cols = [col_art_nombre, 'pais', 'fechaCreacion', 'imagen', 'biografia', 'Discografica_idDiscografica']
                vals = [nombre_artistico, pais, fecha_creacion, 'default_artist.png', biografia, disco_id]
                placeholders = ["%s"] * len(cols)
                
                if col_art_usuario and id_usuario:
                    cols.append(col_art_usuario)
                    vals.append(int(id_usuario))
                    placeholders.append("%s")
                
                # Si la columna de género existe, agregamos el texto seleccionado a la inserción SQL
                if col_art_genero and genero_form:
                    cols.append(col_art_genero)
                    vals.append(genero_form)
                    placeholders.append("%s")
                    
                sql_insert = f"INSERT INTO Catalogo.Artista ({', '.join(cols)}) VALUES ({', '.join(placeholders)})"
                cursor.execute(sql_insert, vals)
                
                messages.success(request, f"Perfil artístico de '{nombre_artistico}' creado y vinculado correctamente.")
                return redirect('listar_artistas')
            except Exception as e:
                messages.error(request, f"Error de integridad en SQL Server: {str(e)}")
                
    usuarios_artistas = Usuario.objects.filter(Rol_idRol__nombre='Artista')
    if not usuarios_artistas.exists():
        usuarios_artistas = Usuario.objects.all()
        
    return render(request, 'artistas/crear.html', {
        'discograficas': discograficas,
        'usuarios_artistas': usuarios_artistas,
        'generos': generos # <-- 2. Enviamos los géneros al contexto de creación
    })

@verificar_rol(['Admin'])
def editar_artista(request, id):
    artista_obj = get_object_or_404(Artista, idArtista=id)
    discograficas = Discografica.objects.all()
    generos = Genero.objects.all() # <-- 1. Recuperamos los géneros de la BD también para la edición
    
    usuarios_artistas = Usuario.objects.filter(Rol_idRol__nombre='Artista')
    if not usuarios_artistas.exists():
        usuarios_artistas = Usuario.objects.all()

    artista_usuario_id = None
    genero_actual = ""
    
    with connection.cursor() as cursor:
        cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'Catalogo' AND TABLE_NAME = 'Artista'")
        art_cols = [row[0] for row in cursor.fetchall()]
        
        col_art_usuario = 'Usuario_idUsuario' if 'Usuario_idUsuario' in art_cols else ('idUsuario' if 'idUsuario' in art_cols else ('Usuario_id' if 'Usuario_id' in art_cols else None))
        col_art_genero = 'genero' if 'genero' in art_cols else ('generoPrincipal' if 'generoPrincipal' in art_cols else None)
        
        query_extra = "SELECT idArtista"
        if col_art_usuario: query_extra += f", {col_art_usuario}"
        if col_art_genero: query_extra += f", {col_art_genero}"
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

    if request.method == 'POST':
        nombre_form = request.POST.get('nombreArtistico')
        biografia_form = request.POST.get('biografia', '')
        pais_form = request.POST.get('pais', 'Desconocido')
        disco_id = request.POST.get('discografica')
        id_usuario = request.POST.get('usuario')
        genero_form = request.POST.get('generoPrincipal') # <-- Ajustado para mantener congruencia de nombres

        with connection.cursor() as cursor:
            try:
                col_art_nombre = 'nombre' if 'nombre' in art_cols else 'nombreArtistico'
                
                sql_update = f"UPDATE Catalogo.Artista SET {col_art_nombre} = %s, biografia = %s, Discografica_idDiscografica = %s"
                params = [nombre_form, biografia_form, disco_id]
                
                if col_art_usuario:
                    sql_update += f", {col_art_usuario} = %s"
                    params.append(int(id_usuario) if id_usuario else None)
                if col_art_genero:
                    sql_update += f", {col_art_genero} = %s"
                    params.append(genero_form)
                    
                sql_update += " WHERE idArtista = %s"
                params.append(id)
                
                cursor.execute(sql_update, params)
                messages.success(request, f"✨ Perfil de '{nombre_form}' actualizado correctamente.")
                return redirect('listar_artistas')
            except Exception as e:
                messages.error(request, f"Error al guardar en SQL Server: {str(e)}")
    
    return render(request, 'artistas/editar.html', {
        'artista': artista_obj,
        'artista_usuario_id': artista_usuario_id,
        'genero_actual': genero_actual,
        'discograficas': discograficas,
        'usuarios_artistas': usuarios_artistas,
        'generos': generos # <-- 2. Enviamos los géneros al contexto de edición
    })

@verificar_rol(['Admin'])
def eliminar_artista(request, id):
    item = get_object_or_404(Artista, idArtista=id)
    if request.method == 'POST':
        item.delete()
        return redirect('listar_artistas')

# ==========================================
# CRUD: ALBUMES
# ==========================================
@verificar_rol(['Admin'])
def listar_albumes(request):
    items = Album.objects.all()
    return render(request, 'albumes/listar.html', {'items': items})

@verificar_rol(['Admin'])
def crear_album(request):
    artistas = Artista.objects.all()
    if request.method == 'POST':
        titulo = request.POST.get('titulo')
        fecha = request.POST.get('fechaLanzamiento')
        artista_id = request.POST.get('artista')
        
        artista = get_object_or_404(Artista, idArtista=artista_id)
        Album.objects.create(titulo=titulo, fechaLanzamiento=fecha, Artista_idArtista=artista, imagen='default_album.png')
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
        item.save()
        return redirect('listar_albumes')
    return render(request, 'albumes/editar.html', {'item': item, 'artistas': artistas})

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
    query = request.GET.get('q', '').strip() # Captura lo que el usuario escribió
    
    if query:
        # Filtra si el título contiene la palabra
        items = Cancion.objects.filter(titulo__icontains=query)
    else:
        # Si no hay búsqueda, trae todo el inventario
        items = Cancion.objects.all()
        
    return render(request, 'canciones/listar.html', {'items': items})

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

        album = get_object_or_404(Album, idAlbum=album_id)
        Cancion.objects.create(
            titulo=titulo, duracion=duracion, numeroPista=pista,
            fechaLanzamiento=fecha, calidadAudio=calidad, Album_idAlbum=album, imagen='default_track.png'
        )
        return redirect('listar_canciones')
    return render(request, 'canciones/crear.html', {'albumes': albumes})

@verificar_rol(['Admin'])
def editar_cancion(request, id):
    item = get_object_or_404(Cancion, idCancion=id)
    albumes = Album.objects.all()
    if request.method == 'POST':
        item.titulo = request.POST.get('titulo')
        item.duracion = request.POST.get('duracion')
        item.numeroPista = request.POST.get('numeroPista')
        item.fechaLanzamiento = request.POST.get('fechaLanzamiento')
        item.calidadAudio = request.POST.get('calidadAudio')
        item.Album_idAlbum = get_object_or_404(Album, idAlbum=request.POST.get('album'))
        item.save()
        return redirect('listar_canciones')
    return render(request, 'canciones/editar.html', {'item': item, 'albumes': albumes})

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
def listar_usuarios(request):
    usuarios = Usuario.objects.all()
    return render(request, 'usuarios/listar.html', {'usuarios': usuarios})

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
# SISTEMA DE AUTENTICACIÓN (LOGIN / LOGOUT)
# ==========================================

def login_view(request):
    if request.method == 'POST':
        correo = request.POST.get('correo', '').strip()
        contrasenia = request.POST.get('contrasenia', '').strip()

        if not correo or not contrasenia:
            messages.error(request, "Por favor, completa todos los campos.")
            return render(request, 'auth/login.html')

        try:
            usuario = Usuario.objects.get(correo=correo)
            
            if usuario.contrasenia == contrasenia:
                if usuario.estado != 'Activo':
                    messages.error(request, f"Tu cuenta se encuentra: {usuario.estado}. Contacta al administrador.")
                    return render(request, 'auth/login.html')
                
                # Variables de sesión
                request.session['usuario_id'] = usuario.idUsuario
                request.session['usuario_nombre'] = f"{usuario.nombre} {usuario.apellido}"
                request.session['usuario_rol'] = usuario.Rol_idRol.nombre
                
                # REDIRECCIÓN DINÁMICA POR ROL
                if usuario.Rol_idRol.nombre == 'Admin':
                    return redirect('index')
                elif usuario.Rol_idRol.nombre == 'Artista':
                    return redirect('dashboard_artista')
                else:
                    return redirect('dashboard_usuario')
            else:
                messages.error(request, "Contraseña incorrecta.")
        except Usuario.DoesNotExist:
            messages.error(request, "El correo electrónico no está registrado.")

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

        # Asignamos una imagen por defecto, ya que es obligatoria en la base de datos
        imagen_default = 'usuario_nuevo.png'
        # El rol por defecto será 2 (Cliente)
        rol_cliente = 2 

        # 2. Ejecutar el Procedimiento Almacenado
        with connection.cursor() as cursor:
            try:
                cursor.execute("""
                    EXEC Usuarios.sp_RegistrarUsuario 
                        @nombre = %s,
                        @apellido = %s,
                        @correo = %s,
                        @contrasenia = %s,
                        @imagen = %s,
                        @fechaNacimiento = %s,
                        @Rol_idRol = %s
                """, [nombre, apellido, correo, contrasenia, imagen_default, fecha_nacimiento, rol_cliente])
                
                # El SP retorna: SELECT 1 AS Estado, 'Mensaje' AS Mensaje
                resultado = cursor.fetchone()
                
                if resultado and resultado[0] == 1:
                    # Registro exitoso
                    messages.success(request, "¡Cuenta creada con éxito! Ahora puedes iniciar sesión.")
                    return redirect('login')
                else:
                    # Error controlado desde el SP (ej. correo duplicado)
                    error_msg = resultado[1] if resultado else "Error desconocido al registrar."
                    messages.error(request, f"Error: {error_msg}")
                    
            except Exception as e:
                # Error de ejecución o conexión
                messages.error(request, f"Ocurrió un error en el servidor: {str(e)}")

    # Si es método GET, solo mostramos el formulario vacío
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
    
    with connection.cursor() as cursor:
        try:
            # Lista "Lo que más escuchas" siempre actualizada
            cursor.execute("EXEC Reportes.sp_TopCancionesUsuario %s", [usuario_id])
            columns_top = [col[0] for col in cursor.description]
            top_canciones = [dict(zip(columns_top, row)) for row in cursor.fetchall()]
            
            # Localizar y mapear la tabla de playlists del cliente de forma dinámica
            cursor.execute("SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE '%Playlist%'")
            p_table = cursor.fetchone()
            if p_table:
                schema_p, name_p = p_table[0], p_table[1]
                cursor.execute(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = '{schema_p}' AND TABLE_NAME = '{name_p}'")
                p_cols = [r[0] for r in cursor.fetchall()]
                col_user = 'Usuario_idUsuario' if 'Usuario_idUsuario' in p_cols else ('idUsuario' if 'idUsuario' in p_cols else 'Usuario_id')
                col_nombre = 'nombre' if 'nombre' in p_cols else ('titulo' if 'titulo' in p_cols else p_cols[1])
                col_id = 'idPlaylist' if 'idPlaylist' in p_cols else ('id' if 'id' in p_cols else p_cols[0])
                
                cursor.execute(f"SELECT {col_id}, {col_nombre} FROM {schema_p}.{name_p} WHERE {col_user} = %s", [usuario_id])
                playlists_usuario = cursor.fetchall()
        except Exception:
            pass

    # Memoria de Sesión Completa para congelar la lista "Especialmente para ti"
    recomendaciones = request.session.get('recomendaciones_cache')
    if not recomendaciones:
        recomendaciones = []
        with connection.cursor() as cursor:
            try:
                cursor.execute("EXEC Reportes.sp_RecomendacionesPersonalizadas %s", [usuario_id])
                columns_rec = [col[0] for col in cursor.description]
                raw_recs = [dict(zip(columns_rec, row)) for row in cursor.fetchall()]
                
                for r in raw_recs:
                    id_can = r.get('idCancion') or r.get('id_cancion') or r.get('id')
                    tit_can = r.get('Cancion') or r.get('titulo')
                    art_can = r.get('Artista') or r.get('nombreArtistico') or r.get('nombre')
                    alb_can = r.get('Album') or r.get('album_titulo') or 'Sencillo'
                    
                    if id_can:
                        recomendaciones.append({
                            'idCancion': id_can, 'Cancion': tit_can, 'Artista': art_can, 'Album': alb_can
                        })
                request.session['recomendaciones_cache'] = recomendaciones
            except Exception:
                recomendaciones = []

    plan_info = {'plan_nombre': 'Free', 'suscripcion_estado': 'Activa'}  # Plan base por defecto si no tiene registro
    with connection.cursor() as cursor:
        try:
            cursor.execute("""
                SELECT TOP 1 P.nombre, S.estado 
                FROM Facturacion.Suscripcion S
                INNER JOIN Facturacion.PlanEntity P ON S.PlanEntity_idPlan = P.idPlan
                WHERE S.Usuario_idUsuario = %s AND S.estado = 'Activa'
                ORDER BY S.idSuscripcion DESC
            """, [usuario_id])
            plan_row = cursor.fetchone()
            if plan_row:
                plan_info = {'plan_nombre': plan_row[0], 'suscripcion_estado': plan_row[1]}
        except Exception:
            pass

    context = {
        'top_canciones': top_canciones,
        'recomendaciones': recomendaciones,
        'plan_info': plan_info,  # <-- Enviamos el plan real extraído de la BD
        'playlists': playlists_usuario,
        'auto_open_playlist_id': auto_open_id,
    }
    return render(request, 'dashboards/usuario.html', context)  

@verificar_rol(['Artista', 'Admin'])
def dashboard_artista(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return redirect('login')
        
    artista = None
    total_regalias = 0
    minutos_cancion_demo = 0
    canciones_artista = []
    albums_artista = []
    art_cols = []  
    
    with connection.cursor() as cursor:
        try:
            # 1. Inspeccionar columnas para blindaje de lógicas dinámicas
            cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'Catalogo' AND TABLE_NAME = 'Artista'")
            art_cols = [row[0] for row in cursor.fetchall()]
            
            col_art_nombre = 'nombreArtistico' if 'nombreArtistico' in art_cols else ('nombre_artistico' if 'nombre_artistico' in art_cols else 'nombre')
            col_art_usuario = 'Usuario_idUsuario' if 'Usuario_idUsuario' in art_cols else ('idUsuario' if 'idUsuario' in art_cols else ('Usuario_id' if 'Usuario_id' in art_cols else 'idArtista'))
            
            cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'Catalogo' AND TABLE_NAME = 'Album'")
            alb_cols = [row[0] for row in cursor.fetchall()]
            col_alb_artista = 'Artista_idArtista' if 'Artista_idArtista' in alb_cols else ('idArtista' if 'idArtista' in alb_cols else 'Artista_id')
            
            cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'Catalogo' AND TABLE_NAME = 'Cancion'")
            can_cols = [row[0] for row in cursor.fetchall()]
            col_can_album = 'Album_idAlbum' if 'Album_idAlbum' in can_cols else ('idAlbum' if 'idAlbum' in can_cols else 'Album_id')

            # --- EJECUCIÓN CON ENLACE DIRECTO ---
            query_artista = f"SELECT idArtista, {col_art_nombre} FROM Catalogo.Artista WHERE {col_art_usuario} = %s"
            cursor.execute(query_artista, [usuario_id])
            artista_row = cursor.fetchone()
            
            if artista_row:
                id_artista = artista_row[0]
                artista = {'idArtista': id_artista, 'nombreArtistico': artista_row[1]}
                
                cursor.execute("SELECT Facturacion.fn_TotalRegaliaArtista(%s)", [id_artista])
                regalias_row = cursor.fetchone()
                total_regalias = regalias_row[0] if regalias_row and regalias_row[0] is not None else 0
                
                cursor.execute(f"""
                    SELECT TOP 1 Usuarios.fn_MinutosReproduccionCancion(idCancion)
                    FROM Catalogo.Cancion 
                    WHERE {col_can_album} IN (SELECT idAlbum FROM Catalogo.Album WHERE {col_alb_artista} = %s)
                """, [id_artista])
                minutos_row = cursor.fetchone()
                minutos_cancion_demo = minutos_row[0] if minutos_row and minutos_row[0] is not None else 0
                
                cursor.execute(f"""
                    SELECT C.titulo, C.duracion, C.calidadAudio, A.titulo AS album_titulo 
                    FROM Catalogo.Cancion C
                    INNER JOIN Catalogo.Album A ON C.{col_can_album} = A.idAlbum
                    WHERE A.{col_alb_artista} = %s
                """, [id_artista])
                raw_canciones = cursor.fetchall()
                
                canciones_artista = [
                    {
                        'titulo': r[0],
                        'duracion': r[1],
                        'calidadAudio': r[2],
                        'Album_idAlbum': {'titulo': r[3]}
                    } for r in raw_canciones
                ]
                
                cursor.execute(f"SELECT idAlbum, titulo FROM Catalogo.Album WHERE {col_alb_artista} = %s", [id_artista])
                albums_artista = cursor.fetchall()
                
        except Exception as e:
            messages.error(request, f"Error al interactuar con la Base de Datos: {str(e)}")

    context = {
        'artista': artista,
        'total_regalias': total_regalias,
        'minutos_cancion_demo': minutos_cancion_demo,
        'canciones_artista': canciones_artista,
        'albums_artista': albums_artista,
        'columnas_encontradas': art_cols,  # <-- Enviado para activar el panel de diagnóstico
    }
    return render(request, 'dashboards/artista.html', context)

@verificar_rol(['Cliente', 'Admin'])
def procesar_pago(request):
    if 'usuario_id' not in request.session:
        return redirect('login')
        
    usuario_id = request.session['usuario_id']
    
    if request.method == 'POST':
        metodo = request.POST.get('metodo') # 'PayPal', 'Tarjeta' o 'Transferencia'
        monto = 9.99  # Precio establecido para el plan Premium
        
        with connection.cursor() as cursor:
            # 1. Validar si el usuario ya cuenta con un registro de suscripción Premium (Plan 2)
            cursor.execute("""
                SELECT idSuscripcion FROM Facturacion.Suscripcion 
                WHERE Usuario_idUsuario = %s AND PlanEntity_idPlan = 2
            """, [usuario_id])
            row = cursor.fetchone()
            
            if row:
                id_suscripcion = row[0]
                cursor.execute("UPDATE Facturacion.Suscripcion SET estado = 'Activa' WHERE idSuscripcion = %s", [id_suscripcion])
            else:
                # Crear una nueva suscripción Premium activa por 30 días
                cursor.execute("""
                    INSERT INTO Facturacion.Suscripcion (fechaInicio, fechaFin, estado, Usuario_idUsuario, PlanEntity_idPlan)
                    VALUES (GETDATE(), DATEADD(day, 30, GETDATE()), 'Activa', %s, 2)
                """, [usuario_id])
                cursor.execute("SELECT @@IDENTITY")
                id_suscripcion = cursor.fetchone()[0]
            
            # 2. CONSUMO DE OBJETO PROGRAMABLE: Registrar el Pago ejecutando el SP
            cursor.execute("""
                EXEC Facturacion.sp_RegistrarPago 
                    @monto = %s, 
                    @metodo = %s, 
                    @idSuscripcion = %s
            """, [monto, metodo, id_suscripcion])
            
        messages.success(request, "¡Transacción completada! Tu cuenta ha sido actualizada a Premium")
        return redirect('dashboard_usuario')
        
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
    usuario_id = request.session['usuario_id']
    with connection.cursor() as cursor:
        try:
            cursor.execute("SELECT duracion, titulo FROM Catalogo.Cancion WHERE idCancion = %s", [id_cancion])
            cancion = cursor.fetchone()
            
            if not cancion:
                return JsonResponse({'status': 'error', 'message': 'La canción no existe.'}, status=404)
                
            duracion_segundos = cancion[0]
            titulo_cancion = cancion[1]

            # Inserción asíncrona que despierta tu disparador automático (Trigger de BD)
            cursor.execute("""
                INSERT INTO Usuarios.Reproduccion 
                (fechaHora, dispositivo, pais, duracionEscuchada, completada, Usuario_idUsuario, Cancion_idCancion)
                VALUES 
                (GETDATE(), 'Navegador Web', 'Ecuador', %s, 1, %s, %s)
            """, [duracion_segundos, usuario_id, id_cancion])
            
            return JsonResponse({
                'status': 'success', 'idCancion': id_cancion, 'titulo': titulo_cancion, 'duracion': duracion_segundos
            })
        except DatabaseError as db_err:
            return JsonResponse({'status': 'error', 'message': f'Filtro de BD: {str(db_err)}'}, status=400)
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)

@verificar_rol(['Artista', 'Admin'])
def crear_album_artista(request):
    if request.method == 'POST':
        titulo = request.POST.get('titulo', '').strip()
        fecha_lanzamiento = request.POST.get('fecha_lanzamiento', '').strip()
        usuario_id = request.session['usuario_id']
        
        with connection.cursor() as cursor:
            try:
                # Resolver columnas dinámicamente para el insert
                cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'Catalogo' AND TABLE_NAME = 'Artista'")
                art_cols = [row[0] for row in cursor.fetchall()]
                col_art_usuario = 'Usuario_idUsuario' if 'Usuario_idUsuario' in art_cols else ('idUsuario' if 'idUsuario' in art_cols else ('Usuario_id' if 'Usuario_id' in art_cols else 'idArtista'))
                
                cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'Catalogo' AND TABLE_NAME = 'Album'")
                alb_cols = [row[0] for row in cursor.fetchall()]
                col_alb_artista = 'Artista_idArtista' if 'Artista_idArtista' in alb_cols else ('idArtista' if 'idArtista' in alb_cols else 'Artista_id')

                cursor.execute(f"SELECT idArtista FROM Catalogo.Artista WHERE {col_art_usuario} = %s", [usuario_id])
                artista_row = cursor.fetchone()
                
                if artista_row:
                    id_artista = artista_row[0]
                    cursor.execute(f"""
                        INSERT INTO Catalogo.Album (titulo, fechaLanzamiento, imagen, {col_alb_artista})
                        VALUES (%s, %s, 'album_default.png', %s)
                    """, [titulo, fecha_lanzamiento, id_artista])
                    messages.success(request, f"💿 El álbum '{titulo}' ha sido creado correctamente.")
            except Exception as e:
                messages.error(request, f"Error al crear álbum: {str(e)}")
                
    return redirect('dashboard_artista')


@verificar_rol(['Artista', 'Admin'])
def subir_cancion_artista(request):
    if request.method == 'POST':
        titulo = request.POST.get('titulo', '').strip()
        duracion = request.POST.get('duracion', '').strip()
        calidad = request.POST.get('calidadAudio', 'Alta')
        album_id = request.POST.get('album_id')
        
        with connection.cursor() as cursor:
            try:
                # 1. Resolver columna de relación en Canción de forma dinámica
                cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'Catalogo' AND TABLE_NAME = 'Cancion'")
                can_cols = [row[0] for row in cursor.fetchall()]
                col_can_album = 'Album_idAlbum' if 'Album_idAlbum' in can_cols else ('idAlbum' if 'idAlbum' in can_cols else 'Album_id')

                # 2. CALCULAR NÚMERO DE PISTA AUTOMÁTICAMENTE
                cursor.execute(f"SELECT COUNT(*) FROM Catalogo.Cancion WHERE {col_can_album} = %s", [album_id])
                count_row = cursor.fetchone()
                numero_pista = (count_row[0] + 1) if count_row else 1

                # 3. HEREDAR LA FECHA DE LANZAMIENTO DEL ÁLBUM
                cursor.execute("SELECT fechaLanzamiento FROM Catalogo.Album WHERE idAlbum = %s", [album_id])
                album_row = cursor.fetchone()
                
                # 4. INSERT FINAL CORREGIDO: Se añade 'imagen', 'numeroPista' y 'fechaLanzamiento'
                if album_row and album_row[0]:
                    fecha_lanzamiento = album_row[0]
                    cursor.execute(f"""
                        INSERT INTO Catalogo.Cancion (titulo, duracion, calidadAudio, imagen, numeroPista, fechaLanzamiento, {col_can_album})
                        VALUES (%s, %s, %s, 'track_default.png', %s, %s, %s)
                    """, [titulo, duracion, calidad, numero_pista, fecha_lanzamiento, album_id])
                else:
                    # Plan B: Si el álbum no tiene fecha por algún motivo, usamos la fecha de hoy mediante SQL
                    cursor.execute(f"""
                        INSERT INTO Catalogo.Cancion (titulo, duracion, calidadAudio, imagen, numeroPista, fechaLanzamiento, {col_can_album})
                        VALUES (%s, %s, %s, 'track_default.png', %s, GETDATE(), %s)
                    """, [titulo, duracion, calidad, numero_pista, album_id])
                
                messages.success(request, f"🎵 La canción '{titulo}' se ha subido como la pista N° {numero_pista} del álbum.")
            except Exception as e:
                messages.error(request, f"Error al subir canción: {str(e)}")
                
    return redirect('dashboard_artista')

@verificar_rol(['Cliente', 'Admin'])
def crear_playlist_usuario(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        usuario_id = request.session['usuario_id']
        
        if not nombre:
            messages.error(request, "El nombre de la playlist no puede estar vacío.")
            return redirect('dashboard_usuario')
            
        with connection.cursor() as cursor:
            try:
                cursor.execute("SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE '%Playlist%'")
                p_table = cursor.fetchone()
                
                if p_table:
                    schema_p, name_p = p_table[0], p_table[1]
                    cursor.execute(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = '{schema_p}' AND TABLE_NAME = '{name_p}'")
                    p_cols = [r[0] for r in cursor.fetchall()]
                    
                    col_user = 'Usuario_idUsuario' if 'Usuario_idUsuario' in p_cols else ('idUsuario' if 'idUsuario' in p_cols else 'Usuario_id')
                    col_nombre = 'nombre' if 'nombre' in p_cols else ('titulo' if 'titulo' in p_cols else p_cols[1])
                    col_fecha = 'fechaCreacion' if 'fechaCreacion' in p_cols else ('fecha' if 'fecha' in p_cols else None)
                    col_desc = 'descripcion' if 'descripcion' in p_cols else ('description' if 'description' in p_cols else None)
                    col_colab = 'colaborativa' if 'colaborativa' in p_cols else ('colaborativo' if 'colaborativo' in p_cols else None)
                    col_id = 'idPlaylist' if 'idPlaylist' in p_cols else ('id' if 'id' in p_cols else p_cols[0])
                    
                    cols, vals, placeholders = [col_nombre, col_user], [nombre, usuario_id], ["%s", "%s"]
                    
                    if col_desc:
                        cols.append(col_desc); vals.append('Playlist personalizada.'); placeholders.append("%s")
                    if col_colab:
                        cols.append(col_colab); vals.append(0); placeholders.append("%s")
                    
                    sql_cols = ", ".join(cols) + (f", {col_fecha}" if col_fecha else "")
                    sql_vals = ", ".join(placeholders) + (", GETDATE()" if col_fecha else "")
                    
                    cursor.execute(f"INSERT INTO {schema_p}.{name_p} ({sql_cols}) VALUES ({sql_vals})", vals)
                    
                    # Captura del ID para activar el auto-open inmediato en el HTML
                    cursor.execute(f"SELECT MAX({col_id}) FROM {schema_p}.{name_p} WHERE {col_user} = %s", [usuario_id])
                    new_id = cursor.fetchone()
                    if new_id:
                        request.session['auto_open_playlist_id'] = new_id[0]
                        
                    messages.success(request, f"Playlist '{nombre}' creada")
                else:
                    messages.error(request, "No se localizó la tabla de Playlists.")
            except Exception as e:
                messages.error(request, f"Fallo al registrar la playlist: {str(e)}")
                
    return redirect('dashboard_usuario')

@verificar_rol(['Cliente', 'Admin'])
def obtener_detalles_playlist(request, id_playlist):
    with connection.cursor() as cursor:
        try:
            # Encontrar de forma segura la tabla intermedia de mapeo Playlist ⇄ Canción
            cursor.execute("""
                SELECT TABLE_SCHEMA, TABLE_NAME FROM (
                    SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE COLUMN_NAME LIKE '%Playlist%'
                    INTERSECT
                    SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE COLUMN_NAME LIKE '%Cancion%'
                ) AS Bridge WHERE TABLE_NAME NOT LIKE 'Playlist'
            """)
            bridge_table = cursor.fetchone()
            if not bridge_table:
                return JsonResponse({'status': 'error', 'message': 'Falta la tabla intermedia de relación.'}, status=404)
                
            schema_b, name_b = bridge_table[0], bridge_table[1]
            cursor.execute(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = '{schema_b}' AND TABLE_NAME = '{name_b}'")
            b_cols = [r[0] for r in cursor.fetchall()]
            col_b_playlist = 'Playlist_idPlaylist' if 'Playlist_idPlaylist' in b_cols else ('idPlaylist' if 'idPlaylist' in b_cols else [c for c in b_cols if 'Playlist' in c][0])
            col_b_cancion = 'Cancion_idCancion' if 'Cancion_idCancion' in b_cols else ('idCancion' if 'idCancion' in b_cols else [c for c in b_cols if 'Cancion' in c][0])

            cursor.execute("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = 'Catalogo' AND TABLE_NAME = 'Cancion'")
            c_cols = [r[0] for r in cursor.fetchall()]
            col_c_id = 'idCancion' if 'idCancion' in c_cols else 'id'

            # A. Canciones actuales dentro de la playlist seleccionada
            cursor.execute(f"""
                SELECT C.{col_c_id}, C.titulo FROM Catalogo.Cancion C
                INNER JOIN {schema_b}.{name_b} B ON C.{col_c_id} = B.{col_b_cancion}
                WHERE B.{col_b_playlist} = %s
            """, [id_playlist])
            canciones_guardadas = [{'id': r[0], 'titulo': r[1]} for r in cursor.fetchall()]

            # B. Catálogo global total disponible para adición (+)
            cursor.execute(f"SELECT {col_c_id}, titulo FROM Catalogo.Cancion")
            todas_canciones = [{'id': r[0], 'titulo': r[1]} for r in cursor.fetchall()]

            return JsonResponse({
                'status': 'success', 'id_playlist': id_playlist, 'guardadas': canciones_guardadas, 'disponibles': todas_canciones
            })
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@verificar_rol(['Cliente', 'Admin'])
def agregar_cancion_playlist(request, id_playlist, id_cancion):
    with connection.cursor() as cursor:
        try:
            cursor.execute("""
                SELECT TABLE_SCHEMA, TABLE_NAME FROM (
                    SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE COLUMN_NAME LIKE '%Playlist%'
                    INTERSECT
                    SELECT TABLE_SCHEMA, TABLE_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE COLUMN_NAME LIKE '%Cancion%'
                ) AS Bridge WHERE TABLE_NAME NOT LIKE 'Playlist'
            """)
            bridge_table = cursor.fetchone()
            schema_b, name_b = bridge_table[0], bridge_table[1]
            
            cursor.execute(f"SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = '{schema_b}' AND TABLE_NAME = '{name_b}'")
            b_cols = [r[0] for r in cursor.fetchall()]
            col_b_playlist = 'Playlist_idPlaylist' if 'Playlist_idPlaylist' in b_cols else ('idPlaylist' if 'idPlaylist' in b_cols else [c for c in b_cols if 'Playlist' in c][0])
            col_b_cancion = 'Cancion_idCancion' if 'Cancion_idCancion' in b_cols else ('idCancion' if 'idCancion' in b_cols else [c for c in b_cols if 'Cancion' in c][0])

            # CORRECCIÓN: Detectar dinámicamente columnas de auditoría temporal (fechaAgregada)
            col_b_fecha = 'fechaAgregada' if 'fechaAgregada' in b_cols else ('fecha_agregada' if 'fecha_agregada' in b_cols else ('fecha' if 'fecha' in b_cols else None))

            if col_b_fecha:
                # Si la columna existe, le mandamos la marca de tiempo de SQL Server
                cursor.execute(f"""
                    INSERT INTO {schema_b}.{name_b} ({col_b_playlist}, {col_b_cancion}, {col_b_fecha}) 
                    VALUES (%s, %s, GETDATE())
                """, [id_playlist, id_cancion])
            else:
                cursor.execute(f"INSERT INTO {schema_b}.{name_b} ({col_b_playlist}, {col_b_cancion}) VALUES (%s, %s)", [id_playlist, id_cancion])
                
            return JsonResponse({'status': 'success', 'message': 'Pista vinculada con éxito.'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': f'Fallo de relación: {str(e)}'}, status=400)

def logout_view(request):
    # Limpiamos por completo la sesión del navegador
    request.session.flush()
    messages.success(request, "Sesión cerrada correctamente.")
    return redirect('login')