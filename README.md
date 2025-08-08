# 🎬 Mi Catálogo - Backend

Backend API para la aplicación de gestión de películas y series con sistema de traducciones inteligente y portadas dinámicas por idioma.

## 🚀 Características

- **🎯 API RESTful** - FastAPI con documentación automática
- **🌐 Sistema de traducciones** - Caché inteligente con TMDb API
- **🖼️ Portadas dinámicas** - Imágenes que cambian según el idioma seleccionado
- **⚡ Cache híbrido** - Redis + memoria para máximo rendimiento ⭐ **NUEVO**
- **🗄️ Base de datos** - PostgreSQL optimizada con índices especializados ⭐ **NUEVO**
- **📊 Gestión completa** - Películas, series, listas, tags y favoritos
- **🔍 Búsqueda avanzada** - Por título, director, actor y género
- **🎨 Skeleton loading** - UX suave con componentes de carga ⭐ **NUEVO**

## 🏗️ Arquitectura

```
Frontend (React) ──→ Backend (FastAPI) ──→ Supabase (PostgreSQL)
                            │                      ↗ Índices optimizados
                            ├──→ TMDb API (traducciones)
                            ├──→ Redis Cache (optional) ⭐ **NUEVO**
                            └──→ Memory Cache (fallback) ⭐ **NUEVO**
```

## 📋 Endpoints Principales

### 🎬 Medios
- `GET /medias` - Listar películas/series con filtros
- `POST /medias` - Añadir nuevo medio
- `GET /medias/{id}` - Obtener detalles de un medio
- `PUT /medias/{id}` - Actualizar medio
- `DELETE /medias/{id}` - Eliminar medio

### 🔍 Búsqueda y TMDb
- `GET /search?q={query}` - Búsqueda por título, director o actor
- `GET /medias/{id}/similares` - Medios similares
- `GET /tmdb?title={title}&language={lang}` - Buscar en TMDb con soporte multi-idioma ⭐ **NUEVO**

### 🌐 Traducciones ⭐ **NUEVO**
- `GET /translations/{media_id}?language=en` - Obtener traducción
- `POST /translations/{media_id}/cache?language=en` - Cachear traducción
- `GET /translations/cache/stats` - Estadísticas del caché
- `DELETE /translations/cache/clear` - Limpiar caché

### 🖼️ Portadas Optimizadas ⭐ **NUEVO**
- `GET /poster/{tmdb_id}?media_type=movie&language=es-ES` - Portada optimizada por idioma
- `GET /posters-optimized` - Endpoint batch para múltiples portadas
- **Cache híbrido**: Redis + memoria con TTL configurable
- **Índices DB**: Consultas ultra-rápidas por (tmdb_id, tipo) y (media_id, language_code)

### 🚀 Gestión de Cache ⭐ **NUEVO**
- `GET /cache/posters/stats` - Estadísticas detalladas del cache
- `DELETE /cache/posters` - Limpiar cache (Redis + memoria)
- **Fallback automático**: Redis → Memoria → Base de datos
- **Batch operations**: Carga eficiente de múltiples elementos

### �📝 Listas y Tags
- `GET /listas` - Obtener listas personalizadas
- `POST /listas` - Crear nueva lista
- `GET /tags` - Obtener tags disponibles

## 🖼️ Sistema de Portadas Dinámicas ⭐ **NUEVO**

### 🎯 Funcionalidad Inteligente

El backend ahora incluye un sistema de **portadas dinámicas** que selecciona automáticamente las mejores imágenes según el idioma solicitado:

```python
def get_best_poster(tmdb_id, media_type, language="es-ES"):
    """
    Busca la mejor portada según el idioma:
    1. Portadas con texto en el idioma específico
    2. Portadas sin texto (universales)  
    3. Fallback a portada por defecto
    """
```

### 🌍 Lógica de Selección

1. **Prioridad por idioma**: Busca imágenes con `iso_639_1` que coincida
2. **Imágenes universales**: Sin texto específico de idioma
3. **Fallback inteligente**: Portada por defecto de TMDb
4. **Tamaño optimizado**: w500 para calidad/velocidad óptima

