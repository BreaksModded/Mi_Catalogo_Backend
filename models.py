from sqlalchemy import Column, Integer, String, Float, Boolean, Table, ForeignKey, DateTime, Date, func
from sqlalchemy.orm import relationship
from datetime import datetime
import unicodedata
from database import Base

def normalize_str(s):
    if s is None:
        return ''
    return ''.join(
        c for c in unicodedata.normalize('NFD', str(s).lower())
        if unicodedata.category(c) != 'Mn'
    )

# Tabla intermedia para la relación muchos-a-muchos Media <-> Keyword
media_keyword = Table(
    'media_keyword', Base.metadata,
    Column('media_id', Integer, ForeignKey('media.id'), primary_key=True),
    Column('keyword_id', Integer, ForeignKey('keyword.id'), primary_key=True)
)

# Tabla intermedia para la relación muchos-a-muchos Media <-> Tag
# Incluye usuario_id para garantizar que solo se asocien media y tags del mismo usuario
media_tag = Table(
    'media_tag', Base.metadata,
    Column('media_id', Integer, ForeignKey('media.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tag.id'), primary_key=True),
    Column('usuario_id', Integer, ForeignKey('usuario.id'), primary_key=True, index=True)
)

# Tabla intermedia para la relación muchos-a-muchos Lista <-> Media
lista_media = Table(
    'lista_media', Base.metadata,
    Column('lista_id', Integer, ForeignKey('lista.id'), primary_key=True),
    Column('media_id', Integer, ForeignKey('media.id'), primary_key=True),
    Column('personal_position', Integer, default=0, nullable=False)
)


# Tabla intermedia para la relación muchos-a-muchos Media <-> Actor
class media_actor(Base):
    __tablename__ = 'media_actor'
    media_id = Column(Integer, ForeignKey('media.id'), primary_key=True)
    actor_id = Column(Integer, ForeignKey('actor.id'), primary_key=True)



# Modelo Actor con id propio y tmdb_id único
class Actor(Base):
    __tablename__ = 'actor'
    id = Column(Integer, primary_key=True, index=True)
    tmdb_id = Column(Integer, unique=True)
    nombre = Column(String, index=True)
    # Puedes añadir más campos: foto, biografía, etc.
    medias = relationship('Media', secondary='media_actor', back_populates='actores')


class Media(Base):
    __tablename__ = "media"
    id = Column(Integer, primary_key=True, index=True)
    # Removemos usuario_id - los medias ahora son compartidos entre usuarios
    tmdb_id = Column(Integer, nullable=True, index=True)
    titulo = Column(String, index=True)
    anio = Column(Integer)
    genero = Column(String)
    sinopsis = Column(String)
    director = Column(String)
    elenco = Column(String)
    imagen = Column(String)
    # CAMPO ELIMINADO: estado (duplicado con status)
    tipo = Column(String)    # pelicula o serie
    temporadas = Column(Integer, nullable=True)
    episodios = Column(Integer, nullable=True)
    nota_imdb = Column(Float, nullable=True)
    original_title = Column(String, nullable=True)
    
    # 🔧 NUEVOS CAMPOS DE CACHE - Información universal
    runtime = Column(Integer, nullable=True)  # Duración en minutos
    production_countries = Column(String, nullable=True)  # Países de producción
    status = Column(String, nullable=True)  # Estado de producción TMDb: Released, Ended, In Production, etc.
    certification = Column(String, nullable=True)  # Certificación en español (referencia principal)
    first_air_date = Column(Date, nullable=True)  # Para series: fecha primer episodio
    last_air_date = Column(Date, nullable=True)  # Para series: fecha último episodio
    episode_runtime = Column(String, nullable=True)  # Para series: duración promedio episodios
    
    # 🔄 CAMPOS DE CONTROL DE ACTUALIZACIONES AUTOMÁTICAS
    last_updated_tmdb = Column(DateTime, nullable=True)  # Última actualización desde TMDb
    auto_update_enabled = Column(Boolean, default=True)  # Si permite actualizaciones automáticas
    needs_update = Column(Boolean, default=False)  # Flag para marcar que necesita actualización
    
    # Relaciones
    # usuario = relationship("User", foreign_keys=[usuario_id])  # Comentamos para evitar import circular
    actores = relationship('Actor', secondary='media_actor', back_populates='medias')
    tags = relationship('Tag', secondary=media_tag, back_populates='medias')
    listas = relationship('Lista', secondary=lista_media, back_populates='medias')
    keywords = relationship('Keyword', secondary=media_keyword, back_populates='medias')
    usuario_medias = relationship('UsuarioMedia', back_populates='media')  # Cambio: ahora puede haber múltiples usuarios

