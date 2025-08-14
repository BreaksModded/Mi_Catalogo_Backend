from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTable
from sqlalchemy import String, Integer, Boolean, DateTime, Date, JSON
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, date
from typing import Optional, Dict, Any
from database import Base

class User(SQLAlchemyBaseUserTable[int], Base):
    __tablename__ = "usuario"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(length=255), unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String(length=50), unique=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(length=255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Información personal
    nombre: Mapped[Optional[str]] = mapped_column(String(length=100), nullable=True)
    apellidos: Mapped[Optional[str]] = mapped_column(String(length=150), nullable=True)
    fecha_nacimiento: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    pais: Mapped[Optional[str]] = mapped_column(String(length=100), nullable=True)
    idioma_preferido: Mapped[str] = mapped_column(String(length=10), default='es', nullable=False)
    
    # Preferencias de entretenimiento
    generos_favoritos: Mapped[Optional[str]] = mapped_column(String(length=500), nullable=True)  # JSON string
    plataformas_streaming: Mapped[Optional[str]] = mapped_column(String(length=500), nullable=True)  # JSON string
    tipo_contenido_preferido: Mapped[Optional[str]] = mapped_column(String(length=50), nullable=True)  # películas, series, ambos
    
    # Configuración de privacidad
    compartir_estadisticas: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    perfil_publico: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Metadatos
    fecha_registro: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    ultima_actividad: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    origen_registro: Mapped[Optional[str]] = mapped_column(String(length=50), nullable=True)  # web, móvil, etc.
    
    # Avatar/imagen de perfil
    avatar_url: Mapped[Optional[str]] = mapped_column(String(length=500), nullable=True)
