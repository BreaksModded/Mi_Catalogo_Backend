import os
import requests
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, Media, Keyword, media_keyword
from database import SQLALCHEMY_DATABASE_URL

# Configuración de la base de datos
engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

TMDB_API_KEY = os.getenv("TMDB_API_KEY", "ffac9eb544563d4d36980ea638fca7ce")
TMDB_BASE_URL = "https://api.themoviedb.org/3"

import unicodedata

def normalize_tipo(tipo):
    if not tipo:
        return ''
    tipo_norm = ''.join(c for c in unicodedata.normalize('NFD', tipo.lower()) if unicodedata.category(c) != 'Mn')
    if tipo_norm in ['pelicula', 'movie']:
        return 'pelicula'
    elif tipo_norm in ['serie', 'tv']:
        return 'serie'
    return tipo_norm

def get_keywords_from_tmdb(tmdb_id, tipo):
    """
    Obtiene los keywords de TMDb para una película o serie.
    tipo: 'pelicula' o 'serie'
    """
    if not tmdb_id:
        return []
    tipo_norm = normalize_tipo(tipo)
    if tipo_norm == 'pelicula':
        url = f"{TMDB_BASE_URL}/movie/{tmdb_id}/keywords"
    elif tipo_norm == 'serie':
        url = f"{TMDB_BASE_URL}/tv/{tmdb_id}/keywords"
    else:
        print(f"[ERROR] Tipo desconocido para TMDb ID {tmdb_id}: '{tipo}' (normalizado: '{tipo_norm}'). Debe ser 'pelicula' o 'serie'. Saltando...")
        return []
    resp = requests.get(url, params={"api_key": TMDB_API_KEY})
    print(f"\n[DEBUG] Consultando TMDb para {tmdb_id} ({tipo}) -> {url}")
    print(f"[DEBUG] Código de estado: {resp.status_code}")
    try:
        data = resp.json()
    except Exception as e:
        print(f"[ERROR] No se pudo decodificar JSON: {e}")
        print(f"[RAW RESPONSE] {resp.text}")
        return []
    print(f"[DEBUG] Respuesta cruda: {data}")
    # TMDb devuelve 'keywords' (películas) o 'results' (series)
    if 'keywords' in data:
        return [k['name'] for k in data['keywords']]
    elif 'results' in data:
        return [k['name'] for k in data['results']]
    return []

def main():
    session = SessionLocal()
    try:
        medias = session.query(Media).all()
        print(f"Procesando {len(medias)} medias...")
        for media in medias:
            if not media.tmdb_id or not media.tipo:
                continue
            keywords = get_keywords_from_tmdb(media.tmdb_id, media.tipo)
            # Borrar todas las relaciones actuales de keywords para esta media
            media.keywords.clear()
            session.flush()
            # Añadir los nuevos keywords
            for kw_name in keywords:
                kw = session.query(Keyword).filter_by(nombre=kw_name).first()
                if not kw:
                    kw = Keyword(nombre=kw_name)
                    session.add(kw)
                    session.flush()  # Para obtener el id
                if kw not in media.keywords:
                    media.keywords.append(kw)
            session.commit()
            print(f"{media.titulo} ({media.tmdb_id}) - Keywords actualizados: {keywords}")
    finally:
        session.close()

if __name__ == "__main__":
    main()
