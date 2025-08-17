from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from models import Media
from typing import List, Dict, Set
import re

router = APIRouter()

def extract_genres_from_db(db: Session) -> Set[str]:
    """Extrae todos los géneros únicos de la base de datos"""
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

def suggest_translation(genre: str, target_language: str) -> str:
    """Sugiere una traducción automática básica para un género"""
    
    # Diccionario de traducciones automáticas básicas
    translations = {
        'es': {
            'action': 'acción', 'adventure': 'aventura', 'comedy': 'comedia',
            'drama': 'drama', 'horror': 'terror', 'thriller': 'thriller',
            'romance': 'romance', 'animation': 'animación', 'documentary': 'documental',
            'crime': 'crimen', 'mystery': 'misterio', 'fantasy': 'fantasía',
            'science fiction': 'ciencia ficción', 'war': 'guerra', 'western': 'western',
            'musical': 'musical', 'biography': 'biografía', 'history': 'historia',
            'family': 'familia', 'sport': 'deporte', 'music': 'música',
            'sci-fi': 'ciencia ficción', 'tv movie': 'película de tv',
            'reality': 'reality'
        },
        'en': {
            'acción': 'action', 'aventura': 'adventure', 'comedia': 'comedy',
            'terror': 'horror', 'misterio': 'mystery', 'fantasía': 'fantasy',
            'ciencia ficción': 'science fiction', 'guerra': 'war',
            'animación': 'animation', 'documental': 'documentary',
            'crimen': 'crime', 'música': 'music', 'familia': 'family',
            'historia': 'history', 'biografía': 'biography', 'bélica': 'war'
        },
        'fr': {
            'action': 'action', 'adventure': 'aventure', 'comedy': 'comédie',
            'drama': 'drame', 'horror': 'horreur', 'thriller': 'thriller',
            'romance': 'romance', 'animation': 'animation', 'documentary': 'documentaire',
            'crime': 'crime', 'mystery': 'mystère', 'fantasy': 'fantaisie',
            'science fiction': 'science-fiction', 'war': 'guerre', 'western': 'western',
            'musical': 'musical', 'biography': 'biographie', 'history': 'histoire',
            'family': 'famille', 'sport': 'sport', 'music': 'musique'
        },
        'de': {
            'action': 'action', 'adventure': 'abenteuer', 'comedy': 'komödie',
            'drama': 'drama', 'horror': 'horror', 'thriller': 'thriller',
            'romance': 'romantik', 'animation': 'animation', 'documentary': 'dokumentation',
            'crime': 'krimi', 'mystery': 'mystery', 'fantasy': 'fantasy',
            'science fiction': 'science-fiction', 'war': 'krieg', 'western': 'western',
            'musical': 'musical', 'biography': 'biografie', 'history': 'geschichte',
            'family': 'familie', 'sport': 'sport', 'music': 'musik'
        },
        'pt': {
            'action': 'ação', 'adventure': 'aventura', 'comedy': 'comédia',
            'drama': 'drama', 'horror': 'terror', 'thriller': 'thriller',
            'romance': 'romance', 'animation': 'animação', 'documentary': 'documentário',
            'crime': 'crime', 'mystery': 'mistério', 'fantasy': 'fantasia',
            'science fiction': 'ficção científica', 'war': 'guerra', 'western': 'western',
            'musical': 'musical', 'biography': 'biografia', 'history': 'história',
            'family': 'família', 'sport': 'esporte', 'music': 'música'
        }
    }
    
    genre_lower = genre.lower()
    
    # Buscar traducción directa
    if target_language in translations and genre_lower in translations[target_language]:
        return translations[target_language][genre_lower]
    
    # Buscar coincidencias parciales
    if target_language in translations:
        for key, value in translations[target_language].items():
            if key in genre_lower or genre_lower in key:
                return genre.lower().replace(key, value).title()
    
    # Fallback: capitalización apropiada
    if target_language == 'en':
        return genre.title()
    else:
        return genre.lower().capitalize()

@router.get("/genres/all")
async def get_all_genres(db: Session = Depends(get_db)) -> List[str]:
    """Obtiene todos los géneros únicos de la base de datos"""
    try:
        genres = extract_genres_from_db(db)
        return sorted(list(genres))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener géneros: {str(e)}")

