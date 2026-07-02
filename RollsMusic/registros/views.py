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

# ==========================================
# CRUD: USUARIOS - MONGODB
# ==========================================

@verificar_rol(['Admin'])
def listar_usuarios(request):
    query = request.GET.get('q', '').strip()
    
    # 1. Filtro de búsqueda NoSQL (Reemplaza a Q() de Django)
    filtro = {}
    if query:
        filtro = {
            "$or": [
                {"nombre": {"$regex": query, "$options": "i"}},
                {"apellido": {"$regex": query, "$options": "i"}}
            ]
        }
        
    # 2. Consultamos directamente a la colección db.usuarios
    usuarios_mongo = list(db.usuarios.find(filtro))
    
    # 3. Preparamos el diccionario para que el HTML no se rompa
    for u in usuarios_mongo:
        # Extraemos el ID como string para pasarlo a los botones de Editar/Eliminar
        u['id_mongo'] = str(u['_id'])
        # Conservamos el ID visual de SQL si existe, sino usamos parte del Object ID
        u['idUsuario'] = u.get('idUsuarioSQL') or str(u['_id'])[-6:].upper()
        # Valores por defecto para evitar errores en vista
        u['nombre'] = u.get('nombre', 'Sin nombre')
        u['apellido'] = u.get('apellido', '')
        u['correo'] = u.get('correo', 'Sin correo')
        u['estado'] = u.get('estado', 'Inactivo')
        u['rol_nombre'] = u.get('rol', 'Cliente') # Antes era u.Rol_idRol.nombre
        
    return render(request, 'usuarios/listar.html', {'usuarios': usuarios_mongo})

