from django.shortcuts import render, redirect
from django.contrib import messages
from datetime import date
from functools import wraps
from django.http import JsonResponse

# Importaciones exclusivas de MongoDB y utilidades
from bson.objectid import ObjectId
from datetime import datetime
from .db import db

import os
from django.core.files.storage import FileSystemStorage
from django.conf import settings


# ==========================================
# DECORADOR DE SEGURIDAD
# ==========================================
def verificar_rol(roles_permitidos):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            rol_usuario = request.session.get('usuario_rol')
            
            if not request.session.get('usuario_id') or not rol_usuario:
                messages.error(request, "Debes iniciar sesión para acceder a esta sección.")
                return redirect('login')
            
            rol_usuario_limpio = str(rol_usuario).strip().capitalize()
            roles_permitidos_limpios = [str(r).strip().capitalize() for r in roles_permitidos]
            
            if rol_usuario_limpio in roles_permitidos_limpios:
                return view_func(request, *args, **kwargs)
            else:
                messages.error(request, f"No tienes permisos para acceder a esta sección con tu rol de {rol_usuario}.")
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
    filtro = {}
    if query:
        filtro = {
            "$or": [
                {"nombre": {"$regex": query, "$options": "i"}},
                {"apellido": {"$regex": query, "$options": "i"}}
            ]
        }
        
    usuarios_mongo = list(db.usuarios.find(filtro))
    
    for u in usuarios_mongo:
        u['id_mongo'] = str(u['_id'])
        u['idUsuario'] = u.get('idUsuarioSQL') or str(u['_id'])[-6:].upper()
        u['nombre'] = u.get('nombre', 'Sin nombre')
        u['apellido'] = u.get('apellido', '')
        u['correo'] = u.get('correo', 'Sin correo')
        u['estado'] = u.get('estado', 'Inactivo')
        u['rol_nombre'] = u.get('rol', 'Cliente')
        
    return render(request, 'usuarios/listar.html', {'usuarios': usuarios_mongo})