class Keyword(Base):
    __tablename__ = 'keyword'
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, unique=True, index=True)
    medias = relationship('Media', secondary=media_keyword, back_populates='keywords')

class Tag(Base):
    __tablename__ = 'tag'
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey('usuario.id'), nullable=False, index=True)  # Cada tag pertenece a un usuario
    nombre = Column(String, index=True)  # Quitamos unique=True porque ahora puede haber tags con el mismo nombre pero de usuarios diferentes
    medias = relationship('Media', secondary=media_tag, back_populates='tags')

class Lista(Base):
    __tablename__ = 'lista'
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey('usuario.id'), nullable=False, index=True)  # Cada lista pertenece a un usuario
    nombre = Column(String, index=True)  # Quitamos unique=True porque ahora puede haber listas con el mismo nombre pero de usuarios diferentes
    descripcion = Column(String, nullable=True)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    
    # Relaciones
    # usuario = relationship("User", foreign_keys=[usuario_id])  # Comentamos para evitar import circular
    medias = relationship('Media', secondary=lista_media, back_populates='listas')

class ContentTranslation(Base):
    __tablename__ = 'content_translations'
    id = Column(Integer, primary_key=True, index=True)
    media_id = Column(Integer, ForeignKey('media.id'), nullable=False)
    language_code = Column(String(5), nullable=False)
    title = Column(String(500))   # Título traducido
    synopsis = Column(String)     # Sinopsis traducida
    tmdb_id = Column(Integer)
    media_type = Column(String(10))
    
    # 🔧 NUEVOS CAMPOS DE CACHE - Información por idioma/región
    poster_url = Column(String(500), nullable=True)    # Poster con texto localizado
    backdrop_url = Column(String(500), nullable=True)  # Backdrop con texto localizado
    tagline = Column(String, nullable=True)            # Frase promocional traducida
    certification = Column(String(10), nullable=True)  # Clasificación local (PG-13, 12+, etc.)
    release_date = Column(Date, nullable=True)         # Fecha de estreno local
    
    # Relación con Media
    media = relationship('Media', backref='translations')
    
    # Constraint para evitar duplicados (se añade en la migración)
    __table_args__ = (
        {'extend_existing': True}
    )

class UsuarioMedia(Base):
    __tablename__ = "usuario_media"
    
    usuario_id = Column(Integer, ForeignKey('usuario.id'), primary_key=True, nullable=False, index=True)
    media_id = Column(Integer, ForeignKey('media.id'), primary_key=True, nullable=False, index=True)
    nota_personal = Column(String, nullable=True)  # TEXT en la BD
    anotacion_personal = Column(String, nullable=True)  # TEXT en la BD
    favorito = Column(Boolean, default=False)
    pendiente = Column(Boolean, default=False)
    fecha_agregado = Column(DateTime, default=datetime.utcnow)  # Nombre correcto según la BD
    
    # Relaciones
    media = relationship('Media', back_populates='usuario_medias')
    # usuario = relationship("User", foreign_keys=[usuario_id])  # Comentamos para evitar import circular
    
    # Constraint para evitar duplicados usuario-media (ya manejado por la clave primaria compuesta)
    __table_args__ = (
        {'extend_existing': True}
    )
