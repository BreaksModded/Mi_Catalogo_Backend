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
                print("Añadiendo columna poster_url a content_translations...")
                conn.execute(text("""
                    ALTER TABLE content_translations 
                    ADD COLUMN poster_url VARCHAR(500)
                """))
                conn.commit()
                print("✅ Columna poster_url añadida exitosamente")
            else:
                print("✓ Columna poster_url ya existe en content_translations")
                
    except Exception as e:
        print(f"Error verificando/añadiendo columna poster_url: {e}")

def init_db():
    Base.metadata.create_all(bind=engine)
    # Ejecutar migraciones necesarias
    check_and_add_poster_column()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