@verificar_rol(['Admin'])
def crear_usuario(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        apellido = request.POST.get('apellido', '').strip()
        correo = request.POST.get('correo', '').strip()
        fecha_nacimiento = request.POST.get('fechaNacimiento', '').strip()
        contrasenia = request.POST.get('contrasenia', '').strip()
        # Obtenemos el texto directo del rol en lugar de un ID relacional
        rol = request.POST.get('rol', 'Cliente') 

        # Validación rápida de correo duplicado en MongoDB
        if db.usuarios.find_one({"correo": correo}):
            messages.error(request, "Error: Este correo ya se encuentra registrado.")
            return redirect('crear_usuario')

        # Documento BSON para insertar
        nuevo_usuario = {
            "nombre": nombre,
            "apellido": apellido,
            "correo": correo,
            "contrasenia": contrasenia,
            "fechaNacimiento": fecha_nacimiento,
            "fechaRegistro": datetime.now(),
            "estado": "Activo",
            "imagen": "default.png",
            "rol": rol,
            "suscripcion": {"plan": "Free", "estado": "Activa"}
        }
        
        db.usuarios.insert_one(nuevo_usuario)
        messages.success(request, f"Usuario {nombre} {apellido} creado correctamente en MongoDB.")
        return redirect('listar_usuarios')
    
    # Lista estática de roles para cargar en el <select>
    roles = [{'nombre': 'Administrador'}, {'nombre': 'Artista'}, {'nombre': 'Cliente'}]
    return render(request, 'usuarios/crear.html', {'roles': roles})

@verificar_rol(['Admin'])
def editar_usuario(request, id):
    # Soporta tanto IDs de MongoDB como los viejos de SQL
    filtro = {"_id": ObjectId(id)} if len(str(id)) == 24 else {"idUsuarioSQL": int(id)}
    usuario = db.usuarios.find_one(filtro)
    
    if request.method == 'POST':
        db.usuarios.update_one(filtro, {
            "$set": {
                "nombre": request.POST.get('nombre', '').strip(),
                "apellido": request.POST.get('apellido', '').strip(),
                "correo": request.POST.get('correo', '').strip(),
                "estado": request.POST.get('estado', '').strip(),
                "rol": request.POST.get('rol', usuario.get('rol')),
                "fechaNacimiento": request.POST.get('fechaNacimiento', usuario.get('fechaNacimiento'))
            }
        })
        messages.success(request, "El perfil ha sido actualizado exitosamente en MongoDB.")
        return redirect('listar_usuarios')
        
    roles = [{'nombre': 'Administrador'}, {'nombre': 'Artista'}, {'nombre': 'Cliente'}]
    usuario['idUsuario'] = str(usuario['_id']) # Requerido para la url del action del formulario
    usuario['rol_nombre'] = usuario.get('rol')
    
    return render(request, 'usuarios/editar.html', {'usuario': usuario, 'roles': roles})

@verificar_rol(['Admin'])
def eliminar_usuario(request, id):
    try:
        filtro = {"_id": ObjectId(id)} if len(str(id)) == 24 else {"idUsuarioSQL": int(id)}
        db.usuarios.delete_one(filtro)
        messages.success(request, "Usuario eliminado correctamente de la plataforma NoSQL.")
    except Exception as e:
        messages.error(request, f"Error en MongoDB: {str(e)}")
    
    return redirect('listar_usuarios')

@verificar_rol(['Admin'])
def index(request):
    """
    Panel principal del Administrador.
    Calcula los totales ultra rápidos usando PyMongo.
    """
    try:
        # Reemplazamos los Modelo.objects.count() por count_documents de Mongo
        total_usuarios = db.usuarios.count_documents({})
        total_artistas = db.artistas.count_documents({})
        total_albumes = db.albumes.count_documents({})
        total_canciones = db.canciones.count_documents({})

        context = {
            'total_usuarios': total_usuarios,
            'total_artistas': total_artistas,
            'total_albumes': total_albumes,
            'total_canciones': total_canciones,
        }
    except Exception as e:
        # Valores por defecto en caso de fallo de conexión
        context = {
            'total_usuarios': 0, 'total_artistas': 0,
            'total_albumes': 0, 'total_canciones': 0,
        }
        
    return render(request, 'index.html', context)

# ==========================================
# CRUD: DISCOGRAFICAS - MONGODB
# ==========================================

@verificar_rol(['Admin'])
def listar_discograficas(request):
    query = request.GET.get('q', '').strip()
    
    # 1. Filtro de búsqueda NoSQL
    filtro = {}
    if query:
        filtro = {"nombre": {"$regex": query, "$options": "i"}}
        
    # 2. Consultamos directamente a la colección db.discograficas
    items_mongo = list(db.discograficas.find(filtro))
    
    # 3. Preparamos el diccionario para el HTML
    for item in items_mongo:
        item['id_mongo'] = str(item['_id'])
        item['idDiscografica'] = item.get('idDiscograficaSQL') or str(item['_id'])[-6:].upper()
        item['nombre'] = item.get('nombre', 'Sin nombre')
        item['pais'] = item.get('pais', 'No especificado')
        item['fechaFundacion'] = item.get('fechaFundacion', '')
        
    return render(request, 'discograficas/listar.html', {'items': items_mongo})

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

        # Documento BSON para insertar
        nueva_discografica = {
            "nombre": nombre,
            "pais": pais,
            "fechaFundacion": fecha,
            "logo": logo
        }
        
        db.discograficas.insert_one(nueva_discografica)
        messages.success(request, f"Discográfica '{nombre}' agregada exitosamente a MongoDB.")
        return redirect('listar_discograficas')
        
    return render(request, 'discograficas/crear.html')

@verificar_rol(['Admin'])
def editar_discografica(request, id):
    # Soporta tanto IDs de MongoDB como los viejos de SQL
    filtro = {"_id": ObjectId(id)} if len(str(id)) == 24 else {"idDiscograficaSQL": int(id)}
    item = db.discograficas.find_one(filtro)
    
    if request.method == 'POST':
        db.discograficas.update_one(filtro, {
            "$set": {
                "nombre": request.POST.get('nombre', item.get('nombre')),
                "pais": request.POST.get('pais', item.get('pais')),
                "fechaFundacion": request.POST.get('fechaFundacion', item.get('fechaFundacion')),
                "logo": request.POST.get('logo', '').strip() or item.get('logo')
            }
        })
        messages.success(request, "Discográfica actualizada exitosamente.")
        return redirect('listar_discograficas')
        
    # Agregamos id_mongo para la URL de retorno en el HTML
    if item:
        item['id_mongo'] = str(item['_id'])
        
    return render(request, 'discograficas/editar.html', {'item': item})

@verificar_rol(['Admin'])
def eliminar_discografica(request, id):
    try:
        # 1. Intentamos estructurar el filtro por ObjectId de forma segura
        if len(str(id)) == 24:
            filtro = {"_id": ObjectId(id)}
        else:
            filtro = {"idDiscograficaSQL": int(id)}
            
        discografica = db.discograficas.find_one(filtro)
        
        if discografica:
            id_sql = discografica.get('idDiscograficaSQL')
            id_mongo = discografica['_id']
            
            # 2. Buscamos relaciones activas soportando enteros, strings y ObjectIds
            condiciones_artistas = [
                {"idDiscografica": id_mongo},
                {"Discografica_idDiscografica": id_mongo},
                {"idDiscografica": str(id_mongo)},
                {"Discografica_idDiscografica": str(id_mongo)}
            ]
            
            # Si el registro vino migrado de SQL, añadimos los identificadores numéricos
            if id_sql is not None:
                condiciones_artistas.extend([
                    {"idDiscografica": int(id_sql)},
                    {"Discografica_idDiscografica": int(id_sql)},
                    {"idDiscografica": str(id_sql)},
                    {"Discografica_idDiscografica": str(id_sql)}
                ])
            
            artistas_asociados = db.artistas.count_documents({"$or": condiciones_artistas})
            
            if artistas_asociados > 0:
                messages.error(request, f"Operación cancelada: La discográfica '{discografica.get('nombre')}' tiene {artistas_asociados} artista(s) vinculados en MongoDB.")
                return redirect('listar_discograficas')
                
            # 3. Si está limpia de dependencias, procedemos al borrado físico
            db.discograficas.delete_one({"_id": id_mongo})
            messages.success(request, f"La discográfica '{discografica.get('nombre')}' ha sido eliminada permanentemente.")
        else:
            messages.error(request, "Error: No se encontró el registro de la discográfica.")
            
    except Exception as e:
        messages.error(request, f"Error de ejecución en MongoDB: {str(e)}")
        
    return redirect('listar_discograficas')

# ==========================================
# CRUD: ARTISTAS (100% MONGODB)
# ==========================================

@verificar_rol(['Admin'])
def listar_artistas(request):
    query = request.GET.get('q', '').strip()
    filtro = {"nombreArtistico": {"$regex": query, "$options": "i"}} if query else {}
        
    items_mongo = list(db.artistas.find(filtro))
    
    # ==========================================
    # 🚀 OPTIMIZACIÓN: COLA DE CONSULTAS EN MEMORIA
    # Traemos las colecciones maestras una sola vez
    # ==========================================
    dict_discos = {}
    for d in db.discograficas.find():
        if d.get('idDiscograficaSQL') is not None: 
            dict_discos[str(d['idDiscograficaSQL'])] = d
        dict_discos[str(d['_id'])] = d
        
    dict_generos = {}
    for g in db.generos.find():
        if g.get('idGeneroSQL') is not None: 
            dict_generos[str(g['idGeneroSQL'])] = g
        dict_generos[str(g['_id'])] = g
    # ==========================================
    
    for item in items_mongo:
        item['id_mongo'] = str(item['_id'])
        item['idArtista'] = item.get('idArtistaSQL') or str(item['_id'])[-6:].upper()
        item['nombreArtistico'] = item.get('nombreArtistico') or item.get('nombre') or 'Desconocido'
        
        # Normalización de rutas de imágenes
        img_raw = item.get('imagen', 'default_artist.png')
        if img_raw and not img_raw.startswith('artistas/') and img_raw != 'default_artist.png':
            item['imagen_limpia'] = f"artistas/{img_raw}"
        else:
            item['imagen_limpia'] = img_raw

        # 🛠️ Cruce en memoria O(1) de Discográfica
        disco_id = str(item.get('idDiscografica') or item.get('Discografica_idDiscografica') or '')
        disco_doc = dict_discos.get(disco_id)
        item['discografica_nombre'] = disco_doc.get('nombre', 'Independiente') if disco_doc else "Independiente"

        # 🛠️ Cruce en memoria O(1) de Género
        genero_id = str(item.get('genero') or item.get('generoPrincipal') or item.get('idGenero') or '')
        genero_name = "N/A"
        
        # Verificación de tipo (si ya es texto plano como "Pop" o un ID relacional)
        genero_raw = item.get('genero') or item.get('generoPrincipal') or item.get('idGenero')
        if isinstance(genero_raw, str) and len(genero_raw) < 20 and not genero_raw.isdigit() and len(genero_id) != 24:
            genero_name = genero_raw
        elif genero_id in dict_generos:
            genero_name = dict_generos[genero_id].get('nombre', 'N/A')
                        
        item['genero_db'] = genero_name
        item['verificado_db'] = bool(item.get('verificado', False))
        
    return render(request, 'artistas/listar.html', {'items': items_mongo})

@verificar_rol(['Admin'])
def crear_artista(request):
    if request.method == 'POST':
        nombre_artistico = request.POST.get('nombreArtistico', '').strip()
        biografia = request.POST.get('biografia', '')
        pais = request.POST.get('pais', 'Desconocido')
        fecha_creacion = request.POST.get('fechaCreacion') or date.today().strftime('%Y-%m-%d')
        disco_id = request.POST.get('discografica')
        id_usuario = request.POST.get('usuario')
        genero_form = request.POST.get('generoPrincipal')
        verificado_form = True if request.POST.get('verificado') else False 
        
        # --- LÓGICA PARA LA IMAGEN (Se mantiene en servidor local) ---
        nombre_imagen = 'default_artist.png'
        if request.FILES.get('imagen'):
            imagen_archivo = request.FILES['imagen']
            fs = FileSystemStorage(location=os.path.join('static', 'images', 'artistas'))
            filename = fs.save(imagen_archivo.name, imagen_archivo)
            nombre_imagen = f"artistas/{filename}"

        nuevo_artista = {
            "nombreArtistico": nombre_artistico,
            "biografia": biografia,
            "pais": pais,
            "fechaCreacion": fecha_creacion,
            "imagen": nombre_imagen,
            "idDiscografica": disco_id,
            "idUsuario": id_usuario,
            "genero": genero_form,
            "verificado": verificado_form
        }
        
        try:
            db.artistas.insert_one(nuevo_artista)
            messages.success(request, f"Perfil de '{nombre_artistico}' creado correctamente en MongoDB.")
            return redirect('listar_artistas')
        except Exception as e:
            messages.error(request, f"Error en MongoDB: {str(e)}")

    # CARGA DE SELECTORES DESDE MONGODB PARA EVITAR ERRORES DE TABLA INEXISTENTE
    discograficas = list(db.discograficas.find({}, {"_id": 1, "nombre": 1, "idDiscograficaSQL": 1}))
    for d in discograficas: d['idDiscografica'] = d.get('idDiscograficaSQL') or str(d['_id'])
        
    usuarios_artistas = list(db.usuarios.find({"$or": [{"rol": "Artista"}, {"rol": "Administrador"}]}))
    for u in usuarios_artistas: u['idUsuario'] = u.get('idUsuarioSQL') or str(u['_id'])
        
    generos = list(db.generos.find({}, {"_id": 1, "nombre": 1, "idGeneroSQL": 1}))
    for g in generos: g['idGenero'] = g.get('idGeneroSQL') or str(g['_id'])
    # Fallback si no hay géneros en mongo aún
    if not generos: generos = [{'idGenero': 'Pop', 'nombre': 'Pop'}, {'idGenero': 'Rock', 'nombre': 'Rock'}, {'idGenero': 'Urbano', 'nombre': 'Urbano'}]

    return render(request, 'artistas/crear.html', {
        'discograficas': discograficas,
        'usuarios_artistas': usuarios_artistas,
        'generos': generos
    })

@verificar_rol(['Admin'])
def editar_artista(request, id):
    filtro = {"_id": ObjectId(id)} if len(str(id)) == 24 else {"idArtistaSQL": int(id)}
    artista_obj = db.artistas.find_one(filtro)
    
    if not artista_obj:
        messages.error(request, "Artista no encontrado.")
        return redirect('listar_artistas')

    if request.method == 'POST':
        nombre_form = request.POST.get('nombreArtistico')
        biografia_form = request.POST.get('biografia', '')
        disco_id = request.POST.get('discografica')
        id_usuario = request.POST.get('usuario')
        genero_form = request.POST.get('generoPrincipal')
        verificado_form = True if request.POST.get('verificado') else False

        # --- ACTUALIZACIÓN DE IMAGEN ---
        nombre_imagen = artista_obj.get('imagen', 'default_artist.png')
        if request.FILES.get('imagen'):
            imagen_archivo = request.FILES['imagen']
            fs = FileSystemStorage(location=os.path.join('static', 'images', 'artistas'))
            filename = fs.save(imagen_archivo.name, imagen_archivo)
            nombre_imagen = f"artistas/{filename}"

        try:
            db.artistas.update_one(filtro, {
                "$set": {
                    "nombreArtistico": nombre_form,
                    "biografia": biografia_form,
                    "idDiscografica": disco_id,
                    "imagen": nombre_imagen,
                    "idUsuario": id_usuario,
                    "genero": genero_form,
                    "verificado": verificado_form
                }
            })
            messages.success(request, f"Perfil de '{nombre_form}' actualizado correctamente.")
            return redirect('listar_artistas')
        except Exception as e:
            messages.error(request, f"Error al guardar en MongoDB: {str(e)}")

    # Preparación de datos para el formulario de edición
    artista_obj['id_mongo'] = str(artista_obj['_id'])
    artista_usuario_id = str(artista_obj.get('idUsuario', ''))
    genero_actual = artista_obj.get('genero', '')
    es_verificado = artista_obj.get('verificado', False)
    
    discograficas = list(db.discograficas.find({}, {"_id": 1, "nombre": 1, "idDiscograficaSQL": 1}))
    for d in discograficas: d['idDiscografica'] = str(d.get('idDiscograficaSQL') or d['_id'])
        
    usuarios_artistas = list(db.usuarios.find({"$or": [{"rol": "Artista"}, {"rol": "Administrador"}]}))
    for u in usuarios_artistas: u['idUsuario'] = str(u.get('idUsuarioSQL') or u['_id'])
        
    generos = list(db.generos.find({}, {"_id": 1, "nombre": 1, "idGeneroSQL": 1}))
    for g in generos: g['idGenero'] = str(g.get('idGeneroSQL') or g['_id'])
    if not generos: generos = [{'idGenero': 'Pop', 'nombre': 'Pop'}, {'idGenero': 'Rock', 'nombre': 'Rock'}, {'idGenero': 'Urbano', 'nombre': 'Urbano'}]

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
    try:
        filtro = {"_id": ObjectId(id)} if len(str(id)) == 24 else {"idArtistaSQL": int(id)}
        artista = db.artistas.find_one(filtro)
        
        if artista:
            id_referencia = artista.get('idArtistaSQL') or str(artista['_id'])
            
            # 1. Validación de integridad
            albumes_vinculados = db.albumes.count_documents({
                "$or": [
                    {"idArtista": id_referencia},
                    {"Artista_idArtista": id_referencia},
                    {"idArtista": str(id_referencia)}
                ]
            })
            
            if albumes_vinculados > 0:
                messages.error(request, f"No se puede eliminar. El artista '{artista.get('nombreArtistico')}' tiene {albumes_vinculados} álbum(es) registrado(s).")
                return redirect('listar_artistas')

            # 2. Guardar la ruta de la imagen antes de eliminar el documento
            imagen_a_borrar = artista.get('imagen')

            # 3. Borrado del registro en MongoDB
            db.artistas.delete_one(filtro)
            
            # 4. Eliminación física del archivo en el sistema de archivos
            if imagen_a_borrar and imagen_a_borrar != 'default_artist.png':
                # Construimos la ruta dinámica utilizando BASE_DIR de Django
                ruta_completa = os.path.join(settings.BASE_DIR, 'registros', 'static', 'images', imagen_a_borrar)
                
                if os.path.exists(ruta_completa):
                    try:
                        os.remove(ruta_completa)
                        print(f"✅ Archivo físico eliminado con éxito: {ruta_completa}")
                    except Exception as err_os:
                        print(f"⚠️ No se pudo eliminar el archivo físico: {str(err_os)}")

            messages.success(request, "Artista y su imagen asociada eliminados correctamente.")
        else:
            messages.error(request, "El artista no existe en la base NoSQL.")
            
    except Exception as e:
        messages.error(request, f"Fallo al eliminar: {str(e)}")
        
    return redirect('listar_artistas')

# ==========================================
# CRUD: ALBUMES (100% MONGODB)
# ==========================================
@verificar_rol(['Admin'])
def listar_albumes(request):
    query = request.GET.get('q', '').strip()
    filtro = {"titulo": {"$regex": query, "$options": "i"}} if query else {}
        
    items_mongo = list(db.albumes.find(filtro))
    
    # ==========================================
    # 🚀 OPTIMIZACIÓN: MAPA DE ARTISTAS EN RAM
    # Evita golpear la base de datos por cada álbum
    # ==========================================
    dict_artistas = {}
    for a in db.artistas.find():
        if a.get('idArtistaSQL') is not None: 
            dict_artistas[str(a['idArtistaSQL'])] = a
        dict_artistas[str(a['_id'])] = a
    # ==========================================
    
    for item in items_mongo:
        item['id_mongo'] = str(item['_id'])
        item['idAlbum'] = item.get('idAlbumSQL') or str(item['_id'])[-6:].upper()
        
        # Lógica de URL de imagen limpia para MEDIA_URL
        img_name = item.get('imagen')
        if img_name and img_name != 'default_album.png' and img_name != 'default_album.jpg':
            item['imagen_url'] = f"{settings.MEDIA_URL}albumes/{img_name}"
        else:
            item['imagen_url'] = None # Usará el fallback por defecto en el HTML
            
        # 🛠️ Cruce en memoria O(1) del Artista Propietario
        id_art = str(item.get('idArtista') or item.get('Artista_idArtista') or '')
        artista_doc = dict_artistas.get(id_art)
        item['artista_nombre'] = artista_doc.get('nombreArtistico', 'Desconocido') if artista_doc else "Desconocido"

    return render(request, 'albumes/listar.html', {'items': items_mongo})

@verificar_rol(['Admin'])
def crear_album(request):
    if request.method == 'POST':
        titulo = request.POST.get('titulo')
        fecha = request.POST.get('fechaLanzamiento')
        artista_id = request.POST.get('artista')
        
        # Guardar imagen física en la carpeta media/albumes/
        imagen = request.FILES.get('imagen') 
        imagen_nombre = 'default_album.png'
        if imagen:
            fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'albumes'))
            filename = fs.save(imagen.name, imagen)
            imagen_nombre = filename

        nuevo_album = {
            "titulo": titulo,
            "fechaLanzamiento": fecha,
            "idArtista": artista_id,
            "imagen": imagen_nombre
        }
        db.albumes.insert_one(nuevo_album)
        messages.success(request, f"Álbum '{titulo}' creado exitosamente.")
        return redirect('listar_albumes')

    # Cargar artistas para el select
    artistas = list(db.artistas.find({}, {"_id": 1, "nombreArtistico": 1, "idArtistaSQL": 1}))
    for a in artistas: a['idArtista'] = a.get('idArtistaSQL') or str(a['_id'])
    
    return render(request, 'albumes/crear.html', {'artistas': artistas})

