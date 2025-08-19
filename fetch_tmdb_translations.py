#!/usr/bin/env python3
"""
Script para obtener traducciones completas de TMDb API
- Obtiene traducciones de título y sinopsis
- Idiomas: inglés (en), alemán (de), portugués (pt), francés (fr)
- Excluye español (ya existe en tabla media)
- Actualiza registros existentes y crea nuevos
"""

import sys
import os
import requests
import time
from sqlalchemy import create_engine, text
from datetime import datetime

# Importar configuración local
from config import get_tmdb_auth_headers, TMDB_API_KEY, TMDB_BEARER, TMDB_BASE_URL
from database import DATABASE_URL

# Verificar configuración TMDb
auth_headers = get_tmdb_auth_headers()
if not auth_headers and not TMDB_API_KEY:
    print("❌ ERROR: No hay configuración de TMDb disponible")
    print("   Configura TMDB_BEARER o TMDB_API_KEY en las variables de entorno")
    sys.exit(1)

# Configuración de idiomas
# Configuración de idiomas
TARGET_LANGUAGES = {
    'en': 'Inglés',
    'de': 'Alemán', 
    'pt': 'Portugués',
    'fr': 'Francés'
}

def convert_media_type_to_tmdb(tipo_espanol):
    """Convierte el tipo de media del español al formato TMDb"""
    if tipo_espanol.lower() == 'película':
        return 'movie'
    elif tipo_espanol.lower() == 'serie':
        return 'tv'
    else:
        return tipo_espanol.lower()  # fallback

class TMDbTranslationFetcher:
    def __init__(self):
        self.base_url = TMDB_BASE_URL
        self.session = requests.Session()
        self.rate_limit_delay = 0.25  # 4 requests per second
        
        # Configurar autenticación
        self.auth_headers = get_tmdb_auth_headers()
        if self.auth_headers:
            self.session.headers.update(self.auth_headers)
        elif TMDB_API_KEY:
            self.api_key = TMDB_API_KEY
        else:
            raise ValueError("No hay configuración de TMDb disponible")
        
    def _make_request(self, endpoint, params=None):
        """Hace una petición a TMDb con manejo de rate limiting"""
        if params is None:
            params = {}
            
        # Si usamos API key en lugar de Bearer token
        if not self.auth_headers and hasattr(self, 'api_key'):
            params['api_key'] = self.api_key
            
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = self.session.get(url, params=params)
            
            if response.status_code == 429:
                print(f"   ⚠️  Rate limit alcanzado, esperando...")
                time.sleep(1)
                response = self.session.get(url, params=params)
            
            time.sleep(self.rate_limit_delay)
            return response
            
        except Exception as e:
            print(f"   ❌ Error en petición: {str(e)}")
            return None
    def get_movie_translations(self, tmdb_id):
        """Obtiene traducciones de una película"""
        try:
            translations = {}
            
            for lang_code in TARGET_LANGUAGES.keys():
                response = self._make_request(f"movie/{tmdb_id}", {'language': lang_code})
                
                if response and response.status_code == 200:
                    data = response.json()
                    translations[lang_code] = {
                        'title': data.get('title', ''),
                        'overview': data.get('overview', '')
                    }
                else:
                    print(f"   ⚠️  No se pudo obtener traducción en {lang_code}")
            
            return translations
            
        except Exception as e:
            print(f"   ❌ Error obteniendo traducciones para movie {tmdb_id}: {str(e)}")
            return {}
    
    def get_tv_translations(self, tmdb_id):
        """Obtiene traducciones de una serie de TV"""
        try:
            translations = {}
            
            for lang_code in TARGET_LANGUAGES.keys():
                response = self._make_request(f"tv/{tmdb_id}", {'language': lang_code})
                
                if response and response.status_code == 200:
                    data = response.json()
                    translations[lang_code] = {
                        'title': data.get('name', ''),  # TV usa 'name' en lugar de 'title'
                        'overview': data.get('overview', '')
                    }
                else:
                    print(f"   ⚠️  No se pudo obtener traducción en {lang_code}")
            
            return translations
            
        except Exception as e:
            print(f"   ❌ Error obteniendo traducciones para TV {tmdb_id}: {str(e)}")
            return {}

