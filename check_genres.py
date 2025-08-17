import os
import psycopg2
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("La variable de entorno DATABASE_URL no está configurada")

# Conectar a PostgreSQL
conn = psycopg2.connect(DATABASE_URL)
cursor = conn.cursor()

# Consultar géneros únicos
cursor.execute('SELECT DISTINCT genero FROM media WHERE genero IS NOT NULL AND genero != %s', ('',))
genres = cursor.fetchall()

print('Géneros encontrados en la base de datos:')
unique_genres = set()
for genre in genres:
    if genre[0]:
        if ',' in genre[0]:
            for sub_genre in genre[0].split(','):
                unique_genres.add(sub_genre.strip())
        else:
            unique_genres.add(genre[0])

for genre in sorted(unique_genres):
    print(f'  - {genre}')

cursor.close()
conn.close()
