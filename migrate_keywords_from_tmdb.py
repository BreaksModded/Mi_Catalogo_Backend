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

def get_keywords_from_tmdb(tmdb_id, tipo):
    """
    Obtiene los keywords de TMDb para una película o serie.
    tipo: 'pelicula' o 'serie'
    """
    if not tmdb_id:
        return []
    if tipo == 'pelicula':
        url = f"{TMDB_BASE_URL}/movie/{tmdb_id}/keywords"
    else:
        url = f"{TMDB_BASE_URL}/tv/{tmdb_id}/keywords"
    resp = requests.get(url, params={"api_key": TMDB_API_KEY})
    if resp.status_code != 200:
        print(f"No se pudieron obtener keywords para TMDb ID {tmdb_id} ({tipo})")
        return []
    data = resp.json()
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
            for kw_name in keywords:
                # Buscar si ya existe el keyword
                kw = session.query(Keyword).filter_by(nombre=kw_name).first()
                if not kw:
                    kw = Keyword(nombre=kw_name)
                    session.add(kw)
                    session.flush()  # Para obtener el id
                # Relacionar si no está ya relacionado
                if kw not in media.keywords:
                    media.keywords.append(kw)
            session.commit()
            print(f"{media.titulo} ({media.tmdb_id}) - Añadidos keywords: {keywords}")
    finally:
        session.close()

if __name__ == "__main__":
    main()