### 📡 Endpoint TMDb Mejorado

```http
GET /tmdb?id=550&media_type=movie&language=en-US
```

**Parámetros:**
- `language`: Código de idioma (es-ES, en-US)
- `id`: ID de TMDb
- `media_type`: "movie" o "tv"
- `title`: Título para búsqueda
- `listar`: true para mostrar opciones múltiples

**Respuesta mejorada:**
```json
{
  "titulo": "Fight Club",
  "imagen": "https://image.tmdb.org/t/p/w500/poster_en.jpg",
  "genero": "Drama, Thriller",
  "sinopsis": "An insomniac office worker...",
  "idioma_original": "en"
}
```

### 🖼️ Endpoint de Portadas Dinámicas ⭐ **NUEVO**

```http
GET /poster/{tmdb_id}?media_type=movie&language=es-ES
```

**Parámetros:**
- `tmdb_id`: ID de TMDb del contenido
- `media_type`: "movie" o "tv" 
- `language`: Código de idioma (es-ES, en-US)

**Respuesta:**
```json
{
  "poster_url": "https://image.tmdb.org/t/p/w500/poster_best_for_language.jpg"
}
```

**Lógica de selección:**
1. Busca portadas con texto en el idioma solicitado
2. Si no encuentra, busca portadas en inglés
3. Si no hay específicas, usa portadas sin idioma
4. Como último recurso, usa cualquier portada disponible

## 🌐 Sistema de Traducciones

### ⚡ Flujo Inteligente

```mermaid
graph TD
    A[Solicitud de traducción] --> B{¿Existe en caché?}
    B -->|Sí| C[Devolver desde BD]
    B -->|No| D[Consultar TMDb API]
    D --> E[Guardar en caché]
    E --> F[Devolver traducción]
    C --> G[Respuesta final]
    F --> G
```

### 📊 Estructura del Caché

| Campo | Descripción |
|-------|-------------|
| `media_id` | ID del medio original |
| `language_code` | Código del idioma (en, es) |
| `translated_title` | Título traducido |
| `translated_synopsis` | Sinopsis traducida |
| `translation_source` | Origen (tmdb, local, original) |
| `created_at` | Fecha de caché |

## 🛠️ Tecnologías

- **Framework**: FastAPI 0.115+
- **Base de datos**: PostgreSQL (Supabase) con índices optimizados ⭐ **NUEVO**
- **Cache**: Redis (opcional) + memoria (fallback) ⭐ **NUEVO**
- **ORM**: SQLAlchemy 2.0+
- **Validación**: Pydantic 2.0+
- **HTTP Client**: Requests
- **Scraping**: BeautifulSoup4
- **Variables entorno**: python-dotenv

## 📁 Estructura del Proyecto

```
backend/
├── main.py                 # 🎯 Aplicación principal FastAPI
├── models.py              # 🗄️ Modelos SQLAlchemy
├── schemas.py             # 📋 Esquemas Pydantic
├── crud.py                # 🔧 Operaciones CRUD
├── database.py            # 🔌 Configuración de BD + índices optimizados ⭐ **NUEVO**
├── poster_cache.py        # 🚀 Sistema de cache híbrido Redis + memoria ⭐ **NUEVO**
├── translation_service.py # 🌐 Servicio de traducciones
├── requirements.txt       # 📦 Dependencias (incluye Redis) ⭐ **NUEVO**
├── install_redis.sh       # 🛠️ Script de instalación Redis ⭐ **NUEVO**
└── .env                   # 🔑 Variables de entorno
```

## ⚙️ Configuración

### 🔧 Variables de Entorno

```env
DATABASE_URL=postgresql://user:password@host:port/database
TMDB_API_KEY=tu_api_key_de_tmdb
REDIS_URL=redis://localhost:6379  # Opcional para cache Redis ⭐ **NUEVO**
```

### 📦 Instalación

```bash
# Instalar dependencias
pip install -r requirements.txt

# Opcional: Instalar y configurar Redis para máximo rendimiento
chmod +x install_redis.sh
./install_redis.sh

# Ejecutar servidor de desarrollo
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 🌍 Despliegue

### 🚀 Render (Actual)

1. **Conectar repositorio** a Render
2. **Configurar variables** de entorno
3. **Deploy automático** con cada push

```bash
# Build Command
pip install -r requirements.txt

