import models
import schemas
from sqlalchemy.orm import Session

def get_medias(db: Session, skip: int = 0, limit: int = 5000, order_by: str = None, tipo: str = None, pendiente: bool = None):
    query = db.query(models.Media)
    
    # Aplicar filtros
    if tipo:
        query = query.filter(models.Media.tipo.ilike(tipo))  # Usar ilike para case-insensitive
    if pendiente is not None:
        query = query.filter(models.Media.pendiente == pendiente)
        
    # Aplicar ordenación
    if order_by == "fecha_creacion":
        query = query.order_by(models.Media.fecha_creacion.desc())
        
    # Aplicar paginación
    return query.offset(skip).limit(limit).all()

def get_media(db: Session, media_id: int):
    return db.query(models.Media).filter(models.Media.id == media_id).first()

def create_media(db: Session, media: schemas.MediaCreate):
    # Si se proporciona tmdb_id, comprobar duplicados
    if getattr(media, 'tmdb_id', None) is not None:
        existe = db.query(models.Media).filter(models.Media.tmdb_id == media.tmdb_id).first()
        if existe:
            # Devuelve info personalizada para el frontend
            raise Exception({
                'custom_type': 'tmdb_id_exists',
                'message': f"Ya existe una entrada con este TMDb ID: '{existe.titulo}' ({existe.tipo})",
                'titulo': existe.titulo,
                'tipo': existe.tipo
            })
    # (Opcional) Si no hay tmdb_id, comprobar por título y año
    elif db.query(models.Media).filter(models.Media.titulo == media.titulo, models.Media.anio == media.anio).first():
        raise Exception('Ya existe una película o serie con ese título y año.')
    tags = db.query(models.Tag).filter(models.Tag.id.in_(media.tags)).all() if hasattr(media, 'tags') else []
    db_media = models.Media(
        nota_imdb=media.nota_imdb,
        **{k: v for k, v in media.dict().items() if k not in ['tags', 'nota_tmdb', 'nota_imdb']}
    )
    db_media.tags = tags
    db.add(db_media)
    db.commit()
    db.refresh(db_media)
    return db_media

def delete_media(db: Session, media_id: int):
    db_media = db.query(models.Media).filter(models.Media.id == media_id).first()
    if db_media:
        db.delete(db_media)
        db.commit()
    return db_media

def update_media_pendiente(db: Session, media_id: int, pendiente: bool):
    db_media = db.query(models.Media).filter(models.Media.id == media_id).first()
    if db_media:
        db_media.pendiente = pendiente
        db.commit()
        db.refresh(db_media)
    return db_media

def update_media_favorito(db: Session, media_id: int, favorito: bool):
    db_media = db.query(models.Media).filter(models.Media.id == media_id).first()
    if db_media:
        db_media.favorito = favorito
        db.commit()
        db.refresh(db_media)
    return db_media

def update_media_anotacion_personal(db: Session, media_id: int, anotacion_personal: str):
    db_media = db.query(models.Media).filter(models.Media.id == media_id).first()
    if db_media:
        db_media.anotacion_personal = anotacion_personal
        db.commit()
        db.refresh(db_media)
    return db_media

def get_pendientes(db: Session):
    return db.query(models.Media).filter(models.Media.pendiente == True).all()

def get_favoritos(db: Session):
    return db.query(models.Media).filter(models.Media.favorito == True).all()

# CRUD para tags

def get_tags(db: Session):
    return db.query(models.Tag).all()

def create_tag(db: Session, tag: schemas.TagCreate):
    db_tag = models.Tag(nombre=tag.nombre)
    db.add(db_tag)
    db.commit()
    db.refresh(db_tag)
    return db_tag

def add_tag_to_media(db: Session, media_id: int, tag_id: int):
    media = db.query(models.Media).filter(models.Media.id == media_id).first()
    tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
    if media and tag and tag not in media.tags:
        media.tags.append(tag)
        db.commit()
        db.refresh(media)
    return media

def remove_tag_from_media(db: Session, media_id: int, tag_id: int):
    media = db.query(models.Media).filter(models.Media.id == media_id).first()
    tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
    if media and tag and tag in media.tags:
        media.tags.remove(tag)
        db.commit()
        db.refresh(media)
    return media

def delete_tag(db: Session, tag_id: int):
    db_tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
    if db_tag:
        db.delete(db_tag)
        db.commit()
    return db_tag

def create_lista(db: Session, lista: schemas.ListaCreate):
    db_lista = models.Lista(nombre=lista.nombre, descripcion=lista.descripcion)
    db.add(db_lista)
    db.commit()
    db.refresh(db_lista)
    return db_lista

def get_listas(db: Session):
    return db.query(models.Lista).all()

def get_lista(db: Session, lista_id: int):
    return db.query(models.Lista).filter(models.Lista.id == lista_id).first()

def delete_lista(db: Session, lista_id: int):
    db_lista = db.query(models.Lista).filter(models.Lista.id == lista_id).first()
    if db_lista:
        db.delete(db_lista)
        db.commit()
    return db_lista

def update_lista(db: Session, lista_id: int, nombre: str = None, descripcion: str = None):
    db_lista = db.query(models.Lista).filter(models.Lista.id == lista_id).first()
    if db_lista:
        if nombre is not None:
            db_lista.nombre = nombre
        if descripcion is not None:
            db_lista.descripcion = descripcion
        db.commit()
        db.refresh(db_lista)
    return db_lista

def add_media_to_lista(db: Session, lista_id: int, media_id: int):
    db_lista = db.query(models.Lista).filter(models.Lista.id == lista_id).first()
    db_media = db.query(models.Media).filter(models.Media.id == media_id).first()
    if db_lista and db_media and db_media not in db_lista.medias:
        db_lista.medias.append(db_media)
        db.commit()
        db.refresh(db_lista)
    return db_lista

def remove_media_from_lista(db: Session, lista_id: int, media_id: int):
    db_lista = db.query(models.Lista).filter(models.Lista.id == lista_id).first()
    db_media = db.query(models.Media).filter(models.Media.id == media_id).first()
    if db_lista and db_media and db_media in db_lista.medias:
        db_lista.medias.remove(db_media)
        db.commit()
        db.refresh(db_lista)
    return db_lista
