#!/usr/bin/env python3
"""
Migración para aumentar el tamaño del campo plataformas_streaming de 500 a 2000 caracteres
y generos_favoritos de 500 a 1000 caracteres.
"""

import asyncio
import os
import logging
from sqlalchemy import create_engine, text

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Cargar variables de entorno desde .env si está disponible
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

async def migrate_platform_field_size():
    """Aumenta el tamaño de los campos de preferencias de usuario"""
    
    try:
        DATABASE_URL = os.getenv("DATABASE_URL")
        
        if not DATABASE_URL:
            # Fallback a SQLite si no hay DATABASE_URL
            DATABASE_URL = "sqlite:///./test.db"
            logger.info("Usando SQLite como fallback")
        
        logger.info(f"Conectando a la base de datos...")
        
        # Crear engine de SQLAlchemy
        engine = create_engine(DATABASE_URL)
        
        with engine.connect() as conn:
            # Verificar que la tabla usuario existe
            if DATABASE_URL.startswith("sqlite"):
                # Para SQLite, verificar si la tabla existe
                result = conn.execute(text("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='usuario';
                """)).fetchone()
                
                if not result:
                    logger.error("❌ La tabla 'usuario' no existe en la base de datos")
                    return False
                
                logger.info("✅ Conexión a SQLite exitosa")
                
                # Para SQLite, necesitamos recrear la tabla con el nuevo tamaño
                logger.info("SQLite detectado - creando tabla temporal con nuevos tamaños...")
                
                # Crear tabla temporal con la nueva estructura
                conn.execute(text("""
                    CREATE TABLE usuario_temp AS SELECT * FROM usuario;
                """))
                
                # Eliminar tabla original
                conn.execute(text("DROP TABLE usuario;"))
                
                # Crear nueva tabla con la estructura actualizada
                conn.execute(text("""
                    CREATE TABLE usuario (
                        id INTEGER NOT NULL, 
                        email VARCHAR(255) NOT NULL, 
                        username VARCHAR(50) NOT NULL, 
                        hashed_password VARCHAR(255) NOT NULL, 
                        is_active BOOLEAN NOT NULL, 
                        is_superuser BOOLEAN NOT NULL, 
                        is_verified BOOLEAN NOT NULL, 
                        nombre VARCHAR(100), 
                        apellidos VARCHAR(150), 
                        fecha_nacimiento DATE, 
                        pais VARCHAR(100), 
                        idioma_preferido VARCHAR(10) NOT NULL, 
                        generos_favoritos VARCHAR(1000), 
                        plataformas_streaming VARCHAR(2000), 
                        tipo_contenido_preferido VARCHAR(50), 
                        compartir_estadisticas BOOLEAN NOT NULL, 
                        perfil_publico BOOLEAN NOT NULL, 
                        fecha_registro DATETIME NOT NULL, 
                        ultima_actividad DATETIME, 
                        origen_registro VARCHAR(50), 
                        avatar_url VARCHAR(500), 
                        PRIMARY KEY (id), 
                        UNIQUE (email), 
                        UNIQUE (username), 
                        CHECK (is_active IN (0, 1)), 
                        CHECK (is_superuser IN (0, 1)), 
                        CHECK (is_verified IN (0, 1)), 
                        CHECK (compartir_estadisticas IN (0, 1)), 
                        CHECK (perfil_publico IN (0, 1))
                    );
                """))
                
                # Copiar datos de la tabla temporal
                conn.execute(text("""
                    INSERT INTO usuario SELECT * FROM usuario_temp;
                """))
                
                # Eliminar tabla temporal
                conn.execute(text("DROP TABLE usuario_temp;"))
                
                logger.info("✅ Tabla usuario recreada con nuevos tamaños de campo")
                
            else:
                # Para PostgreSQL
                result = conn.execute(text("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'usuario'
                    );
                """)).fetchone()
                
                if not result[0]:
                    logger.error("❌ La tabla 'usuario' no existe en la base de datos")
                    return False
                
                logger.info("✅ Conexión a PostgreSQL exitosa")
                
                # Verificar la estructura actual
                logger.info("Verificando estructura actual de la tabla usuario...")
                
                current_info = conn.execute(text("""
                    SELECT column_name, data_type, character_maximum_length 
                    FROM information_schema.columns 
                    WHERE table_name = 'usuario' 
                    AND column_name IN ('plataformas_streaming', 'generos_favoritos')
                    ORDER BY column_name;
                """)).fetchall()
                
                logger.info("Estructura actual:")
                for row in current_info:
                    logger.info(f"  {row[0]}: {row[1]}({row[2]})")
                
                # Aplicar las migraciones
                logger.info("Aplicando migración para plataformas_streaming...")
                conn.execute(text("""
                    ALTER TABLE usuario 
                    ALTER COLUMN plataformas_streaming TYPE VARCHAR(2000);
                """))
                logger.info("✅ Campo plataformas_streaming actualizado a VARCHAR(2000)")
                
                logger.info("Aplicando migración para generos_favoritos...")
                conn.execute(text("""
                    ALTER TABLE usuario 
                    ALTER COLUMN generos_favoritos TYPE VARCHAR(1000);
                """))
                logger.info("✅ Campo generos_favoritos actualizado a VARCHAR(1000)")
                
                # Verificar los cambios
                logger.info("Verificando cambios aplicados...")
                
                updated_info = conn.execute(text("""
                    SELECT column_name, data_type, character_maximum_length 
                    FROM information_schema.columns 
                    WHERE table_name = 'usuario' 
                    AND column_name IN ('plataformas_streaming', 'generos_favoritos')
                    ORDER BY column_name;
                """)).fetchall()
                
                logger.info("Estructura actualizada:")
                for row in updated_info:
                    logger.info(f"  {row[0]}: {row[1]}({row[2]})")
            
            conn.commit()
            logger.info("🎉 Migración completada exitosamente!")
            
    except Exception as e:
        logger.error(f"❌ Error durante la migración: {e}")
        raise

if __name__ == "__main__":
    async def main():
        logger.info("🚀 Iniciando migración de campos de usuario...")
        await migrate_platform_field_size()
        
    asyncio.run(main())
