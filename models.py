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

# Tabla intermedia para la relación muchos-a-muchos Media <-> Tag
media_tag = Table(
    'media_tag', Base.metadata,
    Column('media_id', Integer, ForeignKey('media.id'), primary_key=True),
    Column('tag_id', Integer, ForeignKey('tag.id'), primary_key=True)
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
    nota_personal = Column(Float, nullable=True)
    anotacion_personal = Column(String, nullable=True)  # <-- NUEVO CAMPO para Markdown
    nota_imdb = Column(Float, nullable=True)
    pendiente = Column(Boolean, default=False)
    favorito = Column(Boolean, default=False)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    titulo_ingles = Column(String, nullable=True)
    tags = relationship('Tag', secondary=media_tag, back_populates='medias')
    listas = relationship('Lista', secondary=lista_media, back_populates='medias')

class Tag(Base):
    __tablename__ = 'tag'
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, unique=True, index=True)
    medias = relationship('Media', secondary=media_tag, back_populates='tags')

class Lista(Base):
    __tablename__ = 'lista'
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, unique=True, index=True)
    descripcion = Column(String, nullable=True)
    fecha_creacion = Column(DateTime, default=datetime.utcnow)
    medias = relationship('Media', secondary=lista_media, back_populates='listas')
