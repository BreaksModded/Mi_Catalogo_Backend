"""
CRUD operations for content translations
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_
from models import ContentTranslation, Media
from datetime import datetime
import requests
import logging
from config import get_tmdb_auth_headers, TMDB_BASE_URL, TMDB_API_KEY, REQUEST_TIMEOUT

logger = logging.getLogger(__name__)

class TranslationService:
    def __init__(self, db: Session):
        self.db = db
        self.tmdb_api_key = TMDB_API_KEY
        self.tmdb_base_url = TMDB_BASE_URL
        
    def get_cached_translation(self, media_id: int, language_code: str) -> ContentTranslation:
        """Get cached translation from database"""
        return self.db.query(ContentTranslation).filter(
            and_(
                ContentTranslation.media_id == media_id,
                ContentTranslation.language_code == language_code
            )
        ).first()
    
    def get_translation_by_tmdb_id(self, tmdb_id: int, media_type: str, language_code: str) -> ContentTranslation:
        """Get cached translation by TMDb ID"""
        return self.db.query(ContentTranslation).filter(
            and_(
                ContentTranslation.tmdb_id == tmdb_id,
                ContentTranslation.media_type == media_type,
                ContentTranslation.language_code == language_code
            )
        ).first()
    
    def save_translation(self, media_id: int, language_code: str, translation_data: dict) -> ContentTranslation:
        """Save or update translation in cache"""
        existing = self.get_cached_translation(media_id, language_code)
        
        if existing:
            # Update existing translation
            for key, value in translation_data.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            existing.updated_at = datetime.utcnow()
            translation = existing
        else:
            # Create new translation
            translation = ContentTranslation(
                media_id=media_id,
                language_code=language_code,
                **translation_data
            )
            self.db.add(translation)
        
        self.db.commit()
        self.db.refresh(translation)
        return translation
    
    def fetch_from_tmdb(self, tmdb_id: int, media_type: str, language_code: str) -> dict:
        """Fetch translation from TMDb API"""
        try:
            # Map language codes
            tmdb_language = self._map_language_code(language_code)
            
            # Determine endpoint based on media type
            endpoint = "movie" if media_type.lower() in ["movie", "película", "pelicula"] else "tv"
            
            url = f"{self.tmdb_base_url}/{endpoint}/{tmdb_id}"
            headers = get_tmdb_auth_headers()
            # Prefer Bearer header; if not present, fall back to API key param
            params = {"language": tmdb_language}
            if not headers and self.tmdb_api_key:
                params["api_key"] = self.tmdb_api_key
            
            response = requests.get(url, headers=headers or None, params=params, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            data = response.json()
            
            # Extract relevant fields
            translation_data = {
                "translated_title": data.get("title") or data.get("name"),
                "translated_synopsis": data.get("overview"),
                "director": self._extract_director(data, endpoint),
                "cast_members": self._extract_cast(data, endpoint),
                "genres": self._extract_genres(data),
                "translation_source": "tmdb",
                "tmdb_id": tmdb_id,
                "media_type": endpoint
            }
            
            return translation_data
            
        except Exception as e:
            logger.error(f"Error fetching from TMDb: {e}")
            return {}
    
    def get_translated_content(self, media_id: int, language_code: str) -> dict:
        """Get translated content with caching strategy"""
        # First, check cache
        cached = self.get_cached_translation(media_id, language_code)
        if cached:
            return self._translation_to_dict(cached)
        
        # Get original media data
        media = self.db.query(Media).filter(Media.id == media_id).first()
        if not media:
            return {}
        
        # If no TMDb ID, return original content
        if not media.tmdb_id:
            return self._media_to_dict(media)
        
        # Check if we have cached translation by TMDb ID
        cached_by_tmdb = self.get_translation_by_tmdb_id(
            media.tmdb_id, media.tipo, language_code
        )
        if cached_by_tmdb:
            # Update the media_id in cache and return
            cached_by_tmdb.media_id = media_id
            self.db.commit()
            return self._translation_to_dict(cached_by_tmdb)
        
        # Fetch from TMDb and cache
        translation_data = self.fetch_from_tmdb(media.tmdb_id, media.tipo, language_code)
        if translation_data:
            saved_translation = self.save_translation(media_id, language_code, translation_data)
            return self._translation_to_dict(saved_translation)
        
        # Fallback to original content
        return self._media_to_dict(media)
    
    def _map_language_code(self, language_code: str) -> str:
        """Map internal language codes to TMDb language codes"""
        mapping = {
            "es": "es-ES",
            "en": "en-US",
            "fr": "fr-FR",
            "de": "de-DE",
            "it": "it-IT",
            "pt": "pt-BR"
        }
        return mapping.get(language_code, language_code)
    
    def _extract_director(self, data: dict, endpoint: str) -> str:
        """Extract director from TMDb data"""
        # This would require additional API calls for credits
        # For now, return empty string
        return ""
    
    def _extract_cast(self, data: dict, endpoint: str) -> str:
        """Extract cast from TMDb data"""
        # This would require additional API calls for credits
        # For now, return empty string
        return ""
    
    def _extract_genres(self, data: dict) -> str:
        """Extract genres from TMDb data"""
        genres = data.get("genres", [])
        return ", ".join([genre["name"] for genre in genres])
    
    def _translation_to_dict(self, translation: ContentTranslation) -> dict:
        """Convert translation model to dictionary"""
        return {
            "titulo": translation.translated_title,
            "sinopsis": translation.translated_synopsis,
            "director": translation.director,
            "elenco": translation.cast_members,
            "genero": translation.genres,
            "translationSource": translation.translation_source,
            "titulo_original": None  # Will be set by the caller if needed
        }
    
    def _media_to_dict(self, media: Media) -> dict:
        """Convert media model to dictionary for fallback"""
        return {
            "titulo": media.titulo,
            "sinopsis": media.sinopsis,
            "descripcion": media.descripcion or media.sinopsis,
            "director": media.director,
            "elenco": media.elenco,
            "genero": media.genero,
            "translationSource": "original",
            "titulo_original": media.titulo
        }

def get_translation_service(db: Session) -> TranslationService:
    """Factory function to get translation service"""
    return TranslationService(db)
