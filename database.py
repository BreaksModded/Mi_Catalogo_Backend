from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base

import os

# URL de conexión a Supabase
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("La variable de entorno DATABASE_URL no está configurada en las variables de entorno del sistema")

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
