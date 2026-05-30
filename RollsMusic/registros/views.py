from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from datetime import date
# Se añade 'Rol' a las importaciones
from .models import Usuario, Discografica, Artista, Album, Cancion, Genero, PlanEntity, Rol
from django.db import connection
from django.db import DatabaseError

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
# CRUD: ARTISTAS (Corregido estructuralmente)
# ==========================================
@verificar_rol(['Admin'])
def listar_artistas(request):
    items = Artista.objects.all()
    return render(request, 'artistas/listar.html', {'items': items})

@verificar_rol(['Admin'])
def crear_artista(request):
    discograficas = Discografica.objects.all()
    
    if request.method == 'POST':
        nombre_artistico = request.POST.get('nombreArtistico')
        biografia = request.POST.get('biografia', '')
        pais = request.POST.get('pais', 'Desconocido') # Añadido según tu BD
        fecha_creacion = request.POST.get('fechaCreacion', date.today()) # Añadido según tu BD
        disco_id = request.POST.get('discografica')
        
        disco = get_object_or_404(Discografica, idDiscografica=disco_id)
        
        Artista.objects.create(
            nombreArtistico=nombre_artistico, 
            biografia=biografia, 
            pais=pais,
            fechaCreacion=fecha_creacion,
            imagen='default_artist.png',
            Discografica_idDiscografica=disco
        )
        return redirect('listar_artistas')
        
    return render(request, 'artistas/crear.html', {
        'discograficas': discograficas
    })

@verificar_rol(['Admin'])
def editar_artista(request, id):
    item = get_object_or_404(Artista, idArtista=id)
    discograficas = Discografica.objects.all()
    
    if request.method == 'POST':
        # CORRECCIÓN: Solo campos reales de la tabla Artista en SQL Server
        item.nombreArtistico = request.POST.get('nombreArtistico')
        item.pais = request.POST.get('pais', item.pais)
        item.biografia = request.POST.get('biografia')
        item.Discografica_idDiscografica = get_object_or_404(Discografica, idDiscografica=request.POST.get('discografica'))
        item.save()
        return redirect('listar_artistas')
        
    return render(request, 'artistas/editar.html', {'item': item, 'discograficas': discograficas})

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
    if request.method == 'POST':
        usuario.nombre = request.POST.get('nombre')
        usuario.apellido = request.POST.get('apellido')
        usuario.correo = request.POST.get('correo')
        usuario.estado = request.POST.get('estado')
        if request.POST.get('fechaNacimiento'):
            usuario.fechaNacimiento = request.POST.get('fechaNacimiento')
        usuario.save()
        return redirect('listar_usuarios') # Corregido
    return render(request, 'usuarios/editar.html', {'usuario': usuario})

@verificar_rol(['Admin'])
def eliminar_usuario(request, id):
    usuario = get_object_or_404(Usuario, idUsuario=id)
    if request.method == 'POST':
        try:
            usuario.delete()
            messages.success(request, "Usuario eliminado correctamente de la plataforma.")
        except Exception as e:
            # Si SQL Server frena el borrado por una restricción severa, te avisará en pantalla
            messages.error(request, f"No se pudo eliminar el usuario debido a dependencias activas en la base de datos.")
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
    if 'usuario_id' not in request.session or request.session.get('usuario_rol') not in ['Cliente', 'Admin']:
        return redirect('login')
        
    usuario_id = request.session['usuario_id']
    top_canciones = []
    recomendaciones = []
    
    # Valores por defecto si no tiene registro de suscripción aún
    plan_info = {'plan_nombre': 'Free', 'suscripcion_estado': 'Inactiva', 'idSuscripcion': None}
    
    with connection.cursor() as cursor:
        # 1. Consulta SQL para obtener el plan y estado de suscripción del usuario
        cursor.execute("""
            SELECT TOP 1 P.nombre, S.estado, S.idSuscripcion
            FROM Facturacion.Suscripcion S
            INNER JOIN Facturacion.PlanEntity P ON S.PlanEntity_idPlan = P.idPlan
            WHERE S.Usuario_idUsuario = %s
            ORDER BY CASE WHEN S.estado = 'Activa' THEN 1 ELSE 2 END, S.idSuscripcion DESC
        """, [usuario_id])
        row = cursor.fetchone()
        if row:
            plan_info = {
                'plan_nombre': row[0],
                'suscripcion_estado': row[1],
                'idSuscripcion': row[2]
            }

        # 2. Ejecutar Reporte: Top Canciones por Usuario
        cursor.execute("EXEC Reportes.sp_TopCancionesUsuario @idUsuario = %s", [usuario_id])
        top_canciones = dictfetchall(cursor)
        
        # 3. Ejecutar Reporte: Recomendaciones Personalizadas
        cursor.execute("EXEC Reportes.sp_RecomendacionesPersonalizadas @idUsuario = %s", [usuario_id])
        recomendaciones = dictfetchall(cursor)
        
    context = {
        'top_canciones': top_canciones,
        'recomendaciones': recommendations if 'recommendations' in locals() else recomendaciones,
        'plan_info': plan_info,
    }
    return render(request, 'dashboards/usuario.html', context)

