from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # Configuración de la base de datos
    DATABASE_URL: str = "sqlite:///./sql_app.db"
    
    # Configuración de autenticación
    SECRET_KEY: str = "tu_clave_secreta_muy_segura_y_unica"  # Cambiar en producción
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Configuración de CORS
    FRONTEND_URL: str = "http://localhost:3000"
    
    # Configuración de entorno
    ENV: str = "development"
    DEBUG: bool = True
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Instancia de configuración
settings = Settings()
