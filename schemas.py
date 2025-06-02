from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class TagBase(BaseModel):
    nombre: str

class TagCreate(TagBase):
    pass

class Tag(TagBase):
    id: int
    class Config:
        from_attributes = True

# Media schemas
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
    nota_personal: Optional[float] = None
    anotacion_personal: Optional[str] = None
    nota_imdb: Optional[float] = None
    pendiente: Optional[bool] = False
    favorito: Optional[bool] = False
    tags: List[Tag] = []

class MediaCreate(MediaBase):
    titulo_ingles: Optional[str] = None
    pendiente: Optional[bool] = False
    favorito: Optional[bool] = False
    tags: List[int] = []  # ids de tags

class Media(MediaBase):
    id: int
    titulo_ingles: Optional[str] = None
    pendiente: Optional[bool] = False
    favorito: Optional[bool] = False
    fecha_creacion: datetime
    tags: List[Tag] = []
    class Config:
        from_attributes = True

# UserMedia schemas
class UserMediaBase(BaseModel):
    nota_personal: Optional[float] = Field(None, ge=0, le=10)
    favorito: bool = False
    pendiente: bool = False
    anotaciones: Optional[str] = None

class UserMediaCreate(UserMediaBase):
    media_id: int

class UserMediaUpdate(UserMediaBase):
    pass

class UserMedia(UserMediaBase):
    id: int
    media: Media
    fecha_creacion: datetime
    fecha_modificacion: Optional[datetime] = None
    
    class Config:
        orm_mode = True

# UserTag schemas
class UserTagBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=50)
    color: str = Field("#6c757d", regex="^#(?:[0-9a-fA-F]{3}){1,2}$")

class UserTagCreate(UserTagBase):
    pass

class UserTag(UserTagBase):
    id: int
    created_at: datetime
    
    class Config:
        orm_mode = True

# List schemas
class ListaBase(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=100)
    descripcion: Optional[str] = Field(None, max_length=500)

class ListaCreate(ListaBase):
    pass

class ListaUpdate(ListaBase):
    pass

class Lista(ListaBase):
    id: int
    user_id: int
    fecha_creacion: datetime
    medias: List[Media] = []

    class Config:
        orm_mode = True

# Keyword schemas
class KeywordBase(BaseModel):
    nombre: str

class KeywordCreate(KeywordBase):
    pass

class Keyword(KeywordBase):
    id: int
    
    class Config:
        orm_mode = True

# Response schemas
class PaginatedResponse(BaseModel):
    total: int
    items: List[Any]
    skip: int
    limit: int
