from django.db import models

# ESQUEMA USUARIOS

class Rol(models.Model):
    idRol = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=30)
    
    class Meta:
        managed = False
        db_table = '[Usuarios].[Rol]'  # Ajusta el nombre exacto de tu esquema/tabla de roles si varía

    def __str__(self):
        return self.nombre

class Usuario(models.Model):
    idUsuario = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50)
    apellido = models.CharField(max_length=50)
    correo = models.CharField(max_length=100, unique=True)
    contrasenia = models.CharField(max_length=250)
    fechaRegistro = models.DateField()
    estado = models.CharField(max_length=15, default='Activo')
    imagen = models.CharField(max_length=255, default='default.png')
    fechaNacimiento = models.DateField()
    # NUEVO CAMPO OBLIGATORIO:
    Rol_idRol = models.ForeignKey(Rol, db_column='Rol_idRol', on_delete=models.PROTECT, default=2)

    class Meta:
        managed = False  
        db_table = '[Usuarios].[Usuario]'

    def __str__(self):
        return f"{self.nombre} {self.apellido}"


class Playlist(models.Model):
    idPlaylist = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    fechaCreacion = models.DateField()
    privacidad = models.CharField(max_length=15, default='Privada')
    descripcion = models.CharField(max_length=255)
    colaborativa = models.BooleanField()
    Usuario_idUsuario = models.ForeignKey('Usuario', db_column='Usuario_idUsuario', on_delete=models.CASCADE)

    class Meta:
        managed = False
        db_table = '[Usuarios].[Playlist]'


class Notificacion(models.Model):
    idNotificacion = models.AutoField(primary_key=True)
    contenido = models.CharField(max_length=255)
    fecha = models.DateTimeField()
    tipo = models.CharField(max_length=30)
    Usuario_idUsuario = models.ForeignKey('Usuario', db_column='Usuario_idUsuario', on_delete=models.CASCADE)

    class Meta:
        managed = False
        db_table = '[Usuarios].[Notificacion]'

# ESQUEMA CATALOGOS

class Discografica(models.Model):
    idDiscografica = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    pais = models.CharField(max_length=50)
    fechaFundacion = models.DateField()
    logo = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = '[Catalogo].[Discografica]'

    def __str__(self):
        return self.nombre


class Artista(models.Model):
    idArtista = models.AutoField(primary_key=True)
    nombreArtistico = models.CharField(max_length=50, db_column='nombre')  # En tu SQL se llama 'nombre'
    pais = models.CharField(max_length=50)
    fechaCreacion = models.DateField()
    imagen = models.CharField(max_length=255, default='default_artist.png')
    biografia = models.CharField(max_length=500)
    Discografica_idDiscografica = models.ForeignKey('Discografica', db_column='Discografica_idDiscografica', on_delete=models.PROTECT)

    class Meta:
        managed = False
        db_table = '[Catalogo].[Artista]'

    def __str__(self):
        return self.nombreArtistico


class Album(models.Model):
    idAlbum = models.AutoField(primary_key=True)
    titulo = models.CharField(max_length=100)
    fechaLanzamiento = models.DateField()
    Artista_idArtista = models.ForeignKey(Artista, db_column='Artista_idArtista', on_delete=models.CASCADE)
    imagen = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = '[Catalogo].[Album]'

    def __str__(self):
        return self.titulo


class Cancion(models.Model):
    idCancion = models.AutoField(primary_key=True)
    titulo = models.CharField(max_length=100)
    duracion = models.IntegerField()
    numeroPista = models.IntegerField()
    fechaLanzamiento = models.DateField()
    calidadAudio = models.CharField(max_length=20, default='Alta')
    Album_idAlbum = models.ForeignKey(Album, db_column='Album_idAlbum', on_delete=models.CASCADE)
    imagen = models.CharField(max_length=255)

    class Meta:
        managed = False
        db_table = '[Catalogo].[Cancion]'

    def __str__(self):
        return self.titulo


class Genero(models.Model):
    idGenero = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50)

    class Meta:
        managed = False
        db_table = '[Catalogo].[Genero]'

    def __str__(self):
        return self.nombre

# ESQUEMA FACTURACION