@verificar_rol(['Admin'])
def editar_album(request, id):
    filtro = {"_id": ObjectId(id)} if len(str(id)) == 24 else {"idAlbumSQL": int(id)}
    item = db.albumes.find_one(filtro)

    if not item:
        messages.error(request, "Álbum no encontrado.")
        return redirect('listar_albumes')

    if request.method == 'POST':
        nueva_imagen = request.FILES.get('imagen')
        imagen_nombre = item.get('imagen', 'default_album.png')
        
        if nueva_imagen:
            fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, 'albumes'))
            filename = fs.save(nueva_imagen.name, nueva_imagen)
            imagen_nombre = filename

        # Si el input de fecha viene vacío por alguna razón, mantenemos la que ya tenía
        fecha_lanzamiento = request.POST.get('fechaLanzamiento') or item.get('fechaLanzamiento')

        db.albumes.update_one(filtro, {
            "$set": {
                "titulo": request.POST.get('titulo'),
                "fechaLanzamiento": fecha_lanzamiento,
                "idArtista": request.POST.get('artista'),
                "imagen": imagen_nombre
            }
        })
        messages.success(request, "Álbum actualizado correctamente.")
        return redirect('listar_albumes')

    # --- PREPARACIÓN DE DATOS PARA LA VISTA (GET) ---
    item['id_mongo'] = str(item['_id'])
    
    # 🌟 CORRECCIÓN AQUÍ: Forzamos la conversión a String limpia de cualquier variante de ID
    artista_id_raw = item.get('idArtista') or item.get('Artista_idArtista')
    if artista_id_raw is not None:
        item['idArtista_actual'] = str(artista_id_raw).strip()
    else:
        item['idArtista_actual'] = ""
    
    # Formateamos la fecha de lanzamiento de forma estricta para el HTML
    fecha_raw = item.get('fechaLanzamiento', '')
    if fecha_raw:
        if hasattr(fecha_raw, 'strftime'):
            item['fecha_formateada'] = fecha_raw.strftime('%Y-%m-%d')
        elif isinstance(fecha_raw, str):
            item['fecha_formateada'] = fecha_raw.split('T')[0]
        else:
            item['fecha_formateada'] = str(fecha_raw)
    else:
        item['fecha_formateada'] = ""

    # Cargar el listado de artistas para el combo box
    artistas = list(db.artistas.find({}, {"_id": 1, "nombreArtistico": 1, "idArtistaSQL": 1}))
    for a in artistas: 
        # Aseguramos también que el ID del bucle sea estrictamente String
        artista_loop_id = a.get('idArtistaSQL') or a['_id']
        a['idArtista'] = str(artista_loop_id).strip()

    return render(request, 'albumes/editar.html', {'item': item, 'artistas': artistas})

