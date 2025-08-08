"""
Sistema de cache para portadas dinámicas.
Soporta cache en memoria (por defecto) y Redis (opcional).
"""

import json
import time
from typing import Optional, Dict, Any
from functools import lru_cache

# Cache en memoria como fallback
_memory_cache: Dict[str, Dict[str, Any]] = {}
_cache_stats = {"hits": 0, "misses": 0, "sets": 0}

# Configuración
CACHE_TTL = 3600  # 1 hora en segundos
MAX_MEMORY_CACHE_SIZE = 1000  # Máximo número de entradas en cache de memoria

# Intentar importar Redis (opcional)
try:
    import redis
    redis_client = None
    try:
        redis_client = redis.Redis(
            host='localhost', 
            port=6379, 
            db=0, 
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1
        )
        # Test de conexión
        redis_client.ping()
        print("✅ Redis conectado para cache de portadas")
    except:
        redis_client = None
        print("ℹ️ Redis no disponible, usando cache en memoria")
except ImportError:
    redis_client = None
    print("ℹ️ Redis no instalado, usando cache en memoria")

def _clean_memory_cache():
    """Limpiar cache en memoria si supera el tamaño máximo"""
    if len(_memory_cache) > MAX_MEMORY_CACHE_SIZE:
        # Eliminar las entradas más antiguas (simple FIFO)
        items_to_remove = len(_memory_cache) - MAX_MEMORY_CACHE_SIZE + 100
        keys_to_remove = list(_memory_cache.keys())[:items_to_remove]
        for key in keys_to_remove:
            del _memory_cache[key]

def get_poster_cache(key: str) -> Optional[str]:
    """Obtener portada del cache"""
    global _cache_stats
    
    # Intentar Redis primero
    if redis_client:
        try:
            cached = redis_client.get(f"poster:{key}")
            if cached:
                _cache_stats["hits"] += 1
                return cached
        except:
            pass  # Fallback a memoria
    
    # Fallback a cache en memoria
    if key in _memory_cache:
        entry = _memory_cache[key]
        # Verificar TTL
        if time.time() - entry["timestamp"] < CACHE_TTL:
            _cache_stats["hits"] += 1
            return entry["value"]
        else:
            del _memory_cache[key]
    
    _cache_stats["misses"] += 1
    return None

def set_poster_cache(key: str, value: str) -> None:
    """Guardar portada en cache"""
    global _cache_stats
    _cache_stats["sets"] += 1
    
    # Intentar Redis primero
    if redis_client:
        try:
            redis_client.setex(f"poster:{key}", CACHE_TTL, value)
            return
        except:
            pass  # Fallback a memoria
    
    # Fallback a cache en memoria
    _clean_memory_cache()
    _memory_cache[key] = {
        "value": value,
        "timestamp": time.time()
    }

def get_batch_poster_cache(keys: list) -> Dict[str, Optional[str]]:
    """Obtener múltiples portadas del cache"""
    result = {}
    
    # Intentar Redis primero (más eficiente para batch)
    if redis_client:
        try:
            redis_keys = [f"poster:{key}" for key in keys]
            cached_values = redis_client.mget(redis_keys)
            for i, key in enumerate(keys):
                result[key] = cached_values[i]
            return result
        except:
            pass  # Fallback a memoria
    
    # Fallback a cache en memoria
    for key in keys:
        result[key] = get_poster_cache(key)
    
    return result

def set_batch_poster_cache(data: Dict[str, str]) -> None:
    """Guardar múltiples portadas en cache"""
    if redis_client:
        try:
            pipe = redis_client.pipeline()
            for key, value in data.items():
                pipe.setex(f"poster:{key}", CACHE_TTL, value)
            pipe.execute()
            return
        except:
            pass  # Fallback a memoria
    
    # Fallback a cache en memoria
    for key, value in data.items():
        set_poster_cache(key, value)

def clear_poster_cache() -> Dict[str, int]:
    """Limpiar todo el cache de portadas"""
    global _memory_cache, _cache_stats
    
    cleared_count = 0
    
    # Limpiar Redis
    if redis_client:
        try:
            keys = redis_client.keys("poster:*")
            if keys:
                cleared_count += redis_client.delete(*keys)
        except:
            pass
    
    # Limpiar memoria
    memory_count = len(_memory_cache)
    _memory_cache.clear()
    cleared_count += memory_count
    
    return {
        "cleared": cleared_count,
        "cache_stats": _cache_stats.copy()
    }

def get_cache_stats() -> Dict[str, Any]:
    """Obtener estadísticas del cache"""
    stats = _cache_stats.copy()
    stats["memory_cache_size"] = len(_memory_cache)
    
    if redis_client:
        try:
            redis_keys = redis_client.keys("poster:*")
            stats["redis_cache_size"] = len(redis_keys)
            stats["redis_connected"] = True
        except:
            stats["redis_connected"] = False
    else:
        stats["redis_connected"] = False
    
    # Calcular hit rate
    total_requests = stats["hits"] + stats["misses"]
    stats["hit_rate"] = (stats["hits"] / total_requests * 100) if total_requests > 0 else 0
    
    return stats

@lru_cache(maxsize=128)
def get_cache_key(media_id: int, language: str, tmdb_id: Optional[int] = None) -> str:
    """Generar clave de cache consistente"""
    if tmdb_id:
        return f"tmdb_{tmdb_id}_{language}"
    return f"media_{media_id}_{language}"
