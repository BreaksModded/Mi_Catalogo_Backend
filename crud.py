import models
import schemas
from sqlalchemy.orm import Session
import os
import unicodedata
import requests
import sqlalchemy as sa

def get_medias_query(db: Session, skip: int = 0, limit: int = 5000, order_by: str = None, tipo: str = None, pendiente: bool = None,
                     genero: str = None, min_year: int = None, max_year: int = None, min_nota: float = None, min_nota_personal: float = None,
                     favorito: bool = None, tag_id: int = None, tmdb_id: int = None):
    query = db.query(models.Media)
    # Aplicar filtros
    if tipo:
        query = query.filter(models.Media.tipo.ilike(tipo))
    if pendiente is not None:
        query = query.filter(models.Media.pendiente == pendiente)
    if favorito is not None:
        query = query.filter(models.Media.favorito == favorito)
    if genero:
        query = query.filter(models.Media.genero.ilike(f"%{genero}%"))
    if min_year:
        query = query.filter(models.Media.anio >= min_year)
    if max_year:
        query = query.filter(models.Media.anio <= max_year)
    if min_nota:
        query = query.filter(models.Media.nota_imdb >= min_nota)
    if min_nota_personal:
        query = query.filter(models.Media.nota_personal >= min_nota_personal)
    if tag_id is not None:
        query = query.join(models.Media.tags).filter(models.Tag.id == tag_id)
    if tmdb_id is not None:
        query = query.filter(models.Media.tmdb_id == tmdb_id)
    # Ordenamiento según el filtro recibido
    if order_by == "fecha" or order_by is None or order_by == "fecha_creacion":
        query = query.order_by(models.Media.fecha_creacion.desc())
    elif order_by == "nota_personal":
        query = query.order_by(models.Media.nota_personal.desc().nullslast())
    elif order_by == "nota_tmdb":
        query = query.order_by(models.Media.nota_imdb.desc().nullslast())
    elif order_by == "random":
        query = query.order_by(sa.func.random())
    return query

def get_medias(db: Session, skip: int = 0, limit: int = 5000, order_by: str = None, tipo: str = None, pendiente: bool = None,
               genero: str = None, min_year: int = None, max_year: int = None, min_nota: float = None, min_nota_personal: float = None,
               favorito: bool = None, tag_id: int = None, tmdb_id: int = None):
    query = get_medias_query(db, skip=skip, limit=limit, order_by=order_by, tipo=tipo, pendiente=pendiente,
                             genero=genero, min_year=min_year, max_year=max_year, min_nota=min_nota,
                             min_nota_personal=min_nota_personal, favorito=favorito, tag_id=tag_id, tmdb_id=tmdb_id)
    return query.offset(skip).limit(limit).all()

def get_media(db: Session, media_id: int):
    return db.query(models.Media).filter(models.Media.id == media_id).first()

# --- NUEVO: obtener similares por género y keywords ---
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

def get_similares_para_media(db: Session, media_id: int, n=24):
    base = db.query(models.Media).filter(models.Media.id == media_id).first()
    if not base:
        return []
    # Normalizar géneros (pueden estar separados por coma)
    base_generos = set(g.strip().lower() for g in (base.genero or '').split(',') if g.strip())
    base_keywords = set(kw.nombre for kw in base.keywords)
    # Filtrar solo medias que compartan al menos un género y cargar keywords de golpe
    query = db.query(models.Media).options(joinedload(models.Media.keywords)).filter(models.Media.id != media_id)
    if base_generos:
        genero_filter = [models.Media.genero.ilike(f"%{g}%") for g in base_generos]
        query = query.filter(or_(*genero_filter))
    medias = query.all()
    scores = []
    for m in medias:
        m_generos = set(g.strip().lower() for g in (m.genero or '').split(',') if g.strip())
        m_keywords = set(kw.nombre for kw in m.keywords)
        genero_score = len(base_generos & m_generos)
        keyword_score = 2 * len(base_keywords & m_keywords)
        score = genero_score + keyword_score
        if score > 0:
            scores.append((score, m))
    # Ordenar por score descendente y fecha_creacion descendente como desempate
    scores.sort(key=lambda x: (-x[0], -x[1].fecha_creacion.timestamp() if x[1].fecha_creacion else 0))
    return [m for _, m in scores[:n]]


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
    # --- Añadir keywords de TMDb si hay tmdb_id y tipo ---
    from config import TMDB_API_KEY, TMDB_BASE_URL, get_tmdb_auth_headers, REQUEST_TIMEOUT
    def normalize_tipo(tipo):
        if not tipo:
            return ''
        tipo_norm = ''.join(c for c in unicodedata.normalize('NFD', tipo.lower()) if unicodedata.category(c) != 'Mn')
        if tipo_norm in ['pelicula', 'movie']:
            return 'pelicula'
        elif tipo_norm in ['serie', 'tv']:
            return 'serie'
        return tipo_norm
    if getattr(media, 'tmdb_id', None) and getattr(media, 'tipo', None):
        tipo_norm = normalize_tipo(media.tipo)
        if tipo_norm == 'pelicula':
            url = f"{TMDB_BASE_URL}/movie/{media.tmdb_id}/keywords"
        elif tipo_norm == 'serie':
            url = f"{TMDB_BASE_URL}/tv/{media.tmdb_id}/keywords"
        else:
            url = None
        if url:
            headers = get_tmdb_auth_headers()
            params = {}
            if not headers and TMDB_API_KEY:
                params["api_key"] = TMDB_API_KEY
            resp = requests.get(url, headers=headers or None, params=params, timeout=REQUEST_TIMEOUT)
            if resp.status_code == 200:
                data = resp.json()
                kw_list = data.get('keywords') if tipo_norm == 'pelicula' else data.get('results')
                if kw_list:
                    for kw in kw_list:
                        nombre_kw = kw.get('name')
                        if not nombre_kw:
                            continue
                        db_kw = db.query(models.Keyword).filter(models.Keyword.nombre == nombre_kw).first()
                        if not db_kw:
                            db_kw = models.Keyword(nombre=nombre_kw)
                            db.add(db_kw)
                            db.flush()
                        if db_kw not in db_media.keywords:
                            db_media.keywords.append(db_kw)
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

def get_pendientes(db: Session, skip: int = 0, limit: int = 24):
    return db.query(models.Media).filter(models.Media.pendiente == True).offset(skip).limit(limit).all()

def get_favoritos(db: Session, skip: int = 0, limit: int = 24):
    return db.query(models.Media).filter(models.Media.favorito == True).offset(skip).limit(limit).all()

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