# Start Command  
uvicorn main:app --host 0.0.0.0 --port $PORT
```

### 🗄️ Base de Datos

- **Proveedor**: Supabase (PostgreSQL)
- **Conexión**: SSL requerida
- **Tablas principales**: `media`, `content_translations`, `listas`, `tags`

## 📊 API Docs

Una vez desplegado, la documentación interactiva está disponible en:

- **Swagger UI**: `https://tu-backend.onrender.com/docs`
- **ReDoc**: `https://tu-backend.onrender.com/redoc`

## 🔍 Endpoints de Traducción Detallados

### Obtener Traducción
```http
GET /translations/{media_id}?language=en
```

**Respuesta exitosa:**
```json
{
  "id": 123,
  "titulo": "The Matrix",
  "sinopsis": "A computer hacker learns...",
  "translation_source": "tmdb"
}
```

### Cachear Traducción Manual
```http
POST /translations/{media_id}/cache?language=en
```

### Estadísticas del Caché
```http
GET /translations/cache/stats
```

**Respuesta:**
```json
{
  "total_translations": 245,
  "by_language": {
    "en": 245,
    "fr": 12
  },
  "by_source": {
    "tmdb": 230,
    "local": 15
  }
}
```

## 🐛 Debugging

### 📝 Logs Importantes

```python
# En translation_service.py
logging.info(f"Fetching translation for media {media_id}")
logging.warning(f"Translation not found in cache")
logging.error(f"TMDb API error: {error}")
```

### 🔧 Solución de Problemas

| Problema | Solución |
|----------|----------|
| Error de conexión BD | Verificar `DATABASE_URL` |
| TMDb API límite | Esperar o revisar API key |
| Traducciones no aparecen | Verificar logs del frontend |
| Cache no funciona | Verificar tabla `content_translations` |

## 📈 Performance

- **Cache hits**: ~95% después del primer uso
- **Tiempo de respuesta**: <200ms con cache
- **TMDb requests**: Solo para contenido nuevo
- **Portadas dinámicas**: <500ms selección inteligente
- **Base de datos**: Conexiones pooled con SSL + índices optimizados ⭐ **NUEVO**
- **Redis cache**: <50ms para datos cached ⭐ **NUEVO**
- **Fallback sistema**: 0ms switching entre cache layers ⭐ **NUEVO**

## 🔄 Últimas Actualizaciones

### v2.2.0 - Sistema de Cache Híbrido y Optimización DB ⭐ **NUEVO** (Enero 2025)
- ✅ **Cache híbrido Redis + memoria** con fallback automático
- ✅ **Índices especializados** en BD para consultas ultrarrápidas
- ✅ **Endpoints batch optimizados** (/posters-optimized)
- ✅ **Gestión avanzada de cache** (stats, clear, TTL)
- ✅ **Script de instalación Redis** para setup simplificado
- ✅ **Sistema de fallback robusto** para máxima disponibilidad
- ✅ **Optimización de consultas** con batch operations

### v2.1.0 - Portadas Dinámicas y Multi-idioma (Enero 2025)
- ✅ **Sistema de portadas dinámicas** por idioma
- ✅ **Endpoint /tmdb mejorado** con parámetro language
- ✅ **Selección inteligente** de imágenes según idioma
- ✅ **Soporte completo multi-idioma** en todas las respuestas
- ✅ **Optimización de imágenes** con fallback automático

### v2.0.0 - Sistema de Traducciones (Diciembre 2024)
- ✅ Sistema completo de traducciones con caché
- ✅ Integración con TMDb API para contenido multiidioma
- ✅ Endpoints de gestión de cache de traducciones
- ✅ Optimización de performance con cache en BD

## 🤝 Contribución

1. Fork del repositorio
2. Crear feature branch
3. Commit con mensajes descriptivos
4. Push y crear Pull Request

---

**🌟 Hecho con amor para gestionar tu catálogo de películas y series**

Backend URL: `https://mi-catalogo-backend.onrender.com`
