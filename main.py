import models
import database
import crud
import schemas
import os
import time
import requests
import unicodedata
from datetime import datetime, date
from translation_service import TranslationService, get_translation_service
from auto_update_service import AutoUpdateService, get_auto_update_service
from poster_cache import (
    get_poster_cache, 
    set_poster_cache, 
    get_batch_poster_cache, 
    set_batch_poster_cache,
    get_cache_key,
    get_cache_stats,
    clear_poster_cache
)
from fastapi import FastAPI, Depends, HTTPException, Query, Request, Body, status, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, text
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from genre_utils import get_consistent_name
from typing import List
import unicodedata
from bs4 import BeautifulSoup
from config import TMDB_BASE_URL, REQUEST_TIMEOUT, get_tmdb_auth_headers, get_allowed_origins, get_lan_origin_regex
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import JWTStrategy, AuthenticationBackend, BearerTransport
from fastapi_users.router import get_auth_router, get_register_router
from users import User
from user_manager import get_user_manager, SECRET, UserManager
from user_manager import get_user_db

from schemas import UserRead, UserCreate
import genre_routes

app = FastAPI()

# Incluir rutas de géneros
app.include_router(
    genre_routes.router,
    prefix="/api",
    tags=["genres"],
)

# Activar compresión GZIP para todas las respuestas

app.add_middleware(GZipMiddleware, minimum_size=500)


origins = get_allowed_origins()

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_origin_regex=get_lan_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)

# Configuración de autenticación
bearer_transport = BearerTransport(tokenUrl="auth/jwt/login")

def get_jwt_strategy() -> JWTStrategy:
    return JWTStrategy(secret=SECRET, lifetime_seconds=60 * 60 * 24)

auth_backend = AuthenticationBackend(
    name="jwt",
    transport=bearer_transport,
    get_strategy=get_jwt_strategy,
)

fastapi_users = FastAPIUsers[User, int](
    get_user_manager,
    [auth_backend],
)

# Dependencia para obtener el usuario actual (opcional)
current_user_optional = fastapi_users.current_user(optional=True)
# Dependencia para obtener el usuario actual (requerido)
current_user_required = fastapi_users.current_user()

# Servir frontend React compilado
CATALOG_BUILD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../catalog/build'))
if os.path.isdir(CATALOG_BUILD_DIR):
    app.mount("/static", StaticFiles(directory=os.path.join(CATALOG_BUILD_DIR, 'static')), name="static")

def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_best_poster(tmdb_id, media_type, language="es-ES"):
    """
    Obtiene la mejor portada para el idioma especificado.
    Busca primero portadas en el idioma solicitado, luego en inglés, y finalmente usa la por defecto.
    """
    headers = get_tmdb_auth_headers()
    
    # Obtener todas las imágenes disponibles
    images_url = f"{TMDB_BASE_URL}/{media_type}/{tmdb_id}/images"
    images_r = requests.get(images_url, headers=headers, timeout=REQUEST_TIMEOUT)
    
    if images_r.status_code != 200:
        # Si falla, usar la portada por defecto
        detail_url = f"{TMDB_BASE_URL}/{media_type}/{tmdb_id}"
        detail_r = requests.get(detail_url, headers=headers, params={"language": language}, timeout=REQUEST_TIMEOUT)
        if detail_r.status_code == 200:
            detail = detail_r.json()
            if detail.get("poster_path"):
                return f"https://image.tmdb.org/t/p/w500{detail['poster_path']}"
        return ""
    
    images_data = images_r.json()
    posters = images_data.get("posters", [])
    
    if not posters:
        return ""
    
    # Extraer el código de idioma base (ej: "es" de "es-ES")
    lang_code = language.split("-")[0] if language else "en"
    
    # Buscar portadas en el idioma específico primero
    lang_posters = [p for p in posters if p.get("iso_639_1") == lang_code]
    if lang_posters:
        # Ordenar por vote_average y tomar la mejor
        best_poster = max(lang_posters, key=lambda x: x.get("vote_average", 0))
        return f"https://image.tmdb.org/t/p/w500{best_poster['file_path']}"
    
    # Si no hay en el idioma solicitado, buscar en inglés
    en_posters = [p for p in posters if p.get("iso_639_1") == "en"]
    if en_posters:
        best_poster = max(en_posters, key=lambda x: x.get("vote_average", 0))
        return f"https://image.tmdb.org/t/p/w500{best_poster['file_path']}"
    
    # Si no hay en inglés, usar la mejor portada sin idioma específico (null)
    null_posters = [p for p in posters if p.get("iso_639_1") is None]
    if null_posters:
        best_poster = max(null_posters, key=lambda x: x.get("vote_average", 0))
        return f"https://image.tmdb.org/t/p/w500{best_poster['file_path']}"
    
    # Como último recurso, usar cualquier portada disponible
    if posters:
        best_poster = max(posters, key=lambda x: x.get("vote_average", 0))
        return f"https://image.tmdb.org/t/p/w500{best_poster['file_path']}"
    
    return ""