@verificar_rol(['Admin'])
def crear_usuario(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        apellido = request.POST.get('apellido', '').strip()
        correo = request.POST.get('correo', '').strip()
        fecha_nacimiento = request.POST.get('fechaNacimiento', '').strip()
        contrasenia = request.POST.get('contrasenia', '').strip()
        rol = request.POST.get('rol', 'Cliente') 

        if db.usuarios.find_one({"correo": correo}):
            messages.error(request, "Error: Este correo ya se encuentra registrado.")
            return redirect('crear_usuario')

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
    
    roles = [{'nombre': 'Administrador'}, {'nombre': 'Artista'}, {'nombre': 'Cliente'}]
    return render(request, 'usuarios/crear.html', {'roles': roles})

@verificar_rol(['Admin'])
def editar_usuario(request, id):
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
    usuario['idUsuario'] = str(usuario['_id'])
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


# ==========================================
# DASHBOARD ADMIN
# ==========================================
@verificar_rol(['Admin'])
def index(request):
    try:
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
    filtro = {"nombre": {"$regex": query, "$options": "i"}} if query else {}
        
    items_mongo = list(db.discograficas.find(filtro))
    
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
        
    if item:
        item['id_mongo'] = str(item['_id'])
        
    return render(request, 'discograficas/editar.html', {'item': item})

@verificar_rol(['Admin'])
def eliminar_discografica(request, id):
    try:
        filtro = {"_id": ObjectId(id)} if len(str(id)) == 24 else {"idDiscograficaSQL": int(id)}
        discografica = db.discograficas.find_one(filtro)
        
        if discografica:
            id_sql = discografica.get('idDiscograficaSQL')
            id_mongo = discografica['_id']
            
            condiciones_artistas = [
                {"idDiscografica": id_mongo},
                {"Discografica_idDiscografica": id_mongo},
                {"idDiscografica": str(id_mongo)},
                {"Discografica_idDiscografica": str(id_mongo)}
            ]
            
            if id_sql is not None:
                condiciones_artistas.extend([
                    {"idDiscografica": int(id_sql)},
                    {"Discografica_idDiscografica": int(id_sql)},
                    {"idDiscografica": str(id_sql)},
                    {"Discografica_idDiscografica": str(id_sql)}
                ])
            
            artistas_asociados = db.artistas.count_documents({"$or": condiciones_artistas})
            
            if artistas_asociados > 0:
                messages.error(request, f"Operación cancelada: La discográfica tiene {artistas_asociados} artista(s) vinculados.")
                return redirect('listar_discograficas')
                
            db.discograficas.delete_one({"_id": id_mongo})
            messages.success(request, f"La discográfica ha sido eliminada permanentemente.")
        else:
            messages.error(request, "Error: No se encontró el registro.")
            
    except Exception as e:
        messages.error(request, f"Error en MongoDB: {str(e)}")
        
    return redirect('listar_discograficas')


# ==========================================
# CRUD: ARTISTAS (100% MONGODB)
# ==========================================
@verificar_rol(['Admin'])
def listar_artistas(request):
    query = request.GET.get('q', '').strip()
    filtro = {"nombreArtistico": {"$regex": query, "$options": "i"}} if query else {}
        
    items_mongo = list(db.artistas.find(filtro))
    
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
    
    for item in items_mongo:
        item['id_mongo'] = str(item['_id'])
        item['idArtista'] = item.get('idArtistaSQL') or str(item['_id'])[-6:].upper()
        item['nombreArtistico'] = item.get('nombreArtistico') or item.get('nombre') or 'Desconocido'
        
        img_raw = item.get('imagen', 'default_artist.png')
        if img_raw and not img_raw.startswith('artistas/') and img_raw != 'default_artist.png':
            item['imagen_limpia'] = f"artistas/{img_raw}"
        else:
            item['imagen_limpia'] = img_raw

        disco_id = str(item.get('idDiscografica') or item.get('Discografica_idDiscografica') or '')
        disco_doc = dict_discos.get(disco_id)
        item['discografica_nombre'] = disco_doc.get('nombre', 'Independiente') if disco_doc else "Independiente"

        genero_id = str(item.get('genero') or item.get('generoPrincipal') or item.get('idGenero') or '')
        genero_name = "N/A"
        
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
            messages.success(request, f"Perfil creado correctamente.")
            return redirect('listar_artistas')
        except Exception as e:
            messages.error(request, f"Error en MongoDB: {str(e)}")

    discograficas = list(db.discograficas.find({}, {"_id": 1, "nombre": 1, "idDiscograficaSQL": 1}))
    for d in discograficas: d['idDiscografica'] = d.get('idDiscograficaSQL') or str(d['_id'])
        
    usuarios_artistas = list(db.usuarios.find({"$or": [{"rol": "Artista"}, {"rol": "Administrador"}]}))
    for u in usuarios_artistas: u['idUsuario'] = u.get('idUsuarioSQL') or str(u['_id'])
        
    generos = list(db.generos.find({}, {"_id": 1, "nombre": 1, "idGeneroSQL": 1}))
    for g in generos: g['idGenero'] = g.get('idGeneroSQL') or str(g['_id'])
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
            messages.success(request, f"Perfil actualizado correctamente.")
            return redirect('listar_artistas')
        except Exception as e:
            messages.error(request, f"Error al guardar en MongoDB: {str(e)}")

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
            
            albumes_vinculados = db.albumes.count_documents({
                "$or": [
                    {"idArtista": id_referencia},
                    {"Artista_idArtista": id_referencia},
                    {"idArtista": str(id_referencia)}
                ]
            })
            
            if albumes_vinculados > 0:
                messages.error(request, f"No se puede eliminar. El artista tiene {albumes_vinculados} álbum(es) registrado(s).")
                return redirect('listar_artistas')

            imagen_a_borrar = artista.get('imagen')
            db.artistas.delete_one(filtro)
            
            if imagen_a_borrar and imagen_a_borrar != 'default_artist.png':
                ruta_completa = os.path.join(settings.BASE_DIR, 'registros', 'static', 'images', imagen_a_borrar)
                if os.path.exists(ruta_completa):
                    try:
                        os.remove(ruta_completa)
                    except Exception:
                        pass

            messages.success(request, "Artista y su imagen asociada eliminados.")
        else:
            messages.error(request, "El artista no existe.")
            
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
    
    dict_artistas = {}
    for a in db.artistas.find():
        if a.get('idArtistaSQL') is not None: 
            dict_artistas[str(a['idArtistaSQL'])] = a
        dict_artistas[str(a['_id'])] = a
    
    for item in items_mongo:
        item['id_mongo'] = str(item['_id'])
        item['idAlbum'] = item.get('idAlbumSQL') or str(item['_id'])[-6:].upper()
        
        img_name = item.get('imagen')
        if img_name and img_name != 'default_album.png' and img_name != 'default_album.jpg':
            item['imagen_url'] = f"{settings.MEDIA_URL}albumes/{img_name}"
        else:
            item['imagen_url'] = None 
            
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

    item['id_mongo'] = str(item['_id'])
    
    artista_id_raw = item.get('idArtista') or item.get('Artista_idArtista')
    if artista_id_raw is not None:
        item['idArtista_actual'] = str(artista_id_raw).strip()
    else:
        item['idArtista_actual'] = ""
    
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

    artistas = list(db.artistas.find({}, {"_id": 1, "nombreArtistico": 1, "idArtistaSQL": 1}))
    for a in artistas: 
        artista_loop_id = a.get('idArtistaSQL') or a['_id']
        a['idArtista'] = str(artista_loop_id).strip()

    return render(request, 'albumes/editar.html', {'item': item, 'artistas': artistas})

@verificar_rol(['Admin'])
def eliminar_album(request, id):
    try:
        filtro = {"_id": ObjectId(id)} if len(str(id)) == 24 else {"idAlbumSQL": int(id)}
        album = db.albumes.find_one(filtro)
        
        if album:
            id_referencia = album.get('idAlbumSQL') or str(album['_id'])
            canciones_vinculadas = db.canciones.count_documents({
                "$or": [{"idAlbum": id_referencia}, {"Album_idAlbum": id_referencia}, {"idAlbum": str(id_referencia)}]
            })
            
            if canciones_vinculadas > 0:
                messages.error(request, f"No se puede eliminar. El álbum contiene canciones.")
                return redirect('listar_albumes')

            imagen_a_borrar = album.get('imagen')
            db.albumes.delete_one(filtro)
            
            if imagen_a_borrar and imagen_a_borrar != 'default_album.png':
                ruta_completa = os.path.join(settings.MEDIA_ROOT, 'albumes', imagen_a_borrar)
                if os.path.exists(ruta_completa): os.remove(ruta_completa)
                    
            messages.success(request, "Álbum eliminado.")
    except Exception as e:
        messages.error(request, f"Fallo al eliminar: {str(e)}")
        
    return redirect('listar_albumes')


# ==========================================
# CRUD: CANCIONES (100% MONGODB)
# ==========================================
@verificar_rol(['Admin'])
def listar_canciones(request):
    query = request.GET.get('q', '').strip()
    filtro = {"titulo": {"$regex": query, "$options": "i"}} if query else {}
        
    canciones_mongo = list(db.canciones.find(filtro))
    
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

    for cancion in canciones_mongo:
        cancion['id_mongo'] = str(cancion['_id'])
        cancion['idCancion'] = cancion.get('idCancionSQL') or str(cancion['_id'])[-6:].upper()
        
        segs = cancion.get('duracionSegundos') or cancion.get('duracion') or 0
        if isinstance(segs, int) and segs > 0:
            cancion['duracion_formateada'] = f"{segs // 60}:{segs % 60:02d}"
        else:
            cancion['duracion_formateada'] = "0:00"

        id_alb = str(cancion.get('idAlbum') or cancion.get('Album_idAlbum', ''))
        album_doc = dict_albumes.get(id_alb)
        
        cancion['album_titulo'] = album_doc.get('titulo') if album_doc else "Sencillo"

        if album_doc and album_doc.get('imagen') and album_doc.get('imagen') not in ['default_album.png', 'default_album.jpg', '']:
            img_name = album_doc.get('imagen')
            cancion['imagen_url'] = f"{settings.MEDIA_URL}albumes/{img_name}"
        else:
            cancion['imagen_url'] = None 

        id_art = str(cancion.get('idArtista') or cancion.get('Artista_idArtista', ''))
        artista_doc = dict_artistas.get(id_art)
        cancion['artista_nombre'] = artista_doc.get('nombreArtistico') if artista_doc else "Artista Independiente"

        nombres_generos = []
        for gen_item in cancion.get('generos', []):
            id_sql = str(gen_item.get('idSQL', ''))
            if id_sql and id_sql in dict_generos:
                nombres_generos.append(dict_generos[id_sql].get('nombre', ''))
                
        if not nombres_generos and isinstance(cancion.get('genero'), str):
            nombres_generos.append(cancion.get('genero'))
            
        cancion['generos_texto'] = ", ".join(nombres_generos) if nombres_generos else "Sin Género"

    return render(request, 'canciones/listar.html', {'items': canciones_mongo})

@verificar_rol(['Admin'])
def crear_cancion(request):
    if request.method == 'POST':
        titulo = request.POST.get('titulo')
        duracion = request.POST.get('duracion')
        pista = request.POST.get('numeroPista')
        fecha = request.POST.get('fechaLanzamiento')
        calidad = request.POST.get('calidadAudio')
        album_id = request.POST.get('album')
        
        # Opcional: Subida de MP3 u otra metadata si es necesario
        
        nueva_cancion = {
            "titulo": titulo,
            "duracionSegundos": int(duracion) if duracion and duracion.isdigit() else 0,
            "numeroPista": int(pista) if pista and pista.isdigit() else 1,
            "fechaLanzamiento": fecha,
            "calidadAudio": calidad,
            "idAlbum": album_id,
            # NOTA: Podrías buscar también el idArtista del álbum y agregarlo
        }
        
        db.canciones.insert_one(nueva_cancion)
        messages.success(request, "Canción creada correctamente en MongoDB.")
        return redirect('listar_canciones')

    # Cargar lista de álbumes para el Select
    albumes_mongo = list(db.albumes.find({}, {"_id": 1, "titulo": 1, "idAlbumSQL": 1}))
    for a in albumes_mongo:
        a['idAlbum'] = a.get('idAlbumSQL') or str(a['_id'])
        
    return render(request, 'canciones/crear.html', {'albumes': albumes_mongo})

@verificar_rol(['Admin'])
def editar_cancion(request, id):
    filtro = {"_id": ObjectId(id)} if len(str(id)) == 24 else {"idCancionSQL": int(id)}
    item = db.canciones.find_one(filtro)
    
    if not item:
        messages.error(request, "Canción no encontrada.")
        return redirect('listar_canciones')

    if request.method == 'POST':
        duracion = request.POST.get('duracion')
        pista = request.POST.get('numeroPista')
        fecha = request.POST.get('fechaLanzamiento') or item.get('fechaLanzamiento')

        db.canciones.update_one(filtro, {
            "$set": {
                "titulo": request.POST.get('titulo'),
                "duracionSegundos": int(duracion) if duracion and duracion.isdigit() else item.get('duracionSegundos'),
                "numeroPista": int(pista) if pista and pista.isdigit() else item.get('numeroPista'),
                "calidadAudio": request.POST.get('calidadAudio'),
                "fechaLanzamiento": fecha,
                "idAlbum": request.POST.get('album')
            }
        })
        messages.success(request, "Canción actualizada exitosamente.")
        return redirect('listar_canciones')

    item['id_mongo'] = str(item['_id'])
    
    # Manejo de la variable original de duración para el formulario
    item['duracion_raw'] = item.get('duracionSegundos') or item.get('duracion') or 0
    item['idAlbum_actual'] = str(item.get('idAlbum') or item.get('Album_idAlbum') or '')
    
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

    albumes_mongo = list(db.albumes.find({}, {"_id": 1, "titulo": 1, "idAlbumSQL": 1}))
    for a in albumes_mongo:
        a['idAlbum'] = str(a.get('idAlbumSQL') or a['_id'])

    return render(request, 'canciones/editar.html', {
        'item': item,
        'albumes': albumes_mongo
    })

@verificar_rol(['Admin'])
def eliminar_cancion(request, id):
    if request.method == 'POST':
        try:
            filtro = {"_id": ObjectId(id)} if len(str(id)) == 24 else {"idCancionSQL": int(id)}
            db.canciones.delete_one(filtro)
            messages.success(request, "Canción eliminada permanentemente.")
        except Exception as e:
            messages.error(request, f"Error al eliminar en MongoDB: {e}")
            
    return redirect('listar_canciones')


# ==========================================
# CRUD: GENEROS - MONGODB
# ==========================================
@verificar_rol(['Admin'])
def listar_generos(request):
    query = request.GET.get('q', '').strip()
    filtro = {"nombre": {"$regex": query, "$options": "i"}} if query else {}
        
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
            nombre_gen = genero.get('nombre')
            usos_artistas = db.artistas.count_documents({"genero": nombre_gen})
            
            if usos_artistas > 0:
                messages.error(request, f"No se puede eliminar. Hay {usos_artistas} artista(s) usando el género.")
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
                    messages.success(request, f"Plan '{nombre}' creado.")
                    return redirect('listar_planes')
                except ValueError:
                    messages.error(request, "Error: Precio y duración deben ser numéricos.")
                    
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
            messages.error(request, "Error: Precio y duración numéricos.")
            
    item['id_mongo'] = str(item['_id'])
    if item.get('precio') is not None:
        item['precio_formateado'] = f"{float(item['precio']):.2f}"
        
    return render(request, 'planes/editar.html', {'item': item})

@verificar_rol(['Admin'])
def eliminar_plan(request, id):
    try:
        filtro = {"_id": ObjectId(id)} if len(str(id)) == 24 else {"idPlanSQL": int(id)}
        plan = db.planes.find_one(filtro)
        
        if plan:
            nombre_plan = plan.get('nombre')
            usuarios_suscritos = db.usuarios.count_documents({"suscripcion.plan": nombre_plan})
            
            id_ref = plan.get('idPlanSQL')
            condiciones_pagos = [{"plan": nombre_plan}]
            if id_ref: condiciones_pagos.append({"idPlan": int(id_ref)})
            
            pagos_vinculados = db.pagos.count_documents({"$or": condiciones_pagos})
            
            if usuarios_suscritos > 0 or pagos_vinculados > 0:
                messages.error(request, f"Plan en uso. Protegido por integridad NoSQL.")
            else:
                db.planes.delete_one(filtro)
                messages.success(request, f"Plan eliminado.")
        else:
            messages.error(request, "Plan no encontrado.")
            
    except Exception as e:
        messages.error(request, f"Error MongoDB: {str(e)}")
        
    return redirect('listar_planes')
    
# ==========================================
# SISTEMA DE AUTENTICACIÓN (100% MONGODB)
# ==========================================
def login_view(request):
    if 'usuario_id' in request.session:
        rol_activo = request.session.get('usuario_rol', 'Cliente') 
        if rol_activo == 'Admin':
            return redirect('index') 
        elif rol_activo == 'Artista':
            return redirect('dashboard_artista')
        else:
            return redirect('dashboard_usuario')

    if request.method == 'POST':
        correo = request.POST.get('correo', '').strip()
        password_ingresada = request.POST.get('contrasenia', '')

        if not correo or not password_ingresada:
            messages.error(request, 'Complete todos los campos.')
            return render(request, 'login.html')

        try:
            usuario = db.usuarios.find_one({
                "correo": correo,
                "contrasenia": password_ingresada
            })

            if usuario:
                if usuario.get('estado') != 'Activo':
                    messages.error(request, 'Cuenta inactiva.')
                    return render(request, 'login.html')

                request.session['usuario_id'] = str(usuario['_id'])
                
                rol_bd = usuario.get('rol', 'Cliente')
                if rol_bd == 'Administrador':
                    request.session['usuario_rol'] = 'Admin'
                else:
                    request.session['usuario_rol'] = rol_bd

                request.session['nombre'] = usuario.get('nombre', '')
                request.session['apellido'] = usuario.get('apellido', '')

                rol = request.session['usuario_rol']
                
                if rol == 'Admin':
                    return redirect('index') 
                elif rol == 'Artista':
                    return redirect('dashboard_artista') 
                else:
                    return redirect('dashboard_usuario') 

            else:
                messages.error(request, 'Credenciales incorrectas.')

        except Exception as e:
            messages.error(request, f'Error BD: {str(e)}')

    return render(request, 'auth/login.html')

def registro_view(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        apellido = request.POST.get('apellido', '').strip()
        correo = request.POST.get('correo', '').strip()
        contrasenia = request.POST.get('contrasenia', '').strip()
        fecha_nacimiento = request.POST.get('fecha_nacimiento', '').strip()
        
        if not all([nombre, apellido, correo, contrasenia, fecha_nacimiento]):
            messages.error(request, "Completa todos los campos obligatorios.")
            return render(request, 'auth/registro.html')

        try:
            if db.usuarios.find_one({"correo": correo}):
                messages.error(request, "Este correo ya está en uso.")
                return render(request, 'auth/registro.html')
            
            nuevo_usuario = {
                "nombre": nombre,
                "apellido": apellido,
                "correo": correo,
                "contrasenia": contrasenia,
                "fechaNacimiento": fecha_nacimiento,
                "fechaRegistro": datetime.now(),
                "estado": "Activo",
                "rol": "Cliente",
                "imagen": "usuario_nuevo.png",
                "suscripcion": {
                    "plan": "Free",
                    "estado": "Activa"
                }
            }
            
            db.usuarios.insert_one(nuevo_usuario)
            messages.success(request, "¡Cuenta creada con éxito! Inicia sesión.")
            return redirect('login')
            
        except Exception as e:
            messages.error(request, f"Error NoSQL: {str(e)}")

    return render(request, 'auth/registro.html')

def logout_view(request):
    request.session.flush()
    messages.success(request, "Sesión cerrada correctamente.")
    return redirect('login')


# ==========================================
# DASHBOARDS E INTEGRACIÓN MONGODB
# ==========================================
@verificar_rol(['Cliente', 'Admin'])
def dashboard_usuario(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return redirect('login')

    top_canciones = []
    playlists_usuario = []
    auto_open_id = request.session.pop('auto_open_playlist_id', None)
    
    # 1. Búsqueda robusta del usuario actual
    try:
        user_query = {"_id": ObjectId(usuario_id)}
    except:
        user_query = {"idUsuarioSQL": int(usuario_id)}
        
    usuario = db.usuarios.find_one(user_query)
    plan_info = {'plan_nombre': 'Free', 'suscripcion_estado': 'Inactiva'}
    
    if usuario:
        # Extraemos su ID oficial o SQL para las consultas siguientes
        id_real_usuario = usuario.get('idUsuarioSQL') or str(usuario['_id'])
        
        if 'suscripcion' in usuario:
            plan_info = {
                'plan_nombre': usuario['suscripcion'].get('plan', 'Free'),
                'suscripcion_estado': usuario['suscripcion'].get('estado', 'Activa')
            }

        # 2. Cargar Playlists del usuario
        condicion_playlists = [
            {"idUsuario": str(id_real_usuario)},
            {"idUsuario": int(id_real_usuario) if str(id_real_usuario).isdigit() else None},
            {"idUsuarioSQL": int(id_real_usuario) if str(id_real_usuario).isdigit() else None}
        ]
        
        try:
            playlists_mongo = list(db.playlists.find({"$or": condicion_playlists}))
            for p in playlists_mongo:
                # Retornamos el ID de mongo y el nombre para el panel lateral
                playlists_usuario.append((str(p['_id']), p.get('nombre', 'Sin nombre')))
        except Exception as e:
            print(f"Error cargando Playlists: {e}")

        # 3. AGGREGATION PIPELINE: "Lo que más escuchas" (Top 5 del usuario)
        try:
            pipeline_top = [
                # a) Filtramos solo reproducciones de este usuario
                {
                    "$match": {
                        "$or": [
                            {"idUsuario": str(id_real_usuario)},
                            {"idUsuario": int(id_real_usuario) if str(id_real_usuario).isdigit() else None},
                            {"idUsuarioSQL": int(id_real_usuario) if str(id_real_usuario).isdigit() else None}
                        ]
                    }
                },
                # b) Agrupamos por canción y sumamos reproducciones y minutos
                {
                    "$group": {
                        "_id": "$idCancionSQL", 
                        "reproducciones": {"$sum": 1},
                        "total_escuchado": {"$sum": "$duracionEscuchada"}
                    }
                },
                # c) Ordenamos por lo más escuchado
                {"$sort": {"reproducciones": -1}},
                {"$limit": 5},
                # d) Traemos los datos de la canción
                {
                    "$lookup": {
                        "from": "canciones",
                        "localField": "_id",
                        "foreignField": "idCancionSQL", 
                        "as": "cancion_info"
                    }
                },
                {"$unwind": {"path": "$cancion_info", "preserveNullAndEmptyArrays": True}}
            ]
            
            resultados_top = list(db.reproducciones.aggregate(pipeline_top))
            
            # Traer artistas a memoria RAM O(1) para cruzar rápido
            dict_art = {str(a.get('idArtistaSQL') or a['_id']): a.get('nombreArtistico', 'Desconocido') for a in db.artistas.find()}
            
            for r in resultados_top:
                c_info = r.get('cancion_info', {})
                if c_info:
                    id_art = str(c_info.get('idArtista') or '')
                    # Formato de tiempo (minutos y segundos)
                    segs = c_info.get('duracionSegundos') or c_info.get('duracion') or 0
                    duracion_fmt = f"{segs // 60}:{segs % 60:02d}" if isinstance(segs, int) else "0:00"

                    top_canciones.append({
                        'idCancion': c_info.get('idCancionSQL') or str(c_info['_id']),
                        'titulo': c_info.get('titulo', 'Desconocido'),
                        'artista_nombre': dict_art.get(id_art, 'Desconocido'),
                        'duracion': duracion_fmt,
                        'calidadAudio': c_info.get('calidadAudio', 'Estándar')
                    })
        except Exception as e:
            print(f"Error Pipeline Top: {e}")

    # 4. RECOMENDACIONES (Aleatorias)
    recomendaciones = request.session.get('recomendaciones_cache')
    if not recomendaciones:
        recomendaciones = []
        try:
            dict_art = {str(a.get('idArtistaSQL') or a['_id']): a.get('nombreArtistico', 'Desconocido') for a in db.artistas.find()}
            recs_mongo = list(db.canciones.aggregate([{"$sample": {"size": 5}}]))
            
            for c in recs_mongo:
                id_art = str(c.get('idArtista') or '')
                segs = c.get('duracionSegundos') or c.get('duracion') or 0
                duracion_fmt = f"{segs // 60}:{segs % 60:02d}" if isinstance(segs, int) else "0:00"

                recomendaciones.append({
                    'idCancion': c.get('idCancionSQL') or str(c['_id']),
                    'titulo': c.get('titulo', 'Desconocido'),
                    'artista_nombre': dict_art.get(id_art, 'Desconocido'),
                    'duracion': duracion_fmt,
                    'calidadAudio': c.get('calidadAudio', 'Estándar')
                })
            request.session['recomendaciones_cache'] = recomendaciones
        except Exception:
            pass

    # ========================================================
    # CONTEXT
    # ========================================================
    context = {
        'top_canciones': top_canciones,
        'recomendaciones': recomendaciones,
        'plan_info': plan_info,
        'playlists': playlists_usuario,
        'auto_open_playlist_id': auto_open_id,
        'usuario_nombre': f"{usuario.get('nombre', '')} {usuario.get('apellido', '')}" if usuario else ""
    }
    
    return render(request, 'dashboards/usuario.html', context)

def _obtener_artista_de_sesion(request):
    """Busca el documento de artista vinculado al usuario en sesión,
    contemplando los distintos formatos de idUsuario heredados de la
    migración SQL -> Mongo (ObjectId nuevo o idUsuarioSQL viejo)."""
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return None

    try:
        usuario_obj = db.usuarios.find_one({"_id": ObjectId(usuario_id)})
    except Exception:
        usuario_obj = None

    if not usuario_obj:
        return None

    id_mongo_str = str(usuario_obj['_id'])
    id_sql = usuario_obj.get('idUsuarioSQL')

    condiciones_busqueda = [
        {"idUsuario": id_mongo_str},
        {"Usuario_idUsuario": id_mongo_str},
        {"idUsuario": usuario_obj['_id']}
    ]

    if id_sql is not None:
        condiciones_busqueda.extend([
            {"idUsuario": str(id_sql)},
            {"idUsuario": int(id_sql)},
            {"Usuario_idUsuario": str(id_sql)},
            {"Usuario_idUsuario": int(id_sql)}
        ])

    return db.artistas.find_one({
        "$and": [
            {"$or": condiciones_busqueda},
            {"idUsuario": {"$ne": ""}},
            {"idUsuario": {"$ne": None}}
        ]
    })

@verificar_rol(['Artista', 'Admin'])
def dashboard_artista(request):
    if not request.session.get('usuario_id'):
        messages.error(request, "Sesión inválida. Por favor, inicia sesión de nuevo.")
        return redirect('login')

    artista = _obtener_artista_de_sesion(request)

    if not artista:
        messages.warning(request, "Tu cuenta de artista no tiene un perfil vinculado. Contacta a un administrador.")
        return render(request, 'dashboards/artista.html', {
            'artista': None, 'total_reproducciones': 0, 'total_regalias': 0.0, 'canciones_recientes': []
        })

    id_artista_metrica = artista.get('idArtistaSQL') or str(artista['_id'])

    total_reproducciones = 0
    total_regalias = 0.0

    try:
        pipeline_reproducciones = [
            {
                "$lookup": {
                    "from": "canciones",
                    "localField": "idCancion",
                    "foreignField": "idCancionSQL",
                    "as": "cancion_info"
                }
            },
            { "$unwind": "$cancion_info" },
            {
                "$match": {
                    "$or": [
                        {"cancion_info.idArtista": id_artista_metrica},
                        {"cancion_info.idArtista": int(id_artista_metrica) if str(id_artista_metrica).isdigit() else None}
                    ]
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_segundos": {"$sum": "$duracionEscuchada"}
                }
            }
        ]

        resultado_rep = list(db.reproducciones.aggregate(pipeline_reproducciones))
        if resultado_rep:
            total_reproducciones = round(resultado_rep[0].get('total_segundos', 0) / 60)

        pipeline_regalias = [
            {
                "$match": {
                    "$or": [
                        {"idArtista": id_artista_metrica},
                        {"idArtista": int(id_artista_metrica) if str(id_artista_metrica).isdigit() else None}
                    ]
                }
            },
            {
                "$group": {
                    "_id": None,
                    "total_dinero": {"$sum": "$monto"}
                }
            }
        ]

        resultado_reg = list(db.regalias.aggregate(pipeline_regalias))
        if resultado_reg:
            total_regalias = round(resultado_reg[0].get('total_dinero', 0.0), 2)

    except Exception as e:
        print(f"[ERROR Métricas Artista]: {str(e)}")

    canciones_artista = list(db.canciones.find({
        "$or": [
            {"idArtista": id_artista_metrica},
            {"idArtista": int(id_artista_metrica) if str(id_artista_metrica).isdigit() else None}
        ]
    }).limit(5))

    for c in canciones_artista:
        segs = c.get('duracionSegundos') or c.get('duracion') or 0
        if isinstance(segs, int) and segs > 0:
            c['duracion_formateada'] = f"{segs // 60}:{segs % 60:02d}"
        else:
            c['duracion_formateada'] = "0:00"

    artista_context = {
        'nombreArtistico': artista.get('nombreArtistico') or artista.get('nombre') or 'Desconocido',
        'verificado': bool(artista.get('verificado', False)),
        'genero': artista.get('genero') or artista.get('generoPrincipal') or 'Independiente',
        'pais': artista.get('pais', 'No especificado'),
        'biografia': artista.get('biografia', 'Sin biografía disponible.')
    }

    img_name = artista.get('imagen')
    if img_name and img_name != 'default_artist.png':
        if not img_name.startswith('artistas/'):
            img_name = f"artistas/{img_name}"
        artista_context['imagen_url'] = f"{settings.STATIC_URL}images/{img_name}"
    else:
        artista_context['imagen_url'] = f"{settings.STATIC_URL}images/default_artist.png"

    # CARGAR ÁLBUMES DEL ARTISTA PARA EL MODAL (comparando string e int)
    id_artista_str = str(id_artista_metrica)
    id_artista_int = int(id_artista_str) if id_artista_str.isdigit() else None

    condiciones_albumes = [
        {"idArtista": id_artista_str},
        {"idArtista": id_artista_int},
        {"Artista_idArtista": id_artista_str},
        {"Artista_idArtista": id_artista_int}
    ]

    albumes_artista_db = list(db.albumes.find({"$or": condiciones_albumes}))
    for alb in albumes_artista_db:
        alb['id_mongo'] = str(alb['_id'])

    context = {
        'artista': artista_context,
        'total_reproducciones': total_reproducciones,
        'total_regalias': total_regalias,
        'canciones_recientes': canciones_artista,
        'albums_artista': albumes_artista_db
    }

    return render(request, 'dashboards/artista.html', context)

# ==========================================
# PROCESOS COMPLEMENTARIOS (PAGOS, MANTENIMIENTO, PLAYLISTS)
# ==========================================

@verificar_rol(['Cliente', 'Admin'])
def procesar_pago(request):
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return redirect('login')
        
    if request.method == 'POST':
        metodo = request.POST.get('metodo') 
        monto = 9.99 
        
        try:
            try:
                user_query = {"_id": ObjectId(usuario_id)}
            except:
                user_query = {"idUsuarioSQL": int(usuario_id)}
                
            db.usuarios.update_one(
                user_query,
                {"$set": {
                    "suscripcion.plan": "Premium",
                    "suscripcion.estado": "Activa"
                }}
            )
            
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
    if 'usuario_id' not in request.session or request.session.get('usuario_rol') != 'Admin':
        messages.error(request, "Acceso denegado. Exclusivo para administradores.")
        return redirect('login')
        
    try:
        fecha_actual = datetime.now()
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
            
        messages.success(request, f"⚙️ Mantenimiento completado: Se degradaron {resultado.modified_count} suscripciones.")
    except Exception as e:
        messages.error(request, f"Error Mantenimiento NoSQL: {str(e)}")
        
    return redirect('index')

@verificar_rol(['Cliente', 'Admin'])
def registrar_reproduccion(request, id_cancion):
    usuario_id = request.session.get('usuario_id')
    
    try:
        usuario_mongo = db.usuarios.find_one({"idUsuarioSQL": int(usuario_id) if str(usuario_id).isdigit() else usuario_id})
        
        if not usuario_mongo:
            return JsonResponse({'status': 'error', 'message': 'Usuario no encontrado.'}, status=404)
            
        if usuario_mongo.get('estado') != 'Activo':
            return JsonResponse({'status': 'error', 'message': 'Cuenta inactiva.'}, status=403)

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
        return JsonResponse({'status': 'success', 'message': 'Reproducción registrada.'})
        
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': f'Fallo BD: {str(e)}'}, status=500)

@verificar_rol(['Artista', 'Admin'])
def _obtener_artista_de_sesion(request):
    """Busca el documento de artista vinculado al usuario en sesión,
    contemplando los distintos formatos de idUsuario heredados de la migración SQL -> Mongo."""
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return None

    try:
        usuario_obj = db.usuarios.find_one({"_id": ObjectId(usuario_id)})
    except Exception:
        usuario_obj = None

    if not usuario_obj:
        return None

    id_mongo_str = str(usuario_obj['_id'])
    id_sql = usuario_obj.get('idUsuarioSQL')

    condiciones_busqueda = [
        {"idUsuario": id_mongo_str},
        {"Usuario_idUsuario": id_mongo_str},
        {"idUsuario": usuario_obj['_id']}
    ]

    if id_sql is not None:
        condiciones_busqueda.extend([
            {"idUsuario": str(id_sql)},
            {"idUsuario": int(id_sql)},
            {"Usuario_idUsuario": str(id_sql)},
            {"Usuario_idUsuario": int(id_sql)}
        ])

    return db.artistas.find_one({
        "$and": [
            {"$or": condiciones_busqueda},
            {"idUsuario": {"$ne": ""}},
            {"idUsuario": {"$ne": None}}
        ]
    })
@verificar_rol(['Artista', 'Admin'])
def crear_album_artista(request):
    artista = _obtener_artista_de_sesion(request)

    if not artista:
        messages.error(request, "Tu cuenta de artista no tiene un perfil vinculado. Contacta a un administrador.")
        return redirect('dashboard_artista')

    artista_id = artista.get('idArtistaSQL') or str(artista['_id'])

    if request.method == 'POST':
        titulo = request.POST.get('titulo')
        fecha_lanzamiento = request.POST.get('fecha_lanzamiento')
        imagen = request.FILES.get('imagen')

        imagen_nombre = "default_album.jpg"
        if imagen:
            fs = FileSystemStorage(location='media/albumes/')
            filename = fs.save(imagen.name, imagen)
            imagen_nombre = filename

        nuevo_album = {
            "titulo": titulo,
            "fechaLanzamiento": fecha_lanzamiento,
            "imagen": imagen_nombre,
            "idArtista": str(artista_id)
        }

        try:
            db.albumes.insert_one(nuevo_album)
            messages.success(request, "Álbum añadido.")
            return redirect('dashboard_artista')
        except Exception as e:
            messages.error(request, f"Error al registrar álbum: {e}")

    return redirect('dashboard_artista')


@verificar_rol(['Artista', 'Admin'])
def _obtener_artista_de_sesion(request):
    """Busca el documento de artista vinculado al usuario en sesión,
    contemplando los distintos formatos de idUsuario heredados de la migración SQL -> Mongo."""
    usuario_id = request.session.get('usuario_id')
    if not usuario_id:
        return None

    try:
        usuario_obj = db.usuarios.find_one({"_id": ObjectId(usuario_id)})
    except Exception:
        usuario_obj = None

    if not usuario_obj:
        return None

    id_mongo_str = str(usuario_obj['_id'])
    id_sql = usuario_obj.get('idUsuarioSQL')

    condiciones_busqueda = [
        {"idUsuario": id_mongo_str},
        {"Usuario_idUsuario": id_mongo_str},
        {"idUsuario": usuario_obj['_id']}
    ]

    if id_sql is not None:
        condiciones_busqueda.extend([
            {"idUsuario": str(id_sql)},
            {"idUsuario": int(id_sql)},
            {"Usuario_idUsuario": str(id_sql)},
            {"Usuario_idUsuario": int(id_sql)}
        ])

    return db.artistas.find_one({
        "$and": [
            {"$or": condiciones_busqueda},
            {"idUsuario": {"$ne": ""}},
            {"idUsuario": {"$ne": None}}
        ]
    })
@verificar_rol(['Artista', 'Admin'])
def subir_cancion_artista(request):
    artista = _obtener_artista_de_sesion(request)

    if not artista:
        messages.error(request, "Tu cuenta de artista no tiene un perfil vinculado. Contacta a un administrador.")
        return redirect('dashboard_artista')

    artista_id = artista.get('idArtistaSQL') or str(artista['_id'])

    if request.method == 'POST':
        titulo = request.POST.get('titulo')
        duracion = request.POST.get('duracion')
        calidad = request.POST.get('calidadAudio', 'Estándar')
        album_id = request.POST.get('album_id')

        try:
            num_pista = db.canciones.count_documents({
                "$or": [{"idAlbum": album_id}, {"idAlbum": str(album_id)}]
            }) + 1

            nueva_cancion = {
                "titulo": titulo,
                "duracionSegundos": int(duracion) if duracion and duracion.isdigit() else 0,
                "calidadAudio": calidad,
                "numeroPista": num_pista,
                "idArtista": str(artista_id),
                "idAlbum": str(album_id)
            }

            db.canciones.insert_one(nueva_cancion)
            messages.success(request, "Pista subida exitosamente.")
            return redirect('dashboard_artista')

        except Exception as e:
            messages.error(request, f"Error al subir canción: {e}")

    return redirect('dashboard_artista')

@verificar_rol(['Cliente', 'Admin'])
def crear_playlist_usuario(request):
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        usuario_id = request.session.get('usuario_id')
        
        if not nombre or len(nombre) < 3:
            messages.error(request, "Nombre inválido.")
            return redirect('dashboard_usuario')
            
        try:
            nueva_playlist = {
                "idUsuarioSQL": int(usuario_id) if str(usuario_id).isdigit() else usuario_id,
                "nombre": nombre,
                "descripcion": "Playlist generada",
                "colaborativa": False,
                "fechaCreacion": datetime.now(),
                "canciones": [] 
            }
            
            db.playlists.insert_one(nueva_playlist)
            messages.success(request, f"Playlist creada en MongoDB 🍃")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
            
    return redirect('dashboard_usuario')


@verificar_rol(['Cliente', 'Admin'])
def obtener_detalles_playlist(request, id_playlist):
    try:
        playlist_mongo = db.playlists.find_one({"_id": ObjectId(id_playlist)})
        if not playlist_mongo:
            return JsonResponse({'status': 'error', 'message': 'No encontrada.'}, status=404)
        
        canciones_array = playlist_mongo.get('canciones', [])
        ids_guardadas = [c.get('idCancionSQL') for c in canciones_array]
        
        canciones_guardadas = []
        todas_canciones = []
        
        catalogo = list(db.canciones.find({}, {"_id": 1, "idCancionSQL": 1, "titulo": 1}))
        
        for pista in catalogo:
            pista_id = pista.get('idCancionSQL') or str(pista['_id'])
            pista_dict = {'id': pista_id, 'titulo': pista.get('titulo', 'Sin título')}
            
            todas_canciones.append(pista_dict)
            
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
        playlist_actual = db.playlists.find_one({"_id": ObjectId(id_playlist)})
        if any(c.get("idCancionSQL") == int(id_cancion) for c in playlist_actual.get("canciones", [])):
            return JsonResponse({'status': 'error', 'message': 'Ya existe en playlist.'}, status=400)

        db.playlists.update_one(
            {"_id": ObjectId(id_playlist)},
            {"$push": {
                "canciones": {
                    "idCancionSQL": int(id_cancion),
                    "fechaAgregada": datetime.now() 
                }
            }}
        )
        return JsonResponse({'status': 'success', 'message': 'Agregada.'})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=500)


@verificar_rol(['Cliente', 'Admin'])
def eliminar_playlist_mongo(request, id_playlist):
    try:
        db.playlists.delete_one({"_id": ObjectId(id_playlist)})
        messages.success(request, "Playlist eliminada de MongoDB.")
    except Exception as e:
        messages.error(request, f"Error BD: {str(e)}")
    return redirect('dashboard_usuario')