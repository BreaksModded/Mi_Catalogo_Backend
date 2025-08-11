from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from fastapi_users import schemas as fa_schemas

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

class MediaCreate(MediaBase):
    titulo_ingles: Optional[str] = None
    tags: List[int] = []  # ids de tags

class Media(MediaBase):
    id: int
    titulo_ingles: Optional[str] = None
    fecha_creacion: datetime
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
    pass

class UserCreate(fa_schemas.BaseUserCreate):
    pass
