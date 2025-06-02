from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from sqlalchemy.exc import SQLAlchemyError
from typing import Generator, Optional
import os

from .config import settings

# Configuración de la base de datos
SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# Configuración del motor de base de datos
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,  # Verifica la conexión antes de usarla
    pool_recycle=300,    # Recicla conexiones después de 5 minutos
    pool_size=5,         # Número de conexiones a mantener en el pool
    max_overflow=10,     # Número máximo de conexiones que pueden crearse
)

# Configuración de la sesión de SQLAlchemy
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False  # Permite acceder a los atributos después del commit
)

# Base para los modelos
Base = declarative_base()

def get_db() -> Generator[Session, None, None]:
    """
    Obtiene una sesión de base de datos.
    
    Uso:
    ```python
    db = next(get_db())
    # Usar db...
    ```
    """
    db: Optional[Session] = None
    try:
        db = SessionLocal()
        yield db
    except SQLAlchemyError as e:
        if db:
            db.rollback()
        raise e
    finally:
        if db:
            db.close()

def init_db() -> None:
    """
    Inicializa la base de datos creando todas las tablas.
    """
    from . import models  # Importar aquí para evitar importaciones circulares
    
    print(f"Inicializando base de datos en: {SQLALCHEMY_DATABASE_URL}")
    try:
        Base.metadata.create_all(bind=engine)
        print("Base de datos inicializada correctamente")
    except Exception as e:
        print(f"Error al inicializar la base de datos: {e}")
        raise

def get_db_session() -> Session:
    """
    Obtiene una sesión de base de datos para usar en scripts.
    
    Uso:
    ```python
    with get_db_session() as db:
        # Usar db...
    ```
    """
    return SessionLocal()
