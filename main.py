import models
import database
import crud
import schemas
from translation_service import get_translation_service
from fastapi import FastAPI, Depends, HTTPException, Query, Request, Body, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
import requests
import time
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os
from typing import List
import unicodedata
from bs4 import BeautifulSoup

app = FastAPI()

# Activar compresión GZIP para todas las respuestas
app.add_middleware(GZipMiddleware, minimum_size=500)

origins = [
    "https://mi-catalogo-oguv.vercel.app",
    "http://localhost:3000",  # para desarrollo local, si lo usas
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OMDB_API_KEY = "5d30c905"
OMDB_URL = "http://www.omdbapi.com/"
TMDB_API_KEY = "ffac9eb544563d4d36980ea638fca7ce"
TMDB_BEARER = "eyJhbGciOiJIUzI1NiJ9.eyJhdWQiOiJmZmFjOWViNTQ0NTYzZDRkMzY5ODBlYTYzOGZjYTdjZSIsIm5iZiI6MTc0NTU3NTMwOC45NDQsInN1YiI6IjY4MGI1ZDhjYmZiZGYxZjhjNTg5ZGQxZiIsInNjb3BlcyI6WyJhcGlfcmVhZCJdLCJ2ZXJzaW9uIjoxfQ.XV-EtgE1xTwwSNtrlQYgemgsaqOApCGwvyNWehExQvs"
TMDB_BASE_URL = "https://api.themoviedb.org/3"

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
    headers = {"Authorization": f"Bearer {TMDB_BEARER}"}
    
    # Obtener todas las imágenes disponibles
    images_url = f"{TMDB_BASE_URL}/{media_type}/{tmdb_id}/images"
    images_r = requests.get(images_url, headers=headers)
    
    if images_r.status_code != 200:
        # Si falla, usar la portada por defecto
        detail_url = f"{TMDB_BASE_URL}/{media_type}/{tmdb_id}"
        detail_r = requests.get(detail_url, headers=headers, params={"language": language})
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
    tmdb_id: int = None,
    db: Session = Depends(get_db)
):
    import traceback
    try:
        result = crud.get_medias(
            db, skip=skip, limit=limit, order_by=order_by, tipo=tipo, pendiente=pendiente,
            genero=genero, min_year=min_year, max_year=max_year,
            min_nota=min_nota, min_nota_personal=min_nota_personal,
            favorito=favorito, tag_id=tag_id, tmdb_id=tmdb_id
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
    media_type: str = Query(None, description="'movie' o 'tv' si se busca por id"),
    language: str = Query("es-ES", description="Idioma para la consulta TMDb (ej: 'es-ES', 'en-US')")
):
    headers = {"Authorization": f"Bearer {TMDB_BEARER}"}
    # Si se pasa id y media_type, buscar detalle exacto
    if id and media_type:
        tipo = "película" if media_type == "movie" else "serie"
        if tipo == "película":
            detail_url = f"{TMDB_BASE_URL}/movie/{id}"
            credits_url = f"{TMDB_BASE_URL}/movie/{id}/credits"
            detail_params = {"language": language}
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
            # Obtener tráiler de YouTube (primero en el idioma solicitado, luego en inglés si no hay)
            trailer_url = None
            videos_url = f"{TMDB_BASE_URL}/movie/{id}/videos"
            videos_r = requests.get(videos_url, headers=headers, params={"language": language})
            videos = []
            if videos_r.status_code == 200:
                videos = videos_r.json().get("results", [])
            yt_trailers = [v for v in videos if v.get("site") == "YouTube" and v.get("type") == "Trailer"]
            if not yt_trailers and language != "en-US":
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
                season_r = requests.get(season_url, headers=headers, params={"language": language})
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
            videos_r = requests.get(videos_url, headers=headers, params={"language": language})
            videos = []
            if videos_r.status_code == 200:
                videos = videos_r.json().get("results", [])
            yt_trailers = [v for v in videos if v.get("site") == "YouTube" and v.get("type") == "Trailer"]
            if not yt_trailers and language != "en-US":
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
        params = {"query": title, "language": language, "include_adult": "false"}
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
        detail_params = {"language": language}
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
            season_r = requests.get(season_url, headers=headers, params={"language": language})
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

# --- Al final del archivo: servir frontend React para rutas no API ---
@app.get("/", include_in_schema=False)
@app.get("/{full_path:path}", include_in_schema=False)
def serve_react_app(full_path: str = ""):
    index_path = os.path.join(CATALOG_BUILD_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"error": "Frontend no compilado. Ejecuta 'npm run build' en la carpeta catalog."}