class PlanEntity(models.Model):
    idPlan = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50, default='Free')
    precio = models.DecimalField(max_digits=8, decimal_places=2)
    duracionDias = models.IntegerField()

    class Meta:
        managed = False
        db_table = '[Facturacion].[PlanEntity]'

    def __str__(self):
        return self.nombre


# ==========================================
# TABLAS INTERMEDIAS Y ADICIONALES (Mantenidas por Integridad)
# ==========================================

class CancionGenero(models.Model):
    Cancion_idCancion = models.ForeignKey(Cancion, db_column='Cancion_idCancion', on_delete=models.CASCADE)
    Genero_idGenero = models.ForeignKey(Genero, db_column='Genero_idGenero', on_delete=models.CASCADE)
    class Meta:
        managed = False
        db_table = '[Catalogo].[CancionGenero]'
        unique_together = ('Cancion_idCancion', 'Genero_idGenero')

class PlaylistCancion(models.Model):
    Playlist_idPlaylist = models.ForeignKey(Playlist, db_column='Playlist_idPlaylist', on_delete=models.CASCADE)
    Cancion_idCancion = models.ForeignKey(Cancion, db_column='Cancion_idCancion', on_delete=models.CASCADE)
    fechaAgregada = models.DateField()
    class Meta:
        managed = False
        db_table = '[Usuarios].[PlaylistCancion]'
        unique_together = ('Playlist_idPlaylist', 'Cancion_idCancion')

class Reproduccion(models.Model):
    idReproduccion = models.AutoField(primary_key=True)
    fechaHora = models.DateTimeField()
    dispositivo = models.CharField(max_length=50)
    pais = models.CharField(max_length=50)
    duracionEscuchada = models.IntegerField()
    completada = models.BooleanField()
    Usuario_idUsuario = models.ForeignKey('Usuario', db_column='Usuario_idUsuario', on_delete=models.CASCADE)
    Cancion_idCancion = models.ForeignKey('Cancion', db_column='Cancion_idCancion', on_delete=models.CASCADE)

    class Meta:
        managed = False
        db_table = '[Usuarios].[Reproduccion]'
        
class UsuarioArtista(models.Model):
    Usuario_idUsuario = models.ForeignKey('Usuario', db_column='Usuario_idUsuario', on_delete=models.CASCADE, primary_key=True)
    Artista_idArtista = models.ForeignKey('Artista', db_column='Artista_idArtista', on_delete=models.CASCADE)
    fechaSeguimiento = models.DateField()

    class Meta:
        managed = False
        db_table = '[Usuarios].[UsuarioArtista]'
        unique_together = ('Usuario_idUsuario', 'Artista_idArtista')

# --- NUEVAS TABLAS AGREGADAS PARA EVITAR ERRORES DE INTEGRIDAD AL ELIMINAR USUARIOS ---

class UsuarioAlbum(models.Model):
    Usuario_idUsuario = models.ForeignKey('Usuario', db_column='Usuario_idUsuario', on_delete=models.CASCADE, primary_key=True)
    Album_idAlbum = models.ForeignKey('Album', db_column='Album_idAlbum', on_delete=models.CASCADE)
    class Meta:
        managed = False
        db_table = '[Usuarios].[UsuarioAlbum]'
        unique_together = ('Usuario_idUsuario', 'Album_idAlbum')

class UsuarioCancion(models.Model):
    Usuario_idUsuario = models.ForeignKey('Usuario', db_column='Usuario_idUsuario', on_delete=models.CASCADE, primary_key=True)
    Cancion_idCancion = models.ForeignKey('Cancion', db_column='Cancion_idCancion', on_delete=models.CASCADE)
    fechaAgregada = models.DateField()
    class Meta:
        managed = False
        db_table = '[Usuarios].[UsuarioCancion]'
        unique_together = ('Usuario_idUsuario', 'Cancion_idCancion')

class Suscripcion(models.Model):
    idSuscripcion = models.AutoField(primary_key=True)
    fechaInicio = models.DateField()
    fechaFin = models.DateField()
    estado = models.CharField(max_length=15, default='Inactiva')
    Usuario_idUsuario = models.ForeignKey('Usuario', db_column='Usuario_idUsuario', on_delete=models.CASCADE)
    PlanEntity_idPlan = models.ForeignKey('PlanEntity', db_column='PlanEntity_idPlan', on_delete=models.CASCADE)
    class Meta:
        managed = False
        db_table = '[Facturacion].[Suscripcion]'