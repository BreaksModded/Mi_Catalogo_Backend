"""
Script para eliminar la columna duplicada 'estado' de la tabla media
Mantiene solo la columna 'status' que contiene la misma información
"""

import os
from sqlalchemy import create_engine, text
from database import DATABASE_URL

def migrate_remove_estado_column():
    """
    Elimina directamente la columna 'estado' de la tabla media 
    ya que es duplicada con 'status' y vamos a usar solo 'status'
    """
    engine = create_engine(DATABASE_URL)
    
    try:
        with engine.connect() as connection:
            # Iniciar transacción
            transaction = connection.begin()
            
            try:
                print("🔄 Iniciando migración: Eliminando columna 'estado' duplicada...")
                
                # Mostrar información antes de la eliminación
                result = connection.execute(text("""
                    SELECT COUNT(*) as total
                    FROM media 
                    WHERE estado IS NOT NULL
                """))
                
                total = result.fetchone()[0]
                print(f"📊 Registros con datos en 'estado': {total}")
                print("💡 Estos datos se perderán, pero están duplicados en 'status'")
                
                # Eliminar la columna estado directamente
                print("🗑️  Eliminando columna 'estado'...")
                connection.execute(text("ALTER TABLE media DROP COLUMN estado"))
                
                # Confirmar transacción
                transaction.commit()
                print("✅ Migración completada exitosamente")
                print("✅ Columna 'estado' eliminada de la tabla media")
                print("💡 Ahora se usa únicamente el campo 'status'")
                
                return True
                
            except Exception as e:
                # Rollback en caso de error
                transaction.rollback()
                print(f"❌ Error durante la migración: {e}")
                return False
                
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return False

def verify_migration():
    """
    Verifica que la migración se haya ejecutado correctamente
    """
    engine = create_engine(DATABASE_URL)
    
    try:
        with engine.connect() as connection:
            # Verificar que la columna estado ya no exista
            result = connection.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'media' 
                AND column_name = 'estado'
            """))
            
            if result.fetchone() is None:
                print("✅ Verificación exitosa: Columna 'estado' eliminada correctamente")
                
                # Verificar que la columna status sigue existiendo
                result = connection.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'media' 
                    AND column_name = 'status'
                """))
                
                if result.fetchone():
                    print("✅ Columna 'status' existe y funcionando correctamente")
                    return True
                else:
                    print("❌ Error: Columna 'status' no encontrada")
                    return False
            else:
                print("❌ Error: Columna 'estado' todavía existe")
                return False
                
    except Exception as e:
        print(f"❌ Error en verificación: {e}")
        return False

if __name__ == "__main__":
    print("🚀 MIGRACIÓN: Eliminar columna 'estado' duplicada")
    print("=" * 50)
    
    # Ejecutar migración
    success = migrate_remove_estado_column()
    
    if success:
        # Verificar migración
        verify_migration()
        print("\n🎉 Migración completada con éxito")
        print("💡 La aplicación ahora usa únicamente el campo 'status'")
    else:
        print("\n❌ Migración falló")
        print("💡 Revisa los errores y ejecuta nuevamente")
