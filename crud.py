import models
import schemas
from sqlalchemy.orm import Session
from sqlalchemy import text
import os
import unicodedata
import requests
import sqlalchemy as sa
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError
from auto_translation_service import ensure_spanish_content, create_automatic_translations, get_translation_summary
from sqlalchemy import or_
from genre_utils import get_variants_for_input, normalize_text


def get_medias_query(db: Session, skip: int = 0, limit: int = 5000, order_by: str = None, tipo: str = None,
                     genero: str = None, min_year: int = None, max_year: int = None, min_nota: float = None,
                     max_nota: float = None, min_nota_personal: float = None, max_nota_personal: float = None,
                     favorito: bool = None, pendiente: bool = None, 
                     tag_id: int = None, tmdb_id: int = None, usuario_id: int = None, exclude_ids: list[int] | None = None):
    # Query básica con LEFT JOIN a usuario_media para obtener datos personales
    query = db.query(models.Media).outerjoin(
        models.UsuarioMedia, 
        (models.Media.id == models.UsuarioMedia.media_id) & 
        (models.UsuarioMedia.usuario_id == usuario_id)
    )
    
    # FILTRO PRINCIPAL: Solo medias del usuario especificado
    if usuario_id is not None:
        # Filtrar usando la tabla UsuarioMedia para obtener solo los medias del usuario
        query = query.filter(models.UsuarioMedia.usuario_id == usuario_id)
    
    # Aplicar filtros adicionales
    if tipo:
        query = query.filter(models.Media.tipo.ilike(tipo))
    if genero:
        # Construir OR con variantes de género (soporta múltiples idiomas/sinónimos)
        variants = get_variants_for_input(genero)
        if variants:
            ors = []
            for v in variants:
                # Coincidir tanto versiones acentuadas como normalizadas
                ors.append(models.Media.genero.ilike(f"%{v}%"))
            query = query.filter(or_(*ors))
        else:
            query = query.filter(models.Media.genero.ilike(f"%{genero}%"))
    if min_year:
        query = query.filter(models.Media.anio >= min_year)
    if max_year:
        query = query.filter(models.Media.anio <= max_year)
    if min_nota is not None:
        query = query.filter(models.Media.nota_imdb >= min_nota)
    if max_nota is not None:
        query = query.filter(models.Media.nota_imdb <= max_nota)
    if min_nota_personal is not None:
        # Filtrar por nota personal desde la tabla usuario_media (guardada como texto), casteando a Float
        query = query.filter(models.UsuarioMedia.nota_personal.isnot(None))
        query = query.filter(sa.cast(models.UsuarioMedia.nota_personal, sa.Float) >= min_nota_personal)
    if max_nota_personal is not None:
        # Filtrar por nota personal máxima desde la tabla usuario_media (guardada como texto), casteando a Float
        query = query.filter(models.UsuarioMedia.nota_personal.isnot(None))
        query = query.filter(sa.cast(models.UsuarioMedia.nota_personal, sa.Float) <= max_nota_personal)
    if favorito is not None:
        # Filtrar por favorito desde la tabla usuario_media
        query = query.filter(models.UsuarioMedia.favorito == favorito)
    if pendiente is not None:
        # Filtrar por pendiente desde la tabla usuario_media
        query = query.filter(models.UsuarioMedia.pendiente == pendiente)
    if tag_id is not None:
        # Para filtro por tag, necesitamos unir con la tabla media_tag incluyendo usuario_id
        query = query.join(models.media_tag).join(models.Tag).filter(
            models.Tag.id == tag_id,
            models.media_tag.c.usuario_id == usuario_id
        )
    if tmdb_id is not None:
        query = query.filter(models.Media.tmdb_id == tmdb_id)
    if exclude_ids:
        query = query.filter(~models.Media.id.in_(exclude_ids))
    # Ordenamiento según el filtro recibido
    if order_by == "fecha" or order_by is None or order_by == "fecha_creacion":
        # Orden estable: primero por fecha agregada (nulls al final), luego por id descendente
        query = query.order_by(
            models.UsuarioMedia.fecha_agregado.desc().nullslast(),
            models.Media.id.desc()
        )
    elif order_by == "nota_tmdb":
        query = query.order_by(
            models.Media.nota_imdb.desc().nullslast(),
            models.Media.id.desc()
        )
    elif order_by == "nota_personal":
        # Ordenar por nota personal numéricamente (columna es texto)
        query = query.order_by(
            sa.cast(models.UsuarioMedia.nota_personal, sa.Float).desc().nullslast(),
            models.Media.id.desc()
        )
    elif order_by == "random":
        query = query.order_by(sa.func.random())
    return query

