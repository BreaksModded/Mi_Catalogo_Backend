# Utilidad para gestión automática de géneros nuevos
import json
import os
from typing import Dict, List, Set
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Media

def get_all_genres_from_db() -> Set[str]:
    """Obtiene todos los géneros únicos de la base de datos"""
    db = SessionLocal()
    try:
        genres_set = set()
        medias = db.query(Media.genero).filter(Media.genero.isnot(None)).all()
        
        for media in medias:
            if media.genero:
                # Separar por comas y limpiar
                for genre in media.genero.split(','):
                    clean_genre = genre.strip()
                    if clean_genre:
                        genres_set.add(clean_genre)
        
        return genres_set
    finally:
        db.close()

def get_missing_genre_translations(current_genres: Set[str]) -> Dict[str, List[str]]:
    """
    Identifica géneros que no tienen traducciones en los archivos de idiomas
    """
    # Ruta base del frontend
    frontend_path = "../catalogo/src/i18n/languages/"
    languages = ['es', 'en', 'fr', 'de', 'pt']
    
    missing_translations = {}
    
    for lang in languages:
        lang_file = f"{frontend_path}{lang}.js"
        if not os.path.exists(lang_file):
            continue
            
        # Leer el archivo de idioma y extraer las claves de géneros
        try:
            with open(lang_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Buscar el objeto genres y extraer las claves
            genre_keys = extract_genre_keys_from_content(content)
            
            # Identificar géneros faltantes
            missing_for_lang = []
            for genre in current_genres:
                genre_key = genre.lower()
                if genre_key not in genre_keys:
                    missing_for_lang.append(genre)
            
            if missing_for_lang:
                missing_translations[lang] = missing_for_lang
                
        except Exception as e:
            print(f"Error procesando archivo {lang_file}: {e}")
    
    return missing_translations

def extract_genre_keys_from_content(content: str) -> Set[str]:
    """Extrae las claves de géneros del contenido del archivo de idioma"""
    genre_keys = set()
    
    # Buscar la sección genres
    import re
    
    # Patrón para encontrar el objeto genres
    genre_pattern = r"genres:\s*\{([^}]+)\}"
    matches = re.findall(genre_pattern, content, re.DOTALL)
    
    for match in matches:
        # Extraer claves individuales
        key_pattern = r"'([^']+)':"
        keys = re.findall(key_pattern, match)
        genre_keys.update(keys)
    
    return genre_keys

def suggest_translations_for_missing_genres(missing_genres: List[str]) -> Dict[str, Dict[str, str]]:
    """
    Sugiere traducciones automáticas para géneros faltantes
    """
    suggestions = {}
    
    # Diccionario básico de traducciones automáticas
    auto_translations = {
        'es': {
            'action': 'acción',
            'adventure': 'aventura',
            'comedy': 'comedia',
            'drama': 'drama',
            'horror': 'terror',
            'thriller': 'thriller',
            'romance': 'romance',
            'animation': 'animación',
            'documentary': 'documental',
            'crime': 'crimen',
            'mystery': 'misterio',
            'fantasy': 'fantasía',
            'science fiction': 'ciencia ficción',
            'war': 'guerra',
            'western': 'western',
            'musical': 'musical',
            'biography': 'biografía',
            'history': 'historia',
            'family': 'familia',
            'sport': 'deporte',
            'music': 'música',
        },
        'en': {
            # El inglés suele ser el origen, pero podemos normalizar
            'sci-fi': 'science fiction',
            'romcom': 'romantic comedy',
            'action/adventure': 'action & adventure',
        },
        'fr': {
            'action': 'action',
            'adventure': 'aventure',
            'comedy': 'comédie',
            'drama': 'drame',
            'horror': 'horreur',
            'thriller': 'thriller',
            'romance': 'romance',
            'animation': 'animation',
            'documentary': 'documentaire',
            'crime': 'crime',
            'mystery': 'mystère',
            'fantasy': 'fantaisie',
            'science fiction': 'science-fiction',
            'war': 'guerre',
            'western': 'western',
            'musical': 'musical',
            'biography': 'biographie',
            'history': 'histoire',
            'family': 'famille',
            'sport': 'sport',
            'music': 'musique',
        },
        'de': {
            'action': 'action',
            'adventure': 'abenteuer',
            'comedy': 'komödie',
            'drama': 'drama',
            'horror': 'horror',
            'thriller': 'thriller',
            'romance': 'romantik',
            'animation': 'animation',
            'documentary': 'dokumentation',
            'crime': 'krimi',
            'mystery': 'mystery',
            'fantasy': 'fantasy',
            'science fiction': 'science-fiction',
            'war': 'krieg',
            'western': 'western',
            'musical': 'musical',
            'biography': 'biografie',
            'history': 'geschichte',
            'family': 'familie',
            'sport': 'sport',
            'music': 'musik',
        },
        'pt': {
            'action': 'ação',
            'adventure': 'aventura',
            'comedy': 'comédia',
            'drama': 'drama',
            'horror': 'terror',
            'thriller': 'thriller',
            'romance': 'romance',
            'animation': 'animação',
            'documentary': 'documentário',
            'crime': 'crime',
            'mystery': 'mistério',
            'fantasy': 'fantasia',
            'science fiction': 'ficção científica',
            'war': 'guerra',
            'western': 'western',
            'musical': 'musical',
            'biography': 'biografia',
            'history': 'história',
            'family': 'família',
            'sport': 'esporte',
            'music': 'música',
        }
    }
    
    for genre in missing_genres:
        genre_lower = genre.lower()
        genre_suggestions = {}
        
        for lang, translations in auto_translations.items():
            # Buscar coincidencia exacta
            if genre_lower in translations:
                genre_suggestions[lang] = translations[genre_lower]
            else:
                # Buscar coincidencias parciales
                for key, value in translations.items():
                    if key in genre_lower or genre_lower in key:
                        # Aplicar la traducción parcial
                        suggested = genre.lower().replace(key, value)
                        genre_suggestions[lang] = suggested.title()
                        break
                else:
                    # Si no hay coincidencia, usar capitalización apropiada
                    if lang == 'en':
                        genre_suggestions[lang] = genre.title()
                    else:
                        genre_suggestions[lang] = genre.lower().capitalize()
        
        if genre_suggestions:
            suggestions[genre] = genre_suggestions
    
    return suggestions

def generate_genre_translation_code(missing_translations: Dict[str, List[str]]) -> Dict[str, str]:
    """
    Genera código JavaScript para añadir a los archivos de idiomas
    """
    suggestions = {}
    
    for lang, missing_genres in missing_translations.items():
        if not missing_genres:
            continue
            
        auto_suggestions = suggest_translations_for_missing_genres(missing_genres)
        
        code_lines = []
        code_lines.append(f"    // Géneros nuevos detectados automáticamente")
        
        for genre in missing_genres:
            key = genre.lower()
            if genre in auto_suggestions and lang in auto_suggestions[genre]:
                translation = auto_suggestions[genre][lang]
                code_lines.append(f"    '{key}': '{translation}',")
            else:
                # Fallback: usar el género original con capitalización apropiada
                fallback = genre.title() if lang == 'en' else genre.lower().capitalize()
                code_lines.append(f"    '{key}': '{fallback}', // TODO: Revisar traducción")
        
        suggestions[lang] = '\n'.join(code_lines)
    
    return suggestions

def check_and_report_missing_genres():
    """
    Función principal que verifica géneros faltantes y genera reporte
    """
    print("🔍 Verificando géneros en la base de datos...")
    current_genres = get_all_genres_from_db()
    print(f"📊 Encontrados {len(current_genres)} géneros únicos")
    
    print("\n🌐 Verificando traducciones faltantes...")
    missing_translations = get_missing_genre_translations(current_genres)
    
    if not missing_translations:
        print("✅ Todos los géneros tienen traducciones en todos los idiomas")
        return
    
    print("❌ Géneros sin traducción encontrados:")
    for lang, missing in missing_translations.items():
        print(f"  {lang.upper()}: {len(missing)} géneros")
        for genre in missing[:5]:  # Mostrar solo los primeros 5
            print(f"    - {genre}")
        if len(missing) > 5:
            print(f"    ... y {len(missing) - 5} más")
    
    print("\n🔧 Generando código de traducción automática...")
    translation_code = generate_genre_translation_code(missing_translations)
    
    for lang, code in translation_code.items():
        print(f"\n📝 Código para {lang}.js:")
        print(code)
        print("-" * 50)

if __name__ == "__main__":
    check_and_report_missing_genres()# Utilidad para gestión automática de géneros nuevos
import json
import os
from typing import Dict, List, Set
from sqlalchemy.orm import Session
from database import SessionLocal
from models import Media

def get_all_genres_from_db() -> Set[str]:
    """Obtiene todos los géneros únicos de la base de datos"""
    db = SessionLocal()
    try:
        genres_set = set()
        medias = db.query(Media.genero).filter(Media.genero.isnot(None)).all()
        
        for media in medias:
            if media.genero:
                # Separar por comas y limpiar
                for genre in media.genero.split(','):
                    clean_genre = genre.strip()
                    if clean_genre:
                        genres_set.add(clean_genre)
        
        return genres_set
    finally:
        db.close()

def get_missing_genre_translations(current_genres: Set[str]) -> Dict[str, List[str]]:
    """
    Identifica géneros que no tienen traducciones en los archivos de idiomas
    """
    # Ruta base del frontend
    frontend_path = "../catalogo/src/i18n/languages/"
    languages = ['es', 'en', 'fr', 'de', 'pt']
    
    missing_translations = {}
    
    for lang in languages:
        lang_file = f"{frontend_path}{lang}.js"
        if not os.path.exists(lang_file):
            continue
            
        # Leer el archivo de idioma y extraer las claves de géneros
        try:
            with open(lang_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Buscar el objeto genres y extraer las claves
            genre_keys = extract_genre_keys_from_content(content)
            
            # Identificar géneros faltantes
            missing_for_lang = []
            for genre in current_genres:
                genre_key = genre.lower()
                if genre_key not in genre_keys:
                    missing_for_lang.append(genre)
            
            if missing_for_lang:
                missing_translations[lang] = missing_for_lang
                
        except Exception as e:
            print(f"Error procesando archivo {lang_file}: {e}")
    
    return missing_translations

def extract_genre_keys_from_content(content: str) -> Set[str]:
    """Extrae las claves de géneros del contenido del archivo de idioma"""
    genre_keys = set()
    
    # Buscar la sección genres
    import re
    
    # Patrón para encontrar el objeto genres
    genre_pattern = r"genres:\s*\{([^}]+)\}"
    matches = re.findall(genre_pattern, content, re.DOTALL)
    
    for match in matches:
        # Extraer claves individuales
        key_pattern = r"'([^']+)':"
        keys = re.findall(key_pattern, match)
        genre_keys.update(keys)
    
    return genre_keys

def suggest_translations_for_missing_genres(missing_genres: List[str]) -> Dict[str, Dict[str, str]]:
    """
    Sugiere traducciones automáticas para géneros faltantes
    """
    suggestions = {}
    
    # Diccionario básico de traducciones automáticas
    auto_translations = {
        'es': {
            'action': 'acción',
            'adventure': 'aventura',
            'comedy': 'comedia',
            'drama': 'drama',
            'horror': 'terror',
            'thriller': 'thriller',
            'romance': 'romance',
            'animation': 'animación',
            'documentary': 'documental',
            'crime': 'crimen',
            'mystery': 'misterio',
            'fantasy': 'fantasía',
            'science fiction': 'ciencia ficción',
            'war': 'guerra',
            'western': 'western',
            'musical': 'musical',
            'biography': 'biografía',
            'history': 'historia',
            'family': 'familia',
            'sport': 'deporte',
            'music': 'música',
        },
        'en': {
            # El inglés suele ser el origen, pero podemos normalizar
            'sci-fi': 'science fiction',
            'romcom': 'romantic comedy',
            'action/adventure': 'action & adventure',
        },
        'fr': {
            'action': 'action',
            'adventure': 'aventure',
            'comedy': 'comédie',
            'drama': 'drame',
            'horror': 'horreur',
            'thriller': 'thriller',
            'romance': 'romance',
            'animation': 'animation',
            'documentary': 'documentaire',
            'crime': 'crime',
            'mystery': 'mystère',
            'fantasy': 'fantaisie',
            'science fiction': 'science-fiction',
            'war': 'guerre',
            'western': 'western',
            'musical': 'musical',
            'biography': 'biographie',
            'history': 'histoire',
            'family': 'famille',
            'sport': 'sport',
            'music': 'musique',
        },
        'de': {
            'action': 'action',
            'adventure': 'abenteuer',
            'comedy': 'komödie',
            'drama': 'drama',
            'horror': 'horror',
            'thriller': 'thriller',
            'romance': 'romantik',
            'animation': 'animation',
            'documentary': 'dokumentation',
            'crime': 'krimi',
            'mystery': 'mystery',
            'fantasy': 'fantasy',
            'science fiction': 'science-fiction',
            'war': 'krieg',
            'western': 'western',
            'musical': 'musical',
            'biography': 'biografie',
            'history': 'geschichte',
            'family': 'familie',
            'sport': 'sport',
            'music': 'musik',
        },
        'pt': {
            'action': 'ação',
            'adventure': 'aventura',
            'comedy': 'comédia',
            'drama': 'drama',
            'horror': 'terror',
            'thriller': 'thriller',
            'romance': 'romance',
            'animation': 'animação',
            'documentary': 'documentário',
            'crime': 'crime',
            'mystery': 'mistério',
            'fantasy': 'fantasia',
            'science fiction': 'ficção científica',
            'war': 'guerra',
            'western': 'western',
            'musical': 'musical',
            'biography': 'biografia',
            'history': 'história',
            'family': 'família',
            'sport': 'esporte',
            'music': 'música',
        }
    }
    
    for genre in missing_genres:
        genre_lower = genre.lower()
        genre_suggestions = {}
        
        for lang, translations in auto_translations.items():
            # Buscar coincidencia exacta
            if genre_lower in translations:
                genre_suggestions[lang] = translations[genre_lower]
            else:
                # Buscar coincidencias parciales
                for key, value in translations.items():
                    if key in genre_lower or genre_lower in key:
                        # Aplicar la traducción parcial
                        suggested = genre.lower().replace(key, value)
                        genre_suggestions[lang] = suggested.title()
                        break
                else:
                    # Si no hay coincidencia, usar capitalización apropiada
                    if lang == 'en':
                        genre_suggestions[lang] = genre.title()
                    else:
                        genre_suggestions[lang] = genre.lower().capitalize()
        
        if genre_suggestions:
            suggestions[genre] = genre_suggestions
    
    return suggestions

def generate_genre_translation_code(missing_translations: Dict[str, List[str]]) -> Dict[str, str]:
    """
    Genera código JavaScript para añadir a los archivos de idiomas
    """
    suggestions = {}
    
    for lang, missing_genres in missing_translations.items():
        if not missing_genres:
            continue
            
        auto_suggestions = suggest_translations_for_missing_genres(missing_genres)
        
        code_lines = []
        code_lines.append(f"    // Géneros nuevos detectados automáticamente")
        
        for genre in missing_genres:
            key = genre.lower()
            if genre in auto_suggestions and lang in auto_suggestions[genre]:
                translation = auto_suggestions[genre][lang]
                code_lines.append(f"    '{key}': '{translation}',")
            else:
                # Fallback: usar el género original con capitalización apropiada
                fallback = genre.title() if lang == 'en' else genre.lower().capitalize()
                code_lines.append(f"    '{key}': '{fallback}', // TODO: Revisar traducción")
        
        suggestions[lang] = '\n'.join(code_lines)
    
    return suggestions

def check_and_report_missing_genres():
    """
    Función principal que verifica géneros faltantes y genera reporte
    """
    print("🔍 Verificando géneros en la base de datos...")
    current_genres = get_all_genres_from_db()
    print(f"📊 Encontrados {len(current_genres)} géneros únicos")
    
    print("\n🌐 Verificando traducciones faltantes...")
    missing_translations = get_missing_genre_translations(current_genres)
    
    if not missing_translations:
        print("✅ Todos los géneros tienen traducciones en todos los idiomas")
        return
    
    print("❌ Géneros sin traducción encontrados:")
    for lang, missing in missing_translations.items():
        print(f"  {lang.upper()}: {len(missing)} géneros")
        for genre in missing[:5]:  # Mostrar solo los primeros 5
            print(f"    - {genre}")
        if len(missing) > 5:
            print(f"    ... y {len(missing) - 5} más")
    
    print("\n🔧 Generando código de traducción automática...")
    translation_code = generate_genre_translation_code(missing_translations)
    
    for lang, code in translation_code.items():
        print(f"\n📝 Código para {lang}.js:")
        print(code)
        print("-" * 50)

if __name__ == "__main__":
    check_and_report_missing_genres()
