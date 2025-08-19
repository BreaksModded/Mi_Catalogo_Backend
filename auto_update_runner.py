#!/usr/bin/env python3
"""
Script de actualización automática de medias
Se puede ejecutar como tarea programada para mantener actualizada la información

Uso:
    python auto_update_runner.py --limit 50 --type serie
    python auto_update_runner.py --stats-only
"""

import argparse
import sys
import os

# Añadir el directorio actual al path para importar módulos
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from auto_update_service import get_auto_update_service
import database


def main():
    parser = argparse.ArgumentParser(description='Actualización automática de medias desde TMDb')
    parser.add_argument('--limit', type=int, default=20, help='Máximo número de medias a actualizar (default: 20)')
    parser.add_argument('--type', choices=['película', 'serie'], help='Filtrar por tipo de media')
    parser.add_argument('--stats-only', action='store_true', help='Solo mostrar estadísticas sin actualizar')
    parser.add_argument('--force-id', type=int, help='Forzar actualización de un TMDb ID específico')
    
    args = parser.parse_args()
    
    # Obtener sesión de base de datos
    db = next(database.get_db())
    update_service = get_auto_update_service()
    
    try:
        if args.stats_only:
            # Solo mostrar estadísticas
            print("📊 ESTADÍSTICAS DE ACTUALIZACIÓN AUTOMÁTICA")
            print("=" * 50)
            
            stats = update_service.get_update_stats(db)
            
            print(f"📚 Total medias con TMDb ID: {stats['total_medias_with_tmdb']}")
            print(f"🔄 Con actualización automática habilitada: {stats['auto_update_enabled']}")
            print(f"📝 Marcados para actualización: {stats['marked_for_update']}")
            print(f"🆕 Nunca actualizados: {stats['never_updated']}")
            print(f"⏰ Necesitan actualización por cronograma: {stats['need_update_by_schedule']}")
            
        elif args.force_id:
            # Actualización forzada de un media específico
            print(f"🎯 ACTUALIZACIÓN FORZADA DE TMDb ID: {args.force_id}")
            print("=" * 50)
            
            # Buscar y marcar el media
            import models
            media = db.query(models.Media).filter(models.Media.tmdb_id == args.force_id).first()
            
            if not media:
                print(f"❌ No se encontró media con TMDb ID {args.force_id}")
                return
                
            print(f"📺 Actualizando: {media.titulo} ({media.tipo})")
            
            success = update_service.update_media_from_tmdb(db, media)
            
            if success:
                print("✅ Actualización completada con éxito")
            else:
                print("❌ Error en la actualización")
                
        else:
            # Actualización automática normal
            print("🚀 EJECUTANDO ACTUALIZACIÓN AUTOMÁTICA")
            print("=" * 50)
            print(f"📋 Límite: {args.limit} medias")
            if args.type:
                print(f"🎭 Tipo: {args.type}")
            print()
            
            results = update_service.update_medias_batch(
                db, 
                limit=args.limit, 
                media_type=args.type
            )
            
            print()
            print("📊 RESUMEN DE ACTUALIZACIÓN")
            print("=" * 30)
            print(f"✅ Actualizados: {results['updated']}")
            print(f"❌ Fallos: {results['failed']}")
            print(f"📄 Total procesados: {results['total']}")
            
            if results['total'] == 0:
                print("ℹ️ No había medias que necesitaran actualización")
            else:
                success_rate = (results['updated'] / results['total']) * 100
                print(f"📈 Tasa de éxito: {success_rate:.1f}%")
                
    except Exception as e:
        print(f"❌ Error durante la ejecución: {str(e)}")
        return 1
        
    finally:
        db.close()
    
    return 0


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