def get_medias(db: Session, skip: int = 0, limit: int = 5000, order_by: str = None, tipo: str = None,
               genero: str = None, min_year: int = None, max_year: int = None, min_nota: float = None,
               max_nota: float = None, min_nota_personal: float = None, max_nota_personal: float = None,
               favorito: bool = None, pendiente: bool = None,
               tag_id: int = None, tmdb_id: int = None, usuario_id: int = None):
    query = get_medias_query(db, skip=skip, limit=limit, order_by=order_by, tipo=tipo,
                             genero=genero, min_year=min_year, max_year=max_year, min_nota=min_nota,
                             max_nota=max_nota, min_nota_personal=min_nota_personal, max_nota_personal=max_nota_personal,
                             favorito=favorito, pendiente=pendiente,
                             tag_id=tag_id, tmdb_id=tmdb_id, usuario_id=usuario_id)
    medias = query.offset(skip).limit(limit).all()
    
    # Cargar tags manualmente para cada media si se proporciona usuario_id
    if usuario_id is not None and medias:
        # Obtener todos los tags para estos medias de una vez
        media_ids = [media.id for media in medias]
        media_ids_str = ','.join(str(id) for id in media_ids)
        
        tag_query = f"""
        SELECT mt.media_id, t.id, t.nombre, t.usuario_id FROM tag t
        JOIN media_tag mt ON t.id = mt.tag_id
        WHERE mt.media_id IN ({media_ids_str}) AND mt.usuario_id = :usuario_id
        """
        result = db.execute(text(tag_query), {"usuario_id": usuario_id})
        
        # Agrupar tags por media_id
        tags_by_media = {}
        for row in result:
            media_id = row.media_id
            tag = models.Tag(
                id=row.id,
                nombre=row.nombre,
                usuario_id=row.usuario_id
            )
            if media_id not in tags_by_media:
                tags_by_media[media_id] = []
            tags_by_media[media_id].append(tag)
        
        # Asignar tags a cada media y copiar datos personales de usuario_media
        for media in medias:
            media.tags = tags_by_media.get(media.id, [])
            
            # Buscar datos personales directamente en la base de datos
            usuario_media = db.query(models.UsuarioMedia).filter(
                models.UsuarioMedia.media_id == media.id,
                models.UsuarioMedia.usuario_id == usuario_id
            ).first()
            
            if usuario_media:
                # Añadir campos temporales al objeto media para el serializado
                media.favorito = usuario_media.favorito or False
                media.pendiente = usuario_media.pendiente or False
                media.nota_personal = usuario_media.nota_personal if usuario_media.nota_personal is not None else None
                media.anotacion_personal = usuario_media.anotacion_personal
                media.fecha_agregado = usuario_media.fecha_agregado if hasattr(usuario_media, 'fecha_agregado') else None
            else:
                # Valores por defecto si no hay datos personales
                media.favorito = False
                media.pendiente = False
                media.nota_personal = None
                media.anotacion_personal = None
                media.fecha_agregado = None  # Si no hay datos personales, no hay fecha de agregado
    
    return medias

def get_media(db: Session, media_id: int, usuario_id: int = None):
    # Obtener el media con LEFT JOIN a usuario_media
    query = db.query(models.Media).outerjoin(
        models.UsuarioMedia, 
        (models.Media.id == models.UsuarioMedia.media_id) & 
        (models.UsuarioMedia.usuario_id == usuario_id)
    ).filter(models.Media.id == media_id)
    
    media = query.first()

    if media and usuario_id is not None:
        # Cargar tags del usuario para este media usando SQL directo
        tag_query = """
        SELECT t.* FROM tag t
        JOIN media_tag mt ON t.id = mt.tag_id
        WHERE mt.media_id = :media_id AND mt.usuario_id = :usuario_id
        """
        result = db.execute(text(tag_query), {"media_id": media_id, "usuario_id": usuario_id})
        tags = [models.Tag(**row._asdict()) for row in result]
        media.tags = tags

        # Cargar datos personales de usuario_media manualmente
        um = db.query(models.UsuarioMedia).filter_by(media_id=media_id, usuario_id=usuario_id).first()
        if um:
            media.favorito = um.favorito or False
            media.pendiente = um.pendiente or False
            media.nota_personal = um.nota_personal if um.nota_personal is not None else None
            media.anotacion_personal = um.anotacion_personal
            media.fecha_agregado = um.fecha_agregado if hasattr(um, 'fecha_agregado') else None
        else:
            media.favorito = False
            media.pendiente = False
            media.nota_personal = None
            media.anotacion_personal = None
            media.fecha_agregado = None  # Si no hay datos personales, no hay fecha de agregado

    return media

# --- SISTEMA AVANZADO DE SIMILARES ---
from sqlalchemy import or_
from sqlalchemy.orm import joinedload

def get_media_tags_for_user(db: Session, media_id: int, usuario_id: int):
    """Obtiene los tags personales de un media para un usuario específico"""
    tags_query = (db.query(models.Tag)
                 .join(models.media_tag)
                 .filter(
                     models.media_tag.c.media_id == media_id,
                     models.media_tag.c.usuario_id == usuario_id,
                     models.Tag.usuario_id == usuario_id
                 ))
    return set(tag.nombre.lower() for tag in tags_query.all())

