import models
import database
import crud
import schemas
from translation_service import TranslationService, get_translation_service
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
import requests
import time
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from typing import List
import unicodedata
from bs4 import BeautifulSoup
from config import TMDB_BASE_URL, REQUEST_TIMEOUT, get_tmdb_auth_headers, get_allowed_origins, get_lan_origin_regex

app = FastAPI()

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
    response: Response = None
):
    """Efficient search using SQL with ASCII-normalized LIKE across key fields.
    Falls back to in-Python filter if DB does not support unaccent.
    """
    term = (q or "").strip()
    if not term:
        return []

    # Try SQL-level case-insensitive search; simple LIKE on multiple columns
    like = f"%{term}%"
    query = db.query(models.Media).filter(
        or_(
            models.Media.titulo.ilike(like),
            models.Media.titulo_ingles.ilike(like),
            models.Media.elenco.ilike(like),
            models.Media.director.ilike(like),
        )
    )
    total = None
    if include_total:
        total = query.count()
        if response is not None:
            response.headers["X-Total-Count"] = str(total)
    # Apply pagination
    items = query.offset(max(0, skip)).limit(max(1, min(limit, 200))).all()
    return items

@app.on_event("startup")
def startup():
    database.init_db()

@app.get("/medias", response_model=List[schemas.Media])
def read_medias(
    skip: int = 0,
    limit: int = 24,
    pendiente: bool = None,
    favorito: bool = None,
    tag_id: int = None,
    order_by: str = None,
    tipo: str = None,
    genero: str = None,
    min_year: int = None,
    max_year: int = None,
    min_nota: float = None,
    min_nota_personal: float = None,
    tmdb_id: int = None,
    include_total: bool = Query(False, description="Si true, añade X-Total-Count a la respuesta"),
    db: Session = Depends(get_db),
    response: Response = None
):
    import traceback
    try:
        base_query = crud.get_medias_query(
            db, skip=skip, limit=limit, order_by=order_by, tipo=tipo, pendiente=pendiente,
            genero=genero, min_year=min_year, max_year=max_year,
            min_nota=min_nota, min_nota_personal=min_nota_personal,
            favorito=favorito, tag_id=tag_id, tmdb_id=tmdb_id
        )
        total = None
        if include_total:
            total = base_query.count()
            if response is not None:
                response.headers["X-Total-Count"] = str(total)
        result = base_query.offset(skip).limit(limit).all()
        return result
    except Exception as e:
        print("ERROR EN /medias:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

import unicodedata

@app.get("/medias/count")
def count_medias(
    pendiente: bool = None,
    tipo: str = None,
    db: Session = Depends(get_db)
):
    query = db.query(models.Media)
    if pendiente is not None:
        query = query.filter(models.Media.pendiente == pendiente)
    if tipo:
        def normalize(s):
            return unicodedata.normalize('NFKD', s or '').encode('ASCII', 'ignore').decode('ASCII').lower().strip()
        ids = [m.id for m in query if normalize(m.tipo) == normalize(tipo)]
        query = query.filter(models.Media.id.in_(ids))
    return {"count": query.count()}

@app.get("/medias/top5")
def top5_medias(
    tipo: str = Query(..., description="pelicula o serie"),
    db: Session = Depends(get_db)
):
    import unicodedata
    def normalize(s):
        return unicodedata.normalize('NFKD', s or '').encode('ASCII', 'ignore').decode('ASCII').lower().strip()
    tipo_norm = normalize(tipo)
    query = db.query(models.Media).filter(
        models.Media.pendiente == False,
        models.Media.nota_personal != None
    )
    ids = [m.id for m in query if normalize(m.tipo) == tipo_norm]
    result = db.query(models.Media).filter(
        models.Media.id.in_(ids)
    ).order_by(models.Media.nota_personal.desc()).limit(5).all()
    return [
        {
            "id": m.id,
            "titulo": m.titulo,
            "nota_personal": m.nota_personal,
            "anio": getattr(m, "anio", None),
            "tipo": m.tipo
        }
        for m in result
    ]

def get_generos(db: Session):
    import unicodedata
    def normalize(s):
        return unicodedata.normalize('NFKD', s or '').encode('ASCII', 'ignore').decode('ASCII').lower().strip()
    medias = db.query(models.Media).filter(models.Media.pendiente == False).all()
    genero_count = {}
    genero_original = {}
    genero_notas = {}
    for m in medias:
        generos = (getattr(m, 'genero', '') or '').split(',')
        generos = [g.strip() for g in generos if g.strip()]
        for g in generos:
            g_norm = normalize(g)
            genero_count[g_norm] = genero_count.get(g_norm, 0) + 1
            if g_norm not in genero_original:
                genero_original[g_norm] = g  # Guarda el nombre original
            if m.nota_personal is not None:
                genero_notas.setdefault(g_norm, []).append(m.nota_personal)
    return genero_count, genero_original, genero_notas

@app.get("/medias/distribucion_generos")
def distribucion_generos(db: Session = Depends(get_db)):
    genero_count, genero_original, _ = get_generos(db)
    return {genero_original[g]: genero_count[g] for g in genero_count}

@app.get("/medias/generos_vistos")
def generos_vistos(db: Session = Depends(get_db)):
    genero_count, genero_original, genero_notas = get_generos(db)
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
def peor_pelicula(db: Session = Depends(get_db)):
    def normalize(s):
        return unicodedata.normalize('NFKD', s or '').encode('ASCII', 'ignore').decode('ASCII').lower().strip()
    tipo_norm = 'pelicula'
    query = db.query(models.Media).filter(
        models.Media.pendiente == False,
        models.Media.nota_personal != None
    )
    ids = [m.id for m in query if normalize(m.tipo) == tipo_norm]
    result = db.query(models.Media).filter(
        models.Media.id.in_(ids)
    ).order_by(models.Media.nota_personal.asc()).first()
    if not result:
        raise HTTPException(status_code=404, detail="No hay películas con nota personal")
    return result

@app.get("/medias/peor_serie", response_model=schemas.Media)
def peor_serie(db: Session = Depends(get_db)):
    def normalize(s):
        return unicodedata.normalize('NFKD', s or '').encode('ASCII', 'ignore').decode('ASCII').lower().strip()
    tipo_norm = 'serie'
    query = db.query(models.Media).filter(
        models.Media.pendiente == False,
        models.Media.nota_personal != None
    )
    ids = [m.id for m in query if normalize(m.tipo) == tipo_norm]
    result = db.query(models.Media).filter(
        models.Media.id.in_(ids)
    ).order_by(models.Media.nota_personal.asc()).first()
    if not result:
        raise HTTPException(status_code=404, detail="No hay series con nota personal")
    return result

@app.get("/medias/vistos_por_anio")
def vistos_por_anio(db: Session = Depends(get_db)):
    medias = db.query(models.Media).filter(models.Media.pendiente == False).all()
    conteo = {}
    for m in medias:
        anio = getattr(m, 'anio', None)
        if anio:
            conteo[anio] = conteo.get(anio, 0) + 1
    return conteo

@app.get("/medias/top_personas")
def top_personas(db: Session = Depends(get_db)):
    from collections import Counter
    medias = db.query(models.Media).filter(models.Media.pendiente == False).all()
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
def read_media(media_id: int, db: Session = Depends(get_db)):
    db_media = crud.get_media(db, media_id=media_id)
    if db_media is None:
        raise HTTPException(status_code=404, detail="Media not found")
    return db_media

@app.get("/medias/{media_id}/similares", response_model=List[schemas.Media])
def get_similares(media_id: int, db: Session = Depends(get_db)):
    similares = crud.get_similares_para_media(db, media_id, n=24)
    return similares

@app.post("/medias", response_model=schemas.Media)
def create_media(media: schemas.MediaCreate, db: Session = Depends(get_db)):
    try:
        return crud.create_media(db, media)
    except Exception as e:
        raise HTTPException(status_code=409, detail=str(e))

@app.delete("/medias/{media_id}", response_model=schemas.Media)
def delete_media(media_id: int, db: Session = Depends(get_db)):
    db_media = crud.delete_media(db, media_id)
    if db_media is None:
        raise HTTPException(status_code=404, detail="Media not found")
    return db_media

@app.patch("/medias/{media_id}/pendiente", response_model=schemas.Media)
def update_pendiente(media_id: int, pendiente: bool, db: Session = Depends(get_db)):
    db_media = crud.update_media_pendiente(db, media_id, pendiente)
    if db_media is None:
        raise HTTPException(status_code=404, detail="Media not found")
    return db_media

@app.patch("/medias/{media_id}/favorito", response_model=schemas.Media)
def update_favorito(media_id: int, favorito: bool, db: Session = Depends(get_db)):
    db_media = crud.update_media_favorito(db, media_id, favorito)
    if db_media is None:
        raise HTTPException(status_code=404, detail="Media not found")
    return db_media

@app.patch("/medias/{media_id}/anotacion_personal", response_model=schemas.Media)
def update_anotacion_personal(media_id: int, anotacion_personal: str = Body(...), db: Session = Depends(get_db)):
    db_media = crud.update_media_anotacion_personal(db, media_id, anotacion_personal)
    if db_media is None:
        raise HTTPException(status_code=404, detail="Media not found")
    return db_media

@app.get("/pendientes", response_model=List[schemas.Media])
def read_pendientes(skip: int = 0, limit: int = 24, db: Session = Depends(get_db)):
    return crud.get_pendientes(db, skip=skip, limit=limit)

@app.get("/favoritos", response_model=List[schemas.Media])
def read_favoritos(skip: int = 0, limit: int = 24, db: Session = Depends(get_db)):
    return crud.get_favoritos(db, skip=skip, limit=limit)

@app.get("/tags", response_model=List[schemas.Tag])
def get_tags(db: Session = Depends(get_db)):
    return crud.get_tags(db)

@app.post("/tags", response_model=schemas.Tag)
def create_tag(tag: schemas.TagCreate, db: Session = Depends(get_db)):
    try:
        return crud.create_tag(db, tag)
    except Exception as e:
        msg = str(e)
        lower = msg.lower()
        status_code = 409 if "existe un tag" in lower else 400
        raise HTTPException(status_code=status_code, detail=msg)

@app.post("/medias/{media_id}/tags/{tag_id}", response_model=schemas.Media)
def add_tag_to_media(media_id: int, tag_id: int, db: Session = Depends(get_db)):
    media = crud.add_tag_to_media(db, media_id, tag_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media o Tag no encontrado")
    return media

@app.delete("/medias/{media_id}/tags/{tag_id}", response_model=schemas.Media)
def remove_tag_from_media(media_id: int, tag_id: int, db: Session = Depends(get_db)):
    media = crud.remove_tag_from_media(db, media_id, tag_id)
    if not media:
        raise HTTPException(status_code=404, detail="Media o Tag no encontrado")
    return media

@app.delete("/tags/{tag_id}", response_model=schemas.Tag)
def delete_tag(tag_id: int, db: Session = Depends(get_db)):
    db_tag = crud.delete_tag(db, tag_id)
    if db_tag is None:
        raise HTTPException(status_code=404, detail="Tag not found")
    return db_tag

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
                "estado": detail.get("status", ""),
                "tipo": tipo,
                "temporadas": None,
                "episodios": None,
                "nota_personal": None,
                "nota_tmdb": detail.get("vote_average"),
                "votos_tmdb": detail.get("vote_count"),
                "presupuesto": detail.get("budget"),
                "recaudacion": detail.get("revenue"),
                "trailer": trailer_url
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
                "estado": detail.get("status", ""),
                "tipo": tipo,
                "temporadas": detail.get("number_of_seasons"),
                "episodios": detail.get("number_of_episodes"),
                "nota_personal": None,
                "nota_tmdb": detail.get("vote_average"),
                "votos_tmdb": detail.get("vote_count"),
                "temporadas_detalle": temporadas_detalle,
                "trailer": trailer_url
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
            "estado": detail.get("status", ""),
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
            "estado": detail.get("status", ""),
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

@app.get("/tmdb/collection/{collection_id}")
def tmdb_collection(collection_id: int, language: str = Query("es-ES")):
    headers = get_tmdb_auth_headers()
    url = f"{TMDB_BASE_URL}/collection/{collection_id}"
    r = requests.get(url, headers=headers, params={"language": language}, timeout=REQUEST_TIMEOUT)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Error al obtener colección de TMDb")
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
# Endpoint: Medias vistas con este actor (por tmdb_id de persona)
@app.get("/medias/by_actor/{person_tmdb_id}", response_model=List[schemas.Media])
def get_medias_by_actor(person_tmdb_id: int, db: Session = Depends(get_db)):
    """
    Devuelve todas las medias donde el actor con ese TMDb ID aparece en el campo elenco (como id o nombre).
    Busca coincidencias en el campo elenco (que es texto, puede contener ids o nombres).
    """
    # El campo elenco puede ser: "Nombre1 (id1), Nombre2 (id2), ..."
    # Buscamos por id entre paréntesis o por nombre exacto si no hay id
    # Ejemplo: elenco = "Tom Hanks (31), Tim Allen (12898)"
    # Para person_tmdb_id=31, buscar "(31)" en elenco
    pattern = f"({person_tmdb_id})"
    query = db.query(models.Media).filter(models.Media.elenco.ilike(f"%{pattern}%"))
    return query.all()
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

# --- Al final del archivo: servir frontend React para rutas no API ---
@app.get("/", include_in_schema=False)
@app.get("/{full_path:path}", include_in_schema=False)
def serve_react_app(full_path: str = ""):
    index_path = os.path.join(CATALOG_BUILD_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "Frontend no compilado. Ejecuta 'npm run build' en la carpeta catalog."}