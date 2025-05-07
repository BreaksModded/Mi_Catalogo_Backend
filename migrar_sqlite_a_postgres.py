import sqlalchemy as sa
from sqlalchemy.orm import sessionmaker
import sqlite3

# Configuración de conexiones
SQLITE_PATH = r"C:/Users/Diego/Documents/Obsidian/Home Cinema/backend/media.db"
POSTGRES_URL = "postgresql://media_0t7l_user:DAOS1Key0XhoQAd8G2DUcnWYjk4A0TF9@dpg-d0dku715pdvs739a5520-a.frankfurt-postgres.render.com/media_0t7l"

# 1. Conexión a SQLite
sqlite_engine = sa.create_engine(f"sqlite:///{SQLITE_PATH}")
sqlite_conn = sqlite_engine.connect()

# 2. Conexión a PostgreSQL
pg_engine = sa.create_engine(POSTGRES_URL)
pg_conn = pg_engine.connect()

# 3. Listar tablas a migrar (ajusta según tus tablas)
tablas = ["media", "tag", "lista", "media_tag", "lista_media"]

for tabla in tablas:
    print(f"Migrando tabla: {tabla}")

    # Leer datos de SQLite
    result = sqlite_conn.execute(sa.text(f"SELECT * FROM {tabla}"))
    rows = result.fetchall()
    columns = result.keys()

    # Vaciar la tabla en PostgreSQL (opcional, cuidado)
    # pg_conn.execute(sa.text(f'TRUNCATE TABLE "{tabla}" RESTART IDENTITY CASCADE'))

    # Insertar en PostgreSQL
    for row in rows:
        row_dict = dict(zip(columns, row))
        # Convierte campos booleanos de 0/1 a True/False SOLO PARA LA TABLA MEDIA
        if tabla == "media":
            for campo_bool in ["pendiente", "favorito"]:
                if campo_bool in row_dict:
                    val = row_dict[campo_bool]
                    if val is not None:
                        row_dict[campo_bool] = bool(val)
        values = ', '.join([f":{col}" for col in columns])
        insert_stmt = sa.text(f'INSERT INTO "{tabla}" ({", ".join(columns)}) VALUES ({values})')
        pg_conn.execute(insert_stmt, row_dict)
    print(f"Tabla {tabla}: {len(rows)} filas migradas.")

# Confirmar cambios
pg_conn.commit()
print("¡Migración completada!")

# Cerrar conexiones
sqlite_conn.close()
pg_conn.close()