def analyze_existing_translations():
    """Analiza las traducciones existentes para identificar problemas"""
    engine = create_engine(DATABASE_URL)
    
    print("🔍 ANALIZANDO TRADUCCIONES EXISTENTES")
    print("=" * 60)
    
    with engine.connect() as conn:
        analysis = {}
        
        for lang_code, lang_name in TARGET_LANGUAGES.items():
            print(f"\n📊 Analizando {lang_name} ({lang_code}):")
            
            # Total traducciones
            result = conn.execute(text("""
                SELECT COUNT(*) FROM content_translations WHERE language_code = :lang
            """), {'lang': lang_code})
            total = result.scalar()
            
            # Sin título
            result = conn.execute(text("""
                SELECT COUNT(*) FROM content_translations 
                WHERE language_code = :lang AND (title IS NULL OR title = '')
            """), {'lang': lang_code})
            without_title = result.scalar()
            
            # Sin sinopsis
            result = conn.execute(text("""
                SELECT COUNT(*) FROM content_translations 
                WHERE language_code = :lang AND (synopsis IS NULL OR synopsis = '')
            """), {'lang': lang_code})
            without_synopsis = result.scalar()
            
            # Títulos muy cortos (posiblemente incorrectos)
            result = conn.execute(text("""
                SELECT COUNT(*) FROM content_translations 
                WHERE language_code = :lang AND LENGTH(title) < 3
            """), {'lang': lang_code})
            short_titles = result.scalar()
            
            analysis[lang_code] = {
                'total': total,
                'without_title': without_title,
                'without_synopsis': without_synopsis,
                'short_titles': short_titles,
                'needs_review': without_title + without_synopsis + short_titles
            }
            
            print(f"   Total: {total}")
            print(f"   Sin título: {without_title}")
            print(f"   Sin sinopsis: {without_synopsis}")
            print(f"   Títulos cortos: {short_titles}")
            print(f"   Necesitan revisión: {analysis[lang_code]['needs_review']}")
        
        return analysis