@verificar_rol(['Artista', 'Admin'])
def dashboard_artista(request):
    if 'usuario_id' not in request.session or request.session.get('usuario_rol') not in ['Artista', 'Admin']:
        return redirect('login')
    
    usuario_nombre = request.session.get('usuario_nombre').split()[0]
    
    # NOTA TÉCNICA: Como en su BD no hay una FK directa de Usuario -> Artista para saber 
    # qué perfil le pertenece, buscaremos una coincidencia por nombre o cargaremos el primer artista a modo de Demo.
    artista = Artista.objects.filter(nombreArtistico__icontains=usuario_nombre).first()
    if not artista:
        artista = Artista.objects.first()

    total_regalias = 0
    minutos_cancion_demo = 0
    canciones_artista = []

    if artista:
        canciones_artista = Cancion.objects.filter(Album_idAlbum__Artista_idArtista=artista.idArtista)
        cancion_demo_id = canciones_artista.first().idCancion if canciones_artista.exists() else None

        # IMPLEMENTACIÓN DE FUNCIONES ESCALARES
        with connection.cursor() as cursor:
            # 1. Función Escalar: Total de regalías generadas por el artista
            cursor.execute("SELECT Facturacion.fn_TotalRegaliaArtista(%s)", [artista.idArtista])
            row = cursor.fetchone()
            total_regalias = row[0] if row and row[0] else 0
            
            # 2. Función Escalar: Minutos Reproducidos (usando la pista principal del artista)
            if cancion_demo_id:
                cursor.execute("SELECT Usuarios.fn_MinutosReproduccionCancion(%s)", [cancion_demo_id])
                row2 = cursor.fetchone()
                minutos_cancion_demo = row2[0] if row2 and row2[0] else 0

    context = {
        'artista': artista,
        'total_regalias': total_regalias,
        'canciones_artista': canciones_artista,
        'minutos_cancion_demo': minutos_cancion_demo,
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
            
        messages.success(request, "¡Transacción completada! Tu cuenta ha sido actualizada a Premium ✨")
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
            # 1. Obtener la duración de la canción para simular que se escuchó completa
            cursor.execute("SELECT duracion, titulo FROM Catalogo.Cancion WHERE idCancion = %s", [id_cancion])
            cancion = cursor.fetchone()
            
            if not cancion:
                messages.error(request, "La canción seleccionada no existe.")
                return redirect('dashboard_usuario')
                
            duracion_segundos = cancion[0]
            titulo_cancion = cancion[1]

            # 2. Inserción directa. Esto disparará automáticamente el TRIGGER de la BD
            cursor.execute("""
                INSERT INTO Usuarios.Reproduccion (fecha, duracion, Usuario_idUsuario, Cancion_idCancion)
                VALUES (GETDATE(), %s, %s, %s)
            """, [duracion_segundos, usuario_id, id_cancion])
            
            messages.success(request, f"▶️ Reproduciendo ahora: '{titulo_cancion}'. ¡Historial y métricas actualizados!")
            
        except DatabaseError as db_err:
            # Si el Trigger trg_ValidarReproduccion lanza un RAISERROR, caerá aquí
            messages.error(request, f"La base de datos rechazó la reproducción: {str(db_err)}")
        except Exception as e:
            messages.error(request, f"Error en el sistema: {str(e)}")
            
    return redirect('dashboard_usuario')


def logout_view(request):
    # Limpiamos por completo la sesión del navegador
    request.session.flush()
    messages.success(request, "Sesión cerrada correctamente.")
    return redirect('login')