@app.get("/search", response_model=List[schemas.Media])
def search_medias(
    q: str = Query(..., description="Búsqueda por título, actor o director"),
    skip: int = 0,
    limit: int = 24,
    include_total: bool = Query(False, description="Si true, añade X-Total-Count y puede envolver en {items,total}"),
    db: Session = Depends(get_db),
    response: Response = None,
    current_user: User = Depends(current_user_optional)  # Autenticación opcional
):
    """Optimized search using direct SQL queries for better performance."""
    term = (q or "").strip()
    if not term:
        return []

    # Si no hay usuario autenticado, devolver lista vacía
    if current_user is None:
        if response is not None:
            response.headers["X-Total-Count"] = "0"
        return []

    # Búsqueda optimizada usando SQL directamente
    search_term = f"%{term.lower()}%"
    
    # Query SQL optimizada que busca directamente en la base de datos
    # Usamos outerjoin para cargar también los datos personales
    query = db.query(models.Media).outerjoin(
        models.UsuarioMedia, 
        (models.Media.id == models.UsuarioMedia.media_id) & 
        (models.UsuarioMedia.usuario_id == current_user.id)
    ).filter(
        # Solo medias que pertenecen al usuario
        models.UsuarioMedia.usuario_id == current_user.id
    ).filter(
        # Búsqueda en los campos de texto
        or_(
            func.lower(models.Media.titulo).like(search_term),
            func.lower(models.Media.original_title).like(search_term),
            func.lower(models.Media.elenco).like(search_term),
            func.lower(models.Media.director).like(search_term)
        )
    )
    
    # Contar resultados totales si es necesario
    if include_total:
        total = query.count()
        if response is not None:
            response.headers["X-Total-Count"] = str(total)
    
    # Aplicar paginación y ejecutar consulta
    items = query.offset(skip).limit(limit).all()
    
    # Agregar datos personales de usuario_media a cada item
    if items:
        for media in items:
            # Buscar datos personales directamente en la base de datos
            usuario_media = db.query(models.UsuarioMedia).filter(
                models.UsuarioMedia.media_id == media.id,
                models.UsuarioMedia.usuario_id == current_user.id
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
                media.fecha_agregado = None
    
    return items

@app.get("/search/multilingual")
async def search_multilingual(
    q: str = Query(..., description="Término de búsqueda"),
    limit: int = Query(20, ge=1, le=100, description="Límite de resultados"),
    include_language_info: bool = Query(False, description="Incluir información del idioma encontrado"),
    db: Session = Depends(get_db)
):
    """
    Búsqueda multiidioma avanzada que busca en:
    1. Títulos en español (media.titulo)
    2. Títulos originales (media.original_title) 
    3. Traducciones en otros idiomas (content_translations.title)
    
    Prioriza resultados en español, luego originales, luego otros idiomas.
    """
    
    search_pattern = f"%{q.lower()}%"
    
    # Query optimizada con UNION para búsqueda multiidioma
    multilingual_query = text("""
        WITH multilingual_search AS (
            -- Búsqueda en títulos españoles (tabla media)
            SELECT DISTINCT
                m.id,
                m.titulo,
                m.original_title,
                m.anio,
                m.tipo,
                m.genero,
                m.director,
                m.elenco,
                m.imagen,
                m.status,  -- Cambiado de estado a status
                m.nota_imdb,
                'es' as idioma_encontrado,
                m.titulo as titulo_encontrado,
                1 as prioridad
            FROM media m
            WHERE LOWER(m.titulo) LIKE :search_pattern
            
            UNION
            
            -- Búsqueda en títulos originales (tabla media)
            SELECT DISTINCT
                m.id,
                m.titulo,
                m.original_title,
                m.anio,
                m.tipo,
                m.genero,
                m.director,
                m.elenco,
                m.imagen,
                m.status,  -- Cambiado de estado a status
                m.nota_imdb,
                'original' as idioma_encontrado,
                m.original_title as titulo_encontrado,
                2 as prioridad
            FROM media m
            WHERE LOWER(m.original_title) LIKE :search_pattern
            AND m.original_title IS NOT NULL
            
            UNION
            
            -- Búsqueda en traducciones (content_translations)
            SELECT DISTINCT
                m.id,
                m.titulo,
                m.original_title,
                m.anio,
                m.tipo,
                m.genero,
                m.director,
                m.elenco,
                m.imagen,
                m.status,  -- Cambiado de estado a status
                m.nota_imdb,
                ct.language_code as idioma_encontrado,
                ct.title as titulo_encontrado,
                3 as prioridad
            FROM media m
            INNER JOIN content_translations ct ON m.id = ct.media_id
            WHERE LOWER(ct.title) LIKE :search_pattern
            AND ct.language_code NOT IN ('es')  -- Evitar duplicar español
        )
        SELECT * FROM multilingual_search
        ORDER BY prioridad, titulo
        LIMIT :limit_val
    """)
    
    # Ejecutar búsqueda
    result = db.execute(multilingual_query, {
        'search_pattern': search_pattern,
        'limit_val': limit
    })
    
    # Procesar resultados
    movies = []
    for row in result:
        movie_data = {
            "id": row[0],
            "titulo": row[1],
            "original_title": row[2],
            "anio": row[3],
            "tipo": row[4],
            "genero": row[5],
            "director": row[6],
            "elenco": row[7],
            "imagen": row[8],
            "status": row[9],  # Cambiado de estado a status
            "nota_imdb": row[10]
        }
        
        # Añadir información del idioma si se solicita
        if include_language_info:
            movie_data["search_info"] = {
                "idioma_encontrado": row[11],
                "titulo_encontrado": row[12],
                "prioridad": row[13]
            }
        
        movies.append(movie_data)
    
    return {
        "query": q,
        "total_found": len(movies),
        "results": movies,
        "search_info": {
            "languages_searched": ["es", "original", "en", "pt", "fr", "de", "it"],
            "priority_order": ["español", "original", "otros_idiomas"]
        }
    }

@app.get("/search/languages")
async def get_available_languages(db: Session = Depends(get_db)):
    """
    Obtiene los idiomas disponibles para búsqueda
    """
    
    # Idiomas en content_translations
    translation_languages = db.execute(text("""
        SELECT language_code, COUNT(*) as count 
        FROM content_translations 
        GROUP BY language_code 
        ORDER BY count DESC
    """)).fetchall()
    
    # Estadísticas de media
    media_stats = db.execute(text("""
        SELECT 
            COUNT(*) as total_media,
            COUNT(original_title) as with_original_title
        FROM media
    """)).fetchone()
    
    return {
        "available_languages": {
            "es": {
                "name": "Español",
                "source": "media.titulo",
                "count": media_stats[0]
            },
            "original": {
                "name": "Título Original",
                "source": "media.original_title", 
                "count": media_stats[1]
            }
        },
        "translation_languages": [
            {
                "code": row[0],
                "count": row[1],
                "source": "content_translations"
            }
            for row in translation_languages
        ],
        "total_searchable_titles": sum(row[1] for row in translation_languages) + media_stats[0]
    }

@app.on_event("startup")
def startup():
    database.init_db()

@app.get("/medias", response_model=List[schemas.Media])
def read_medias(
    skip: int = 0,
    limit: int = 24,
    tag_id: int = None,
    order_by: str = None,
    tipo: str = None,
    genero: str = None,
    min_year: int = None,
    max_year: int = None,
    min_nota: float = None,
    max_nota: float = None,
    min_nota_personal: float = None,
    max_nota_personal: float = None,
    favorito: bool = None,
    pendiente: bool = None,
    tmdb_id: int = None,
    exclude_ids: str | None = Query(None, description="Comma-separated IDs to exclude from results"),
    include_total: bool = Query(False, description="Si true, añade X-Total-Count a la respuesta"),
    db: Session = Depends(get_db),
    response: Response = None,
    current_user: User = Depends(current_user_optional)  # Autenticación opcional
):
    """
    Obtiene las películas/series del catálogo privado del usuario autenticado.
    Si no hay usuario autenticado, devuelve lista vacía.
    """
    import traceback
    try:
        # Si no hay usuario autenticado, devolver lista vacía
        if current_user is None:
            if response is not None:
                response.headers["X-Total-Count"] = "0"
            return []
        
        # Solo obtener medias del usuario actual
        exclude_list = []
        if exclude_ids:
            try:
                exclude_list = [int(x) for x in exclude_ids.split(',') if x.strip().isdigit()]
            except Exception:
                exclude_list = []

        base_query = crud.get_medias_query(
            db, skip=skip, limit=limit, order_by=order_by, tipo=tipo,
            genero=genero, min_year=min_year, max_year=max_year,
            min_nota=min_nota, max_nota=max_nota, min_nota_personal=min_nota_personal, max_nota_personal=max_nota_personal,
            favorito=favorito, pendiente=pendiente, tag_id=tag_id, tmdb_id=tmdb_id,
            usuario_id=current_user.id,  # Filtrar por usuario
            exclude_ids=exclude_list
        )
        
        if include_total:
            # Para el total, usamos la query sin paginación
            total_query = crud.get_medias_query(
                db, skip=0, limit=99999, order_by=order_by, tipo=tipo,
                genero=genero, min_year=min_year, max_year=max_year,
                min_nota=min_nota, max_nota=max_nota, min_nota_personal=min_nota_personal, max_nota_personal=max_nota_personal,
                favorito=favorito, pendiente=pendiente, tag_id=tag_id, tmdb_id=tmdb_id,
                usuario_id=current_user.id
            )
            total = total_query.count()
            if response is not None:
                response.headers["X-Total-Count"] = str(total)
        
        result = base_query.offset(skip).limit(limit).all()
        
        # Cargar manualmente los datos personales de UsuarioMedia para cada resultado
        if result and current_user:
            media_ids = [media.id for media in result]
            user_data = db.query(models.UsuarioMedia).filter(
                models.UsuarioMedia.media_id.in_(media_ids),
                models.UsuarioMedia.usuario_id == current_user.id
            ).all()
            
            # Crear un diccionario para mapear rápido
            user_data_map = {um.media_id: um for um in user_data}
            
            # Aplicar datos personales a cada media
            for media in result:
                um = user_data_map.get(media.id)
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
        
        return result
    except Exception as e:
        print("ERROR EN /medias:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

import unicodedata

@app.get("/medias/count")
def count_medias(
    tipo: str = None,
    pendiente: bool = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_user_required)
):
    # Query con JOIN a usuario_media para filtros personales
    query = db.query(models.Media).join(
        models.UsuarioMedia,
        (models.Media.id == models.UsuarioMedia.media_id) & 
        (models.UsuarioMedia.usuario_id == current_user.id)
    )
    
    # Filtrar por pendiente si se especifica
    if pendiente is not None:
        if pendiente:
            query = query.filter(models.UsuarioMedia.pendiente == True)
        else:
            query = query.filter(
                (models.UsuarioMedia.pendiente == False) | 
                (models.UsuarioMedia.pendiente.is_(None))
            )
    
    if tipo:
        def normalize(s):
            return unicodedata.normalize('NFKD', s or '').encode('ASCII', 'ignore').decode('ASCII').lower().strip()
        ids = [m.id for m in query if normalize(m.tipo) == normalize(tipo)]
        query = query.filter(models.Media.id.in_(ids))
    return {"count": query.count()}

@app.get("/medias/top5")
def top5_medias(
    tipo: str = Query(..., description="pelicula o serie"),
    db: Session = Depends(get_db),
    current_user: User = Depends(current_user_required)
):
    # Query con JOIN a usuario_media para obtener notas personales
    results = db.query(models.Media, models.UsuarioMedia).join(
        models.UsuarioMedia,
        models.Media.id == models.UsuarioMedia.media_id
    ).filter(
        models.UsuarioMedia.usuario_id == current_user.id,
        models.UsuarioMedia.nota_personal.isnot(None),
        models.UsuarioMedia.pendiente == False
    )
    
    # Filtrar por tipo
    if tipo:
        def normalize(s):
            return unicodedata.normalize('NFKD', s or '').encode('ASCII', 'ignore').decode('ASCII').lower().strip()
        tipo_norm = normalize(tipo)
        results = results.filter(
            func.lower(func.replace(func.replace(models.Media.tipo, 'í', 'i'), 'é', 'e')) == tipo_norm
        )
    
    # Ordenar por nota personal descendente y obtener top 5
    top_results = results.order_by(models.UsuarioMedia.nota_personal.desc()).limit(5).all()
    
    # Procesar resultados para incluir datos personales
    medias = []
    for media, usuario_media in top_results:
        # Agregar datos personales a cada media
        media.nota_personal = usuario_media.nota_personal
        media.favorito = usuario_media.favorito or False
        media.pendiente = usuario_media.pendiente or False
        media.anotacion_personal = usuario_media.anotacion_personal
        media.fecha_agregado = usuario_media.fecha_agregado
        medias.append(media)
    
    return medias

def get_generos(db: Session, user: User):
    import unicodedata
    def normalize(s):
        return unicodedata.normalize('NFKD', s or '').encode('ASCII', 'ignore').decode('ASCII').lower().strip()
    
    # Obtener medias vistas por el usuario (no pendientes)
    results = db.query(models.Media, models.UsuarioMedia).join(
        models.UsuarioMedia, models.Media.id == models.UsuarioMedia.media_id
    ).filter(
        models.UsuarioMedia.usuario_id == user.id,
        models.UsuarioMedia.pendiente == False
    ).all()
    
    genero_count = {}
    genero_original = {}
    genero_notas = {}
    
    for media, usuario_media in results:
        generos = (getattr(media, 'genero', '') or '').split(',')
        generos = [g.strip() for g in generos if g.strip()]
        for g in generos:
            g_norm = normalize(g)
            genero_count[g_norm] = genero_count.get(g_norm, 0) + 1
            if g_norm not in genero_original:
                genero_original[g_norm] = g  # Guarda el nombre original
            if usuario_media.nota_personal is not None:
                genero_notas.setdefault(g_norm, []).append(usuario_media.nota_personal)
    return genero_count, genero_original, genero_notas

@app.get("/medias/distribucion_generos")
def distribucion_generos(user: User = Depends(current_user_required), db: Session = Depends(get_db)):
    genero_count, genero_original, _ = get_generos(db, user)
    # Consolidar géneros usando el mapeo centralizado (genre_utils)
    generos_consolidados = {}
    for g_norm, count in genero_count.items():
        # Tomar el nombre original almacenado y normalizar mediante genre_utils
        original_name = genero_original[g_norm]
        consistent_name = get_consistent_name(original_name) or original_name.title()
        
        if consistent_name in generos_consolidados:
            generos_consolidados[consistent_name] += count
        else:
            generos_consolidados[consistent_name] = count
    
    return generos_consolidados

@app.get("/medias/generos_vistos")
def generos_vistos(user: User = Depends(current_user_required), db: Session = Depends(get_db)):
    genero_count, genero_original, genero_notas = get_generos(db, user)
    # Género más visto
    mas_visto = None
    mas_visto_count = 0
    if genero_count:
        mas_visto_norm = max(genero_count.items(), key=lambda x: x[1])[0]
        mas_visto = genero_original.get(mas_visto_norm, mas_visto_norm)
        mas_visto_count = genero_count[mas_visto_norm]
    # Género mejor valorado
    mejor_valorado = None
    mejor_media = None
    if genero_notas:
        candidatos = [(g, sum(notas)/len(notas), len(notas)) for g, notas in genero_notas.items() if len(notas) >= 1]
        candidatos.sort(key=lambda x: (-x[1], -x[2]))
        if candidatos:
            mejor_valorado = genero_original.get(candidatos[0][0], candidatos[0][0])
            mejor_media = round(candidatos[0][1], 2)
    return {
        "mas_visto": mas_visto or '',
        "mas_visto_count": mas_visto_count,
        "mejor_valorado": mejor_valorado or '',
        "mejor_valorado_media": mejor_media if mejor_media is not None else ''
    }

@app.get("/medias/peor_pelicula", response_model=schemas.Media)
def peor_pelicula(user: User = Depends(current_user_required), db: Session = Depends(get_db)):
    def normalize(s):
        return unicodedata.normalize('NFKD', s or '').encode('ASCII', 'ignore').decode('ASCII').lower().strip()
    tipo_norm = 'pelicula'
    result = db.query(models.Media, models.UsuarioMedia).join(
        models.UsuarioMedia, models.Media.id == models.UsuarioMedia.media_id
    ).filter(
        models.UsuarioMedia.usuario_id == user.id,
        models.UsuarioMedia.pendiente == False,
        models.UsuarioMedia.nota_personal != None
    ).filter(
        func.lower(func.replace(func.replace(models.Media.tipo, 'í', 'i'), 'é', 'e')) == tipo_norm
    ).order_by(models.UsuarioMedia.nota_personal.asc()).first()
    if not result:
        raise HTTPException(status_code=404, detail="No hay películas con nota personal")
    
    media, usuario_media = result
    # Agregar datos personales
    media.nota_personal = usuario_media.nota_personal
    media.favorito = usuario_media.favorito or False
    media.pendiente = usuario_media.pendiente or False
    media.anotacion_personal = usuario_media.anotacion_personal
    media.fecha_agregado = usuario_media.fecha_agregado
    return media

@app.get("/medias/peor_serie", response_model=schemas.Media)
def peor_serie(user: User = Depends(current_user_required), db: Session = Depends(get_db)):
    def normalize(s):
        return unicodedata.normalize('NFKD', s or '').encode('ASCII', 'ignore').decode('ASCII').lower().strip()
    tipo_norm = 'serie'
    result = db.query(models.Media, models.UsuarioMedia).join(
        models.UsuarioMedia, models.Media.id == models.UsuarioMedia.media_id
    ).filter(
        models.UsuarioMedia.usuario_id == user.id,
        models.UsuarioMedia.pendiente == False,
        models.UsuarioMedia.nota_personal != None
    ).filter(
        func.lower(func.replace(func.replace(models.Media.tipo, 'í', 'i'), 'é', 'e')) == tipo_norm
    ).order_by(models.UsuarioMedia.nota_personal.asc()).first()
    if not result:
        raise HTTPException(status_code=404, detail="No hay series con nota personal")
    
    media, usuario_media = result
    # Agregar datos personales
    media.nota_personal = usuario_media.nota_personal
    media.favorito = usuario_media.favorito or False
    media.pendiente = usuario_media.pendiente or False
    media.anotacion_personal = usuario_media.anotacion_personal
    media.fecha_agregado = usuario_media.fecha_agregado
    return media

@app.get("/medias/vistos_por_anio")
def vistos_por_anio(user: User = Depends(current_user_required), db: Session = Depends(get_db)):
    medias = db.query(models.Media).join(
        models.UsuarioMedia, models.Media.id == models.UsuarioMedia.media_id
    ).filter(
        models.UsuarioMedia.usuario_id == user.id,
        models.UsuarioMedia.pendiente == False
    ).all()
    conteo = {}
    for m in medias:
        anio = getattr(m, 'anio', None)
        if anio:
            conteo[anio] = conteo.get(anio, 0) + 1
    return conteo

@app.get("/medias/top_personas")
def top_personas(user: User = Depends(current_user_required), db: Session = Depends(get_db)):
    from collections import Counter
    medias = db.query(models.Media).join(
        models.UsuarioMedia, models.Media.id == models.UsuarioMedia.media_id
    ).filter(
        models.UsuarioMedia.usuario_id == user.id,
        models.UsuarioMedia.pendiente == False
    ).all()
    actores = []
    directores = []
    for m in medias:
        # Elenco: puede ser una cadena separada por coma
        elenco = (getattr(m, 'elenco', '') or '').split(',')
        elenco = [a.strip() for a in elenco if a.strip()]
        actores.extend(elenco)
        # Director: puede ser una cadena separada por coma
        director = (getattr(m, 'director', '') or '').split(',')
        director = [d.strip() for d in director if d.strip()]
        directores.extend(director)
    top_actores = Counter(actores).most_common(5)
    top_directores = Counter(directores).most_common(5)
    return {
        "top_actores": top_actores,
        "top_directores": top_directores
    }

    conteo = {}
    for m in medias:
        anio = getattr(m, 'anio', None)
        if anio is not None:
            conteo[anio] = conteo.get(anio, 0) + 1
    # Devuelve ordenado por año ascendente
    return dict(sorted(conteo.items()))

@app.get("/health")
def healthcheck():
    started = time.time()
    db_status = "error"
    db_error = None
    try:
        with database.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_error = str(e)
    cache = {
        "poster_cache": get_cache_stats() or {}
    }
    elapsed_ms = round((time.time() - started) * 1000)
    overall = "ok" if db_status == "ok" else "degraded"
    return {
        "status": overall,
        "db": db_status,
        "db_error": db_error,
        "cache": cache,
        "latency_ms": elapsed_ms
    }

@app.get("/medias/{media_id}", response_model=schemas.Media)
def read_media(media_id: int, db: Session = Depends(get_db), current_user: User = Depends(current_user_required)):
    # Verificar que el usuario tiene este media en su catálogo
    usuario_media = db.query(models.UsuarioMedia).filter(
        models.UsuarioMedia.media_id == media_id,
        models.UsuarioMedia.usuario_id == current_user.id
    ).first()
    
    if usuario_media is None:
        raise HTTPException(status_code=404, detail="Media not found")
    
    # Obtener el media completo con tags del usuario
    db_media = crud.get_media(db, media_id=media_id, usuario_id=current_user.id)
    return db_media

@app.get("/medias/{media_id}/similares", response_model=List[schemas.Media])
def get_similares(media_id: int, db: Session = Depends(get_db), current_user: User = Depends(current_user_required)):
    # Verificar que el usuario tiene este media en su catálogo
    usuario_media = db.query(models.UsuarioMedia).filter(
        models.UsuarioMedia.media_id == media_id,
        models.UsuarioMedia.usuario_id == current_user.id
    ).first()
    
    if usuario_media is None:
        raise HTTPException(status_code=404, detail="Media not found")
    
    # Obtener similares solo del catálogo del usuario actual
    similares = crud.get_similares_para_media(db, media_id, usuario_id=current_user.id, n=24)
    return similares

@app.post("/medias", response_model=schemas.Media)
def create_media(media: schemas.MediaCreate, db: Session = Depends(get_db), current_user: User = Depends(current_user_required)):
    try:
        return crud.create_media(db, media, usuario_id=current_user.id)
    except Exception as e:
        raise HTTPException(status_code=409, detail=str(e))

@app.delete("/medias/{media_id}", response_model=schemas.Media)
def delete_media(media_id: int, db: Session = Depends(get_db), current_user: User = Depends(current_user_required)):
    db_media = crud.delete_media(db, media_id, usuario_id=current_user.id)
    if db_media is None:
        raise HTTPException(status_code=404, detail="Media not found")
    return db_media

@app.patch("/medias/{media_id}/pendiente", response_model=schemas.Media)
def update_pendiente(media_id: int, pendiente: bool, db: Session = Depends(get_db), current_user: User = Depends(current_user_required)):
    db_media = crud.update_media_pendiente(db, media_id, pendiente, usuario_id=current_user.id)
    if db_media is None:
        raise HTTPException(status_code=404, detail="Media not found")
    return db_media

@app.patch("/medias/{media_id}/favorito", response_model=schemas.Media)
def update_favorito(media_id: int, favorito: bool, db: Session = Depends(get_db), current_user: User = Depends(current_user_required)):
    db_media = crud.update_media_favorito(db, media_id, favorito, usuario_id=current_user.id)
    if db_media is None:
        raise HTTPException(status_code=404, detail="Media not found")
    return db_media

@app.patch("/medias/{media_id}/anotacion_personal", response_model=schemas.Media)
def update_anotacion_personal(media_id: int, anotacion_personal: str = Body(...), db: Session = Depends(get_db), current_user: User = Depends(current_user_required)):
    db_media = crud.update_media_anotacion_personal(db, media_id, anotacion_personal, usuario_id=current_user.id)
    if db_media is None:
        raise HTTPException(status_code=404, detail="Media not found")
    return db_media

@app.patch("/medias/{media_id}/nota_personal", response_model=schemas.Media)
def update_nota_personal(media_id: int, nota_personal: float = Body(...), db: Session = Depends(get_db), current_user: User = Depends(current_user_required)):
    db_media = crud.update_media_nota_personal(db, media_id, nota_personal, usuario_id=current_user.id)
    if db_media is None:
        raise HTTPException(status_code=404, detail="Media not found")
    return db_media

@app.get("/pendientes", response_model=List[schemas.Media])
def read_pendientes(skip: int = 0, limit: int = 24, db: Session = Depends(get_db), current_user: User = Depends(current_user_required)):
    return crud.get_pendientes(db, skip=skip, limit=limit, usuario_id=current_user.id)

@app.get("/favoritos", response_model=List[schemas.Media])
def read_favoritos(skip: int = 0, limit: int = 24, db: Session = Depends(get_db), current_user: User = Depends(current_user_required)):
    return crud.get_favoritos(db, skip=skip, limit=limit, usuario_id=current_user.id)

@app.get("/tags", response_model=List[schemas.Tag])
def get_tags(db: Session = Depends(get_db), current_user: User = Depends(current_user_optional)):
    """
    Obtiene los tags disponibles del usuario autenticado. Sin autenticación devuelve lista vacía.
    """
    if current_user is None:
        return []
    return crud.get_tags(db, usuario_id=current_user.id)

@app.post("/tags", response_model=schemas.Tag)
def create_tag(tag: schemas.TagCreate, db: Session = Depends(get_db), current_user: User = Depends(current_user_required)):
    try:
        return crud.create_tag(db, tag, usuario_id=current_user.id)
    except Exception as e:
        msg = str(e)
        lower = msg.lower()
        status_code = 409 if "existe un tag" in lower else 400
        raise HTTPException(status_code=status_code, detail=msg)

@app.get("/medias/{media_id}/translations", response_model=schemas.TranslationSummary)
def get_media_translation_summary(media_id: int, db: Session = Depends(get_db), current_user: User = Depends(current_user_required)):
    """
    Obtiene un resumen de las traducciones disponibles para un media específico
    """
    # Verificar que el usuario tiene acceso a este media
    user_media = crud.get_media(db, media_id, usuario_id=current_user.id)
    if not user_media:
        raise HTTPException(status_code=404, detail="Media not found")
    
    from auto_translation_service import get_translation_summary
    summary = get_translation_summary(db, media_id)
    return schemas.TranslationSummary(**summary)

@app.get("/medias/check-personal-catalog/{tmdb_id}")
def check_tmdb_in_personal_catalog(tmdb_id: int, db: Session = Depends(get_db), current_user: User = Depends(current_user_required)):
    """
    Verifica si un título (por TMDb ID) ya está en el catálogo personal del usuario
    """
    # Buscar si existe un media con este tmdb_id en el catálogo personal del usuario
    user_media = db.query(models.UsuarioMedia).join(
        models.Media, models.UsuarioMedia.media_id == models.Media.id
    ).filter(
        models.Media.tmdb_id == tmdb_id,
        models.UsuarioMedia.usuario_id == current_user.id
    ).first()
    
    if user_media:
        # El título ya está en el catálogo personal
        media = db.query(models.Media).filter(models.Media.id == user_media.media_id).first()
        return {
            "exists": True,
            "in_personal_catalog": True,
            "media_id": media.id,
            "titulo": media.titulo,
            "tipo": media.tipo,
            "anio": media.anio,
            "fecha_agregado": user_media.fecha_agregado.isoformat() if user_media.fecha_agregado else None,
            "favorito": user_media.favorito,
            "pendiente": user_media.pendiente
        }
    else:
        # Verificar si el título existe en la tabla media general pero no en el catálogo personal
        media_exists = db.query(models.Media).filter(models.Media.tmdb_id == tmdb_id).first()
        
        return {
            "exists": False,
            "in_personal_catalog": False,
            "exists_in_general": media_exists is not None,
            "media_id": media_exists.id if media_exists else None,
            "titulo": media_exists.titulo if media_exists else None,
            "tipo": media_exists.tipo if media_exists else None
        }

@app.post("/medias/{media_id}/tags/{tag_id}", response_model=schemas.Media)
def add_tag_to_media(media_id: int, tag_id: int, db: Session = Depends(get_db), current_user: User = Depends(current_user_required)):
    # Verificar que el usuario tiene este media en su catálogo
    usuario_media = db.query(models.UsuarioMedia).filter(
        models.UsuarioMedia.media_id == media_id, 
        models.UsuarioMedia.usuario_id == current_user.id
    ).first()
    if not usuario_media:
        raise HTTPException(status_code=404, detail="Media not found")
    
    tag = db.query(models.Tag).filter(models.Tag.id == tag_id, models.Tag.usuario_id == current_user.id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    media = crud.add_tag_to_media(db, media_id, tag_id, current_user.id)
    if not media:
        raise HTTPException(status_code=404, detail="Media o Tag no encontrado")
    return media

@app.delete("/medias/{media_id}/tags/{tag_id}", response_model=schemas.Media)
def remove_tag_from_media(media_id: int, tag_id: int, db: Session = Depends(get_db), current_user: User = Depends(current_user_required)):
    # Verificar que el usuario tiene este media en su catálogo
    usuario_media = db.query(models.UsuarioMedia).filter(
        models.UsuarioMedia.media_id == media_id, 
        models.UsuarioMedia.usuario_id == current_user.id
    ).first()
    if not usuario_media:
        raise HTTPException(status_code=404, detail="Media not found")
    
    tag = db.query(models.Tag).filter(models.Tag.id == tag_id, models.Tag.usuario_id == current_user.id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    media = crud.remove_tag_from_media(db, media_id, tag_id, current_user.id)
    if not media:
        raise HTTPException(status_code=404, detail="Media o Tag no encontrado")
    return media

@app.delete("/tags/{tag_id}", response_model=schemas.Tag)
def delete_tag(tag_id: int, db: Session = Depends(get_db), current_user: User = Depends(current_user_required)):
    # Verificar que el tag pertenece al usuario autenticado
    tag = db.query(models.Tag).filter(models.Tag.id == tag_id, models.Tag.usuario_id == current_user.id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    
    db_tag = crud.delete_tag(db, tag_id)
    if db_tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    return db_tag

# ===== ENDPOINTS DE LISTAS =====

@app.get("/listas")
def get_listas(db: Session = Depends(get_db), current_user: User = Depends(current_user_optional)):
    """
    Obtiene las listas del usuario autenticado. Sin autenticación devuelve lista vacía.
    """
    if current_user is None:
        return []
    
    listas = crud.get_listas(db, usuario_id=current_user.id)
    return listas

@app.post("/listas")
def create_lista(lista_data: dict, db: Session = Depends(get_db), current_user: User = Depends(current_user_required)):
    """
    Crea una nueva lista para el usuario autenticado.
    """
    nombre = lista_data.get('nombre', '').strip()
    descripcion = lista_data.get('descripcion', '').strip() or None
    
    if not nombre:
        raise HTTPException(status_code=400, detail="El nombre es obligatorio")
    
    # Crear la lista en la base de datos
    db_lista = models.Lista(
        nombre=nombre,
        descripcion=descripcion,
        usuario_id=current_user.id
    )
    db.add(db_lista)
    db.commit()
    db.refresh(db_lista)
    
    # Devolver la lista con medias vacías para compatibilidad con el frontend
    return {
        "id": db_lista.id,
        "nombre": db_lista.nombre,
        "descripcion": db_lista.descripcion,
        "medias": []
    }

@app.get("/listas/{lista_id}")
def get_lista(lista_id: int, db: Session = Depends(get_db), current_user: User = Depends(current_user_required)):
    """
    Obtiene una lista específica del usuario autenticado.
    """
    lista = crud.get_lista(db, lista_id, usuario_id=current_user.id)
    if not lista:
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    return lista

@app.delete("/listas/{lista_id}")
def delete_lista(lista_id: int, db: Session = Depends(get_db), current_user: User = Depends(current_user_required)):
    """
    Elimina una lista del usuario autenticado.
    """
    lista = crud.delete_lista(db, lista_id, usuario_id=current_user.id)
    if not lista:
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    return {"message": "Lista eliminada correctamente"}

@app.put("/listas/{lista_id}")
def update_lista(lista_id: int, lista_data: dict, db: Session = Depends(get_db), current_user: User = Depends(current_user_required)):
    """
    Actualiza una lista del usuario autenticado.
    """
    nombre = lista_data.get('nombre')
    descripcion = lista_data.get('descripcion')
    
    lista = crud.update_lista(db, lista_id, nombre=nombre, descripcion=descripcion, usuario_id=current_user.id)
    if not lista:
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    return lista

@app.post("/listas/{lista_id}/medias/{media_id}")
def add_media_to_lista(lista_id: int, media_id: int, db: Session = Depends(get_db), current_user: User = Depends(current_user_required)):
    """
    Añade un media a una lista del usuario autenticado.
    """
    lista = crud.add_media_to_lista(db, lista_id, media_id, usuario_id=current_user.id)
    if not lista:
        raise HTTPException(status_code=404, detail="Lista o Media no encontrado")
    return lista

@app.delete("/listas/{lista_id}/medias/{media_id}")
def remove_media_from_lista(lista_id: int, media_id: int, db: Session = Depends(get_db), current_user: User = Depends(current_user_required)):
    """
    Remueve un media de una lista del usuario autenticado.
    """
    lista = crud.remove_media_from_lista(db, lista_id, media_id, usuario_id=current_user.id)
    if not lista:
        raise HTTPException(status_code=404, detail="Lista o Media no encontrado")
    return lista

@app.put("/listas/{lista_id}/order")
def update_lista_order(lista_id: int, media_ids: List[int] = Body(...), db: Session = Depends(get_db), current_user: User = Depends(current_user_required)):
    """
    Actualiza el orden personalizado de los medias en una lista del usuario autenticado.
    """
    lista = crud.update_lista_order(db, lista_id, media_ids, usuario_id=current_user.id)
    if not lista:
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    return {"success": True, "message": "Orden actualizado correctamente"}

@app.get("/tmdb")
def get_tmdb_info(
    title: str = Query(None, description="Título de la película o serie"),
    tipo_preferido: str = Query(None, description="Priorizar 'película' o 'serie' si se desea"),
    listar: bool = Query(False, description="Si True, devuelve todas las coincidencias en vez de solo una"),
    id: int = Query(None, description="ID TMDb exacto"),
    media_type: str = Query(None, description="'movie' o 'tv' si se busca por id"),
    language: str = Query("es-ES", description="Idioma para la consulta TMDb (ej: 'es-ES', 'en-US')")
):
    headers = get_tmdb_auth_headers()
    # Si se pasa id y media_type, buscar detalle exacto
    if id and media_type:
        tipo = "película" if media_type == "movie" else "serie"
        if tipo == "película":
            detail_url = f"{TMDB_BASE_URL}/movie/{id}"
            credits_url = f"{TMDB_BASE_URL}/movie/{id}/credits"
            detail_params = {"language": language}
            detail_r = requests.get(detail_url, headers=headers, params=detail_params, timeout=REQUEST_TIMEOUT)
            if detail_r.status_code != 200:
                raise HTTPException(status_code=502, detail="Error al obtener detalles de TMDb")
            detail = detail_r.json()
            credits_r = requests.get(credits_url, headers=headers, timeout=REQUEST_TIMEOUT)
            director = ""
            elenco = ""
            if credits_r.status_code == 200:
                credits = credits_r.json()
                director_list = [c["name"] for c in credits.get("crew", []) if c.get("job") == "Director"]
                director = ", ".join(director_list)
                elenco_list = [a["name"] for a in credits.get("cast", [])[:5]]
                elenco = ", ".join(elenco_list)
            # Obtener tráiler de YouTube (primero en el idioma solicitado, luego en inglés si no hay)
            trailer_url = None
            videos_url = f"{TMDB_BASE_URL}/movie/{id}/videos"
            videos_r = requests.get(videos_url, headers=headers, params={"language": language}, timeout=REQUEST_TIMEOUT)
            videos = []
            if videos_r.status_code == 200:
                videos = videos_r.json().get("results", [])
            yt_trailers = [v for v in videos if v.get("site") == "YouTube" and v.get("type") == "Trailer"]
            if not yt_trailers and language != "en-US":
                videos_r_en = requests.get(videos_url, headers=headers, params={"language": "en-US"}, timeout=REQUEST_TIMEOUT)
                if videos_r_en.status_code == 200:
                    videos_en = videos_r_en.json().get("results", [])
                    yt_trailers = [v for v in videos_en if v.get("site") == "YouTube" and v.get("type") == "Trailer"]
            if yt_trailers:
                trailer_url = f"https://www.youtube.com/watch?v={yt_trailers[0]['key']}"
            
            # Procesar production_countries
            production_countries = None
            if detail.get("production_countries"):
                production_countries = ", ".join([country["name"] for country in detail["production_countries"]])
            
            # Procesar release_date
            release_date = None
            if detail.get("release_date"):
                try:
                    release_date = datetime.strptime(detail["release_date"], "%Y-%m-%d").date()
                except:
                    pass
            
            return {
                "titulo": detail.get("title") or detail.get("name", ""),
                "titulo_original": detail.get("original_title", ""),
                "idioma_original": detail.get("original_language", ""),
                "anio": int(detail.get("release_date", "").split("-")[0]) if detail.get("release_date") else None,
                "genero": ", ".join([g["name"] for g in detail.get("genres", [])]),
                "sinopsis": detail.get("overview", ""),
                "director": director,
                "elenco": elenco,
                "imagen": get_best_poster(id, "movie", language),
                "status": detail.get("status", ""),  # Cambiado de estado a status
                "tipo": tipo,
                "temporadas": None,
                "episodios": None,
                "nota_personal": None,
                "nota_tmdb": detail.get("vote_average"),
                "votos_tmdb": detail.get("vote_count"),
                "presupuesto": detail.get("budget"),
                "recaudacion": detail.get("revenue"),
                "trailer": trailer_url,
                # Campos adicionales para películas
                "runtime": detail.get("runtime"),
                "production_countries": production_countries,
                "status": detail.get("status", ""),
                "certification": None,  # Se manejará en las traducciones por región
                "first_air_date": None,  # Solo para series
                "last_air_date": None,   # Solo para series
                "episode_runtime": None  # Solo para series
            }
        else:
            detail_url = f"{TMDB_BASE_URL}/tv/{id}"
            credits_url = f"{TMDB_BASE_URL}/tv/{id}/credits"
            detail_params = {"language": language}
            detail_r = requests.get(detail_url, headers=headers, params=detail_params, timeout=REQUEST_TIMEOUT)
            if detail_r.status_code != 200:
                raise HTTPException(status_code=502, detail="Error al obtener detalles de TMDb")
            detail = detail_r.json()
            credits_r = requests.get(credits_url, headers=headers, timeout=REQUEST_TIMEOUT)
            director = ""
            elenco = ""
            if credits_r.status_code == 200:
                credits = credits_r.json()
                creators = [c["name"] for c in credits.get("crew", []) if c.get("job") in ("Creator", "Director")]
                director = ", ".join(list(set(creators)))
                elenco_list = [a["name"] for a in credits.get("cast", [])[:5]]
                elenco = ", ".join(elenco_list)
            temporadas_detalle = []
            for season in detail.get("seasons", []):
                if not season.get("season_number"):
                    continue
                season_number = season["season_number"]
                season_url = f"{TMDB_BASE_URL}/tv/{id}/season/{season_number}"
                season_r = requests.get(season_url, headers=headers, params={"language": language}, timeout=REQUEST_TIMEOUT)
                if season_r.status_code != 200:
                    continue
                season_data = season_r.json()
                episodios = []
                for ep in season_data.get("episodes", []):
                    episodios.append({
                        "numero": ep.get("episode_number"),
                        "titulo": ep.get("name", ""),
                        "resumen": ep.get("overview", ""),
                        "imagen": f"https://image.tmdb.org/t/p/w300{ep['still_path']}" if ep.get("still_path") else "",
                        "fecha": ep.get("air_date", "")
                    })
                temporadas_detalle.append({
                    "numero": season_number,
                    "nombre": season.get("name", f"Temporada {season_number}"),
                    "episodios": episodios
                })
                time.sleep(0.15)
            # Obtener tráiler de YouTube para series (primero en el idioma solicitado, luego en inglés si no hay)
            trailer_url = None
            videos_url = f"{TMDB_BASE_URL}/tv/{id}/videos"
            videos_r = requests.get(videos_url, headers=headers, params={"language": language}, timeout=REQUEST_TIMEOUT)
            videos = []
            if videos_r.status_code == 200:
                videos = videos_r.json().get("results", [])
            yt_trailers = [v for v in videos if v.get("site") == "YouTube" and v.get("type") == "Trailer"]
            if not yt_trailers and language != "en-US":
                videos_r_en = requests.get(videos_url, headers=headers, params={"language": "en-US"}, timeout=REQUEST_TIMEOUT)
                if videos_r_en.status_code == 200:
                    videos_en = videos_r_en.json().get("results", [])
                    yt_trailers = [v for v in videos_en if v.get("site") == "YouTube" and v.get("type") == "Trailer"]
            if yt_trailers:
                trailer_url = f"https://www.youtube.com/watch?v={yt_trailers[0]['key']}"
            
            # Procesar episode_runtime
            episode_runtime = None
            if detail.get("episode_run_time"):
                episode_runtime = ", ".join(map(str, detail["episode_run_time"]))
            
            # Procesar production_countries
            production_countries = None
            if detail.get("production_countries"):
                production_countries = ", ".join([country["name"] for country in detail["production_countries"]])
            
            # Procesar first_air_date y last_air_date
            first_air_date = None
            last_air_date = None
            if detail.get("first_air_date"):
                try:
                    first_air_date = datetime.strptime(detail["first_air_date"], "%Y-%m-%d").date()
                except:
                    pass
            if detail.get("last_air_date"):
                try:
                    last_air_date = datetime.strptime(detail["last_air_date"], "%Y-%m-%d").date()
                except:
                    pass
            
            return {
                "titulo": detail.get("name", ""),
                "titulo_original": detail.get("original_name", ""),
                "idioma_original": detail.get("original_language", ""),
                "anio": int(detail.get("first_air_date", "").split("-")[0]) if detail.get("first_air_date") else None,
                "genero": ", ".join([g["name"] for g in detail.get("genres", [])]),
                "sinopsis": detail.get("overview", ""),
                "director": director,
                "elenco": elenco,
                "imagen": get_best_poster(id, "tv", language),
                "status": detail.get("status", ""),  # Cambiado de estado a status
                "tipo": tipo,
                "temporadas": detail.get("number_of_seasons"),
                "episodios": detail.get("number_of_episodes"),
                "nota_personal": None,
                "nota_tmdb": detail.get("vote_average"),
                "votos_tmdb": detail.get("vote_count"),
                "temporadas_detalle": temporadas_detalle,
                "trailer": trailer_url,
                # Campos adicionales para series
                "runtime": None,  # Las series no tienen runtime general
                "production_countries": production_countries,
                "status": detail.get("status", ""),
                "certification": None,  # Se manejará en las traducciones por región
                "first_air_date": first_air_date,
                "last_air_date": last_air_date,
                "episode_runtime": episode_runtime
            }
    # Si listar=True, devolver lista resumida de opciones
    if listar:
        search_url = f"{TMDB_BASE_URL}/search/multi"
        params = {"query": title, "language": language, "include_adult": "false"}
        r = requests.get(search_url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail="Error al conectar con TMDb")
        data = r.json()
        if not data.get("results"):
            raise HTTPException(status_code=404, detail="No encontrado en TMDb")
        opciones = []
        for res in data["results"]:
            if res["media_type"] not in ("movie", "tv"):
                continue
            media_type = res["media_type"]
            opciones.append({
                "id": res["id"],
                "media_type": media_type,
                "titulo": res.get("title") or res.get("name", ""),
                "anio": (res.get("release_date") or res.get("first_air_date") or "")[:4],
                "imagen": get_best_poster(res["id"], media_type, language),
                "nota_tmdb": res.get("vote_average"),
                "votos_tmdb": res.get("vote_count")
            })
        return {"opciones": opciones}
    # Si no, lógica anterior (elige uno y devuelve detalle)
    item = None
    if tipo_preferido:
        search_url = f"{TMDB_BASE_URL}/search/multi"
        params = {"query": title, "language": language, "include_adult": "false"}
        r = requests.get(search_url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail="Error al conectar con TMDb")
        data = r.json()
        if not data.get("results"):
            raise HTTPException(status_code=404, detail="No encontrado en TMDb")
        for res in data["results"]:
            if tipo_preferido == "película" and res["media_type"] == "movie":
                item = res
                break
            if tipo_preferido == "serie" and res["media_type"] == "tv":
                item = res
                break
    if not item:
        search_url = f"{TMDB_BASE_URL}/search/multi"
        params = {"query": title, "language": language, "include_adult": "false"}
        r = requests.get(search_url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail="Error al conectar con TMDb")
        data = r.json()
        if not data.get("results"):
            raise HTTPException(status_code=404, detail="No encontrado en TMDb")
        item = data["results"][0]
    tipo = "película" if item["media_type"] == "movie" else "serie"
    # Obtenemos detalles completos
    if tipo == "película":
        detail_url = f"{TMDB_BASE_URL}/movie/{item['id']}"
        credits_url = f"{TMDB_BASE_URL}/movie/{item['id']}/credits"
        detail_params = {"language": language}
        detail_r = requests.get(detail_url, headers=headers, params=detail_params, timeout=REQUEST_TIMEOUT)
        if detail_r.status_code != 200:
            raise HTTPException(status_code=502, detail="Error al obtener detalles de TMDb")
        detail = detail_r.json()
        credits_r = requests.get(credits_url, headers=headers, timeout=REQUEST_TIMEOUT)
        director = ""
        elenco = ""
        if credits_r.status_code == 200:
            credits = credits_r.json()
            director_list = [c["name"] for c in credits.get("crew", []) if c.get("job") == "Director"]
            director = ", ".join(director_list)
            elenco_list = [a["name"] for a in credits.get("cast", [])[:5]]
            elenco = ", ".join(elenco_list)
        return {
            "titulo": detail.get("title") or detail.get("name", ""),
            "titulo_original": detail.get("original_title", ""),
            "idioma_original": detail.get("original_language", ""),
            "anio": int(detail.get("release_date", "").split("-")[0]) if detail.get("release_date") else None,
            "genero": ", ".join([g["name"] for g in detail.get("genres", [])]),
            "sinopsis": detail.get("overview", ""),
            "director": director,
            "elenco": elenco,
            "imagen": get_best_poster(item['id'], "movie", language),
            "status": detail.get("status", ""),  # Cambiado de estado a status
            "tipo": tipo,
            "temporadas": None,
            "episodios": None,
            "nota_personal": None,
            "nota_tmdb": detail.get("vote_average"),
            "votos_tmdb": detail.get("vote_count"),
            "presupuesto": detail.get("budget"),
            "recaudacion": detail.get("revenue")
        }
    else:
        detail_url = f"{TMDB_BASE_URL}/tv/{item['id']}"
        credits_url = f"{TMDB_BASE_URL}/tv/{item['id']}/credits"
        detail_params = {"language": language}
        detail_r = requests.get(detail_url, headers=headers, params=detail_params, timeout=REQUEST_TIMEOUT)
        if detail_r.status_code != 200:
            raise HTTPException(status_code=502, detail="Error al obtener detalles de TMDb")
        detail = detail_r.json()
        credits_r = requests.get(credits_url, headers=headers, timeout=REQUEST_TIMEOUT)
        director = ""
        elenco = ""
        if credits_r.status_code == 200:
            credits = credits_r.json()
            creators = [c["name"] for c in credits.get("crew", []) if c.get("job") in ("Creator", "Director")]
            director = ", ".join(list(set(creators)))
            elenco_list = [a["name"] for a in credits.get("cast", [])[:5]]
            elenco = ", ".join(elenco_list)
        # Obtener temporadas y episodios
        temporadas_detalle = []
        for season in detail.get("seasons", []):
            if not season.get("season_number"):
                continue
            season_number = season["season_number"]
            season_url = f"{TMDB_BASE_URL}/tv/{item['id']}/season/{season_number}"
            season_r = requests.get(season_url, headers=headers, params={"language": language}, timeout=REQUEST_TIMEOUT)
            if season_r.status_code != 200:
                continue  # saltar temporadas sin info
            season_data = season_r.json()
            episodios = []
            for ep in season_data.get("episodes", []):
                episodios.append({
                    "numero": ep.get("episode_number"),
                    "titulo": ep.get("name", ""),
                    "resumen": ep.get("overview", ""),
                    "imagen": f"https://image.tmdb.org/t/p/w300{ep['still_path']}" if ep.get("still_path") else "",
                    "fecha": ep.get("air_date", "")
                })
            temporadas_detalle.append({
                "numero": season_number,
                "nombre": season.get("name", f"Temporada {season_number}"),
                "episodios": episodios
            })
            time.sleep(0.15)  # para no sobrecargar la API
        return {
            "titulo": detail.get("name", ""),
            "titulo_original": detail.get("original_name", ""),
            "idioma_original": detail.get("original_language", ""),
            "anio": int(detail.get("first_air_date", "").split("-")[0]) if detail.get("first_air_date") else None,
            "genero": ", ".join([g["name"] for g in detail.get("genres", [])]),
            "sinopsis": detail.get("overview", ""),
            "director": director,
            "elenco": elenco,
            "imagen": get_best_poster(item['id'], "tv", language),
            "status": detail.get("status", ""),  # Cambiado de estado a status
            "tipo": tipo,
            "temporadas": detail.get("number_of_seasons"),
            "episodios": detail.get("number_of_episodes"),
            "nota_personal": None,
            "nota_tmdb": detail.get("vote_average"),
            "votos_tmdb": detail.get("vote_count"),
            "temporadas_detalle": temporadas_detalle
        }

@app.get("/tmdb/{media_type}/{tmdb_id}/watch/providers")
def tmdb_watch_providers(media_type: str, tmdb_id: int):
    if media_type not in ("movie", "tv"):
        raise HTTPException(status_code=400, detail="media_type must be 'movie' or 'tv'")
    headers = get_tmdb_auth_headers()
    url = f"{TMDB_BASE_URL}/{media_type}/{tmdb_id}/watch/providers"
    r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Error al obtener watch providers de TMDb")
    return r.json()

@app.get("/tmdb/watch/providers/list")
def tmdb_watch_providers_list():
    """Obtener lista completa de watch providers disponibles en TMDb"""
    headers = get_tmdb_auth_headers()
    url = f"{TMDB_BASE_URL}/watch/providers/movie"
    r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Error al obtener lista de watch providers de TMDb")
    return r.json()

@app.get("/tmdb/watch/providers/regions/{country_code}")
def tmdb_watch_providers_by_country(country_code: str):
    """Obtener watch providers disponibles en un país específico"""
    headers = get_tmdb_auth_headers()
    
    # Obtener providers tanto de movies como de TV para tener cobertura completa
    movie_url = f"{TMDB_BASE_URL}/watch/providers/movie?watch_region={country_code.upper()}"
    tv_url = f"{TMDB_BASE_URL}/watch/providers/tv?watch_region={country_code.upper()}"
    
    try:
        movie_response = requests.get(movie_url, headers=headers, timeout=REQUEST_TIMEOUT)
        tv_response = requests.get(tv_url, headers=headers, timeout=REQUEST_TIMEOUT)
        
        providers = {}
        
        # Combinar providers de movies y TV
        if movie_response.status_code == 200:
            movie_data = movie_response.json()
            if 'results' in movie_data:
                for provider in movie_data['results']:
                    providers[provider['provider_id']] = provider
        
        if tv_response.status_code == 200:
            tv_data = tv_response.json()
            if 'results' in tv_data:
                for provider in tv_data['results']:
                    providers[provider['provider_id']] = provider
        
        # Retornar la lista consolidada
        return {
            "results": list(providers.values()),
            "country_code": country_code.upper()
        }
        
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error al obtener providers para {country_code}: {str(e)}")

@app.get("/tmdb/{media_type}/{tmdb_id}/external_ids")
def tmdb_external_ids(media_type: str, tmdb_id: int):
    # Accept person as well to avoid route conflicts with /tmdb/person/{id}/external_ids
    if media_type not in ("movie", "tv", "person"):
        raise HTTPException(status_code=400, detail="media_type must be 'movie', 'tv' or 'person'")
    headers = get_tmdb_auth_headers()
    if media_type == "person":
        url = f"{TMDB_BASE_URL}/person/{tmdb_id}/external_ids"
    else:
        url = f"{TMDB_BASE_URL}/{media_type}/{tmdb_id}/external_ids"
    r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Error al obtener external_ids de TMDb")
    return r.json()

@app.get("/tmdb/collection/{collection_id}")
def tmdb_collection(collection_id: int, language: str = Query("es-ES")):
    headers = get_tmdb_auth_headers()
    url = f"{TMDB_BASE_URL}/collection/{collection_id}"
    r = requests.get(url, headers=headers, params={"language": language}, timeout=REQUEST_TIMEOUT)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Error al obtener colección de TMDb")
    return r.json()

@app.get("/tmdb/{media_type}/{tmdb_id}")
def tmdb_detail(media_type: str, tmdb_id: int, language: str = Query("es-ES")):
    # Accept person as well to avoid conflicts with /tmdb/person/{id}
    if media_type not in ("movie", "tv", "person"):
        raise HTTPException(status_code=400, detail="media_type must be 'movie', 'tv' or 'person'")
    headers = get_tmdb_auth_headers()
    if media_type == "person":
        url = f"{TMDB_BASE_URL}/person/{tmdb_id}"
    else:
        url = f"{TMDB_BASE_URL}/{media_type}/{tmdb_id}"
    r = requests.get(url, headers=headers, params={"language": language}, timeout=REQUEST_TIMEOUT)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Error al obtener detalle de TMDb")
    return r.json()


# Endpoint para obtener los créditos (reparto y equipo) de una película o serie desde TMDb
@app.get("/tmdb/{media_type}/{tmdb_id}/credits")
def tmdb_credits(media_type: str, tmdb_id: int):
    """Proxy para obtener créditos (cast y crew) de una película o serie desde TMDb"""
    if media_type not in ("movie", "tv"):
        raise HTTPException(status_code=400, detail="media_type must be 'movie' or 'tv'")
    headers = get_tmdb_auth_headers()
    url = f"{TMDB_BASE_URL}/{media_type}/{tmdb_id}/credits"
    r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Error al obtener créditos de TMDb")
    return r.json()

@app.get("/tmdb/{media_type}/{tmdb_id}/recommendations")
def tmdb_recommendations(media_type: str, tmdb_id: int, language: str = Query("es-ES"), page: int = Query(1)):
    if media_type not in ("movie", "tv"):
        raise HTTPException(status_code=400, detail="media_type must be 'movie' or 'tv'")
    headers = get_tmdb_auth_headers()
    url = f"{TMDB_BASE_URL}/{media_type}/{tmdb_id}/recommendations"
    r = requests.get(url, headers=headers, params={"language": language, "page": page}, timeout=REQUEST_TIMEOUT)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Error al obtener recomendaciones de TMDb")
    return r.json()

from sqlalchemy import or_
# --- Person endpoints (TMDb proxy) ---

# Nuevo endpoint: Medias vistas con este actor usando la relación real
@app.get("/medias/by_actor/{person_tmdb_id}", response_model=List[schemas.Media])
def get_medias_by_actor(person_tmdb_id: int, db: Session = Depends(get_db), current_user: User = Depends(current_user_required)):
    """
    Devuelve todas las medias del usuario autenticado donde el actor con ese TMDb ID aparece (usando la relación real).
    Incluye información personal del usuario (notas, favoritos, etc.)
    """
    actor = db.query(models.Actor).filter(models.Actor.tmdb_id == person_tmdb_id).first()
    if not actor:
        return []
    
    # Obtener medias del actor que están en la biblioteca del usuario actual
    # Incluir información personal del usuario usando join con UsuarioMedia
    medias_with_user_data = db.query(models.Media, models.UsuarioMedia).join(
        models.UsuarioMedia, models.Media.id == models.UsuarioMedia.media_id
    ).filter(
        models.UsuarioMedia.usuario_id == current_user.id,
        models.Media.id.in_([m.id for m in actor.medias])
    ).all()
    
    # Combinar datos de Media con datos personales de UsuarioMedia
    result = []
    for media, usuario_media in medias_with_user_data:
        # Crear un objeto que combine ambos
        media_dict = {
            "id": media.id,
            "tmdb_id": media.tmdb_id,
            "titulo": media.titulo,
            "anio": media.anio,
            "genero": media.genero,
            "sinopsis": media.sinopsis,
            "director": media.director,
            "elenco": media.elenco,
            "imagen": media.imagen,
            "status": media.status,  # Cambiado de estado a status
            "tipo": media.tipo,
            "temporadas": media.temporadas,
            "episodios": media.episodios,
            "nota_imdb": media.nota_imdb,
            "original_title": media.original_title,
            "runtime": media.runtime,
            "production_countries": media.production_countries,
            "status": media.status,
            # Datos personales del usuario
            "nota_personal": usuario_media.nota_personal,
            "anotacion_personal": usuario_media.anotacion_personal,
            "favorito": usuario_media.favorito,
            "pendiente": usuario_media.pendiente,
            "fecha_agregado": usuario_media.fecha_agregado
        }
        result.append(schemas.Media(**media_dict))
    
    return result
@app.get("/tmdb/person/{person_id}")
def tmdb_person_detail(person_id: int, language: str = Query("es-ES")):
    """Proxy para obtener detalles de una persona (actor/director) desde TMDb"""
    headers = get_tmdb_auth_headers()
    url = f"{TMDB_BASE_URL}/person/{person_id}"
    r = requests.get(url, headers=headers, params={"language": language}, timeout=REQUEST_TIMEOUT)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Error al obtener detalles de la persona en TMDb")
    return r.json()

@app.get("/tmdb/person/{person_id}/combined_credits")
def tmdb_person_combined_credits(person_id: int, language: str = Query("es-ES")):
    """Proxy para obtener créditos combinados (películas y series) de una persona en TMDb"""
    headers = get_tmdb_auth_headers()
    url = f"{TMDB_BASE_URL}/person/{person_id}/combined_credits"
    # language suele aplicarse a los títulos de movie/tv en los créditos
    r = requests.get(url, headers=headers, params={"language": language}, timeout=REQUEST_TIMEOUT)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Error al obtener combined_credits de la persona en TMDb")
    return r.json()

@app.get("/tmdb/person/{person_id}/external_ids")
def tmdb_person_external_ids(person_id: int):
    """Proxy para obtener IDs externos (Twitter/Instagram/FB) de una persona en TMDb"""
    headers = get_tmdb_auth_headers()
    url = f"{TMDB_BASE_URL}/person/{person_id}/external_ids"
    r = requests.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Error al obtener external_ids de la persona en TMDb")
    return r.json()

# --- ENDPOINTS PARA TRADUCCIONES ---

@app.get("/translations/{media_id}")
def get_media_translation(
    media_id: int, 
    language: str = Query(..., description="Language code (e.g., 'en', 'es')"),
    db: Session = Depends(get_db)
):
    """Get translated content for a specific media item"""
    try:
        translation_service = get_translation_service(db)
        translated_content = translation_service.get_translated_content(media_id, language)
        
        if not translated_content:
            raise HTTPException(status_code=404, detail="Media not found")
        
        return translated_content
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting translation: {str(e)}")

@app.post("/translations/{media_id}/cache")
def cache_media_translation(
    media_id: int,
    language: str = Query(..., description="Language code"),
    db: Session = Depends(get_db)
):
    """Force cache a translation for a media item"""
    try:
        # Get media to get TMDb ID
        media = db.query(models.Media).filter(models.Media.id == media_id).first()
        if not media or not media.tmdb_id:
            raise HTTPException(status_code=404, detail="Media not found or no TMDb ID")
        
        translation_service = get_translation_service(db)
        
        # Fetch and cache from TMDb
        translation_data = translation_service.fetch_from_tmdb(
            media.tmdb_id, media.tipo, language
        )
        
        if translation_data:
            saved_translation = translation_service.save_translation(
                media_id, language, translation_data
            )
            return {"message": "Translation cached successfully", "data": translation_data}
        else:
            raise HTTPException(status_code=404, detail="No translation found in TMDb")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error caching translation: {str(e)}")

@app.get("/translations/cache/stats")
def get_cache_stats(db: Session = Depends(get_db)):
    """Get statistics about cached translations"""
    try:
        from sqlalchemy import func
        
        total_translations = db.query(func.count(models.ContentTranslation.id)).scalar()
        
        by_language = db.query(
            models.ContentTranslation.language_code,
            func.count(models.ContentTranslation.id).label('count')
        ).group_by(models.ContentTranslation.language_code).all()
        
        by_source = db.query(
            models.ContentTranslation.translation_source,
            func.count(models.ContentTranslation.id).label('count')
        ).group_by(models.ContentTranslation.translation_source).all()
        
        return {
            "total_cached_translations": total_translations,
            "by_language": [{"language": lang, "count": count} for lang, count in by_language],
            "by_source": [{"source": source, "count": count} for source, count in by_source]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting cache stats: {str(e)}")

@app.delete("/translations/cache/clear")
def clear_translation_cache(
    language: str = Query(None, description="Language to clear (optional)"),
    older_than_days: int = Query(None, description="Clear translations older than X days"),
    db: Session = Depends(get_db)
):
    """Clear translation cache"""
    try:
        query = db.query(models.ContentTranslation)
        
        if language:
            query = query.filter(models.ContentTranslation.language_code == language)
        
        if older_than_days:
            from datetime import datetime, timedelta
            cutoff_date = datetime.utcnow() - timedelta(days=older_than_days)
            query = query.filter(models.ContentTranslation.created_at < cutoff_date)
        
        deleted_count = query.count()
        query.delete()
        db.commit()
        
        return {"message": f"Cleared {deleted_count} cached translations"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error clearing cache: {str(e)}")

@app.get("/poster/{tmdb_id}")
def get_dynamic_poster(
    tmdb_id: int,
    media_type: str = Query(..., description="movie o tv"),
    language: str = Query("es-ES", description="Idioma para la portada (ej: es-ES, en-US, pt-PT, fr-FR, de-DE)"),
    db: Session = Depends(get_db)
):
    """
    Obtiene la mejor portada para un contenido específico en el idioma solicitado.
    Busca primero en cache, luego en la base de datos, luego en TMDb si no existe.
    """
    try:
        # Convertir language a formato simple (es, en, pt, fr, de)
        if language.startswith("es"): lang_code = "es"
        elif language.startswith("en"): lang_code = "en"
        elif language.startswith("pt"): lang_code = "pt"
        elif language.startswith("fr"): lang_code = "fr"
        elif language.startswith("de"): lang_code = "de"
        else: lang_code = "en"
        
        # Generar clave de cache
        cache_key = get_cache_key(None, lang_code, tmdb_id)
        
        # Verificar cache primero
        cached_poster = get_poster_cache(cache_key)
        if cached_poster:
            return {"poster_url": cached_poster}
        
        # Buscar el media en la base de datos por tmdb_id usando índice optimizado
        media = db.query(models.Media).filter(
            models.Media.tmdb_id == tmdb_id
        ).first()
        
        if media:
            poster_url = None
            
            # Query optimizada: buscar español e inglés en una sola consulta
            if lang_code == "es" and media.imagen:
                poster_url = media.imagen
            # Si idioma es inglés reutiliza lógica existente
            if not poster_url and lang_code == "en":
                translation = db.query(models.ContentTranslation).filter(
                    models.ContentTranslation.media_id == media.id,
                    models.ContentTranslation.language_code == "en-US",
                    models.ContentTranslation.poster_url.isnot(None),
                    models.ContentTranslation.poster_url != ""
                ).first()
                if translation:
                    poster_url = translation.poster_url
            # Intentar traducciones adicionales (pt, fr, de)
            if not poster_url and lang_code in ("pt", "fr", "de"):
                lang_full_map = {"pt": "pt-PT", "fr": "fr-FR", "de": "de-DE"}
                translation = db.query(models.ContentTranslation).filter(
                    models.ContentTranslation.media_id == media.id,
                    models.ContentTranslation.language_code == lang_full_map[lang_code],
                    models.ContentTranslation.poster_url.isnot(None),
                    models.ContentTranslation.poster_url != ""
                ).first()
                if translation:
                    poster_url = translation.poster_url
            # Si no hay poster en la BD, hacer llamada a TMDb y guardar
            if not poster_url:
                tmdb_poster = get_best_poster(tmdb_id, media_type, language)
                if tmdb_poster:
                    poster_url = tmdb_poster
                    
                    # Guardar en la base de datos
                    if lang_code == "en":
                        # Solo actualizar si ya existe una translation (no crear fila nueva)
                        translation = db.query(models.ContentTranslation).filter(
                            models.ContentTranslation.media_id == media.id,
                            models.ContentTranslation.language_code == "en-US"
                        ).first()
                        
                        if translation and hasattr(translation, 'poster_url'):
                            translation.poster_url = poster_url
                            translation.updated_at = func.now()
                            db.commit()
                    elif lang_code in ("pt", "fr", "de"):
                        # Actualizar/crear traducción específica si existe fila
                        lang_full_map = {"pt": "pt-PT", "fr": "fr-FR", "de": "de-DE"}
                        translation = db.query(models.ContentTranslation).filter(
                            models.ContentTranslation.media_id == media.id,
                            models.ContentTranslation.language_code == lang_full_map[lang_code]
                        ).first()
                        if translation and (not translation.poster_url or translation.poster_url.strip() == ""):
                            translation.poster_url = poster_url
                            translation.updated_at = func.now()
                            db.commit()
                    else:
                        # Español
                        if not media.imagen or media.imagen.strip() == "":
                            media.imagen = poster_url
                            db.commit()
            
            # Fallback a imagen original si no se encontró nada
            if not poster_url:
                poster_url = media.imagen
        else:
            # Si no existe en la BD, solo hacer llamada a TMDb
            poster_url = get_best_poster(tmdb_id, media_type, language)
        
        # Guardar en cache si encontramos algo
        if poster_url:
            set_poster_cache(cache_key, poster_url)
            return {"poster_url": poster_url}
        else:
            raise HTTPException(status_code=404, detail="No poster found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting poster: {str(e)}")

@app.get("/posters-optimized")
def get_optimized_posters(
    media_ids: str = Query(..., description="Lista de IDs de media separados por comas"),
    language: str = Query("es", description="Idioma preferido (es, en, pt, fr, de)"),
    db: Session = Depends(get_db)
):
    """
    Obtiene las URLs de los posters desde cache primero, luego BD, luego TMDb.
    Versión optimizada con batch queries y cache inteligente.
    """
    try:
        ids = [int(id.strip()) for id in media_ids.split(",") if id.strip().isdigit()]
        if not ids:
            return {"posters": {}}

        # Normalizar idioma ampliado
        lang = language.lower()
        if lang.startswith("en"): lang_code, lang_db, tmdb_lang = "en", "en-US", "en-US"
        elif lang.startswith("pt"): lang_code, lang_db, tmdb_lang = "pt", "pt-PT", "pt-PT"
        elif lang.startswith("fr"): lang_code, lang_db, tmdb_lang = "fr", "fr-FR", "fr-FR"
        elif lang.startswith("de"): lang_code, lang_db, tmdb_lang = "de", "de-DE", "de-DE"
        else: lang_code, lang_db, tmdb_lang = "es", "es-ES", "es-ES"

        # Generar claves de cache para todos los medias
        cache_keys = {media_id: get_cache_key(media_id, lang_code) for media_id in ids}
        
        # Verificar cache batch
        cached_posters = get_batch_poster_cache(list(cache_keys.values()))
        
        # Filtrar IDs que no están en cache
        ids_to_fetch = []
        result = {}
        
        for media_id in ids:
            cache_key = cache_keys[media_id]
            cached_value = cached_posters.get(cache_key)
            if cached_value:
                result[str(media_id)] = cached_value
            else:
                ids_to_fetch.append(media_id)

        # Solo hacer query de BD para los que no están en cache
        if ids_to_fetch:
            # Query optimizada: una sola consulta para todos los medias
            medias = db.query(models.Media).filter(models.Media.id.in_(ids_to_fetch)).all()
            
            # Query optimizada: una sola consulta para todas las traducciones si es inglés
            translations_map = {}
            if lang_code == "en":
                translations = db.query(models.ContentTranslation).filter(
                    models.ContentTranslation.media_id.in_(ids_to_fetch),
                    models.ContentTranslation.language_code == "en-US",
                    models.ContentTranslation.poster_url.isnot(None),
                    models.ContentTranslation.poster_url != ""
                ).all()
                translations_map = {t.media_id: t.poster_url for t in translations}
            elif lang_code in ("pt", "fr", "de"):
                lang_full_map = {"pt": "pt-PT", "fr": "fr-FR", "de": "de-DE"}
                translations = db.query(models.ContentTranslation).filter(
                    models.ContentTranslation.media_id.in_(ids_to_fetch),
                    models.ContentTranslation.language_code == lang_full_map[lang_code],
                    models.ContentTranslation.poster_url.isnot(None),
                    models.ContentTranslation.poster_url != ""
                ).all()
                translations_map = {t.media_id: t.poster_url for t in translations}

            # Procesar cada media
            new_cache_data = {}
            tmdb_requests = []  # Para llamadas batch a TMDb
            
            for media in medias:
                poster_url = None

                # Lógica optimizada de búsqueda
                if lang_code == "en":
                    poster_url = translations_map.get(media.id)
                elif lang_code == "es" and media.imagen and str(media.imagen).strip() != "":
                    poster_url = media.imagen
                elif lang_code in ("pt", "fr", "de"):
                    poster_url = translations_map.get(media.id)

                # Si no hay poster en la BD, preparar para TMDb
                if (not poster_url or str(poster_url).strip() == "") and media.tmdb_id:
                    tmdb_requests.append((media.id, media.tmdb_id, media.tipo))
                else:
                    # Tenemos poster, agregarlo al resultado y cache
                    if not poster_url:
                        poster_url = media.imagen  # Fallback
                    
                    result[str(media.id)] = poster_url
                    new_cache_data[cache_keys[media.id]] = poster_url

            # Procesar llamadas a TMDb (podrían optimizarse con async en el futuro)
            for media_id, tmdb_id, tipo in tmdb_requests:
                try:
                    tmdb_poster = get_best_poster(tmdb_id, tipo, tmdb_lang)
                    if tmdb_poster:
                        poster_url = tmdb_poster
                        if lang_code == "en":
                            # Solo actualizar si ya existe una translation (no crear fila nueva)
                            translation = db.query(models.ContentTranslation).filter(
                                models.ContentTranslation.media_id == media_id,
                                models.ContentTranslation.language_code == "en-US"
                            ).first()
                            if translation and hasattr(translation, 'poster_url'):
                                translation.poster_url = poster_url
                                translation.updated_at = func.now()
                        elif lang_code == "es":
                            # Español: solo actualizar si no hay imagen
                            media = next((m for m in medias if m.id == media_id), None)
                            if media and (not media.imagen or media.imagen.strip() == ""):
                                media.imagen = poster_url
                        elif lang_code in ("pt", "fr", "de"):
                            lang_full_map = {"pt": "pt-PT", "fr": "fr-FR", "de": "de-DE"}
                            translation = db.query(models.ContentTranslation).filter(
                                models.ContentTranslation.media_id == media_id,
                                models.ContentTranslation.language_code == lang_full_map[lang_code]
                            ).first()
                            if translation and (not translation.poster_url or translation.poster_url.strip() == ""):
                                translation.poster_url = poster_url
                    else:
                        # No se encontró en TMDb, usar imagen original
                        media = next((m for m in medias if m.id == media_id), None)
                        poster_url = media.imagen if media else ""
                    
                    result[str(media_id)] = poster_url or ""
                    new_cache_data[cache_keys[media_id]] = poster_url or ""
                    
                except Exception as e:
                    # Error con TMDb, usar fallback
                    media = next((m for m in medias if m.id == media_id), None)
                    fallback_poster = media.imagen if media else ""
                    result[str(media_id)] = fallback_poster
                    new_cache_data[cache_keys[media_id]] = fallback_poster

            # Commit de cambios en BD y actualizar cache batch
            if tmdb_requests:
                db.commit()
            
            if new_cache_data:
                set_batch_poster_cache(new_cache_data)

        return {"posters": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting optimized posters: {str(e)}")

# Endpoints de gestión de cache
@app.get("/cache/posters/stats")
def get_poster_cache_stats():
    """Obtener estadísticas del cache de portadas"""
    return get_cache_stats()

@app.delete("/cache/posters")
def clear_poster_cache_endpoint():
    """Limpiar todo el cache de portadas"""
    result = clear_poster_cache()
    return {
        "message": f"Cache cleared successfully. {result['cleared']} entries removed.",
        "stats": result["cache_stats"]
    }

from fastapi import Form
from fastapi.responses import JSONResponse
from fastapi_users.authentication import JWTStrategy


# Custom login endpoint for SPA: returns JWT in body
@app.post("/auth/jwt/login", tags=["auth"])
async def custom_jwt_login(
    response: Response,
    username: str = Form(...),
    password: str = Form(...),
    user_manager = Depends(get_user_manager),
):
    try:
        # Get user by email
        user = await user_manager.get_by_email(username)
        if user is None or not user.is_active:
            raise HTTPException(status_code=400, detail="Credenciales incorrectas")
        
        # Verify password using the user manager's method
        verified, updated_password_hash = user_manager.password_helper.verify_and_update(password, user.hashed_password)
        if not verified:
            raise HTTPException(status_code=400, detail="Credenciales incorrectas")
        
        # Generate JWT token
        jwt_strategy = get_jwt_strategy()
        token = await jwt_strategy.write_token(user)
        
        # Set cookie for compatibility
        response.set_cookie(
            key="auth",
            value=token,
            max_age=3600,
            httponly=False,  # Allow JS access for SPA
            samesite="lax",
            secure=False
        )
        return {"access_token": token, "token_type": "bearer"}
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(status_code=400, detail="Credenciales incorrectas")

# Endpoint personalizado para recuperación de contraseña que permite email o username
@app.post("/auth/forgot-password-custom")
async def forgot_password_custom(
    email_or_username: str = Body(..., embed=True),
    language: str = Body('es', embed=True),  # Idioma para el email
    user_manager = Depends(get_user_manager)
):
    """Permite recuperación de contraseña usando email o username"""
    try:
        # Buscar usuario por email o username
        if hasattr(user_manager.user_db, 'get_by_email_or_username'):
            user = await user_manager.user_db.get_by_email_or_username(email_or_username)
        else:
            # Fallback: intentar por email
            try:
                user = await user_manager.user_db.get_by_email(email_or_username)
            except:
                user = None
        
        if user is None:
            # Por seguridad, no revelar si el usuario existe o no
            return {"message": "Si el email/usuario existe, recibirás un correo con instrucciones para restablecer tu contraseña"}
        
        # Generar token de recuperación
        token = await user_manager.forgot_password(user)
        
        # Enviar email usando el idioma especificado por el usuario
        from email_service import get_email_service
        email_service = get_email_service()
        
        await email_service.send_password_reset_email(
            to_email=user.email,
            username=user.username,
            reset_token=token,
            user_language=language  # Usar el idioma del frontend
        )
        
        return {"message": "Si el email/usuario existe, recibirás un correo con instrucciones para restablecer tu contraseña"}
        
    except Exception as e:
        print(f"Error en forgot-password-custom: {e}")
        return {"message": "Si el email/usuario existe, recibirás un correo con instrucciones para restablecer tu contraseña"}

# Endpoint para verificar disponibilidad de username
@app.get("/auth/check-username/{username}")
async def check_username_availability(username: str, db: Session = Depends(get_db)):
    """Verifica si un nombre de usuario está disponible"""
    # Normalizar el username a minúsculas
    username_lower = username.lower().strip()
    
    # Validaciones básicas
    if len(username_lower) < 3:
        raise HTTPException(status_code=400, detail="El nombre de usuario debe tener al menos 3 caracteres")
    if len(username_lower) > 50:
        raise HTTPException(status_code=400, detail="El nombre de usuario no puede tener más de 50 caracteres")
    if not username_lower.replace('_', '').replace('-', '').replace('.', '').isalnum():
        raise HTTPException(status_code=400, detail="El nombre de usuario solo puede contener letras, números, guiones, guiones bajos y puntos")
    
    # Verificar si ya existe (sin distinguir mayúsculas/minúsculas)
    existing_user = db.query(User).filter(func.lower(User.username) == username_lower).first()
    
    if existing_user:
        return {"available": False, "message": "Este nombre de usuario ya está en uso"}
    
    return {"available": True, "message": "Nombre de usuario disponible"}

# Endpoint para restablecer contraseña
@app.post("/auth/reset-password")
async def reset_password_custom(
    token: str = Body(...),
    password: str = Body(...),
    user_manager = Depends(get_user_manager)
):
    """Restablece la contraseña usando el token de recuperación"""
    try:
        await user_manager.reset_password(token, password)
        return {"message": "Contraseña restablecida exitosamente"}
    except Exception as e:
        print(f"Error en reset-password: {e}")
        raise HTTPException(status_code=400, detail="Token inválido o expirado")

# --- Debug endpoint para registro ---
@app.post("/auth/debug-register")
async def debug_register(request: Request):
    try:
        body = await request.json()
        print("=== DEBUG REGISTER ===")
        print("Data recibida:", body)
        print("Tipos de datos:")
        for key, value in body.items():
            print(f"  {key}: {type(value)} = {repr(value)}")
        print("=====================")
        
        # Intentar validar con el schema
        try:
            user_create = UserCreate(**body)
            print("Schema validation SUCCESS")
            return {"status": "ok", "message": "Datos válidos"}
        except Exception as e:
            print(f"Schema validation ERROR: {e}")
            return {"status": "error", "validation_error": str(e)}
            
    except Exception as e:
        print(f"General error: {e}")
        return {"status": "error", "error": str(e)}

# Endpoint personalizado para buscar email por username
@app.get("/users/lookup/{username_or_email}")
async def lookup_user_email(username_or_email: str, user_db = Depends(get_user_db)):
    """Busca el email de un usuario por username o email"""
    try:
        # Usar el método personalizado para buscar por email o username
        if hasattr(user_db, 'get_by_email_or_username'):
            user = await user_db.get_by_email_or_username(username_or_email)
        else:
            # Fallback: buscar solo por email
            user = await user_db.get_by_email(username_or_email)
        
        if not user:
            raise HTTPException(status_code=404, detail="Usuario no encontrado")
        
        return {"email": user.email, "username": user.username}
    except Exception as e:
        print(f"Error en lookup de usuario: {e}")
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

# ===== ENDPOINT DE VERIFICACIÓN DE EMAIL =====

@app.post("/auth/verify-email")
async def verify_email(
    token: str = Body(..., embed=True),
    user_manager: UserManager = Depends(get_user_manager),
    db: Session = Depends(get_db)
):
    """Verifica el email de un usuario usando el token enviado por email"""
    try:
        # Usar el método de fastapi-users para verificar el token
        # (reutilizamos la lógica de reset password para la verificación)
        user = await user_manager.verify_password_reset_token(token)
        
        if not user:
            raise HTTPException(
                status_code=400,
                detail="Token de verificación inválido o expirado"
            )
        
        # Marcar el usuario como verificado
        user.is_verified = True
        db.commit()
        
        print(f"Usuario verificado exitosamente: {user.username} ({user.email})")
        
        return {
            "message": "Email verificado exitosamente",
            "username": user.username,
            "email": user.email
        }
        
    except Exception as e:
        print(f"Error en verificación de email: {e}")
        raise HTTPException(
            status_code=400,
            detail="Error al verificar el email. El token puede ser inválido o haber expirado."
        )

@app.post("/auth/resend-verification")
async def resend_verification_email(
    email: str = Body(..., embed=True),
    user_manager: UserManager = Depends(get_user_manager),
    db: Session = Depends(get_db)
):
    """Reenvía el email de verificación a un usuario"""
    try:
        # Buscar el usuario por email
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            # Por seguridad, no revelamos si el email existe o no
            return {"message": "Si el email existe en nuestro sistema, se enviará un nuevo email de verificación"}
        
        if user.is_verified:
            raise HTTPException(
                status_code=400,
                detail="Esta cuenta ya está verificada"
            )
        
        # Generar nuevo token de verificación
        verification_token = await user_manager.get_reset_password_token(user)
        
        # Enviar email de verificación
        from email_service import get_email_service
        email_service = get_email_service()
        
        verification_sent = await email_service.send_verification_email(
            to_email=user.email,
            username=user.username,
            verification_token=verification_token,
            user_language='es'  # Por defecto español
        )
        
        if verification_sent:
            print(f"Email de verificación reenviado a {user.email}")
        else:
            print(f"Error reenviando email de verificación a {user.email}")
        
        return {"message": "Si el email existe en nuestro sistema, se enviará un nuevo email de verificación"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error reenviando verificación: {e}")
        return {"message": "Si el email existe en nuestro sistema, se enviará un nuevo email de verificación"}

# Incluir rutas de autenticación (mantener para compatibilidad con fastapi-users)
app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/auth/jwt",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserRead),
    prefix="/users",
    tags=["users"],
)

# Incluir rutas de géneros
app.include_router(
    genre_routes.router,
    prefix="/api",
    tags=["genres"],
)

# --- Endpoints de contenido híbrido (cache + TMDb fallback) ---

@app.get("/content-cache/{tmdb_id}/{language_code}")
async def get_cached_content(tmdb_id: int, language_code: str, db: Session = Depends(database.get_db)):
    """Obtiene contenido desde cache local por TMDb ID e idioma"""
    try:
        # Buscar en traducciones primero
        translation = db.query(models.ContentTranslation).filter(
            models.ContentTranslation.tmdb_id == tmdb_id,
            models.ContentTranslation.language_code == language_code
        ).first()
        
        if translation:
            return {
                "tmdb_id": tmdb_id,
                "language_code": language_code,
                "poster_url": translation.poster_url,
                "backdrop_url": translation.backdrop_url,
                "title": translation.title,
                "synopsis": translation.synopsis,
                "tagline": translation.tagline,
                "cached": True
            }
        
        # Si no hay traducción, buscar en media (datos base)
        media = db.query(models.Media).filter(
            models.Media.tmdb_id == tmdb_id
        ).first()
        
        if media:
            return {
                "tmdb_id": tmdb_id,
                "language_code": language_code,
                "poster_url": media.imagen,  # Poster original
                "backdrop_url": None,
                "title": media.titulo,
                "synopsis": media.sinopsis,
                "tagline": None,
                "cached": True
            }
        
        # No lanzar excepción, devolver 404 directamente
        raise HTTPException(status_code=404, detail="Contenido no encontrado en cache")
        
    except HTTPException:
        # Re-lanzar HTTPExceptions sin convertirlas
        raise
    except Exception as e:
        # Solo convertir errores reales de base de datos/sistema
        raise HTTPException(status_code=500, detail=f"Error obteniendo cache: {str(e)}")

@app.post("/content-cache/batch")
async def get_batch_cached_content(request: dict, db: Session = Depends(database.get_db)):
    """Obtiene contenido en lote desde cache local"""
    try:
        tmdb_ids = request.get("tmdb_ids", [])
        language_code = request.get("language_code", "es")
        
        if not tmdb_ids:
            return []
        
        # Buscar traducciones
        translations = db.query(models.ContentTranslation).filter(
            models.ContentTranslation.tmdb_id.in_(tmdb_ids),
            models.ContentTranslation.language_code == language_code
        ).all()
        
        results = []
        found_ids = set()
        
        for translation in translations:
            results.append({
                "tmdb_id": translation.tmdb_id,
                "language_code": language_code,
                "poster_url": translation.poster_url,
                "backdrop_url": translation.backdrop_url,
                "title": translation.title,
                "synopsis": translation.synopsis,
                "tagline": translation.tagline,
                "cached": True
            })
            found_ids.add(translation.tmdb_id)
        
        # Para IDs no encontrados, buscar en media
        missing_ids = set(tmdb_ids) - found_ids
        if missing_ids:
            medias = db.query(models.Media).filter(
                models.Media.tmdb_id.in_(missing_ids)
            ).all()
            
            for media in medias:
                results.append({
                    "tmdb_id": media.tmdb_id,
                    "language_code": language_code,
                    "poster_url": media.imagen,
                    "backdrop_url": None,
                    "title": media.titulo,
                    "synopsis": media.sinopsis,
                    "tagline": None,
                    "cached": True
                })
        
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error obteniendo lote: {str(e)}")

@app.post("/content-cache")
async def save_content_cache(content_data: dict, db: Session = Depends(database.get_db)):
    """Guarda contenido en cache (fire-and-forget)"""
    try:
        tmdb_id = content_data.get("tmdb_id")
        media_type = content_data.get("media_type")
        language_code = content_data.get("language_code")
        
        if not all([tmdb_id, media_type, language_code]):
            return {"status": "error", "message": "Datos incompletos"}
        
        # Buscar o crear traducción
        translation = db.query(models.ContentTranslation).filter(
            models.ContentTranslation.tmdb_id == tmdb_id,
            models.ContentTranslation.language_code == language_code
        ).first()
        
        if not translation:
            # Buscar media base para obtener información
            media = db.query(models.Media).filter(
                models.Media.tmdb_id == tmdb_id
            ).first()
            
            if not media:
                return {"status": "error", "message": "Media no encontrada"}
            
            # Crear nueva traducción
            translation = models.ContentTranslation(
                tmdb_id=tmdb_id,
                media_type=media_type,
                language_code=language_code,
                title=content_data.get("title"),
                synopsis=content_data.get("synopsis"),
                poster_url=content_data.get("poster_url"),
                backdrop_url=content_data.get("backdrop_url"),
                tagline=content_data.get("tagline")
            )
            db.add(translation)
        else:
            # Actualizar campos solo si están vacíos
            if not translation.poster_url and content_data.get("poster_url"):
                translation.poster_url = content_data.get("poster_url")
            if not translation.backdrop_url and content_data.get("backdrop_url"):
                translation.backdrop_url = content_data.get("backdrop_url")
            if not translation.title and content_data.get("title"):
                translation.title = content_data.get("title")
            if not translation.synopsis and content_data.get("synopsis"):
                translation.synopsis = content_data.get("synopsis")
            if not translation.tagline and content_data.get("tagline"):
                translation.tagline = content_data.get("tagline")
        
        db.commit()
        return {"status": "success", "message": "Cache actualizado"}
        
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Error guardando cache: {str(e)}"}

# --- Endpoint mejorado de TMDb con soporte de idioma ---

@app.get("/tmdb/{media_type}/{tmdb_id}")
async def get_tmdb_data(
    media_type: str, 
    tmdb_id: int, 
    language: str = Query(default="es-ES", description="Código de idioma para TMDb")
):
    """Proxy endpoint para obtener datos de TMDB con soporte de idioma"""
    try:
        headers = get_tmdb_auth_headers()
        
        # Construir URL y parámetros
        url = f"{TMDB_BASE_URL}/{media_type}/{tmdb_id}"
        params = {"language": language}
        
        # Si no hay Bearer token, usar API key si está disponible
        if not headers:
            from config import TMDB_API_KEY
            if TMDB_API_KEY:
                params["api_key"] = TMDB_API_KEY
            else:
                raise HTTPException(status_code=500, detail="TMDB API key no configurada")
        
        # Hacer petición a TMDB
        response = requests.get(url, headers=headers, params=params, timeout=REQUEST_TIMEOUT)
        
        if response.status_code == 200:
            return response.json()
        else:
            raise HTTPException(status_code=response.status_code, detail=f"Error de TMDB: {response.text}")
            
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=500, detail=f"Error al conectar con TMDB: {str(e)}")

# --- ENDPOINTS DE ACTUALIZACIÓN AUTOMÁTICA ---

@app.post("/admin/auto-update/run")
def run_auto_update(
    limit: int = Query(10, description="Máximo número de medias a actualizar"),
    media_type: str = Query(None, description="Filtrar por tipo (película/serie)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(current_user_required)
):
    """Ejecuta la actualización automática manualmente"""
    update_service = get_auto_update_service()
    results = update_service.update_medias_batch(db, limit=limit, media_type=media_type)
    return {
        "message": "Actualización automática ejecutada",
        "results": results
    }

@app.get("/admin/auto-update/stats")
def get_auto_update_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(current_user_required)
):
    """Obtiene estadísticas del sistema de actualización automática"""
    update_service = get_auto_update_service()
    stats = update_service.get_update_stats(db)
    return stats

@app.get("/admin/auto-update/stats/detailed")
def get_auto_update_detailed_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(current_user_required)
):
    """Obtiene estadísticas detalladas del sistema de auto-actualización"""
    try:
        update_service = get_auto_update_service()
        stats = update_service.get_update_stats(db)
        
        # Información adicional sobre la próxima ejecución
        next_update_info = {
            "recommended_frequency": "Cada 24-48 horas para contenido activo",
            "optimization_notes": [
                "Series finalizadas se actualizan cada 4-6 meses",
                "Películas estrenadas se actualizan cada 4 meses", 
                "Contenido activo se actualiza cada 3-7 días",
                "Se priorizan cambios de reparto para contenido finalizado"
            ]
        }
        
        return {
            **stats,
            "next_update_info": next_update_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener estadísticas detalladas: {str(e)}")

@app.post("/admin/auto-update/mark/{tmdb_id}")
def mark_media_for_update(
    tmdb_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(current_user_required)
):
    """Marca un media específico para actualización forzada"""
    update_service = get_auto_update_service()
    update_service.mark_media_for_update(db, tmdb_id)
    return {"message": f"Media con TMDb ID {tmdb_id} marcado para actualización"}

@app.patch("/medias/{media_id}/auto-update")
def toggle_auto_update(
    media_id: int,
    enabled: bool = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(current_user_required)
):
    """Habilita/deshabilita la actualización automática para un media específico"""
    media = crud.get_media(db, media_id, usuario_id=current_user.id)
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
    
    # Obtener el media base (no el UsuarioMedia)
    base_media = db.query(models.Media).filter(models.Media.id == media_id).first()
    if not base_media:
        raise HTTPException(status_code=404, detail="Base media not found")
    
    base_media.auto_update_enabled = enabled
    db.commit()
    
    return {
        "message": f"Actualización automática {'habilitada' if enabled else 'deshabilitada'} para {media.titulo}",
        "auto_update_enabled": enabled
    }

@app.get("/medias/outdated")
def get_outdated_medias(
    limit: int = Query(20, description="Máximo número de medias a devolver"),
    media_type: str = Query(None, description="Filtrar por tipo (película/serie)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(current_user_required)
):
    """Obtiene la lista de medias que necesitan actualización"""
    update_service = get_auto_update_service()
    
    # Construir query base
    query = db.query(models.Media).filter(
        models.Media.tmdb_id.isnot(None),
        models.Media.auto_update_enabled == True
    )
    
    # Filtrar por tipo si se especifica
    if media_type:
        query = query.filter(models.Media.tipo == media_type)
    
    # Obtener medias que necesitan actualización
    outdated_medias = []
    
    for media in query.all():
        if update_service.should_update_media(media):
            # Calcular días desde última actualización
            days_since_update = None
            if media.last_updated_tmdb:
                days_since_update = (datetime.now() - media.last_updated_tmdb).days
            
            outdated_medias.append({
                "id": media.id,
                "titulo": media.titulo,
                "tipo": media.tipo,
                "tmdb_id": media.tmdb_id,
                "status": media.status,
                "temporadas": media.temporadas,
                "episodios": media.episodios,
                "last_updated_tmdb": media.last_updated_tmdb,
                "days_since_update": days_since_update,
                "needs_update": media.needs_update,
                "auto_update_enabled": media.auto_update_enabled
            })
            
            if len(outdated_medias) >= limit:
                break
    
    return {
        "total": len(outdated_medias),
        "medias": outdated_medias
    }

# --- Al final del archivo: servir frontend React para rutas no API ---
@app.get("/", include_in_schema=False)
@app.get("/{full_path:path}", include_in_schema=False)
def serve_react_app(full_path: str = ""):
    index_path = os.path.join(CATALOG_BUILD_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "Frontend no compilado. Ejecuta 'npm run build' en la carpeta catalog."}