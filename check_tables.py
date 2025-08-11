from sqlalchemy import create_engine, text
from database import DATABASE_URL

def check_usuario_media_table():
    """
    Verificar la estructura de la tabla usuario_media
    """
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        # Verificar si la tabla existe
        result = conn.execute(text("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = 'usuario_media'
            );
        """))
        table_exists = result.fetchone()[0]
        
        if not table_exists:
            print("❌ La tabla usuario_media no existe")
            print("Creando tabla usuario_media...")
            
            # Crear la tabla usuario_media
            conn.execute(text("""
                CREATE TABLE usuario_media (
                    id SERIAL PRIMARY KEY,
                    usuario_id INTEGER NOT NULL REFERENCES usuario(id) ON DELETE CASCADE,
                    media_id INTEGER NOT NULL REFERENCES media(id) ON DELETE CASCADE,
                    nota_personal TEXT,
                    anotacion_personal TEXT,
                    favorito BOOLEAN DEFAULT FALSE,
                    pendiente BOOLEAN DEFAULT FALSE,
                    fecha_creacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    fecha_actualizacion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(usuario_id, media_id)
                );
            """))
            
            # Crear índices
            conn.execute(text("""
                CREATE INDEX idx_usuario_media_usuario ON usuario_media(usuario_id);
                CREATE INDEX idx_usuario_media_media ON usuario_media(media_id);
                CREATE INDEX idx_usuario_media_favorito ON usuario_media(usuario_id, favorito);
                CREATE INDEX idx_usuario_media_pendiente ON usuario_media(usuario_id, pendiente);
            """))
            
            conn.commit()
            print("✓ Tabla usuario_media creada con índices")
        else:
            print("✓ La tabla usuario_media existe")
            
            # Mostrar estructura
            result = conn.execute(text("""
                SELECT column_name, data_type, is_nullable, column_default 
                FROM information_schema.columns 
                WHERE table_name = 'usuario_media'
                ORDER BY ordinal_position;
            """))
            
            columns = result.fetchall()
            print("\nEstructura de usuario_media:")
            for col in columns:
                print(f"  - {col[0]} ({col[1]}) {'NULL' if col[2] == 'YES' else 'NOT NULL'} {col[3] or ''}")
            
            # Contar registros
            result = conn.execute(text("SELECT COUNT(*) FROM usuario_media;"))
            count = result.fetchone()[0]
            print(f"\nRegistros en usuario_media: {count}")

if __name__ == "__main__":
    check_usuario_media_table()
