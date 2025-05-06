import requests
import time
from sqlalchemy.orm import sessionmaker
from models import Media, Base
from database import engine

# Configuración TMDb
TMDB_API_KEY = "ffac9eb544563d4d36980ea638fca7ce"
TMDB_BASE_URL = "https://api.themoviedb.org/3"

Session = sessionmaker(bind=engine)
session = Session()

def buscar_tmdb_id(titulo, anio=None, tipo="movie"):
    params = {
        "api_key": TMDB_API_KEY,
        "query": titulo,
        "language": "es-ES",
    }
    if anio:
        if tipo == "movie":
            params["year"] = anio
        else:
            params["first_air_date_year"] = anio
    url = f"{TMDB_BASE_URL}/search/{'movie' if tipo == 'movie' else 'tv'}"
    r = requests.get(url, params=params)
    if r.status_code == 200:
        results = r.json().get("results", [])
        if results:
            return results[0]["id"]
    return None

def main():
    medias = session.query(Media).all()
    for media in medias:
        tipo = "tv" if media.tipo and media.tipo.lower() == "serie" else "movie"
        correcto_id = buscar_tmdb_id(media.titulo, media.anio, tipo)
        if correcto_id:
            if media.tmdb_id == correcto_id:
                print(f"OK: {media.titulo} ({media.anio}) - tmdb_id correcto: {media.tmdb_id}")
            else:
                existente = session.query(Media).filter(Media.tmdb_id == correcto_id, Media.id != media.id).first()
                if existente:
                    print(f"[DUPLICADO] {media.titulo} ({media.anio}) NO actualizado: tmdb_id correcto sería {correcto_id} pero ya lo tiene '{existente.titulo}' (ID {existente.id})")
                else:
                    print(f"Corrigiendo {media.titulo} ({media.anio}) - tmdb_id: {media.tmdb_id} -> {correcto_id}")
                    media.tmdb_id = correcto_id
                    # Commit inmediato y manejo de database locked
                    for intento in range(5):
                        try:
                            session.commit()
                            break
                        except Exception as e:
                            if 'database is locked' in str(e):
                                print("[AVISO] database is locked, reintentando en 0.5s...")
                                time.sleep(0.5)
                            else:
                                raise
                    time.sleep(0.1)
        else:
            print(f"[NO ENCONTRADO] {media.titulo} ({media.anio}) - tmdb_id actual: {media.tmdb_id}")
    print("Corrección terminada.")

if __name__ == "__main__":
    main()
