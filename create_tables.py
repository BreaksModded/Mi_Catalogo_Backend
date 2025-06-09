# backend/create_tables.py
import os
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, func, ForeignKey, Table
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

# Configuración de la base de datos
# URL de conexión a Supabase
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres.xxxxxxxxxxxxxxxx:xxxxxxxxxxxxxxxx@aws-0-eu-central-1.pooler.supabase.com:5432/postgres"
)

# Reemplaza la URL anterior con tu URL real de conexión a Supabase
engine = create_engine(DATABASE_URL)
Base = declarative_base()

# Tabla de usuarios
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# Tabla de medios (simplificada)
class Media(Base):
    __tablename__ = "media"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    media_type = Column(String)  # 'movie', 'tv_show', etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

# Tabla para la relación usuario-medio (para marcar favoritos, etc.)
class UserMedia(Base):
    __tablename__ = "user_media"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    media_id = Column(Integer, ForeignKey("media.id", ondelete="CASCADE"))
    is_favorite = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relaciones
    user = relationship("User", back_populates="user_medias")
    media = relationship("Media")

# Actualizar la relación en User
User.user_medias = relationship("UserMedia", back_populates="user")

def create_tables():
    print("Conectando a la base de datos...")
    print(f"URL: {DATABASE_URL[:50]}...")  # Muestra solo el inicio por seguridad

    print("\nCreando tablas...")
    Base.metadata.create_all(bind=engine)

    print("\n¡Tablas creadas exitosamente!")
    print("Tablas creadas:")
    for table in Base.metadata.tables:
        print(f"- {table}")

if __name__ == "__main__":
    create_tables()
