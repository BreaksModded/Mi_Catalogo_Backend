import os
import re
import json
import unicodedata
from datetime import datetime, timedelta
from typing import List, Optional, Any, Dict

from fastapi import (
    FastAPI, Depends, HTTPException, Query, Request, Response, 
    status, Body, Form, File, UploadFile
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.security import OAuth2PasswordRequestForm, OAuth2PasswordBearer
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from jose import JWTError, jwt
from passlib.context import CryptContext
import requests
from bs4 import BeautifulSoup

# Importar modelos, esquemas y utilidades de autenticación
from . import models, schemas, auth
from .database import SessionLocal, engine, get_db
from .config import settings

# Verificar si estamos en modo de desarrollo
IS_DEV = settings.ENV == "development"

# Crear tablas en la base de datos (en desarrollo)
if IS_DEV:
    models.Base.metadata.create_all(bind=engine)

# Configuración de CORS
origins = [
    settings.FRONTEND_URL,
    "http://localhost:3000",  # React por defecto
    "http://localhost:8000",  # FastAPI por defecto
]

# Inicializar la aplicación FastAPI
app = FastAPI(
    title="Home Cinema API",
    description="API para gestionar tu catálogo personal de películas y series",
    version="1.0.0",
    docs_url="/docs" if IS_DEV else None,
    redoc_url="/redoc" if IS_DEV else None,
    openapi_url="/openapi.json" if IS_DEV else None,
)

# Añadir middlewares
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Montar archivos estáticos
app.mount("/static", StaticFiles(directory="static"), name="static")

# Variables globales
OMDB_API_KEY = "5d30c905"
OMDB_URL = "http://www.omdbapi.com/"
TMDB_API_KEY = "ffac9eb544563d4d36980ea638fca7ce"
TMDB_BEARER = "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJmZmFjOWViNTQ0NTYzZDRkMzY5ODBlYTYzOGZjYTdjZSIsIm5iZiI6MTc0NTU3NTMwOC45NDQsInN1YiI6IjY4MGI1ZDhjYmZiZGYxZjhjNTg5ZGQxZiIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.XV-EtgE1xTwwSNtrlQYgemgsaqOApCGwvyNWehExQvs"
TMDB_BASE_URL = "https://api.themoviedb.org/3"

# Servir frontend React compilado
CATALOG_BUILD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../catalog/build'))
if os.path.isdir(CATALOG_BUILD_DIR):
    app.mount("/static", StaticFiles(directory=os.path.join(CATALOG_BUILD_DIR, 'static')), name="static")

# --- Rutas de Autenticación ---

@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Obtener token de acceso para autenticación.
    """
    token = auth.authenticate_and_get_token(
        db, form_data.username, form_data.password
    )
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario o contraseña incorrectos",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token

@app.post("/users/", response_model=schemas.UserInDB, status_code=status.HTTP_201_CREATED)
def create_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """
    Crear un nuevo usuario.
    """
    return auth.create_user(db=db, user=user)

@app.get("/users/me/", response_model=schemas.UserInDB)
async def read_users_me(current_user: models.User = Depends(auth.get_current_active_user)):
    """
    Obtener información del usuario actual.
    """
    return current_user

@app.get("/users/me/items/")
async def read_own_items(
    current_user: models.User = Depends(auth.get_current_active_user)
):
    """
    Obtener los ítems del usuario actual.
    """
    return [{"item_id": 1, "owner": current_user.username}]

@app.get("/search", response_model=List[schemas.Media])
def search_medias(q: str = Query(..., description="Búsqueda por título, actor o director"), db: Session = Depends(get_db)):
    def normalize_str(s):
        return ''.join(
            c for c in unicodedata.normalize('NFD', s.lower())
            if unicodedata.category(c) != 'Mn'
        )
    q_norm = normalize_str(q.strip())
    # Buscar todas las medias y filtrar en Python por coincidencia normalizada
    medias = db.query(models.Media).all()
    resultados = []
    for m in medias:
        if (
            q_norm in normalize_str(m.titulo or "") or
            q_norm in normalize_str(m.titulo_ingles or "") or
            q_norm in normalize_str(m.elenco or "") or
            q_norm in normalize_str(m.director or "")
        ):
            resultados.append(m)
    return resultados

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
    db: Session = Depends(get_db)
):
    import traceback
    try:
        result = crud.get_medias(
            db, skip=skip, limit=limit, order_by=order_by, tipo=tipo, pendiente=pendiente,
            genero=genero, min_year=min_year, max_year=max_year,
            min_nota=min_nota, min_nota_personal=min_nota_personal,
            favorito=favorito, tag_id=tag_id
        )
        return result
    except Exception as e:
        print("ERROR EN /medias:", e)
        traceback.print_exc()
        from fastapi import HTTPException
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
    return crud.create_tag(db, tag)

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
    media_type: str = Query(None, description="'movie' o 'tv' si se busca por id")
):
    headers = {"Authorization": f"Bearer {TMDB_BEARER}"}
    # Si se pasa id y media_type, buscar detalle exacto
    if id and media_type:
        tipo = "película" if media_type == "movie" else "serie"
        if tipo == "película":
            detail_url = f"{TMDB_BASE_URL}/movie/{id}"
            credits_url = f"{TMDB_BASE_URL}/movie/{id}/credits"
            detail_params = {"language": "es-ES"}
            detail_r = requests.get(detail_url, headers=headers, params=detail_params)
            if detail_r.status_code != 200:
                raise HTTPException(status_code=502, detail="Error al obtener detalles de TMDb")
            detail = detail_r.json()
            credits_r = requests.get(credits_url, headers=headers)
            director = ""
            elenco = ""
            if credits_r.status_code == 200:
                credits = credits_r.json()
                director_list = [c["name"] for c in credits.get("crew", []) if c.get("job") == "Director"]
                director = ", ".join(director_list)
                elenco_list = [a["name"] for a in credits.get("cast", [])[:5]]
                elenco = ", ".join(elenco_list)
            # Obtener tráiler de YouTube (primero en español, luego en inglés si no hay)
            trailer_url = None
            videos_url = f"{TMDB_BASE_URL}/movie/{id}/videos"
            videos_r = requests.get(videos_url, headers=headers, params={"language": "es-ES"})
            videos = []
            if videos_r.status_code == 200:
                videos = videos_r.json().get("results", [])
            yt_trailers = [v for v in videos if v.get("site") == "YouTube" and v.get("type") == "Trailer"]
            if not yt_trailers:
                videos_r_en = requests.get(videos_url, headers=headers, params={"language": "en-US"})
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
                "imagen": f"https://image.tmdb.org/t/p/w500{detail['poster_path']}" if detail.get("poster_path") else "",
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
            detail_params = {"language": "es-ES"}
            detail_r = requests.get(detail_url, headers=headers, params=detail_params)
            if detail_r.status_code != 200:
                raise HTTPException(status_code=502, detail="Error al obtener detalles de TMDb")
            detail = detail_r.json()
            credits_r = requests.get(credits_url, headers=headers)
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
                season_r = requests.get(season_url, headers=headers, params={"language": "es-ES"})
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
            # Obtener tráiler de YouTube para series (primero en español, luego en inglés si no hay)
            trailer_url = None
            videos_url = f"{TMDB_BASE_URL}/tv/{id}/videos"
            videos_r = requests.get(videos_url, headers=headers, params={"language": "es-ES"})
            videos = []
            if videos_r.status_code == 200:
                videos = videos_r.json().get("results", [])
            yt_trailers = [v for v in videos if v.get("site") == "YouTube" and v.get("type") == "Trailer"]
            if not yt_trailers:
                videos_r_en = requests.get(videos_url, headers=headers, params={"language": "en-US"})
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
                "imagen": f"https://image.tmdb.org/t/p/w500{detail['poster_path']}" if detail.get("poster_path") else "",
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
        params = {"query": title, "language": "es-ES", "include_adult": "false"}
        r = requests.get(search_url, headers=headers, params=params)
        if r.status_code != 200:
            raise HTTPException(status_code=502, detail="Error al conectar con TMDb")
        data = r.json()
        if not data.get("results"):
            raise HTTPException(status_code=404, detail="No encontrado en TMDb")
        opciones = []
        for res in data["results"]:
            if res["media_type"] not in ("movie", "tv"):
                continue
            opciones.append({
                "id": res["id"],
                "media_type": res["media_type"],
                "titulo": res.get("title") or res.get("name", ""),
                "anio": (res.get("release_date") or res.get("first_air_date") or "")[:4],
                "imagen": f"https://image.tmdb.org/t/p/w200{res['poster_path']}" if res.get("poster_path") else "",
                "nota_tmdb": res.get("vote_average"),
                "votos_tmdb": res.get("vote_count")
            })
        return {"opciones": opciones}
    # Si no, lógica anterior (elige uno y devuelve detalle)
    item = None
    if tipo_preferido:
        search_url = f"{TMDB_BASE_URL}/search/multi"
        params = {"query": title, "language": "es-ES", "include_adult": "false"}
        r = requests.get(search_url, headers=headers, params=params)
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
        params = {"query": title, "language": "es-ES", "include_adult": "false"}
        r = requests.get(search_url, headers=headers, params=params)
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
        detail_params = {"language": "es-ES"}
        detail_r = requests.get(detail_url, headers=headers, params=detail_params)
        if detail_r.status_code != 200:
            raise HTTPException(status_code=502, detail="Error al obtener detalles de TMDb")
        detail = detail_r.json()
        credits_r = requests.get(credits_url, headers=headers)
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
            "imagen": f"https://image.tmdb.org/t/p/w500{detail['poster_path']}" if detail.get("poster_path") else "",
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
        detail_params = {"language": "es-ES"}
        detail_r = requests.get(detail_url, headers=headers, params=detail_params)
        if detail_r.status_code != 200:
            raise HTTPException(status_code=502, detail="Error al obtener detalles de TMDb")
        detail = detail_r.json()
        credits_r = requests.get(credits_url, headers=headers)
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
            season_r = requests.get(season_url, headers=headers, params={"language": "es-ES"})
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
            "imagen": f"https://image.tmdb.org/t/p/w500{detail['poster_path']}" if detail.get("poster_path") else "",
            "estado": detail.get("status", ""),
            "tipo": tipo,
            "temporadas": detail.get("number_of_seasons"),
            "episodios": detail.get("number_of_episodes"),
            "nota_personal": None,
            "nota_tmdb": detail.get("vote_average"),
            "votos_tmdb": detail.get("vote_count"),
            "temporadas_detalle": temporadas_detalle
        }

@app.get("/listas", response_model=List[schemas.Lista])
def get_listas(db: Session = Depends(get_db)):
    return crud.get_listas(db)

@app.get("/listas/{lista_id}", response_model=schemas.Lista)
def get_lista(lista_id: int, db: Session = Depends(get_db)):
    lista = crud.get_lista(db, lista_id)
    if not lista:
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    return lista

@app.post("/listas", response_model=schemas.Lista, status_code=status.HTTP_201_CREATED)
def create_lista(lista: schemas.ListaCreate, db: Session = Depends(get_db)):
    return crud.create_lista(db, lista)

@app.delete("/listas/{lista_id}", response_model=schemas.Lista)
def delete_lista(lista_id: int, db: Session = Depends(get_db)):
    lista = crud.delete_lista(db, lista_id)
    if not lista:
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    return lista

@app.put("/listas/{lista_id}", response_model=schemas.Lista)
def update_lista(lista_id: int, nombre: str = Body(None), descripcion: str = Body(None), db: Session = Depends(get_db)):
    lista = crud.update_lista(db, lista_id, nombre, descripcion)
    if not lista:
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    return lista

@app.post("/listas/{lista_id}/add_media/{media_id}", response_model=schemas.Lista)
def add_media_to_lista(lista_id: int, media_id: int, db: Session = Depends(get_db)):
    lista = crud.add_media_to_lista(db, lista_id, media_id)
    if not lista:
        raise HTTPException(status_code=404, detail="Lista o media no encontrada")
    return lista

@app.delete("/listas/{lista_id}/remove_media/{media_id}", response_model=schemas.Lista)
def remove_media_from_lista(lista_id: int, media_id: int, db: Session = Depends(get_db)):
    lista = crud.remove_media_from_lista(db, lista_id, media_id)
    if not lista:
        raise HTTPException(status_code=404, detail="Lista o media no encontrada")
    return lista

# --- Al final del archivo: servir frontend React para rutas no API ---
@app.get("/", include_in_schema=False)
@app.get("/{full_path:path}", include_in_schema=False)
def serve_react_app(full_path: str = ""):
    index_path = os.path.join(CATALOG_BUILD_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "Frontend no compilado. Ejecuta 'npm run build' en la carpeta catalog."}