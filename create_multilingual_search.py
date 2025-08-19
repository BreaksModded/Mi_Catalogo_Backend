#!/usr/bin/env python3
"""
Endpoint de búsqueda multiidioma avanzada
Utiliza la estructura optimizada:
- media.titulo (español)
- media.original_title (título original)  
- content_translations.title (otros idiomas)
"""

import sys
import os
from sqlalchemy import create_engine, text, func, or_
from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Query
from typing import Optional, List
import json

# Cargar variables de entorno
load_dotenv()

# Configurar conexión a la base de datos
DATABASE_URL = os.getenv('DATABASE_URL')

def create_multilingual_search_endpoint():
    """Crea el endpoint de búsqueda multiidioma"""
    
    endpoint_code = '''
# Añadir a main.py

@app.get("/search/multilingual")
async def search_multilingual(
    q: str = Query(..., description="Término de búsqueda"),
    limit: int = Query(20, ge=1, le=100, description="Límite de resultados"),
    include_language_info: bool = Query(False, description="Incluir información del idioma encontrado"),
    db: Session = Depends(get_db)
):
    """
    Búsqueda multiidioma avanzada que busca en:
    1. Títulos en español (media.titulo)
    2. Títulos originales (media.original_title) 
    3. Traducciones en otros idiomas (content_translations.title)
    
    Prioriza resultados en español, luego originales, luego otros idiomas.
    """
    
    search_pattern = f"%{q.lower()}%"
    
    # Query optimizada con UNION para búsqueda multiidioma
    multilingual_query = text("""
        WITH multilingual_search AS (
            -- Búsqueda en títulos españoles (tabla media)
            SELECT DISTINCT
                m.id,
                m.titulo,
                m.original_title,
                m.anio,
                m.tipo,
                m.genero,
                m.director,
                m.elenco,
                m.imagen,
                m.status,  -- Cambiado de estado a status
                m.nota_imdb,
                'es' as idioma_encontrado,
                m.titulo as titulo_encontrado,
                1 as prioridad
            FROM media m
            WHERE LOWER(m.titulo) LIKE :search_pattern
            
            UNION
            
            -- Búsqueda en títulos originales (tabla media)
            SELECT DISTINCT
                m.id,
                m.titulo,
                m.original_title,
                m.anio,
                m.tipo,
                m.genero,
                m.director,
                m.elenco,
                m.imagen,
                m.status,  -- Cambiado de estado a status
                m.nota_imdb,
                'original' as idioma_encontrado,
                m.original_title as titulo_encontrado,
                2 as prioridad
            FROM media m
            WHERE LOWER(m.original_title) LIKE :search_pattern
            AND m.original_title IS NOT NULL
            
            UNION
            
            -- Búsqueda en traducciones (content_translations)
            SELECT DISTINCT
                m.id,
                m.titulo,
                m.original_title,
                m.anio,
                m.tipo,
                m.genero,
                m.director,
                m.elenco,
                m.imagen,
                m.status,  -- Cambiado de estado a status
                m.nota_imdb,
                ct.language_code as idioma_encontrado,
                ct.title as titulo_encontrado,
                3 as prioridad
            FROM media m
            INNER JOIN content_translations ct ON m.id = ct.media_id
            WHERE LOWER(ct.title) LIKE :search_pattern
            AND ct.language_code NOT IN ('es')  -- Evitar duplicar español
        )
        SELECT * FROM multilingual_search
        ORDER BY prioridad, titulo
        LIMIT :limit_val
    """)
    
    # Ejecutar búsqueda
    result = db.execute(multilingual_query, {
        'search_pattern': search_pattern,
        'limit_val': limit
    })
    
    # Procesar resultados
    movies = []
    for row in result:
        movie_data = {
            "id": row[0],
            "titulo": row[1],
            "original_title": row[2],
            "anio": row[3],
            "tipo": row[4],
            "genero": row[5],
            "director": row[6],
            "elenco": row[7],
            "imagen": row[8],
            "status": row[9],  # Cambiado de estado a status
            "nota_imdb": row[10]
        }
        
        # Añadir información del idioma si se solicita
        if include_language_info:
            movie_data["search_info"] = {
                "idioma_encontrado": row[11],
                "titulo_encontrado": row[12],
                "prioridad": row[13]
            }
        
        movies.append(movie_data)
    
    return {
        "query": q,
        "total_found": len(movies),
        "results": movies,
        "search_info": {
            "languages_searched": ["es", "original", "en", "pt", "fr", "de", "it"],
            "priority_order": ["español", "original", "otros_idiomas"]
        }
    }

@app.get("/search/languages")
async def get_available_languages(db: Session = Depends(get_db)):
    """
    Obtiene los idiomas disponibles para búsqueda
    """
    
    # Idiomas en content_translations
    translation_languages = db.execute(text("""
        SELECT language_code, COUNT(*) as count 
        FROM content_translations 
        GROUP BY language_code 
        ORDER BY count DESC
    """)).fetchall()
    
    # Estadísticas de media
    media_stats = db.execute(text("""
        SELECT 
            COUNT(*) as total_media,
            COUNT(original_title) as with_original_title
        FROM media
    """)).fetchone()
    
    return {
        "available_languages": {
            "es": {
                "name": "Español",
                "source": "media.titulo",
                "count": media_stats[0]
            },
            "original": {
                "name": "Título Original",
                "source": "media.original_title", 
                "count": media_stats[1]
            }
        },
        "translation_languages": [
            {
                "code": row[0],
                "count": row[1],
                "source": "content_translations"
            }
            for row in translation_languages
        ],
        "total_searchable_titles": sum(row[1] for row in translation_languages) + media_stats[0]
    }
'''
    
    return endpoint_code

