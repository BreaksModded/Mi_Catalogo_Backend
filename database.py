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

def optimize_poster_indexes():
    """Crear índices optimizados para consultas de portadas"""
    try:
        # CREATE INDEX CONCURRENTLY no puede ejecutarse dentro de una transacción
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
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
            
            # AUTOCOMMIT se encarga del commit
            
    except Exception as e:
        pass  # Continúa silenciosamente si hay errores de índices

def ensure_pg_trgm_extension():
    """Habilita la extensión pg_trgm para acelerar búsquedas ILIKE si está disponible."""
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
            conn.commit()
    except Exception:
        # En plataformas gestionadas puede no ser necesario o estar restringido.
        pass

def optimize_search_indexes():
    """Crear índices para acelerar búsquedas y listados (ILIKE y ordenaciones)."""
    try:
        # Para índices CONCURRENTLY, usar AUTOCOMMIT
        with engine.connect().execution_options(isolation_level="AUTOCOMMIT") as conn:
            # Índices GIN con pg_trgm para búsquedas por ILIKE
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_media_titulo_trgm 
                ON media USING gin (titulo gin_trgm_ops)
            """))
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_media_titulo_ingles_trgm 
                ON media USING gin (titulo_ingles gin_trgm_ops)
            """))
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_media_elenco_trgm 
                ON media USING gin (elenco gin_trgm_ops)
            """))
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_media_director_trgm 
                ON media USING gin (director gin_trgm_ops)
            """))
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_media_genero_trgm 
                ON media USING gin (genero gin_trgm_ops)
            """))

            # Índices BTREE para filtros y ordenaciones frecuentes
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_media_fecha_creacion_desc 
                ON media (fecha_creacion DESC)
            """))
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_media_pendiente 
                ON media (pendiente)
            """))
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_media_favorito 
                ON media (favorito)
            """))
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_media_anio 
                ON media (anio)
            """))
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_media_nota_imdb 
                ON media (nota_imdb)
            """))
            conn.execute(text("""
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_media_nota_personal 
                ON media (nota_personal)
            """))
            # AUTOCOMMIT se encarga del commit
    except Exception:
        # Si falla (permiso/extension no disponible), continuar sin bloquear el arranque
        pass

def init_db():
    Base.metadata.create_all(bind=engine)
    # Optimización y extensiones necesarias
    ensure_pg_trgm_extension()
    optimize_poster_indexes()
    optimize_search_indexes()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