@verificar_rol(['Admin'])
def eliminar_album(request, id):
    try:
        filtro = {"_id": ObjectId(id)} if len(str(id)) == 24 else {"idAlbumSQL": int(id)}
        album = db.albumes.find_one(filtro)
        
        if album:
            # Validar si tiene canciones
            id_referencia = album.get('idAlbumSQL') or str(album['_id'])
            canciones_vinculadas = db.canciones.count_documents({
                "$or": [{"idAlbum": id_referencia}, {"Album_idAlbum": id_referencia}, {"idAlbum": str(id_referencia)}]
            })
            
            if canciones_vinculadas > 0:
                messages.error(request, f"No se puede eliminar. El álbum contiene {canciones_vinculadas} canciones.")
                return redirect('listar_albumes')

            imagen_a_borrar = album.get('imagen')
            db.albumes.delete_one(filtro)
            
            # Borrado físico
            if imagen_a_borrar and imagen_a_borrar != 'default_album.png':
                ruta_completa = os.path.join(settings.MEDIA_ROOT, 'albumes', imagen_a_borrar)
                if os.path.exists(ruta_completa): os.remove(ruta_completa)
                    
            messages.success(request, "Álbum eliminado correctamente.")
    except Exception as e:
        messages.error(request, f"Fallo al eliminar: {str(e)}")
        
    return redirect('listar_albumes')

