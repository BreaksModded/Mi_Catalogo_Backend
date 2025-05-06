import sqlite3
import requests
import time

TMDB_API_KEY = "ffac9eb544563d4d36980ea638fca7ce"
TMDB_MOVIE_URL = "https://api.themoviedb.org/3/movie/{}"
TMDB_TV_URL = "https://api.themoviedb.org/3/tv/{}"
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/multi"

conn = sqlite3.connect("media.db")
cur = conn.cursor()

cur.execute("SELECT id, titulo, titulo_ingles, anio, tmdb_id, tipo FROM media")
registros = cur.fetchall()

for id_, titulo, titulo_ingles, anio, tmdb_id, tipo in registros:
    if titulo_ingles and titulo_ingles.strip():
        continue  # Ya tiene título en inglés
    original_title = None
    # 1. Si hay tmdb_id, buscar por id
    if tmdb_id:
        if tipo == 'pelicula' or tipo == 'película':
            url = TMDB_MOVIE_URL.format(tmdb_id)
        elif tipo == 'serie':
            url = TMDB_TV_URL.format(tmdb_id)
        else:
            url = None
        if url:
            resp = requests.get(url, params={"api_key": TMDB_API_KEY, "language": "en-US"})
            if resp.status_code == 200:
                data = resp.json()
                original_title = data.get('original_title') or data.get('original_name')
    # 2. Si no hay tmdb_id o no se ha encontrado, buscar por título y año
    if not original_title:
        params = {
            "api_key": TMDB_API_KEY,
            "query": titulo,
            "year": anio,
            "language": "en-US"
        }
        resp = requests.get(TMDB_SEARCH_URL, params=params)
        if resp.status_code == 200:
            data = resp.json()
            if data["results"]:
                result = data["results"][0]
                original_title = result.get('original_title') or result.get('original_name')
    # 3. Actualizar si se ha encontrado el título en inglés
    if original_title and original_title != titulo:
        print(f"Actualizando ID {id_}: '{titulo}' -> '{original_title}'")
        cur.execute("UPDATE media SET titulo_ingles = ? WHERE id = ?", (original_title, id_))
        conn.commit()
    else:
        print(f"No encontrado título inglés para ID {id_}: '{titulo}'")
    time.sleep(0.25)  # Para evitar rate limit de TMDb

conn.close()
print("Proceso completado.")
