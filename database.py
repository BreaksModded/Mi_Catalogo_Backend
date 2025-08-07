import os
from sqlalchemy import create_engine, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Cargar variables de entorno desde .env si está disponible
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("La variable de entorno DATABASE_URL no está configurada en las variables de entorno del sistema")

# Para Session Pooler de Supabase, usar SSL
engine = create_engine(
    DATABASE_URL,
    connect_args={"sslmode": "require"},
    pool_pre_ping=True,  # Verificar conexiones antes de usar
    pool_recycle=300     # Reciclar conexiones cada 5 minutos
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def check_and_add_poster_column():
    """Verificar si existe la columna poster_url en content_translations y añadirla si no existe"""
    try:
        with engine.connect() as conn:
            # Verificar si la columna ya existe
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'content_translations' 
                AND column_name = 'poster_url'
            """))
            
            if not result.fetchone():
                conn.execute(text("""
                    ALTER TABLE content_translations 
                    ADD COLUMN poster_url VARCHAR(500)
                """))
                conn.commit()
                
    except Exception as e:
        pass  # Continúa silenciosamente

def remove_translated_description_column():
    """Eliminar la columna translated_description duplicada de content_translations"""
    try:
        with engine.connect() as conn:
            # Verificar si la columna existe
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'content_translations' 
                AND column_name = 'translated_description'
            """))
            
            if result.fetchone():
                print("Eliminando columna duplicada translated_description de content_translations...")
                conn.execute(text("""
                    ALTER TABLE content_translations 
                    DROP COLUMN translated_description
                """))
                conn.commit()
                print("✅ Columna translated_description eliminada exitosamente")
            else:
                print("✓ Columna translated_description ya no existe en content_translations")
                
    except Exception as e:
        print(f"Error eliminando columna translated_description: {e}")

def optimize_poster_indexes():
    """Crear índices optimizados para consultas de portadas"""
    try:
        with engine.connect() as conn:
            # Índice compuesto para media (tmdb_id, tipo) - mejora consultas individuales
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_media_tmdb_tipo 
                ON media (tmdb_id, tipo) 
                WHERE tmdb_id IS NOT NULL
            """))
            
            # Índice compuesto para content_translations (media_id, language_code) - mejora consultas batch
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_content_translations_media_lang 
                ON content_translations (media_id, language_code)
            """))
            
            # Índice para poster_url no nulo en content_translations
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_content_translations_poster_url 
                ON content_translations (media_id, language_code, poster_url) 
                WHERE poster_url IS NOT NULL AND poster_url != ''
            """))
            
            # Índice para imagen no nula en media
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_media_imagen 
                ON media (id, imagen) 
                WHERE imagen IS NOT NULL AND imagen != ''
            """))
            
            conn.commit()
            
    except Exception as e:
        pass  # Continúa silenciosamente si hay errores de índices

def init_db():
    Base.metadata.create_all(bind=engine)
    # Ejecutar migraciones necesarias
    check_and_add_poster_column()
    remove_translated_description_column()
    optimize_poster_indexes()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