def test_search_functionality():
    """Prueba la funcionalidad de búsqueda multiidioma"""
    engine = create_engine(DATABASE_URL)
    
    print("🔍 PROBANDO BÚSQUEDA MULTIIDIOMA")
    print("=" * 60)
    
    test_queries = [
        "harry",      # Debería encontrar en español e inglés
        "potter",     # Debería encontrar principalmente en inglés
        "avengers",   # Debería encontrar en original/inglés
        "tintin",     # Debería encontrar en múltiples idiomas
    ]
    
    with engine.connect() as conn:
        for query in test_queries:
            print(f"\n🔍 Búsqueda: '{query}'")
            print("-" * 30)
            
            search_pattern = f"%{query.lower()}%"
            
            # Ejecutar búsqueda de prueba
            test_query = text("""
                SELECT 
                    m.titulo,
                    COALESCE(m.original_title, 'N/A') as original_title,
                    'es' as source,
                    m.titulo as found_title
                FROM media m
                WHERE LOWER(m.titulo) LIKE :pattern
                
                UNION ALL
                
                SELECT 
                    m.titulo,
                    COALESCE(m.original_title, 'N/A') as original_title,
                    'original' as source,
                    m.original_title as found_title
                FROM media m
                WHERE LOWER(m.original_title) LIKE :pattern
                AND m.original_title IS NOT NULL
                
                UNION ALL
                
                SELECT 
                    m.titulo,
                    COALESCE(m.original_title, 'N/A') as original_title,
                    ct.language_code as source,
                    ct.title as found_title
                FROM media m
                INNER JOIN content_translations ct ON m.id = ct.media_id
                WHERE LOWER(ct.title) LIKE :pattern
                
                LIMIT 5
            """)
            
            result = conn.execute(test_query, {'pattern': search_pattern})
            results = result.fetchall()
            
            if results:
                for row in results:
                    print(f"   📽️  {row[0]}")
                    print(f"      Original: {row[1]}")
                    print(f"      Encontrado en: {row[2]} → '{row[3]}'")
                    print()
            else:
                print("   No se encontraron resultados")

if __name__ == "__main__":
    print("🚀 GENERADOR DE ENDPOINT DE BÚSQUEDA MULTIIDIOMA")
    print("=" * 70)
    
    # Generar código del endpoint
    endpoint_code = create_multilingual_search_endpoint()
    
    # Guardar en archivo
    with open("multilingual_search_endpoint.py", "w", encoding="utf-8") as f:
        f.write(endpoint_code)
    
    print("✅ Código del endpoint generado en 'multilingual_search_endpoint.py'")
    
    # Probar funcionalidad
    print("\n" + "=" * 70)
    test_search_functionality()
    
    print("\n💡 PRÓXIMOS PASOS:")
    print("1. Copiar el código generado a main.py")
    print("2. Reiniciar el servidor FastAPI")
    print("3. Probar los endpoints:")
    print("   - GET /search/multilingual?q=harry")
    print("   - GET /search/languages")
    print("4. Actualizar frontend para usar la nueva búsqueda")
