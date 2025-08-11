from sqlalchemy import Column, Integer, String, Float, Boolean, Table, ForeignKey, DateTime, func
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import unicodedata

def normalize_str(s):
    if s is None:
        return ''
    return ''.join(
        c for c in unicodedata.normalize('NFD', str(s).lower())
        if unicodedata.category(c) != 'Mn'
    )

Base = declarative_base()

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
    Column('media_id', Integer, ForeignKey('media.id'), primary_key=True)
)

class Media(Base):
    __tablename__ = "media"
    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey('usuario.id'), nullable=False, index=True)  # Cada media pertenece a un usuario
    tmdb_id = Column(Integer, nullable=True, index=True)
    titulo = Column(String, index=True)
    anio = Column(Integer)
    genero = Column(String)
    sinopsis = Column(String)
    director = Column(String)
    elenco = Column(String)
    imagen = Column(String)
    estado = Column(String)  # vista, no vista, favorita, etc.
    tipo = Column(String)    # pelicula o serie
    temporadas = Column(Integer, nullable=True)
    episodios = Column(Integer, nullable=True)
    nota_imdb = Column(Float, nullable=True)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    titulo_ingles = Column(String, nullable=True)
    
    # Relaciones
    # usuario = relationship("User", foreign_keys=[usuario_id])  # Comentamos para evitar import circular
    tags = relationship('Tag', secondary=media_tag, back_populates='medias')
    listas = relationship('Lista', secondary=lista_media, back_populates='medias')
    keywords = relationship('Keyword', secondary=media_keyword, back_populates='medias')
    usuario_media = relationship('UsuarioMedia', back_populates='media', uselist=False)

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
    translated_title = Column(String(500))
    translated_synopsis = Column(String)
    director = Column(String(300))
    cast_members = Column(String)
    genres = Column(String(300))
    poster_url = Column(String(500))  # URL del poster en este idioma
    translation_source = Column(String(20), default='tmdb')
    tmdb_id = Column(Integer)
    media_type = Column(String(10))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relación con Media
    media = relationship('Media', backref='translations')
    
    # Constraint para evitar duplicados
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
    media = relationship('Media', back_populates='usuario_media')
    # usuario = relationship("User", foreign_keys=[usuario_id])  # Comentamos para evitar import circular
    
    # Constraint para evitar duplicados usuario-media (ya manejado por la clave primaria compuesta)
    __table_args__ = (
        {'extend_existing': True}
    )