# ==========================================
# CRUD: CANCIONES
# ==========================================

@verificar_rol(['Admin'])
def listar_canciones(request):
    query = request.GET.get('q', '').strip()
    filtro = {"titulo": {"$regex": query, "$options": "i"}} if query else {}
        
    # 1. Traer todas las canciones de golpe
    canciones_mongo = list(db.canciones.find(filtro))
    
    # ==========================================
    # 🚀 OPTIMIZACIÓN: DICCIONARIOS EN MEMORIA
    # Traemos las otras colecciones 1 sola vez y las guardamos en memoria.
    # Soportan tanto el ID viejo de SQL como el nuevo de Mongo.
    # ==========================================
    dict_artistas = {}
    for a in db.artistas.find():
        if a.get('idArtistaSQL') is not None: dict_artistas[str(a['idArtistaSQL'])] = a
        dict_artistas[str(a['_id'])] = a
        
    dict_albumes = {}
    for alb in db.albumes.find():
        if alb.get('idAlbumSQL') is not None: dict_albumes[str(alb['idAlbumSQL'])] = alb
        dict_albumes[str(alb['_id'])] = alb
        
    dict_generos = {}
    for g in db.generos.find():
        if g.get('idGeneroSQL') is not None: dict_generos[str(g['idGeneroSQL'])] = g
        dict_generos[str(g['_id'])] = g
    # ==========================================

    for cancion in canciones_mongo:
        cancion['id_mongo'] = str(cancion['_id'])
        cancion['idCancion'] = cancion.get('idCancionSQL') or str(cancion['_id'])[-6:].upper()
        
        segs = cancion.get('duracionSegundos') or cancion.get('duracion') or 0
        if isinstance(segs, int) and segs > 0:
            cancion['duracion_formateada'] = f"{segs // 60}:{segs % 60:02d}"
        else:
            cancion['duracion_formateada'] = "0:00"

        # 2. RESOLVER ÁLBUM Y HEREDAR IMAGEN
        # Buscamos el ID del álbum en nuestro diccionario rápido
        id_alb = str(cancion.get('idAlbum') or cancion.get('Album_idAlbum', ''))
        album_doc = dict_albumes.get(id_alb)
        
        cancion['album_titulo'] = album_doc.get('titulo') if album_doc else "Sencillo"

        # 🌟 EL TRUCO: Heredamos la imagen física del álbum en lugar de la canción
        if album_doc and album_doc.get('imagen') and album_doc.get('imagen') not in ['default_album.png', 'default_album.jpg', '']:
            img_name = album_doc.get('imagen')
            # Las canciones ahora buscarán la portada del álbum en media/albumes/
            cancion['imagen_url'] = f"{settings.MEDIA_URL}albumes/{img_name}"
        else:
            cancion['imagen_url'] = None # Usará el track por defecto en el HTML

        # 3. RESOLVER ARTISTA
        id_art = str(cancion.get('idArtista') or cancion.get('Artista_idArtista', ''))
        artista_doc = dict_artistas.get(id_art)
        cancion['artista_nombre'] = artista_doc.get('nombreArtistico') if artista_doc else "Artista Independiente"

        # 4. RESOLVER GÉNEROS
        nombres_generos = []
        for gen_item in cancion.get('generos', []):
            id_sql = str(gen_item.get('idSQL', ''))
            if id_sql and id_sql in dict_generos:
                nombres_generos.append(dict_generos[id_sql].get('nombre', ''))
                
        if not nombres_generos and isinstance(cancion.get('genero'), str):
            nombres_generos.append(cancion.get('genero'))
            
        cancion['generos_texto'] = ", ".join(nombres_generos) if nombres_generos else "Sin Género"

    return render(request, 'canciones/listar.html', {'items': canciones_mongo})
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
# CRUD: GENEROS - MONGODB
# ==========================================
@verificar_rol(['Admin'])
def listar_generos(request):
    query = request.GET.get('q', '').strip()
    filtro = {}
    if query:
        filtro = {"nombre": {"$regex": query, "$options": "i"}}
        
    items_mongo = list(db.generos.find(filtro))
    
    for item in items_mongo:
        item['id_mongo'] = str(item['_id'])
        item['idGenero'] = item.get('idGeneroSQL') or str(item['_id'])[-6:].upper()
        item['nombre'] = item.get('nombre', 'Desconocido')
        
    return render(request, 'generos/listar.html', {'items': items_mongo})