def get_similares_para_media(db: Session, media_id: int, usuario_id: int, n=24):
    """
    Sistema de recomendación SIMPLIFICADO y PERMISIVO que combina múltiples factores:
    - Géneros compartidos (peso alto)
    - Tags personales compartidos (peso muy alto)
    - Keywords de TMDb (peso medio)
    - Director, año, rating (peso bajo)
    
    VERSIÓN PERMISIVA: Acepta medias con al menos 1 punto de coincidencia
    """
    base = db.query(models.Media).filter(models.Media.id == media_id).first()
    if not base:
        return []
    
    # Normalizar datos de la media base
    base_generos = set(g.strip().lower() for g in (base.genero or '').split(',') if g.strip())
    base_keywords = set(kw.nombre for kw in base.keywords)
    base_director = (base.director or '').strip().lower()
    base_anio = base.anio
    base_rating = base.nota_imdb or 0
    
    # Obtener tags personales de la media base para este usuario
    base_tags = get_media_tags_for_user(db, media_id, usuario_id)
    
    # Obtener todas las medias del usuario (excepto la actual)
    query = (db.query(models.Media)
             .join(models.UsuarioMedia, models.Media.id == models.UsuarioMedia.media_id)
             .options(joinedload(models.Media.keywords))
             .filter(
                 models.Media.id != media_id,
                 models.UsuarioMedia.usuario_id == usuario_id
             ))
    
    medias = query.all()
    scores = []
    
    for m in medias:
        score = 0
        
        # 1. GÉNERO - Factor principal (muy permisivo)
        m_generos = set(g.strip().lower() for g in (m.genero or '').split(',') if g.strip())
        genero_coincidencias = len(base_generos & m_generos)
        score += genero_coincidencias * 5  # 5 puntos por género coincidente
        
        # 2. TAGS PERSONALES - Factor más importante si existen
        m_tags = get_media_tags_for_user(db, m.id, usuario_id)
        tag_coincidencias = len(base_tags & m_tags)
        score += tag_coincidencias * 8  # 8 puntos por tag personal coincidente
        
        # 3. KEYWORDS/TAGS TMDB - Factor secundario
        m_keywords = set(kw.nombre for kw in m.keywords)
        keyword_coincidencias = len(base_keywords & m_keywords)
        score += keyword_coincidencias * 3  # 3 puntos por keyword coincidente
        
        # 4. MISMO DIRECTOR - Bonus significativo
        m_director = (m.director or '').strip().lower()
        if base_director and m_director and base_director == m_director:
            score += 4
        
        # 5. MISMO TIPO (película/serie) - Bonus básico
        if base.tipo and m.tipo and base.tipo.lower() == m.tipo.lower():
            score += 1
        
        # 6. AÑO CERCANO - Bonus menor (MUY permisivo)
        if base_anio and m.anio:
            diferencia_anios = abs(base_anio - m.anio)
            if diferencia_anios <= 5:
                score += 2
            elif diferencia_anios <= 10:
                score += 1
            elif diferencia_anios <= 20:
                score += 0.5
        
        # 7. RATING SIMILAR - Bonus menor
        if base_rating and m.nota_imdb:
            diferencia_rating = abs(base_rating - m.nota_imdb)
            if diferencia_rating <= 2:
                score += 1
            elif diferencia_rating <= 4:
                score += 0.5
        
        # INCLUIR CUALQUIER MEDIA CON SCORE > 0
        if score > 0:
            scores.append((score, m))
    
    # Si no hay resultados, hacer una búsqueda MUY permisiva solo por género
    if not scores and base_generos:
        for m in medias:
            m_generos = set(g.strip().lower() for g in (m.genero or '').split(',') if g.strip())
            if base_generos & m_generos:  # Al menos un género en común
                scores.append((1, m))  # Score mínimo
    
    # Ordenar por score descendente y por ID descendente como desempate
    scores.sort(key=lambda x: (-x[0], -x[1].id))
    return [m for _, m in scores[:n]]


