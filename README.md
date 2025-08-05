# 🎬 Mi Catálogo - Backend

Backend API para la aplicación de gestión de películas y series con sistema de traducciones inteligente.

## 🚀 Características

- **🎯 API RESTful** - FastAPI con documentación automática
- **🌐 Sistema de traducciones** - Caché inteligente con TMDb API
- **🗄️ Base de datos** - PostgreSQL en Supabase
- **📊 Gestión completa** - Películas, series, listas, tags y favoritos
- **🔍 Búsqueda avanzada** - Por título, director, actor y género
- **⚡ Optimizado** - Cache en memoria y base de datos

## 🏗️ Arquitectura

```
Frontend (React) ──→ Backend (FastAPI) ──→ Supabase (PostgreSQL)
                            │
                            ├──→ TMDb API (traducciones)
                            └──→ Cache (memoria + BD)
```

## 📋 Endpoints Principales

### 🎬 Medios
- `GET /medias` - Listar películas/series con filtros
- `POST /medias` - Añadir nuevo medio
- `GET /medias/{id}` - Obtener detalles de un medio
- `PUT /medias/{id}` - Actualizar medio
- `DELETE /medias/{id}` - Eliminar medio

### 🔍 Búsqueda
- `GET /search?q={query}` - Búsqueda por título, director o actor
- `GET /medias/{id}/similares` - Medios similares

### 🌐 Traducciones ⭐ **NUEVO**
- `GET /translations/{media_id}?language=en` - Obtener traducción
- `POST /translations/{media_id}/cache?language=en` - Cachear traducción
- `GET /translations/cache/stats` - Estadísticas del caché
- `DELETE /translations/cache/clear` - Limpiar caché

### 📝 Listas y Tags
- `GET /listas` - Obtener listas personalizadas
- `POST /listas` - Crear nueva lista
- `GET /tags` - Obtener tags disponibles

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
- **Base de datos**: PostgreSQL (Supabase)
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
├── database.py            # 🔌 Configuración de BD
├── translation_service.py # 🌐 Servicio de traducciones
├── requirements.txt       # 📦 Dependencias
└── .env                   # 🔑 Variables de entorno
```

## ⚙️ Configuración

### 🔧 Variables de Entorno

```env
DATABASE_URL=postgresql://user:password@host:port/database
TMDB_API_KEY=tu_api_key_de_tmdb
```

### 📦 Instalación

```bash
# Instalar dependencias
pip install -r requirements.txt

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
- **Base de datos**: Conexiones pooled con SSL

## 🤝 Contribución

1. Fork del repositorio
2. Crear feature branch
3. Commit con mensajes descriptivos
4. Push y crear Pull Request

---

**🌟 Hecho con amor para gestionar tu catálogo de películas y series**

Backend URL: `https://mi-catalogo-backend.onrender.com`