@router.get("/genres/missing-translations")
async def check_missing_translations(db: Session = Depends(get_db)) -> Dict:
    """
    Verifica si hay géneros que podrían necesitar nuevas traducciones
    Este endpoint devuelve géneros que son nuevos o poco comunes
    """
    try:
        current_genres = extract_genres_from_db(db)
        
        # Lista de géneros "conocidos" que probablemente ya tienen traducciones
        common_genres = {
            'action', 'adventure', 'animation', 'biography', 'comedy', 'crime',
            'documentary', 'drama', 'family', 'fantasy', 'history', 'horror',
            'music', 'mystery', 'romance', 'sci-fi', 'science fiction', 'sport',
            'thriller', 'war', 'western', 'musical', 'acción', 'aventura',
            'animación', 'comedia', 'crimen', 'documental', 'drama', 'familia',
            'fantasía', 'historia', 'terror', 'música', 'misterio', 'romance',
            'ciencia ficción', 'deporte', 'guerra', 'bélica', 'kids', 'reality',
            'soap', 'tv movie', 'película de tv', 'action & adventure',
            'sci-fi & fantasy', 'war & politics', 'talk'
        }
        
        # Normalizar géneros conocidos
        common_genres_normalized = {genre.lower().strip() for genre in common_genres}
        
        # Encontrar géneros potencialmente nuevos
        potentially_new = []
        for genre in current_genres:
            genre_normalized = genre.lower().strip()
            if genre_normalized not in common_genres_normalized:
                potentially_new.append(genre)
        
        # Generar sugerencias de traducción para géneros nuevos
        suggestions = {}
        for genre in potentially_new:
            suggestions[genre] = {
                'es': suggest_translation(genre, 'es'),
                'en': suggest_translation(genre, 'en'),
                'fr': suggest_translation(genre, 'fr'),
                'de': suggest_translation(genre, 'de'),
                'pt': suggest_translation(genre, 'pt')
            }
        
        return {
            "total_genres": len(current_genres),
            "potentially_new_genres": potentially_new,
            "suggestions": suggestions,
            "message": f"Se encontraron {len(potentially_new)} géneros que podrían necesitar traducciones" if potentially_new else "Todos los géneros parecen estar cubiertos"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al verificar traducciones: {str(e)}")

@router.post("/genres/suggest-translation")
async def suggest_genre_translation(genre: str, target_languages: List[str] = None) -> Dict:
    """
    Sugiere traducciones para un género específico
    """
    if not genre:
        raise HTTPException(status_code=400, detail="Género no puede estar vacío")
    
    if target_languages is None:
        target_languages = ['es', 'en', 'fr', 'de', 'pt']
    
    suggestions = {}
    for lang in target_languages:
        suggestions[lang] = suggest_translation(genre, lang)
    
    return {
        "genre": genre,
        "suggestions": suggestions
    }
from sqlalchemy.orm import Session
from database import get_db
from models import Media
from typing import List, Dict, Set
import re

router = APIRouter()

def extract_genres_from_db(db: Session) -> Set[str]:
    """Extrae todos los géneros únicos de la base de datos"""
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

def suggest_translation(genre: str, target_language: str) -> str:
    """Sugiere una traducción automática básica para un género"""
    
    # Diccionario de traducciones automáticas básicas
    translations = {
        'es': {
            'action': 'acción', 'adventure': 'aventura', 'comedy': 'comedia',
            'drama': 'drama', 'horror': 'terror', 'thriller': 'thriller',
            'romance': 'romance', 'animation': 'animación', 'documentary': 'documental',
            'crime': 'crimen', 'mystery': 'misterio', 'fantasy': 'fantasía',
            'science fiction': 'ciencia ficción', 'war': 'guerra', 'western': 'western',
            'musical': 'musical', 'biography': 'biografía', 'history': 'historia',
            'family': 'familia', 'sport': 'deporte', 'music': 'música',
            'sci-fi': 'ciencia ficción', 'tv movie': 'película de tv',
            'reality': 'reality'
        },
        'en': {
            'acción': 'action', 'aventura': 'adventure', 'comedia': 'comedy',
            'terror': 'horror', 'misterio': 'mystery', 'fantasía': 'fantasy',
            'ciencia ficción': 'science fiction', 'guerra': 'war',
            'animación': 'animation', 'documental': 'documentary',
            'crimen': 'crime', 'música': 'music', 'familia': 'family',
            'historia': 'history', 'biografía': 'biography', 'bélica': 'war'
        },
        'fr': {
            'action': 'action', 'adventure': 'aventure', 'comedy': 'comédie',
            'drama': 'drame', 'horror': 'horreur', 'thriller': 'thriller',
            'romance': 'romance', 'animation': 'animation', 'documentary': 'documentaire',
            'crime': 'crime', 'mystery': 'mystère', 'fantasy': 'fantaisie',
            'science fiction': 'science-fiction', 'war': 'guerre', 'western': 'western',
            'musical': 'musical', 'biography': 'biographie', 'history': 'histoire',
            'family': 'famille', 'sport': 'sport', 'music': 'musique'
        },
        'de': {
            'action': 'action', 'adventure': 'abenteuer', 'comedy': 'komödie',
            'drama': 'drama', 'horror': 'horror', 'thriller': 'thriller',
            'romance': 'romantik', 'animation': 'animation', 'documentary': 'dokumentation',
            'crime': 'krimi', 'mystery': 'mystery', 'fantasy': 'fantasy',
            'science fiction': 'science-fiction', 'war': 'krieg', 'western': 'western',
            'musical': 'musical', 'biography': 'biografie', 'history': 'geschichte',
            'family': 'familie', 'sport': 'sport', 'music': 'musik'
        },
        'pt': {
            'action': 'ação', 'adventure': 'aventura', 'comedy': 'comédia',
            'drama': 'drama', 'horror': 'terror', 'thriller': 'thriller',
            'romance': 'romance', 'animation': 'animação', 'documentary': 'documentário',
            'crime': 'crime', 'mystery': 'mistério', 'fantasy': 'fantasia',
            'science fiction': 'ficção científica', 'war': 'guerra', 'western': 'western',
            'musical': 'musical', 'biography': 'biografia', 'history': 'história',
            'family': 'família', 'sport': 'esporte', 'music': 'música'
        }
    }
    
    genre_lower = genre.lower()
    
    # Buscar traducción directa
    if target_language in translations and genre_lower in translations[target_language]:
        return translations[target_language][genre_lower]
    
    # Buscar coincidencias parciales
    if target_language in translations:
        for key, value in translations[target_language].items():
            if key in genre_lower or genre_lower in key:
                return genre.lower().replace(key, value).title()
    
    # Fallback: capitalización apropiada
    if target_language == 'en':
        return genre.title()
    else:
        return genre.lower().capitalize()

@router.get("/genres/all")
async def get_all_genres(db: Session = Depends(get_db)) -> List[str]:
    """Obtiene todos los géneros únicos de la base de datos"""
    try:
        genres = extract_genres_from_db(db)
        return sorted(list(genres))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener géneros: {str(e)}")

@router.get("/genres/missing-translations")
async def check_missing_translations(db: Session = Depends(get_db)) -> Dict:
    """
    Verifica si hay géneros que podrían necesitar nuevas traducciones
    Este endpoint devuelve géneros que son nuevos o poco comunes
    """
    try:
        current_genres = extract_genres_from_db(db)
        
        # Lista de géneros "conocidos" que probablemente ya tienen traducciones
        common_genres = {
            'action', 'adventure', 'animation', 'biography', 'comedy', 'crime',
            'documentary', 'drama', 'family', 'fantasy', 'history', 'horror',
            'music', 'mystery', 'romance', 'sci-fi', 'science fiction', 'sport',
            'thriller', 'war', 'western', 'musical', 'acción', 'aventura',
            'animación', 'comedia', 'crimen', 'documental', 'drama', 'familia',
            'fantasía', 'historia', 'terror', 'música', 'misterio', 'romance',
            'ciencia ficción', 'deporte', 'guerra', 'bélica', 'kids', 'reality',
            'soap', 'tv movie', 'película de tv', 'action & adventure',
            'sci-fi & fantasy', 'war & politics', 'talk'
        }
        
        # Normalizar géneros conocidos
        common_genres_normalized = {genre.lower().strip() for genre in common_genres}
        
        # Encontrar géneros potencialmente nuevos
        potentially_new = []
        for genre in current_genres:
            genre_normalized = genre.lower().strip()
            if genre_normalized not in common_genres_normalized:
                potentially_new.append(genre)
        
        # Generar sugerencias de traducción para géneros nuevos
        suggestions = {}
        for genre in potentially_new:
            suggestions[genre] = {
                'es': suggest_translation(genre, 'es'),
                'en': suggest_translation(genre, 'en'),
                'fr': suggest_translation(genre, 'fr'),
                'de': suggest_translation(genre, 'de'),
                'pt': suggest_translation(genre, 'pt')
            }
        
        return {
            "total_genres": len(current_genres),
            "potentially_new_genres": potentially_new,
            "suggestions": suggestions,
            "message": f"Se encontraron {len(potentially_new)} géneros que podrían necesitar traducciones" if potentially_new else "Todos los géneros parecen estar cubiertos"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al verificar traducciones: {str(e)}")

@router.post("/genres/suggest-translation")
async def suggest_genre_translation(genre: str, target_languages: List[str] = None) -> Dict:
    """
    Sugiere traducciones para un género específico
    """
    if not genre:
        raise HTTPException(status_code=400, detail="Género no puede estar vacío")
    
    if target_languages is None:
        target_languages = ['es', 'en', 'fr', 'de', 'pt']
    
    suggestions = {}
    for lang in target_languages:
        suggestions[lang] = suggest_translation(genre, lang)
    
    return {
        "genre": genre,
        "suggestions": suggestions
    }