def create_media(db: Session, media: schemas.MediaCreate, usuario_id: int):
    # Extraer datos personales del media al inicio para reutilizar
    nota_personal = getattr(media, 'nota_personal', None)
    anotacion_personal = getattr(media, 'anotacion_personal', None)
    favorito = getattr(media, 'favorito', False)
    pendiente = getattr(media, 'pendiente', False)
    
    # Obtener tags del usuario al inicio para reutilizar
    tags = db.query(models.Tag).filter(
        models.Tag.id.in_(media.tags),
        models.Tag.usuario_id == usuario_id
    ).all() if hasattr(media, 'tags') and media.tags else []
    
    # Verificar si el usuario ya tiene este media en su catálogo
    if getattr(media, 'tmdb_id', None) is not None:
        # Buscar si ya existe un media con este tmdb_id
        existing_media = db.query(models.Media).filter(
            models.Media.tmdb_id == media.tmdb_id
        ).first()
        
        if existing_media:
            # Verificar si el usuario ya lo tiene en su catálogo
            existing_user_media = db.query(models.UsuarioMedia).filter(
                models.UsuarioMedia.usuario_id == usuario_id,
                models.UsuarioMedia.media_id == existing_media.id
            ).first()
            
            if existing_user_media:
                # El usuario ya tiene este media
                raise Exception({
                    'custom_type': 'tmdb_id_exists',
                    'message': f"Ya existe una entrada con este TMDb ID: '{existing_media.titulo}' ({existing_media.tipo})",
                    'titulo': existing_media.titulo,
                    'tipo': existing_media.tipo
                })
            
            # El media existe pero el usuario no lo tiene - crear solo la relación UsuarioMedia
            db_usuario_media = models.UsuarioMedia(
                usuario_id=usuario_id,
                media_id=existing_media.id,
                nota_personal=str(nota_personal) if nota_personal is not None else None,
                anotacion_personal=anotacion_personal,
                favorito=favorito,
                pendiente=pendiente
            )
            db.add(db_usuario_media)
            db.commit()
            
            # Asociar tags del usuario a través de la tabla media_tag
            if tags:
                for tag in tags:
                    # Verificar si la asociación ya existe para evitar duplicados
                    existing_tag = db.execute(
                        text("SELECT 1 FROM media_tag WHERE media_id = :media_id AND tag_id = :tag_id AND usuario_id = :usuario_id"),
                        {"media_id": existing_media.id, "tag_id": tag.id, "usuario_id": usuario_id}
                    ).fetchone()
                    
                    if not existing_tag:
                        db.execute(
                            text("INSERT INTO media_tag (media_id, tag_id, usuario_id) VALUES (:media_id, :tag_id, :usuario_id)"),
                            {"media_id": existing_media.id, "tag_id": tag.id, "usuario_id": usuario_id}
                        )
                db.commit()
            
            # 🌐 Verificar y crear traducciones automáticas si faltan
            if getattr(media, 'tmdb_id', None) and getattr(media, 'tipo', None):
                print(f"🔍 Verificando traducciones para media existente: {existing_media.titulo}")
                summary_before = get_translation_summary(db, existing_media.id)
                
                if summary_before['total'] < 4:  # Si no tiene las 4 traducciones
                    print(f"📊 Traducciones actuales: {summary_before['total']}/4")
                    create_automatic_translations(db, existing_media.id, media.tmdb_id, media.tipo)
                    summary_after = get_translation_summary(db, existing_media.id)
                    print(f"✅ Traducciones actualizadas: {summary_after['total']}/4")
            
            # Retornar el media existente con los datos personales del usuario
            return get_media(db, existing_media.id, usuario_id)
    
    # Si no hay tmdb_id, verificar por título y año para este usuario específico
    elif db.query(models.Media).join(models.UsuarioMedia).filter(
        models.Media.titulo == media.titulo,
        models.Media.anio == media.anio,
        models.UsuarioMedia.usuario_id == usuario_id
    ).first():
        raise Exception('Ya existe una película o serie con ese título y año en tu catálogo.')
    
    # El media no existe - crear nuevo registro en Media
    # Crear el media (sin datos personales y sin usuario_id)
    media_data = {k: v for k, v in media.dict().items() 
                  if k not in ['tags', 'nota_tmdb', 'nota_personal', 'anotacion_personal', 'favorito', 'pendiente', 'fecha_agregado']}
    media_data['nota_imdb'] = media.nota_imdb
    
    # 🌐 PASO 1: Asegurar que el contenido esté en español para la tabla media
    if getattr(media, 'tmdb_id', None):
        media_data = ensure_spanish_content(db, media_data)
    
    db_media = models.Media(**media_data)
    # No asignar tags directamente - se manejará después en la tabla media_tag
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
    
    # Primero guardar el media
    db.add(db_media)
    db.commit()
    db.refresh(db_media)
    
    # Crear el registro en UsuarioMedia con los datos personales
    db_usuario_media = models.UsuarioMedia(
        usuario_id=usuario_id,
        media_id=db_media.id,
        nota_personal=str(nota_personal) if nota_personal is not None else None,
        anotacion_personal=anotacion_personal,
        favorito=favorito,
        pendiente=pendiente
    )
    db.add(db_usuario_media)
    db.commit()
    
    # Asociar tags del usuario a través de la tabla media_tag
    if tags:
        for tag in tags:
            # Verificar si la asociación ya existe para evitar duplicados
            existing = db.execute(
                text("SELECT 1 FROM media_tag WHERE media_id = :media_id AND tag_id = :tag_id AND usuario_id = :usuario_id"),
                {"media_id": db_media.id, "tag_id": tag.id, "usuario_id": usuario_id}
            ).fetchone()
            
            if not existing:
                db.execute(
                    text("INSERT INTO media_tag (media_id, tag_id, usuario_id) VALUES (:media_id, :tag_id, :usuario_id)"),
                    {"media_id": db_media.id, "tag_id": tag.id, "usuario_id": usuario_id}
                )
        db.commit()
    
    # 🌐 PASO 2: Crear traducciones automáticas para todos los idiomas disponibles
    if getattr(media, 'tmdb_id', None) and getattr(media, 'tipo', None):
        create_automatic_translations(db, db_media.id, media.tmdb_id, media.tipo)
        
        # Mostrar resumen de traducciones creadas
        summary = get_translation_summary(db, db_media.id)
    
    # Cargar el media completo con datos personales para devolverlo
    return get_media(db, db_media.id, usuario_id)