def fetch_all_translations():
    """Obtiene y actualiza traducciones completas de TMDb"""
    engine = create_engine(DATABASE_URL)
    fetcher = TMDbTranslationFetcher()
    
    print("🌐 OBTENIENDO Y ACTUALIZANDO TRADUCCIONES COMPLETAS DE TMDb")
    print("=" * 70)
    print(f"Idiomas objetivo: {', '.join([f'{code} ({name})' for code, name in TARGET_LANGUAGES.items()])}")
    
    # 1. Analizar estado actual
    analysis = analyze_existing_translations()
    
    with engine.connect() as conn:
        # 2. Obtener toda la media disponible
        print("\n📊 OBTENIENDO MEDIA DISPONIBLE:")
        
        media_query = """
        SELECT 
            m.id,
            m.titulo,
            m.tmdb_id,
            m.tipo
        FROM media m
        WHERE m.tmdb_id IS NOT NULL
        ORDER BY m.id
        """
        
        result = conn.execute(text(media_query))
        all_media = result.fetchall()
        media_dict = {media[0]: media for media in all_media}
        
        print(f"   Total media con TMDb ID: {len(all_media)}")
        
        # 3. Calcular trabajo total (nuevas + actualizaciones)
        total_work = 0
        work_plan = {}
        
        for lang_code, lang_name in TARGET_LANGUAGES.items():
            print(f"\n📋 Planificando trabajo para {lang_name} ({lang_code}):")
            
            # Obtener traducciones existentes que necesitan revisión
            result = conn.execute(text("""
                SELECT ct.media_id, ct.title, ct.synopsis, ct.id
                FROM content_translations ct
                WHERE ct.language_code = :lang
                AND (
                    ct.title IS NULL OR ct.title = '' OR LENGTH(ct.title) < 3 OR
                    ct.synopsis IS NULL OR ct.synopsis = ''
                )
            """), {'lang': lang_code})
            
            existing_to_update = result.fetchall()
            
            # Media sin traducciones
            result = conn.execute(text("""
                SELECT m.id
                FROM media m
                WHERE m.tmdb_id IS NOT NULL
                AND m.id NOT IN (
                    SELECT ct.media_id 
                    FROM content_translations ct 
                    WHERE ct.language_code = :lang
                )
            """), {'lang': lang_code})
            
            missing_media_ids = [row[0] for row in result]
            missing_media = [media_dict[mid] for mid in missing_media_ids if mid in media_dict]
            
            work_plan[lang_code] = {
                'existing_to_update': existing_to_update,
                'missing_media': missing_media,
                'total_items': len(existing_to_update) + len(missing_media)
            }
            
            print(f"   Traducciones existentes a actualizar: {len(existing_to_update)}")
            print(f"   Media sin traducir: {len(missing_media)}")
            print(f"   Total elementos a procesar: {work_plan[lang_code]['total_items']}")
            
            total_work += work_plan[lang_code]['total_items']
        
        print(f"\n⚠️  RESUMEN DEL TRABAJO:")
        print(f"   Total elementos a procesar: {total_work}")
        print(f"   Tiempo estimado: ~{total_work * 0.3 / 60:.1f} minutos")
        print(f"   Requests a TMDb: ~{total_work}")
        
        confirm = input("\n¿Continuar con la obtención y actualización de traducciones? (si/no): ").lower().strip()
        if confirm not in ['si', 's', 'yes', 'y']:
            print("❌ Operación cancelada")
            return
        
        # 4. Procesar cada idioma
        for lang_code, lang_name in TARGET_LANGUAGES.items():
            work_data = work_plan[lang_code]
            
            if work_data['total_items'] == 0:
                print(f"\n✅ {lang_name} ({lang_code}): No hay trabajo pendiente")
                continue
                
            print(f"\n🔄 Procesando {lang_name} ({lang_code}): {work_data['total_items']} elementos")
            
            success_count = 0
            error_count = 0
            updated_count = 0
            created_count = 0
            
            # Procesar traducciones existentes que necesitan actualización
            for i, existing in enumerate(work_data['existing_to_update'], 1):
                trans_media_id, current_title, current_synopsis, trans_id = existing
                
                if trans_media_id not in media_dict:
                    continue
                    
                media_data = media_dict[trans_media_id]
                media_id, titulo, tmdb_id, tipo = media_data
                
                print(f"   [UPD {i}/{len(work_data['existing_to_update'])}] Actualizando: {titulo}")
                
                # Obtener traducciones según el tipo
                if tipo.lower() == 'película':
                    translations = fetcher.get_movie_translations(tmdb_id)
                else:  # serie
                    translations = fetcher.get_tv_translations(tmdb_id)
                
                if lang_code in translations:
                    translation_data = translations[lang_code]
                    new_title = translation_data['title']
                    new_synopsis = translation_data['overview']
                    
                    # Decidir qué actualizar
                    should_update = False
                    updates = {}
                    
                    if not current_title or len(current_title) < 3:
                        if new_title:
                            updates['title'] = new_title
                            should_update = True
                    
                    if not current_synopsis:
                        if new_synopsis:
                            updates['synopsis'] = new_synopsis
                            should_update = True
                    
                    if should_update:
                        try:
                            update_parts = []
                            update_values = {'trans_id': trans_id}
                            
                            if 'title' in updates:
                                update_parts.append("title = :title")
                                update_values['title'] = updates['title']
                                
                            if 'synopsis' in updates:
                                update_parts.append("synopsis = :synopsis")
                                update_values['synopsis'] = updates['synopsis']
                            
                            update_query = f"""
                                UPDATE content_translations 
                                SET {', '.join(update_parts)}
                                WHERE id = :trans_id
                            """
                            
                            conn.execute(text(update_query), update_values)
                            conn.commit()
                            
                            updated_count += 1
                            success_count += 1
                            
                            update_details = []
                            if 'title' in updates:
                                update_details.append("título")
                            if 'synopsis' in updates:
                                update_details.append("sinopsis")
                            
                            print(f"     ✅ Actualizado: {', '.join(update_details)}")
                            
                        except Exception as e:
                            print(f"     ❌ Error actualizando: {str(e)}")
                            error_count += 1
                    else:
                        print(f"     ⚠️  No necesita actualización")
                else:
                    print(f"     ❌ No se pudo obtener traducción de TMDb")
                    error_count += 1
            
            # Procesar media sin traducciones
            for i, media in enumerate(work_data['missing_media'], 1):
                media_id, titulo, tmdb_id, tipo = media
                
                print(f"   [NEW {i}/{len(work_data['missing_media'])}] Creando: {titulo}")
                
                # Obtener traducciones según el tipo
                if tipo.lower() == 'película':
                    translations = fetcher.get_movie_translations(tmdb_id)
                else:  # serie
                    translations = fetcher.get_tv_translations(tmdb_id)
                
                if lang_code in translations:
                    translation_data = translations[lang_code]
                    
                    if translation_data['title']:
                        try:
                            conn.execute(text("""
                                INSERT INTO content_translations 
                                (media_id, language_code, title, synopsis, tmdb_id, media_type)
                                VALUES (:media_id, :lang, :title, :synopsis, :tmdb_id, :media_type)
                            """), {
                                'media_id': media_id,
                                'lang': lang_code,
                                'title': translation_data['title'],
                                'synopsis': translation_data['overview'] or None,
                                'tmdb_id': tmdb_id,
                                'media_type': convert_media_type_to_tmdb(tipo)
                            })
                            
                            conn.commit()
                            created_count += 1
                            success_count += 1
                            
                            print(f"     ✅ Creado con título y sinopsis")
                            
                        except Exception as e:
                            print(f"     ❌ Error creando: {str(e)}")
                            error_count += 1
                    else:
                        print(f"     ⚠️  Sin título disponible en TMDb")
                else:
                    print(f"     ❌ No se pudo obtener traducción de TMDb")
                    error_count += 1
                
                # Progress update cada 10 elementos
                if i % 10 == 0:
                    print(f"     Progreso nuevos: {i}/{len(work_data['missing_media'])}")
            
            print(f"   ✅ {lang_name} completado:")
            print(f"     Actualizados: {updated_count}")
            print(f"     Creados: {created_count}")
            print(f"     Errores: {error_count}")
        
        # 5. Estadísticas finales
        print(f"\n📊 ESTADÍSTICAS FINALES:")
        for lang_code, lang_name in TARGET_LANGUAGES.items():
            result = conn.execute(text("""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN title IS NOT NULL AND title != '' THEN 1 END) as with_title,
                    COUNT(CASE WHEN synopsis IS NOT NULL AND synopsis != '' THEN 1 END) as with_synopsis
                FROM content_translations 
                WHERE language_code = :lang
            """), {'lang': lang_code})
            
            stats = result.fetchone()
            total, with_title, with_synopsis = stats
            
            print(f"   {lang_name} ({lang_code}):")
            print(f"     Total: {total}")
            print(f"     Con título: {with_title} ({with_title/total*100:.1f}%)")
            print(f"     Con sinopsis: {with_synopsis} ({with_synopsis/total*100:.1f}%)")
        
        # Total general
        result = conn.execute(text("SELECT COUNT(*) FROM content_translations"))
        total = result.scalar()
        print(f"\n   📈 Total general: {total} traducciones en content_translations")