@verificar_rol(['Admin'])
def crear_genero(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        if nombre:
            # Validar que no haya duplicados (ignorando mayúsculas/minúsculas)
            if db.generos.find_one({"nombre": {"$regex": f"^{nombre}$", "$options": "i"}}):
                messages.error(request, f"El género '{nombre}' ya existe en el catálogo.")
            else:
                db.generos.insert_one({"nombre": nombre})
                messages.success(request, f"Género '{nombre}' creado exitosamente.")
                return redirect('listar_generos')
    return render(request, 'generos/crear.html')

@verificar_rol(['Admin'])
def editar_genero(request, id):
    filtro = {"_id": ObjectId(id)} if len(str(id)) == 24 else {"idGeneroSQL": int(id)}
    item = db.generos.find_one(filtro)
    
    if request.method == 'POST':
        nuevo_nombre = request.POST.get('nombre', '').strip()
        if nuevo_nombre:
            db.generos.update_one(filtro, {"$set": {"nombre": nuevo_nombre}})
            messages.success(request, "El nombre del género ha sido actualizado.")
            return redirect('listar_generos')
            
    if item:
        item['id_mongo'] = str(item['_id'])
        
    return render(request, 'generos/editar.html', {'item': item})

@verificar_rol(['Admin'])
def eliminar_genero(request, id):
    try:
        filtro = {"_id": ObjectId(id)} if len(str(id)) == 24 else {"idGeneroSQL": int(id)}
        genero = db.generos.find_one(filtro)
        
        if genero:
            # Validar integridad: ¿Hay artistas usando este género?
            nombre_gen = genero.get('nombre')
            usos_artistas = db.artistas.count_documents({"genero": nombre_gen})
            
            if usos_artistas > 0:
                messages.error(request, f"No se puede eliminar. Hay {usos_artistas} artista(s) usando el género '{nombre_gen}'.")
            else:
                db.generos.delete_one(filtro)
                messages.success(request, "Género eliminado correctamente.")
        else:
            messages.error(request, "El género no existe.")
            
    except Exception as e:
        messages.error(request, f"Error al eliminar en MongoDB: {str(e)}")
        
    return redirect('listar_generos')

# ==========================================
# CRUD: PLANES (100% MONGODB)
# ==========================================
@verificar_rol(['Admin'])
def listar_planes(request):
    query = request.GET.get('q', '').strip()
    filtro = {"nombre": {"$regex": query, "$options": "i"}} if query else {}
        
    items_mongo = list(db.planes.find(filtro))
    
    for item in items_mongo:
        item['id_mongo'] = str(item['_id'])
        item['idPlan'] = item.get('idPlanSQL') or str(item['_id'])[-6:].upper()
        # Asegurar valores numéricos para visualización
        item['precio'] = float(item.get('precio', 0.0))
        item['duracionMeses'] = int(item.get('duracionMeses', 0))
        
    return render(request, 'planes/listar.html', {'items': items_mongo})

@verificar_rol(['Admin'])
def crear_plan(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        precio = request.POST.get('precio', 0)
        duracion = request.POST.get('duracionMeses', 0)
        
        if nombre:
            if db.planes.find_one({"nombre": {"$regex": f"^{nombre}$", "$options": "i"}}):
                messages.error(request, f"El plan '{nombre}' ya existe.")
            else:
                try:
                    db.planes.insert_one({
                        "nombre": nombre,
                        "precio": float(precio),
                        "duracionMeses": int(duracion)
                    })
                    messages.success(request, f"Plan '{nombre}' creado exitosamente.")
                    return redirect('listar_planes')
                except ValueError:
                    messages.error(request, "Error: El precio y la duración deben ser números válidos.")
                    
    return render(request, 'planes/crear.html')

@verificar_rol(['Admin'])
def editar_plan(request, id):
    filtro = {"_id": ObjectId(id)} if len(str(id)) == 24 else {"idPlanSQL": int(id)}
    item = db.planes.find_one(filtro)
    
    if not item:
        messages.error(request, "El plan no existe.")
        return redirect('listar_planes')

    if request.method == 'POST':
        nuevo_nombre = request.POST.get('nombre', '').strip()
        precio = request.POST.get('precio', 0)
        duracion = request.POST.get('duracionMeses', 0)
        
        try:
            db.planes.update_one(filtro, {
                "$set": {
                    "nombre": nuevo_nombre,
                    "precio": float(precio),
                    "duracionMeses": int(duracion)
                }
            })
            messages.success(request, "Plan actualizado correctamente.")
            return redirect('listar_planes')
        except ValueError:
            messages.error(request, "Error: El precio y la duración deben ser numéricos.")
            
    item['id_mongo'] = str(item['_id'])
    
    # Formatear el precio sin decimales raros para el input type="number"
    if item.get('precio') is not None:
        item['precio_formateado'] = f"{float(item['precio']):.2f}"
        
    return render(request, 'planes/editar.html', {'item': item})

@verificar_rol(['Admin'])
def eliminar_plan(request, id):
    try:
        filtro = {"_id": ObjectId(id)} if len(str(id)) == 24 else {"idPlanSQL": int(id)}
        plan = db.planes.find_one(filtro)
        
        if plan:
            # 1. Bloqueo de integridad: Evitar borrar un plan si hay pagos/suscripciones atadas a él
            nombre_plan = plan.get('nombre')
            
            # Buscar en usuarios si alguno tiene esta suscripción activa (como string)
            usuarios_suscritos = db.usuarios.count_documents({"suscripcion.plan": nombre_plan})
            
            # Buscar en pagos si hay recibos asociados a este plan (usando su idSQL o nombre)
            id_ref = plan.get('idPlanSQL')
            condiciones_pagos = [{"plan": nombre_plan}]
            if id_ref: condiciones_pagos.append({"idPlan": int(id_ref)})
            
            pagos_vinculados = db.pagos.count_documents({"$or": condiciones_pagos})
            
            if usuarios_suscritos > 0 or pagos_vinculados > 0:
                messages.error(request, f"No se puede eliminar. El plan '{nombre_plan}' está en uso por {usuarios_suscritos} usuarios y tiene {pagos_vinculados} pagos registrados.")
            else:
                db.planes.delete_one(filtro)
                messages.success(request, f"Plan '{nombre_plan}' eliminado permanentemente.")
        else:
            messages.error(request, "Plan no encontrado.")
            
    except Exception as e:
        messages.error(request, f"Error en MongoDB: {str(e)}")
        
    return redirect('listar_planes')
    
# ==========================================
# SISTEMA DE AUTENTICACIÓN (LOGIN / LOGOUT) - MIGRADO A MONGODB 
# ==========================================

def login_view(request):
    """
    Controlador global de autenticación para Proyecto RollsMusic utilizando MongoDB (PyMongo).
    """
    
    # 1. CONTROL ANTIBUCLE CORREGIDO
    if 'usuario_id' in request.session:
        # Ahora usamos 'usuario_rol' para coincidir con tu decorador
        rol_activo = request.session.get('usuario_rol', 'Cliente') 
        if rol_activo == 'Admin':
            return redirect('index') # Tu vista de admin se llama 'index'
        elif rol_activo == 'Artista':
            return redirect('dashboard_artista')
        else:
            return redirect('dashboard_usuario')

    if request.method == 'POST':
        correo = request.POST.get('correo', '').strip()
        
        # 2. COINCIDENCIA EXACTA CON EL HTML ('contrasenia')
        password_ingresada = request.POST.get('contrasenia', '')

        if not correo or not password_ingresada:
            messages.error(request, 'Por favor, complete todos los campos.')
            return render(request, 'login.html')

        try:
            usuario = db.usuarios.find_one({
                "correo": correo,
                "contrasenia": password_ingresada
            })

            if usuario:
                if usuario.get('estado') != 'Activo':
                    messages.error(request, 'Esta cuenta se encuentra actualmente inactiva.')
                    return render(request, 'login.html')

                # 3. CREACIÓN DE SESIÓN (Sincronizada con el decorador)
                request.session['usuario_id'] = str(usuario['_id'])
                
                # Normalizamos el nombre del rol para que pase las validaciones de tu decorador
                rol_bd = usuario.get('rol', 'Cliente')
                if rol_bd == 'Administrador':
                    request.session['usuario_rol'] = 'Admin'
                else:
                    request.session['usuario_rol'] = rol_bd

                request.session['nombre'] = usuario.get('nombre', '')
                request.session['apellido'] = usuario.get('apellido', '')

                # 4. REDIRECCIÓN SEGÚN TU urls.py
                rol = request.session['usuario_rol']
                
                if rol == 'Admin':
                    return redirect('index') # Redirige a la vista index (Admin)
                elif rol == 'Artista':
                    return redirect('dashboard_artista') 
                else:
                    return redirect('dashboard_usuario') 

            else:
                messages.error(request, 'Credenciales incorrectas. Inténtelo de nuevo.')

        except Exception as e:
            messages.error(request, f'Error de conexión con la base de datos: {str(e)}')

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

# MANTENIMIENTO DE SUSCRIPCIONES
@verificar_rol(['Admin'])
def verificar_suscripciones(request):
    """
    Reemplazo del Procedimiento Almacenado de SQL Server.
    Actualiza el estado de las suscripciones vencidas directamente en Mongo.
    """
    if 'usuario_id' not in request.session or request.session.get('usuario_rol') != 'Admin':
        messages.error(request, "Acceso denegado. Esta acción es exclusiva para administradores.")
        return redirect('login')
        
    try:
        fecha_actual = datetime.now()
        
        # Actualización masiva: Busca planes Premium que ya pasaron su fecha de fin
        # y los degrada a Free usando $set
        resultado = db.usuarios.update_many(
            {
                "suscripcion.plan": "Premium",
                "suscripcion.fechaFin": {"$lt": fecha_actual}
            },
            {
                "$set": {
                    "suscripcion.plan": "Free",
                    "suscripcion.estado": "Vencida"
                }
            }
        )
            
        messages.success(request, f"⚙️ Mantenimiento completado: Se degradaron {resultado.modified_count} suscripciones vencidas a plan Free.")
    except Exception as e:
        messages.error(request, f"Error al ejecutar el mantenimiento NoSQL: {str(e)}")
        
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