def delete_media(db: Session, media_id: int, usuario_id: int = None):
    """Elimina todas las relaciones personales del usuario con el media, pero preserva el media compartido"""
    # Verificar que el usuario tiene acceso a este media
    if usuario_id is not None:
        usuario_media = db.query(models.UsuarioMedia).filter(
            models.UsuarioMedia.media_id == media_id,
            models.UsuarioMedia.usuario_id == usuario_id
        ).first()
        if not usuario_media:
            return None  # El usuario no tiene acceso a este media
    
    # Eliminar todas las relaciones personales del usuario con este media
    if usuario_id is not None:
        # 1. Eliminar la relación principal usuario-media
        db.query(models.UsuarioMedia).filter(
            models.UsuarioMedia.media_id == media_id,
            models.UsuarioMedia.usuario_id == usuario_id
        ).delete()
        
        # 2. Eliminar tags personales asociados al media
        db.execute(
            text("DELETE FROM media_tag WHERE media_id = :media_id AND usuario_id = :usuario_id"),
            {"media_id": media_id, "usuario_id": usuario_id}
        )
        
        # 3. Eliminar el media de las listas personales del usuario
        # Obtener las listas del usuario que contienen este media
        listas_usuario = db.query(models.Lista).filter(
            models.Lista.usuario_id == usuario_id
        ).all()
        
        for lista in listas_usuario:
            # Eliminar el media de esta lista si existe
            db.execute(
                text("DELETE FROM lista_media WHERE lista_id = :lista_id AND media_id = :media_id"),
                {"lista_id": lista.id, "media_id": media_id}
            )
    
    # NUNCA eliminar el media de la tabla Media - es información compartida
    # Obtener el media para retornarlo
    db_media = db.query(models.Media).filter(models.Media.id == media_id).first()
    
    db.commit()
    return db_media

def update_media_pendiente(db: Session, media_id: int, pendiente: bool, usuario_id: int):
    """Actualiza el estado pendiente en UsuarioMedia"""
    # Verificar que el usuario tiene acceso a este media
    usuario_media = db.query(models.UsuarioMedia).filter(
        models.UsuarioMedia.media_id == media_id,
        models.UsuarioMedia.usuario_id == usuario_id
    ).first()
    
    if not usuario_media:
        # Si no existe la relación UsuarioMedia, el usuario no tiene acceso a este media
        return None
    
    # Actualizar el estado pendiente
    usuario_media.pendiente = pendiente
    
    db.commit()
    
    # Devolver el media completo con datos personales
    return get_media(db, media_id, usuario_id)

def update_media_favorito(db: Session, media_id: int, favorito: bool, usuario_id: int):
    """Actualiza el estado favorito en UsuarioMedia"""
    # Verificar que el usuario tiene acceso a este media
    usuario_media = db.query(models.UsuarioMedia).filter(
        models.UsuarioMedia.media_id == media_id,
        models.UsuarioMedia.usuario_id == usuario_id
    ).first()
    
    if not usuario_media:
        # Si no existe la relación UsuarioMedia, el usuario no tiene acceso a este media
        return None
    
    # Actualizar el estado favorito
    usuario_media.favorito = favorito
    
    db.commit()
    
    # Devolver el media completo con datos personales
    return get_media(db, media_id, usuario_id)

def update_media_anotacion_personal(db: Session, media_id: int, anotacion_personal: str, usuario_id: int):
    """Actualiza la anotación personal en UsuarioMedia"""
    # Verificar que el usuario tiene acceso a este media
    usuario_media = db.query(models.UsuarioMedia).filter(
        models.UsuarioMedia.media_id == media_id,
        models.UsuarioMedia.usuario_id == usuario_id
    ).first()
    
    if not usuario_media:
        # Si no existe la relación UsuarioMedia, el usuario no tiene acceso a este media
        return None
    
    # Actualizar la anotación personal
    usuario_media.anotacion_personal = anotacion_personal
    
    db.commit()
    
    # Devolver el media completo con datos personales
    return get_media(db, media_id, usuario_id)

def update_media_nota_personal(db: Session, media_id: int, nota_personal: float, usuario_id: int):
    """Actualiza la nota personal en UsuarioMedia"""
    # Validar rango de nota personal
    if nota_personal is not None and (nota_personal < 0 or nota_personal > 10):
        raise ValueError('La nota personal debe estar entre 0 y 10')
    
    # Verificar que el usuario tiene acceso a este media
    usuario_media = db.query(models.UsuarioMedia).filter(
        models.UsuarioMedia.media_id == media_id,
        models.UsuarioMedia.usuario_id == usuario_id
    ).first()
    
    if not usuario_media:
        # Si no existe la relación UsuarioMedia, el usuario no tiene acceso a este media
        return None
    
    # Actualizar la nota personal
    usuario_media.nota_personal = str(nota_personal) if nota_personal is not None else None
    
    db.commit()
    
    # Devolver el media completo con datos personales
    return get_media(db, media_id, usuario_id)

