from pydantic import BaseModel, EmailStr, validator
from typing import Optional, List
from datetime import datetime, date
from fastapi_users import schemas as fa_schemas
import json

class TagBase(BaseModel):
    nombre: str

class TagCreate(TagBase):
    pass

class Tag(TagBase):
    id: int
    class Config:
        from_attributes = True

class MediaBase(BaseModel):
    tmdb_id: Optional[int] = None
    titulo: str
    titulo_ingles: Optional[str] = None
    anio: int
    genero: str
    sinopsis: str
    director: str
    elenco: str
    imagen: str
    estado: str
    tipo: str
    temporadas: Optional[int] = None
    episodios: Optional[int] = None
    nota_imdb: Optional[float] = None
    # Campos personales del usuario
    favorito: Optional[bool] = False
    pendiente: Optional[bool] = False
    nota_personal: Optional[float] = None
    anotacion_personal: Optional[str] = None
    fecha_agregado: Optional[datetime] = None
    tags: List[Tag] = []
    
    @validator('nota_personal')
    def validate_nota_personal(cls, v):
        if v is not None:
            if v < 0 or v > 10:
                raise ValueError('La nota personal debe estar entre 0 y 10')
        return v
    
    @validator('nota_imdb')
    def validate_nota_imdb(cls, v):
        if v is not None:
            if v < 0 or v > 10:
                raise ValueError('La nota IMDB debe estar entre 0 y 10')
        return v

class MediaCreate(MediaBase):
    titulo_ingles: Optional[str] = None
    tags: List[int] = []  # ids de tags

class Media(MediaBase):
    id: int
    titulo_ingles: Optional[str] = None
    fecha_agregado: Optional[datetime] = None  # Cambiado de fecha_creacion a fecha_agregado
    tags: List[Tag] = []
    class Config:
        from_attributes = True

class ListaBase(BaseModel):
    nombre: str
    descripcion: str = ""

class ListaCreate(ListaBase):
    pass

class Lista(ListaBase):
    id: int
    fecha_creacion: datetime
    medias: List[Media] = []
    class Config:
        from_attributes = True

class UserRead(fa_schemas.BaseUser[int]):
    username: str
    nombre: Optional[str] = None
    apellidos: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    pais: Optional[str] = None
    idioma_preferido: str = 'es'
    generos_favoritos: Optional[List[str]] = None
    plataformas_streaming: Optional[List[str]] = None
    tipo_contenido_preferido: Optional[str] = None
    compartir_estadisticas: bool = True
    perfil_publico: bool = False
    fecha_registro: datetime
    avatar_url: Optional[str] = None
    
    @validator('generos_favoritos', pre=True)
    def parse_generos_favoritos(cls, v):
        if isinstance(v, str) and v:
            try:
                return json.loads(v)
            except:
                return []
        return v or []
    
    @validator('plataformas_streaming', pre=True)
    def parse_plataformas_streaming(cls, v):
        if isinstance(v, str) and v:
            try:
                return json.loads(v)
            except:
                return []
        return v or []

class UserCreate(fa_schemas.BaseUserCreate):
    username: str
    nombre: Optional[str] = None
    apellidos: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    pais: Optional[str] = None
    idioma_preferido: str = 'es'
    generos_favoritos: Optional[str] = None  # JSON string internally
    plataformas_streaming: Optional[str] = None  # JSON string internally
    tipo_contenido_preferido: Optional[str] = None
    compartir_estadisticas: bool = True
    perfil_publico: bool = False
    origen_registro: Optional[str] = 'web'
    
    @validator('username')
    def validate_username(cls, v):
        if not v or len(v) < 3:
            raise ValueError('El nombre de usuario debe tener al menos 3 caracteres')
        if len(v) > 50:
            raise ValueError('El nombre de usuario no puede tener más de 50 caracteres')
        if not v.replace('_', '').replace('-', '').replace('.', '').isalnum():
            raise ValueError('El nombre de usuario solo puede contener letras, números, guiones, guiones bajos y puntos')
        return v.lower()  # Convertir a minúsculas para evitar duplicados por case
    
    @validator('generos_favoritos', pre=True)
    def serialize_generos_favoritos(cls, v):
        if v is None:
            return None
        if isinstance(v, list):
            return json.dumps(v) if v else None
        if isinstance(v, str):
            return v  # Ya es un string JSON
        return json.dumps(v) if v else None
    
    @validator('plataformas_streaming', pre=True)
    def serialize_plataformas_streaming(cls, v):
        if v is None:
            return None
        if isinstance(v, list):
            return json.dumps(v) if v else None
        if isinstance(v, str):
            return v  # Ya es un string JSON
        return json.dumps(v) if v else None

class UserUpdate(fa_schemas.BaseUserUpdate):
    username: Optional[str] = None
    nombre: Optional[str] = None
    apellidos: Optional[str] = None
    fecha_nacimiento: Optional[date] = None
    pais: Optional[str] = None
    idioma_preferido: Optional[str] = None
    generos_favoritos: Optional[str] = None  # JSON string internally
    plataformas_streaming: Optional[str] = None  # JSON string internally
    tipo_contenido_preferido: Optional[str] = None
    compartir_estadisticas: Optional[bool] = None
    perfil_publico: Optional[bool] = None
    avatar_url: Optional[str] = None
