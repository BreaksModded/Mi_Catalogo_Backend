#!/usr/bin/env python3
"""
Servicio para manejar traducciones automáticas al crear media
"""

import requests
import time
from sqlalchemy import text
from config import get_tmdb_auth_headers, TMDB_API_KEY, TMDB_BASE_URL, REQUEST_TIMEOUT

# Configuración de idiomas objetivo (NO incluye español porque ya está en la tabla media)
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
        return tipo_espanol.lower()

def fetch_spanish_data_from_tmdb(tmdb_id, media_type):
    """Obtiene datos en español desde TMDb con campos de caché"""
    try:
        headers = get_tmdb_auth_headers()
        params = {'language': 'es-ES'}
        
        if not headers and TMDB_API_KEY:
            params['api_key'] = TMDB_API_KEY
        
        endpoint = f"{media_type}/{tmdb_id}"
        url = f"{TMDB_BASE_URL}/{endpoint}"
        
        response = requests.get(url, headers=headers or None, params=params, timeout=REQUEST_TIMEOUT)
        
        if response.status_code == 200:
            data = response.json()
            
            # Construir URLs completas para imágenes
            poster_url = None
            backdrop_url = None
            if data.get('poster_path'):
                poster_url = f"https://image.tmdb.org/t/p/w500{data['poster_path']}"
            if data.get('backdrop_path'):
                backdrop_url = f"https://image.tmdb.org/t/p/w1280{data['backdrop_path']}"
            
            # Obtener fecha de estreno según el tipo de media
            release_date = None
            if media_type == 'movie':
                release_date = data.get('release_date')
            elif media_type == 'tv':
                release_date = data.get('first_air_date')
            
            return {
                'title': data.get('title') or data.get('name', ''),
                'overview': data.get('overview', ''),
                'original_title': data.get('original_title') or data.get('original_name', ''),
                'poster_url': poster_url,
                'backdrop_url': backdrop_url,
                'tagline': data.get('tagline', ''),
                'release_date': release_date
            }
    except Exception as e:
        print(f"Error obteniendo datos en español: {str(e)}")
    
    return None

def fetch_translation_from_tmdb(tmdb_id, media_type, language_code):
    """Obtiene una traducción específica desde TMDb con todos los campos de caché"""
    try:
        headers = get_tmdb_auth_headers()
        params = {'language': language_code}
        
        if not headers and TMDB_API_KEY:
            params['api_key'] = TMDB_API_KEY
        
        endpoint = f"{media_type}/{tmdb_id}"
        url = f"{TMDB_BASE_URL}/{endpoint}"
        
        response = requests.get(url, headers=headers or None, params=params, timeout=REQUEST_TIMEOUT)
        
        if response.status_code == 200:
            data = response.json()
            
            # Construir URLs completas para imágenes
            poster_url = None
            backdrop_url = None
            if data.get('poster_path'):
                poster_url = f"https://image.tmdb.org/t/p/w500{data['poster_path']}"
            if data.get('backdrop_path'):
                backdrop_url = f"https://image.tmdb.org/t/p/w1280{data['backdrop_path']}"
            
            # Obtener fecha de estreno según el tipo de media
            release_date = None
            if media_type == 'movie':
                release_date = data.get('release_date')
            elif media_type == 'tv':
                release_date = data.get('first_air_date')
            
            return {
                'title': data.get('title') or data.get('name', ''),
                'overview': data.get('overview', ''),
                'poster_url': poster_url,
                'backdrop_url': backdrop_url,
                'tagline': data.get('tagline', ''),
                'release_date': release_date
            }
        
        time.sleep(0.25)  # Rate limiting
        
    except Exception as e:
        print(f"Error obteniendo traducción {language_code}: {str(e)}")
    
    return None

def ensure_spanish_content(db, media_data):
    """
    Asegura que el contenido esté en español para guardar en la tabla media
    Si no está en español, intenta obtenerlo desde TMDb
    """
    if not media_data.get('tmdb_id'):
        return media_data
    
    # Si ya tenemos datos en español, usar esos
    spanish_data = fetch_spanish_data_from_tmdb(
        media_data['tmdb_id'], 
        convert_media_type_to_tmdb(media_data.get('tipo', ''))
    )
    
    if spanish_data:
        # Usar datos en español para campos principales
        if spanish_data['title']:
            media_data['titulo'] = spanish_data['title']
        if spanish_data['overview']:
            media_data['sinopsis'] = spanish_data['overview']
        if spanish_data['original_title']:
            media_data['original_title'] = spanish_data['original_title']
    
    return media_data

def create_automatic_translations(db, media_id, tmdb_id, media_type):
    """
    Crea automáticamente traducciones para todos los idiomas disponibles
    NOTA: NO crea traducción al español porque ya está en la tabla media principal
    """
    if not tmdb_id or not media_type:
        print("No se puede crear traducciones automáticas: falta tmdb_id o media_type")
        return
    
    tmdb_media_type = convert_media_type_to_tmdb(media_type)
    translations_created = 0
    
    for lang_code, lang_name in TARGET_LANGUAGES.items():
        try:
            # Verificar si ya existe esta traducción
            existing = db.execute(text("""
                SELECT id FROM content_translations 
                WHERE media_id = :media_id AND language_code = :lang_code
            """), {'media_id': media_id, 'lang_code': lang_code}).fetchone()
            
            if existing:
                print(f"   ⚠️  Traducción {lang_code} ya existe, omitiendo...")
                continue
            
            # Obtener traducción desde TMDb
            translation_data = fetch_translation_from_tmdb(tmdb_id, tmdb_media_type, lang_code)
            
            if translation_data and translation_data['title']:
                # Crear registro de traducción con todos los campos de caché
                db.execute(text("""
                    INSERT INTO content_translations 
                    (media_id, language_code, title, synopsis, tmdb_id, media_type, 
                     poster_url, backdrop_url, tagline, release_date)
                    VALUES (:media_id, :lang_code, :title, :synopsis, :tmdb_id, :media_type,
                            :poster_url, :backdrop_url, :tagline, :release_date)
                """), {
                    'media_id': media_id,
                    'lang_code': lang_code,
                    'title': translation_data['title'],
                    'synopsis': translation_data['overview'] or None,
                    'tmdb_id': tmdb_id,
                    'media_type': tmdb_media_type,
                    'poster_url': translation_data.get('poster_url'),
                    'backdrop_url': translation_data.get('backdrop_url'),
                    'tagline': translation_data.get('tagline') or None,
                    'release_date': translation_data.get('release_date')
                })
                
                translations_created += 1
            else:
                pass
                
        except Exception as e:
            pass
    
    if translations_created > 0:
        db.commit()
    else:
        pass

def get_translation_summary(db, media_id):
    """Obtiene un resumen de las traducciones disponibles para un media"""
    try:
        result = db.execute(text("""
            SELECT language_code, title, 
                   CASE WHEN synopsis IS NOT NULL AND synopsis != '' THEN 1 ELSE 0 END as has_synopsis
            FROM content_translations 
            WHERE media_id = :media_id
            ORDER BY language_code
        """), {'media_id': media_id})
        
        translations = result.fetchall()
        
        summary = {
            'total': len(translations),
            'languages': [row[0] for row in translations],
            'with_synopsis': sum(row[2] for row in translations)
        }
        
        return summary
        
    except Exception as e:
        print(f"Error obteniendo resumen de traducciones: {str(e)}")
        return {'total': 0, 'languages': [], 'with_synopsis': 0}