def get_pendientes(db: Session, skip: int = 0, limit: int = 24, usuario_id: int = None):
    """Obtiene los medias marcados como pendientes por el usuario"""
    if usuario_id is None:
        return []
    
    # Obtener medias pendientes usando UsuarioMedia
    query = db.query(models.Media).join(
        models.UsuarioMedia,
        (models.Media.id == models.UsuarioMedia.media_id) &
        (models.UsuarioMedia.usuario_id == usuario_id) &
        (models.UsuarioMedia.pendiente == True)
    )
    
    medias = query.offset(skip).limit(limit).all()
    
    # Cargar datos personales para cada media
    for media in medias:
        usuario_media = db.query(models.UsuarioMedia).filter(
            models.UsuarioMedia.media_id == media.id,
            models.UsuarioMedia.usuario_id == usuario_id
        ).first()
        
        if usuario_media:
            media.favorito = usuario_media.favorito or False
            media.pendiente = usuario_media.pendiente or False
            media.nota_personal = usuario_media.nota_personal
            media.anotacion_personal = usuario_media.anotacion_personal
        else:
            media.favorito = False
            media.pendiente = False
            media.nota_personal = None
            media.anotacion_personal = None
    
    return medias

def get_favoritos(db: Session, skip: int = 0, limit: int = 24, usuario_id: int = None):
    """Obtiene los medias marcados como favoritos por el usuario"""
    if usuario_id is None:
        return []
    
    # Obtener medias favoritos usando UsuarioMedia
    query = db.query(models.Media).join(
        models.UsuarioMedia,
        (models.Media.id == models.UsuarioMedia.media_id) &
        (models.UsuarioMedia.usuario_id == usuario_id) &
        (models.UsuarioMedia.favorito == True)
    )
    
    medias = query.offset(skip).limit(limit).all()
    
    # Cargar datos personales para cada media
    for media in medias:
        usuario_media = db.query(models.UsuarioMedia).filter(
            models.UsuarioMedia.media_id == media.id,
            models.UsuarioMedia.usuario_id == usuario_id
        ).first()
        
        if usuario_media:
            media.favorito = usuario_media.favorito or False
            media.pendiente = usuario_media.pendiente or False
            media.nota_personal = usuario_media.nota_personal
            media.anotacion_personal = usuario_media.anotacion_personal
        else:
            media.favorito = False
            media.pendiente = False
            media.nota_personal = None
            media.anotacion_personal = None
    
    return medias

# CRUD para tags

def get_tags(db: Session, usuario_id: int = None):
    query = db.query(models.Tag)
    if usuario_id is not None:
        query = query.filter(models.Tag.usuario_id == usuario_id)
    return query.all()

def create_tag(db: Session, tag: schemas.TagCreate, usuario_id: int):
    # Normalizar y validar nombre (evita vacíos y duplicados por acentos/mayúsculas)
    name_input = (getattr(tag, 'nombre', '') or '').strip()
    if not name_input:
        # Mensaje claro para frontend/i18n existente
        raise Exception('El nombre del tag no puede estar vacío')
    normalized_new = models.normalize_str(name_input)

    # Comprobación en Python para evitar duplicados accent/case-insensitive
    # Solo verificar duplicados dentro de los tags del mismo usuario
    existing_tags = db.query(models.Tag).filter(models.Tag.usuario_id == usuario_id).all()
    for t in existing_tags:
        if models.normalize_str(getattr(t, 'nombre', '')) == normalized_new:
            raise Exception('Ya existe un tag con ese nombre')

    # Intentar crear; si hay colisión por UNIQUE, capturar y devolver mensaje coherente
    try:
        db_tag = models.Tag(nombre=name_input, usuario_id=usuario_id)
        db.add(db_tag)
        db.commit()
        db.refresh(db_tag)
        return db_tag
    except IntegrityError:
        db.rollback()
        raise Exception('Ya existe un tag con ese nombre')

def add_tag_to_media(db: Session, media_id: int, tag_id: int, usuario_id: int):
    # Verificar que el usuario tiene acceso al media y que el tag le pertenece
    usuario_media = db.query(models.UsuarioMedia).filter(
        models.UsuarioMedia.media_id == media_id,
        models.UsuarioMedia.usuario_id == usuario_id
    ).first()
    tag = db.query(models.Tag).filter(models.Tag.id == tag_id, models.Tag.usuario_id == usuario_id).first()
    
    if not usuario_media or not tag:
        return None
    
    # Verificar si la asociación ya existe
    existing = db.execute(
        text("SELECT 1 FROM media_tag WHERE media_id = :media_id AND tag_id = :tag_id AND usuario_id = :usuario_id"),
        {"media_id": media_id, "tag_id": tag_id, "usuario_id": usuario_id}
    ).fetchone()
    
    if not existing:
        # Insertar la asociación con usuario_id
        db.execute(
            text("INSERT INTO media_tag (media_id, tag_id, usuario_id) VALUES (:media_id, :tag_id, :usuario_id)"),
            {"media_id": media_id, "tag_id": tag_id, "usuario_id": usuario_id}
        )
        db.commit()
    
    # Devolver el media con tags eager-loaded
    from sqlalchemy.orm import joinedload
    return db.query(models.Media).options(joinedload(models.Media.tags)).filter(models.Media.id == media_id).first()