def show_completion_summary():
    """Muestra resumen de completitud"""
    print("\n💡 RESUMEN DE COMPLETITUD:")
    print("=" * 60)
    print("✅ Traducciones existentes revisadas y actualizadas")
    print("✅ Títulos faltantes completados desde TMDb")
    print("✅ Sinopsis faltantes añadidas desde TMDb")
    print("✅ Nuevas traducciones creadas para media sin traducir")
    print("✅ Base de datos optimizada sin columnas innecesarias")
    print("✅ Búsqueda multiidioma implementada")
    print("\n🚀 PRÓXIMOS PASOS:")
    print("1. Probar endpoints de búsqueda multiidioma")
    print("2. Actualizar frontend para aprovechar traducciones completas")
    print("3. Configurar actualizaciones periódicas de traducciones")
    print("4. Implementar cache de traducciones para mejor rendimiento")
    
def show_analysis_only():
    """Solo muestra el análisis sin hacer cambios"""
    print("🔍 MODO ANÁLISIS - Solo revisando estado actual")
    print("=" * 60)
    
    analysis = analyze_existing_translations()
    
    total_issues = sum(lang_data['needs_review'] for lang_data in analysis.values())
    
    print(f"\n📊 RESUMEN GENERAL:")
    print(f"   Total traducciones con problemas: {total_issues}")
    
    if total_issues > 0:
        print("\n💡 RECOMENDACIONES:")
        print("   Ejecuta el script completo para:")
        print("   - Completar títulos faltantes")
        print("   - Añadir sinopsis faltantes") 
        print("   - Corregir títulos muy cortos")
        print("   - Crear traducciones para media sin traducir")
    else:
        print("\n✅ Todas las traducciones están en buen estado!")
    
    return analysis

if __name__ == "__main__":
    print("🌐 FETCHER Y ACTUALIZADOR DE TRADUCCIONES TMDb")
    print("=" * 70)
    print("Este script puede:")
    print("1. Analizar el estado actual de las traducciones")
    print("2. Actualizar traducciones existentes incompletas")
    print("3. Crear nuevas traducciones para media sin traducir")
    print("4. Completar títulos y sinopsis faltantes")
    
    print("\nOpciones:")
    print("1. Solo análisis (no hace cambios)")
    print("2. Análisis completo + actualización")
    
    choice = input("\nSelecciona una opción (1 o 2): ").strip()
    
    try:
        if choice == "1":
            show_analysis_only()
        elif choice == "2":
            fetch_all_translations()
            show_completion_summary()
        else:
            print("❌ Opción no válida. Usa 1 o 2.")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\n❌ Operación interrumpida por el usuario")
    except Exception as e:
        print(f"\n💥 Error inesperado: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
