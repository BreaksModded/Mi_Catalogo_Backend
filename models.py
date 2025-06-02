from sqlalchemy import Column, Integer, String, Float, Boolean, Table, ForeignKey, DateTime, func, Text
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime
import unicodedata
from passlib.context import CryptContext

# Configuración para el hash de contraseñas
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

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
    Column('media_id', Integer, ForeignKey('media.id', ondelete='CASCADE'), primary_key=True),
    Column('keyword_id', Integer, ForeignKey('keyword.id', ondelete='CASCADE'), primary_key=True)
)

# Tabla intermedia para la relación muchos-a-muchos Lista <-> Media
lista_media = Table(
    'lista_media', Base.metadata,
    Column('lista_id', Integer, ForeignKey('lista.id', ondelete='CASCADE'), primary_key=True),
    Column('media_id', Integer, ForeignKey('media.id', ondelete='CASCADE'), primary_key=True)
)

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relaciones
    user_medias = relationship("UserMedia", back_populates="user", cascade="all, delete-orphan")
    user_tags = relationship("UserTag", back_populates="user", cascade="all, delete-orphan")

    def verify_password(self, password: str) -> bool:
        return pwd_context.verify(password, self.hashed_password)

class Media(Base):
    __tablename__ = "media"
    id = Column(Integer, primary_key=True, index=True)
    tmdb_id = Column(Integer, nullable=True, index=True)
    titulo = Column(String, index=True)
    anio = Column(Integer)
    genero = Column(String)
    sinopsis = Column(Text, nullable=True)
    director = Column(String, nullable=True)
    elenco = Column(Text, nullable=True)
    imagen = Column(String, nullable=True)
    tipo = Column(String)  # pelicula o serie
    temporadas = Column(Integer, nullable=True)
    episodios = Column(Integer, nullable=True)
    nota_imdb = Column(Float, nullable=True)
    titulo_ingles = Column(String, nullable=True)
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relaciones
    keywords = relationship('Keyword', secondary=media_keyword, back_populates='medias')
    listas = relationship('Lista', secondary=lista_media, back_populates='medias')
    user_medias = relationship("UserMedia", back_populates="media", cascade="all, delete-orphan")

class Keyword(Base):
    __tablename__ = 'keyword'
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, unique=True, index=True)
    medias = relationship('Media', secondary=media_keyword, back_populates='keywords')

class Lista(Base):
    __tablename__ = 'lista'
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String, unique=True, index=True)
    descripcion = Column(Text, nullable=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relaciones
    medias = relationship('Media', secondary=lista_media, back_populates='listas')
    user = relationship("User", back_populates="user_lists")

# Modelos para datos específicos del usuario
class UserMedia(Base):
    __tablename__ = "user_media"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    media_id = Column(Integer, ForeignKey("media.id", ondelete="CASCADE"), nullable=False)
    nota_personal = Column(Float, nullable=True)
    favorito = Column(Boolean, default=False)
    pendiente = Column(Boolean, default=False)
    anotaciones = Column(Text, nullable=True)
    fecha_creacion = Column(DateTime(timezone=True), server_default=func.now())
    fecha_modificacion = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relaciones
    user = relationship("User", back_populates="user_medias")
    media = relationship("Media", back_populates="user_medias")
    tags = relationship("UserMediaTag", back_populates="user_media", cascade="all, delete-orphan")
    
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )

class UserTag(Base):
    __tablename__ = "user_tags"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    nombre = Column(String(50), nullable=False)
    color = Column(String(7), default="#6c757d")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relaciones
    user = relationship("User", back_populates="user_tags")
    media_tags = relationship("UserMediaTag", back_populates="tag", cascade="all, delete-orphan")
    
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )

class UserMediaTag(Base):
    __tablename__ = "user_media_tags"
    
    user_media_id = Column(Integer, ForeignKey("user_media.id", ondelete="CASCADE"), primary_key=True)
    tag_id = Column(Integer, ForeignKey("user_tags.id", ondelete="CASCADE"), primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relaciones
    user_media = relationship("UserMedia", back_populates="tags")
    tag = relationship("UserTag", back_populates="media_tags")