def remove_tag_from_media(db: Session, media_id: int, tag_id: int, usuario_id: int):
    # Verificar que el usuario tiene acceso al media y que el tag le pertenece
    usuario_media = db.query(models.UsuarioMedia).filter(
        models.UsuarioMedia.media_id == media_id,
        models.UsuarioMedia.usuario_id == usuario_id
    ).first()
    tag = db.query(models.Tag).filter(models.Tag.id == tag_id, models.Tag.usuario_id == usuario_id).first()
    
    if not usuario_media or not tag:
        return None
    
    # Eliminar la asociación específica del usuario
    db.execute(
        text("DELETE FROM media_tag WHERE media_id = :media_id AND tag_id = :tag_id AND usuario_id = :usuario_id"),
        {"media_id": media_id, "tag_id": tag_id, "usuario_id": usuario_id}
    )
    db.commit()
    
    # Devolver el media con tags eager-loaded
    from sqlalchemy.orm import joinedload
    return db.query(models.Media).options(joinedload(models.Media.tags)).filter(models.Media.id == media_id).first()

def delete_tag(db: Session, tag_id: int):
    db_tag = db.query(models.Tag).filter(models.Tag.id == tag_id).first()
    if db_tag:
        db.delete(db_tag)
        db.commit()
    return db_tag

def create_lista(db: Session, lista: schemas.ListaCreate, usuario_id: int):
    db_lista = models.Lista(nombre=lista.nombre, descripcion=lista.descripcion, usuario_id=usuario_id)
    db.add(db_lista)
    db.commit()
    db.refresh(db_lista)
    return db_lista

def get_listas(db: Session, usuario_id: int = None):
    query = db.query(models.Lista)
    if usuario_id is not None:
        query = query.filter(models.Lista.usuario_id == usuario_id)
    listas = query.all()
    
    # Cargar las medias de cada lista con sus datos personales del usuario
    for lista in listas:
        # Obtener las medias de la lista que el usuario tiene en su catálogo
        medias_con_datos = db.query(models.Media, models.UsuarioMedia).join(
            models.lista_media,
            models.Media.id == models.lista_media.c.media_id
        ).join(
            models.UsuarioMedia,
            (models.Media.id == models.UsuarioMedia.media_id) & 
            (models.UsuarioMedia.usuario_id == usuario_id)  # Usar el usuario_id del parámetro
        ).filter(
            models.lista_media.c.lista_id == lista.id
        ).all()
        
        # Enriquecer cada media con sus datos personales
        lista.medias = []
        for media, usuario_media in medias_con_datos:
            # Copiar datos personales al objeto media
            media.nota_personal = usuario_media.nota_personal
            media.anotacion_personal = usuario_media.anotacion_personal
            media.favorito = usuario_media.favorito
            media.pendiente = usuario_media.pendiente
            media.fecha_agregado = usuario_media.fecha_agregado
            lista.medias.append(media)
    
    return listas

def get_lista(db: Session, lista_id: int, usuario_id: int = None):
    query = db.query(models.Lista).filter(models.Lista.id == lista_id)
    if usuario_id is not None:
        query = query.filter(models.Lista.usuario_id == usuario_id)
    lista = query.first()
    
    if lista:
        # Obtener las medias de la lista que el usuario tiene en su catálogo, ordenadas por personal_position
        medias_con_datos = db.query(models.Media, models.UsuarioMedia, models.lista_media.c.personal_position).join(
            models.lista_media,
            models.Media.id == models.lista_media.c.media_id
        ).join(
            models.UsuarioMedia,
            (models.Media.id == models.UsuarioMedia.media_id) & 
            (models.UsuarioMedia.usuario_id == usuario_id)  # Usar el usuario_id del parámetro
        ).filter(
            models.lista_media.c.lista_id == lista.id
        ).order_by(models.lista_media.c.personal_position.asc()).all()
        
        # Enriquecer cada media con sus datos personales
        medias_enriquecidas = []
        for media, usuario_media, personal_position in medias_con_datos:
            if usuario_media:
                media.nota_personal = usuario_media.nota_personal
                media.anotacion_personal = usuario_media.anotacion_personal
                media.favorito = usuario_media.favorito
                media.pendiente = usuario_media.pendiente
                media.fecha_agregado = usuario_media.fecha_agregado
            else:
                # Valores por defecto si no hay datos personales
                media.nota_personal = None
                media.anotacion_personal = None
                media.favorito = False
                media.pendiente = False
                media.fecha_agregado = None
            # Agregar la posición personalizada
            media.personal_position = personal_position
            medias_enriquecidas.append(media)
        
        # Asignar las medias enriquecidas
        lista.medias = medias_enriquecidas
    
    return lista

