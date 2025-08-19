"""
Servicio de Actualización Automática de Media desde TMDb
Mantiene actualizada la información de películas y series
"""

import requests
import time
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

import models
import database
from config import TMDB_API_KEY, TMDB_BASE_URL, get_tmdb_auth_headers, REQUEST_TIMEOUT


class AutoUpdateService:
    """Servicio para mantener actualizada la información de medias desde TMDb"""
    
    def __init__(self):
        self.headers = get_tmdb_auth_headers()
        
    def should_update_media(self, media: models.Media) -> bool:
        """Determina si un media necesita ser actualizado"""
        
        # No actualizar si está deshabilitado
        if not media.auto_update_enabled:
            return False
            
        # Si está marcado como needs_update, actualizarlo
        if media.needs_update:
            return True
            
        # Si no tiene tmdb_id, no se puede actualizar
        if not media.tmdb_id:
            return False
            
        # Si nunca se ha actualizado, actualizarlo
        if not media.last_updated_tmdb:
            return True
        
        # 🎯 LÓGICA OPTIMIZADA: Saltarse contenido finalizado
        
        # Series finalizadas/canceladas: solo actualizar si nunca se actualizó después de finalizar
        if media.tipo == "serie" and media.status in ["Ended", "Canceled", "Cancelled"]:
            # Si se actualizó después de que se marcó como finalizada, no volver a actualizar
            # Solo actualizar una vez cada 6 meses para verificar cambios en el cast
            days_since_update = (datetime.now() - media.last_updated_tmdb).days
            return days_since_update >= 180  # 6 meses
            
        # Películas estrenadas: menos frecuente, principalmente para cambios en el cast
        if media.tipo == "película" and media.status == "Released":
            days_since_update = (datetime.now() - media.last_updated_tmdb).days
            # Solo cada 4 meses para películas ya estrenadas
            return days_since_update >= 120  # 4 meses
            
        # Lógica de frecuencia normal para contenido activo
        now = datetime.now()
        days_since_update = (now - media.last_updated_tmdb).days
        
        # Series en emisión: actualizar frecuentemente para nuevos episodios/temporadas
        if media.tipo == "serie" and media.status in ["Returning Series", "In Production", "Continuing"]:
            return days_since_update >= 7
            
        # Películas en producción/post-producción: actualizar frecuentemente
        elif media.tipo == "película" and media.status in ["In Production", "Post Production", "Planned", "Announced"]:
            return days_since_update >= 3
            
        # Estados desconocidos o sin estado: actualizar moderadamente
        elif not media.status or media.status in ["", "Unknown"]:
            return days_since_update >= 14
            
        # Por defecto: actualizar cada 30 días
        return days_since_update >= 30
    
    def get_media_details_from_tmdb(self, tmdb_id: int, media_type: str, language: str = "es-ES") -> Optional[Dict[str, Any]]:
        """Obtiene detalles actualizados de un media desde TMDb"""
        
        try:
            if media_type == "película":
                detail_url = f"{TMDB_BASE_URL}/movie/{tmdb_id}"
                credits_url = f"{TMDB_BASE_URL}/movie/{tmdb_id}/credits"
            else:  # serie
                detail_url = f"{TMDB_BASE_URL}/tv/{tmdb_id}"
                credits_url = f"{TMDB_BASE_URL}/tv/{tmdb_id}/credits"
                
            detail_params = {"language": language}
            
            # Obtener detalles principales
            detail_r = requests.get(detail_url, headers=self.headers, params=detail_params, timeout=REQUEST_TIMEOUT)
            
            if detail_r.status_code != 200:
                print(f"❌ Error al obtener detalles de TMDb para {tmdb_id}: {detail_r.status_code}")
                return None
                
            detail = detail_r.json()
            
            # 🎬 Obtener información actualizada del elenco y dirección
            director = ""
            elenco = ""
            
            credits_r = requests.get(credits_url, headers=self.headers, timeout=REQUEST_TIMEOUT)
            if credits_r.status_code == 200:
                credits = credits_r.json()
                
                if media_type == "película":
                    # Para películas: buscar directores
                    director_list = [c["name"] for c in credits.get("crew", []) if c.get("job") == "Director"]
                    director = ", ".join(director_list)
                else:
                    # Para series: buscar creadores y directores principales
                    creators = [c["name"] for c in credits.get("crew", []) if c.get("job") in ("Creator", "Director", "Executive Producer")]
                    director = ", ".join(list(set(creators))[:3])  # Limitar a 3 principales
                
                # Elenco principal (primeros 8 actores para incluir nuevos actores)
                elenco_list = [a["name"] for a in credits.get("cast", [])[:8]]
                elenco = ", ".join(elenco_list)
            
            # Procesar los datos según el tipo
            if media_type == "película":
                return self._process_movie_data(detail, director, elenco)
            else:
                return self._process_tv_data(detail, director, elenco)
                
        except Exception as e:
            print(f"❌ Error al obtener detalles de TMDb para {tmdb_id}: {str(e)}")
            return None
    
    def _process_movie_data(self, detail: Dict[str, Any], director: str = "", elenco: str = "") -> Dict[str, Any]:
        """Procesa datos de película desde TMDb"""
        
        # Procesar production_countries
        production_countries = None
        if detail.get("production_countries"):
            production_countries = ", ".join([country["name"] for country in detail["production_countries"]])
            
        return {
            "runtime": detail.get("runtime"),
            "production_countries": production_countries,
            "status": detail.get("status", ""),
            "temporadas": None,
            "episodios": None,
            "first_air_date": None,
            "last_air_date": None,
            "episode_runtime": None,
            "nota_imdb": detail.get("vote_average"),
            "votos_tmdb": detail.get("vote_count"),
            # 🎬 Información actualizada del elenco
            "director": director,
            "elenco": elenco
        }
    
    def _process_tv_data(self, detail: Dict[str, Any], director: str = "", elenco: str = "") -> Dict[str, Any]:
        """Procesa datos de serie desde TMDb"""
        
        # Procesar production_countries
        production_countries = None
        if detail.get("production_countries"):
            production_countries = ", ".join([country["name"] for country in detail["production_countries"]])
            
        # Procesar episode_runtime
        episode_runtime = None
        if detail.get("episode_run_time"):
            episode_runtime = ", ".join(map(str, detail["episode_run_time"]))
            
        # Procesar fechas
        first_air_date = None
        last_air_date = None
        
        if detail.get("first_air_date"):
            try:
                first_air_date = datetime.strptime(detail["first_air_date"], "%Y-%m-%d").date()
            except:
                pass
                
        if detail.get("last_air_date"):
            try:
                last_air_date = datetime.strptime(detail["last_air_date"], "%Y-%m-%d").date()
            except:
                pass
                
        return {
            "runtime": None,  # Las series no tienen runtime general
            "production_countries": production_countries,
            "status": detail.get("status", ""),
            "temporadas": detail.get("number_of_seasons"),
            "episodios": detail.get("number_of_episodes"),
            "first_air_date": first_air_date,
            "last_air_date": last_air_date,
            "episode_runtime": episode_runtime,
            "nota_imdb": detail.get("vote_average"),
            "votos_tmdb": detail.get("vote_count"),
            # 🎬 Información actualizada del elenco
            "director": director,
            "elenco": elenco
        }
    
    def update_media_from_tmdb(self, db: Session, media: models.Media) -> bool:
        """Actualiza un media específico desde TMDb"""
        
        if not media.tmdb_id:
            return False
            
        print(f"🔄 Actualizando {media.titulo} (TMDb ID: {media.tmdb_id})")
        
        # Obtener datos actualizados
        updated_data = self.get_media_details_from_tmdb(
            media.tmdb_id, 
            media.tipo,
            "es-ES"
        )
        
        if not updated_data:
            return False
            
        # Verificar si hay cambios significativos
        changes = []
        significant_changes = []  # Para cambios importantes como nuevas temporadas
        cast_changes = []  # Para cambios en el elenco
        
        for field, new_value in updated_data.items():
            old_value = getattr(media, field, None)
            if old_value != new_value:
                change_desc = f"{field}: {old_value} → {new_value}"
                changes.append(change_desc)
                
                # Categorizar tipos de cambios
                if field in ['temporadas', 'episodios', 'status', 'last_air_date']:
                    significant_changes.append(change_desc)
                elif field in ['director', 'elenco']:
                    cast_changes.append(change_desc)
                
                setattr(media, field, new_value)
        
        if changes:
            print(f"📝 Cambios detectados en {media.titulo}:")
            
            if significant_changes:
                print(f"   🚨 Cambios importantes:")
                for change in significant_changes:
                    print(f"      - {change}")
                    
            if cast_changes:
                print(f"   🎭 Cambios en elenco/dirección:")
                for change in cast_changes:
                    print(f"      - {change}")
                    
            # Mostrar otros cambios
            other_changes = [c for c in changes if c not in significant_changes and c not in cast_changes]
            if other_changes:
                print(f"   📊 Otros cambios:")
                for change in other_changes:
                    print(f"      - {change}")
                
            # Actualizar timestamps
            media.last_updated_tmdb = datetime.now()
            media.needs_update = False
            
            try:
                db.commit()
                
                # Mensaje de resumen
                if significant_changes:
                    print(f"✅ {media.titulo} actualizado con cambios importantes!")
                elif cast_changes:
                    print(f"✅ {media.titulo} actualizado con cambios en el elenco")
                else:
                    print(f"✅ {media.titulo} actualizado correctamente")
                    
                return True
            except Exception as e:
                print(f"❌ Error al guardar cambios en {media.titulo}: {str(e)}")
                db.rollback()
                return False
        else:
            # No hay cambios, pero actualizar timestamp
            media.last_updated_tmdb = datetime.now()
            media.needs_update = False
            db.commit()
            
            # Mensaje diferente según el estado
            if media.status in ["Ended", "Canceled", "Cancelled", "Released"]:
                print(f"ℹ️ {media.titulo} confirmado como finalizado, no requiere más actualizaciones frecuentes")
            else:
                print(f"ℹ️ {media.titulo} ya está actualizado")
            return True
    
    def update_medias_batch(self, db: Session, limit: int = 10, media_type: Optional[str] = None) -> Dict[str, int]:
        """Actualiza un lote de medias que necesitan actualización"""
        
        print(f"🚀 Iniciando actualización automática de medias (límite: {limit})")
        
        # Construir query base
        query = db.query(models.Media).filter(
            models.Media.tmdb_id.isnot(None),
            models.Media.auto_update_enabled == True
        )
        
        # Filtrar por tipo si se especifica
        if media_type:
            query = query.filter(models.Media.tipo == media_type)
        
        # Obtener medias que necesitan actualización
        medias_to_update = []
        
        for media in query.all():
            if self.should_update_media(media):
                medias_to_update.append(media)
                if len(medias_to_update) >= limit:
                    break
        
        if not medias_to_update:
            print("ℹ️ No hay medias que necesiten actualización")
            return {"updated": 0, "failed": 0, "total": 0}
        
        print(f"📋 {len(medias_to_update)} medias necesitan actualización")
        
        # Actualizar cada media
        updated_count = 0
        failed_count = 0
        
        for media in medias_to_update:
            try:
                if self.update_media_from_tmdb(db, media):
                    updated_count += 1
                else:
                    failed_count += 1
                    
                # Pausa entre requests para no sobrecargar la API
                time.sleep(0.5)
                
            except Exception as e:
                print(f"❌ Error al actualizar {media.titulo}: {str(e)}")
                failed_count += 1
        
        results = {
            "updated": updated_count,
            "failed": failed_count,
            "total": len(medias_to_update)
        }
        
        print(f"✅ Actualización completada: {updated_count} actualizados, {failed_count} fallos")
        return results
    
    def mark_media_for_update(self, db: Session, tmdb_id: int):
        """Marca un media específico para actualización forzada"""
        
        media = db.query(models.Media).filter(models.Media.tmdb_id == tmdb_id).first()
        if media:
            media.needs_update = True
            db.commit()
            print(f"📝 {media.titulo} marcado para actualización")
    
    def get_update_stats(self, db: Session) -> Dict[str, Any]:
        """Obtiene estadísticas del sistema de actualización"""
        
        total_medias = db.query(models.Media).filter(models.Media.tmdb_id.isnot(None)).count()
        
        auto_update_enabled = db.query(models.Media).filter(
            models.Media.tmdb_id.isnot(None),
            models.Media.auto_update_enabled == True
        ).count()
        
        needs_update = db.query(models.Media).filter(
            models.Media.tmdb_id.isnot(None),
            models.Media.needs_update == True
        ).count()
        
        never_updated = db.query(models.Media).filter(
            models.Media.tmdb_id.isnot(None),
            models.Media.last_updated_tmdb.is_(None)
        ).count()
        
        # Estadísticas por estado
        series_active = db.query(models.Media).filter(
            models.Media.tmdb_id.isnot(None),
            models.Media.tipo == "serie",
            models.Media.status.in_(["Returning Series", "In Production", "Continuing"])
        ).count()
        
        series_ended = db.query(models.Media).filter(
            models.Media.tmdb_id.isnot(None),
            models.Media.tipo == "serie",
            models.Media.status.in_(["Ended", "Canceled", "Cancelled"])
        ).count()
        
        movies_released = db.query(models.Media).filter(
            models.Media.tmdb_id.isnot(None),
            models.Media.tipo == "película",
            models.Media.status == "Released"
        ).count()
        
        movies_upcoming = db.query(models.Media).filter(
            models.Media.tmdb_id.isnot(None),
            models.Media.tipo == "película",
            models.Media.status.in_(["In Production", "Post Production", "Planned", "Announced"])
        ).count()
        
        # Contar cuántos necesitan actualización según la lógica optimizada
        medias_needing_update = 0
        active_content_needing_update = 0
        finished_content_needing_update = 0
        
        for media in db.query(models.Media).filter(
            models.Media.tmdb_id.isnot(None),
            models.Media.auto_update_enabled == True
        ).all():
            if self.should_update_media(media):
                medias_needing_update += 1
                
                # Categorizar por tipo de contenido
                if media.status in ["Ended", "Canceled", "Cancelled", "Released"]:
                    finished_content_needing_update += 1
                else:
                    active_content_needing_update += 1
        
        return {
            "total_medias_with_tmdb": total_medias,
            "auto_update_enabled": auto_update_enabled,
            "marked_for_update": needs_update,
            "never_updated": never_updated,
            "need_update_by_schedule": medias_needing_update,
            "active_content_needing_update": active_content_needing_update,
            "finished_content_needing_update": finished_content_needing_update,
            "breakdown": {
                "series_active": series_active,
                "series_ended": series_ended,
                "movies_released": movies_released,
                "movies_upcoming": movies_upcoming
            }
        }


# Instancia global del servicio
auto_update_service = AutoUpdateService()


def get_auto_update_service() -> AutoUpdateService:
    """Obtiene la instancia del servicio de actualización automática"""
    return auto_update_service
