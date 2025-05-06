import sqlite3
import requests
import time

TMDB_API_KEY = "ffac9eb544563d4d36980ea638fca7ce"
TMDB_SEARCH_URL = "https://api.themoviedb.org/3/search/multi"

conn = sqlite3.connect("media.db")
cur = conn.cursor()

cur.execute("SELECT id, titulo, anio FROM media WHERE tmdb_id IS NULL OR tmdb_id = ''")
registros = cur.fetchall()

for id_, titulo, anio in registros:
    params = {
        "api_key": TMDB_API_KEY,
        "query": titulo,
        "year": anio,
        "language": "es-ES"
    }
    resp = requests.get(TMDB_SEARCH_URL, params=params)
    if resp.status_code == 200:
        data = resp.json()
        if data["results"]:
            # Mostrar todos los resultados encontrados
            print(f"\nResultados para '{titulo}' ({anio}):")
            for i, result in enumerate(data["results"][:3], 1):
                print(f"{i}. {result.get('title', result.get('name'))} ({result.get('release_date', result.get('first_air_date', 'N/A'))}) - ID: {result['id']}")
            
            # Buscar el resultado que coincida mejor con el título y año
            mejor_resultado = None
            for result in data["results"]:
                if result.get("release_date", "").startswith(str(anio)):
                    mejor_resultado = result
                    break
            
            if mejor_resultado is None:
                mejor_resultado = data["results"][0]
            
            tmdb_id = mejor_resultado["id"]
            print(f"Asignando {tmdb_id} a {titulo} ({anio})")
            cur.execute("UPDATE media SET tmdb_id = ? WHERE id = ?", (tmdb_id, id_))
            conn.commit()
        else:
            print(f"No encontrado: {titulo} ({anio})")
    else:
        print(f"Error con {titulo} ({anio})")
    time.sleep(0.3)

conn.close()
print("Actualización completada.")