def delete_lista(db: Session, lista_id: int, usuario_id: int = None):
    query = db.query(models.Lista).filter(models.Lista.id == lista_id)
    if usuario_id is not None:
        query = query.filter(models.Lista.usuario_id == usuario_id)
    db_lista = query.first()
    if db_lista:
        db.delete(db_lista)
        db.commit()
    return db_lista

def update_lista(db: Session, lista_id: int, nombre: str = None, descripcion: str = None, usuario_id: int = None):
    query = db.query(models.Lista).filter(models.Lista.id == lista_id)
    if usuario_id is not None:
        query = query.filter(models.Lista.usuario_id == usuario_id)
    db_lista = query.first()
    if db_lista:
        if nombre is not None:
            db_lista.nombre = nombre
        if descripcion is not None:
            db_lista.descripcion = descripcion
        db.commit()
        db.refresh(db_lista)
    return db_lista

def add_media_to_lista(db: Session, lista_id: int, media_id: int, usuario_id: int = None):
    # Verificar que la lista pertenece al usuario
    lista_query = db.query(models.Lista).filter(models.Lista.id == lista_id)
    if usuario_id is not None:
        lista_query = lista_query.filter(models.Lista.usuario_id == usuario_id)
    db_lista = lista_query.first()
    
    # Verificar que el usuario tiene el media en su catálogo
    usuario_media = None
    if usuario_id is not None:
        usuario_media = db.query(models.UsuarioMedia).filter(
            models.UsuarioMedia.media_id == media_id,
            models.UsuarioMedia.usuario_id == usuario_id
        ).first()
    db_media = db.query(models.Media).filter(models.Media.id == media_id).first()
    
    if db_lista and db_media and usuario_media:
        # Verificar si ya existe la relación
        existing = db.execute(
            text("SELECT 1 FROM lista_media WHERE lista_id = :lista_id AND media_id = :media_id"),
            {"lista_id": lista_id, "media_id": media_id}
        ).fetchone()
        
        if not existing:
            # Obtener la siguiente posición (máxima + 1)
            max_position = db.execute(
                text("SELECT COALESCE(MAX(personal_position), 0) FROM lista_media WHERE lista_id = :lista_id"),
                {"lista_id": lista_id}
            ).scalar()
            
            next_position = (max_position or 0) + 1
            
            # Insertar con la nueva posición
            db.execute(
                text("INSERT INTO lista_media (lista_id, media_id, personal_position) VALUES (:lista_id, :media_id, :position)"),
                {"lista_id": lista_id, "media_id": media_id, "position": next_position}
            )
            db.commit()
        
        db.refresh(db_lista)
    return db_lista

def remove_media_from_lista(db: Session, lista_id: int, media_id: int, usuario_id: int = None):
    # Verificar que la lista pertenece al usuario
    lista_query = db.query(models.Lista).filter(models.Lista.id == lista_id)
    if usuario_id is not None:
        lista_query = lista_query.filter(models.Lista.usuario_id == usuario_id)
    db_lista = lista_query.first()
    
    # Verificar que el usuario tiene el media en su catálogo
    usuario_media = None
    if usuario_id is not None:
        usuario_media = db.query(models.UsuarioMedia).filter(
            models.UsuarioMedia.media_id == media_id,
            models.UsuarioMedia.usuario_id == usuario_id
        ).first()
    db_media = db.query(models.Media).filter(models.Media.id == media_id).first()
    
    if db_lista and db_media and usuario_media:
        # Eliminar directamente de la tabla lista_media
        db.execute(
            text("DELETE FROM lista_media WHERE lista_id = :lista_id AND media_id = :media_id"),
            {"lista_id": lista_id, "media_id": media_id}
        )
        db.commit()
        db.refresh(db_lista)
    return db_lista

def update_lista_order(db: Session, lista_id: int, media_ids: list, usuario_id: int = None):
    """
    Actualiza el orden personalizado de los medias en una lista.
    media_ids debe ser una lista con los IDs en el orden deseado.
    """
    # Verificar que la lista pertenece al usuario
    lista_query = db.query(models.Lista).filter(models.Lista.id == lista_id)
    if usuario_id is not None:
        lista_query = lista_query.filter(models.Lista.usuario_id == usuario_id)
    db_lista = lista_query.first()
    
    if not db_lista:
        return None
    
    # Actualizar las posiciones en batch
    for position, media_id in enumerate(media_ids, start=1):
        db.execute(
            text("UPDATE lista_media SET personal_position = :position WHERE lista_id = :lista_id AND media_id = :media_id"),
            {"position": position, "lista_id": lista_id, "media_id": media_id}
        )
    
    db.commit()
    db.refresh(db_lista)
    return db_lista
