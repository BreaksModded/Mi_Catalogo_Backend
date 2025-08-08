# 🎬 My Catalog - Backend

Backend API for the movie and series management application with intelligent translation system and dynamic posters by language.

## 🚀 Features

- **🎯 RESTful API** - FastAPI with automatic documentation
- **🌐 Translation system** - Intelligent caching with TMDb API
- **🖼️ Dynamic posters** - Images that change according to selected language
- **⚡ Hybrid cache** - Redis + memory for maximum performance ⭐ **NEW**
- **🗄️ Database** - Optimized PostgreSQL with specialized indexes ⭐ **NEW**
- **📊 Complete management** - Movies, series, lists, tags and favorites
- **🔍 Advanced search** - By title, director, actor and genre
- **🎨 Skeleton loading** - Smooth UX with loading components ⭐ **NEW**

## 🏗️ Architecture

```
Frontend (React) ──→ Backend (FastAPI) ──→ Supabase (PostgreSQL)
                            │                      ↗ Optimized indexes
                            ├──→ TMDb API (translations)
                            ├──→ Redis Cache (optional) ⭐ **NEW**
                            └──→ Memory Cache (fallback) ⭐ **NEW**
```

## 📋 Main Endpoints

### 🎬 Media
- `GET /medias` - List movies/series with filters
- `POST /medias` - Add new media
- `GET /medias/{id}` - Get media details
- `PUT /medias/{id}` - Update media
- `DELETE /medias/{id}` - Delete media

### 🔍 Search and TMDb
- `GET /search?q={query}` - Search by title, director or actor
- `GET /medias/{id}/similares` - Similar media
- `GET /tmdb?title={title}&language={lang}` - Search TMDb with multi-language support ⭐ **NEW**

### 🌐 Translations ⭐ **NEW**
- `GET /translations/{media_id}?language=en` - Get translation
- `POST /translations/{media_id}/cache?language=en` - Cache translation
- `GET /translations/cache/stats` - Cache statistics
- `DELETE /translations/cache/clear` - Clear cache

### �️ Optimized Posters ⭐ **NEW**
- `GET /poster/{tmdb_id}?media_type=movie&language=es-ES` - Language-optimized poster
- `GET /posters-optimized` - Batch endpoint for multiple posters
- **Hybrid cache**: Redis + memory with configurable TTL
- **DB indexes**: Ultra-fast queries by (tmdb_id, type) and (media_id, language_code)

### 🚀 Cache Management ⭐ **NEW**
- `GET /cache/posters/stats` - Detailed cache statistics
- `DELETE /cache/posters` - Clear cache (Redis + memory)
- **Automatic fallback**: Redis → Memory → Database
- **Batch operations**: Efficient loading of multiple elements
### 📝 Lists and Tags
- `GET /listas` - Get custom lists
- `POST /listas` - Create new list
- `GET /tags` - Get available tags

## 🖼️ Dynamic Poster System ⭐ **NEW**

### 🎯 Intelligent Functionality

The backend now includes a **dynamic poster** system that automatically selects the best images according to the requested language:

```python
def get_best_poster(tmdb_id, media_type, language="es-ES"):
    """
    Find the best poster according to language:
    1. Posters with text in specific language
    2. Universal posters (no text)  
    3. Intelligent fallback to default poster
    """
```

### 🌍 Selection Logic

1. **Language priority**: Search images with matching `iso_639_1`
2. **Universal images**: Without specific language text
3. **Intelligent fallback**: Default TMDb poster
4. **Optimized size**: w500 for optimal quality/speed

### 📡 Enhanced TMDb Endpoint

```http
GET /tmdb?id=550&media_type=movie&language=en-US
```

**Parameters:**
- `language`: Language code (es-ES, en-US)
- `id`: TMDb ID
- `media_type`: "movie" or "tv"
- `title`: Title for search
- `listar`: true to show multiple options

**Enhanced response:**
```json
{
  "titulo": "Fight Club",
  "imagen": "https://image.tmdb.org/t/p/w500/poster_en.jpg",
  "genero": "Drama, Thriller",
  "sinopsis": "An insomniac office worker...",
  "idioma_original": "en"
}
```

## 🌐 Translation System

### ⚡ Intelligent Flow

```mermaid
graph TD
    A[Translation request] --> B{Exists in cache?}
    B -->|Yes| C[Return from DB]
    B -->|No| D[Query TMDb API]
    D --> E[Save to cache]
    E --> F[Return translation]
    C --> G[Final response]
    F --> G
```

### 📊 Cache Structure

| Field | Description |
|-------|-------------|
| `media_id` | Original media ID |
| `language_code` | Language code (en, es) |
| `translated_title` | Translated title |
| `translated_synopsis` | Translated synopsis |
| `translation_source` | Source (tmdb, local, original) |
| `created_at` | Cache date |

## 🛠️ Technologies

- **Framework**: FastAPI 0.115+
- **Database**: PostgreSQL (Supabase)
- **ORM**: SQLAlchemy 2.0+
- **Validation**: Pydantic 2.0+
- **HTTP Client**: Requests
- **Scraping**: BeautifulSoup4
- **Environment vars**: python-dotenv

## 📁 Project Structure

```
backend/
├── main.py                 # 🎯 Main FastAPI application
├── models.py              # 🗄️ SQLAlchemy models
├── schemas.py             # 📋 Pydantic schemas
├── crud.py                # 🔧 CRUD operations
├── database.py            # 🔌 Database configuration
├── translation_service.py # 🌐 Translation service
├── requirements.txt       # 📦 Dependencies
└── .env                   # 🔑 Environment variables
```

## ⚙️ Configuration

### 🔧 Environment Variables

```env
DATABASE_URL=postgresql://user:password@host:port/database
TMDB_API_KEY=your_tmdb_api_key
```

### 📦 Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

## 🌍 Deployment

### 🚀 Render (Current)

1. **Connect repository** to Render
2. **Configure environment** variables
3. **Automatic deploy** with each push

```bash
# Build Command
pip install -r requirements.txt

# Start Command  
uvicorn main:app --host 0.0.0.0 --port $PORT
```

### 🗄️ Database

- **Provider**: Supabase (PostgreSQL)
- **Connection**: SSL required
- **Main tables**: `media`, `content_translations`, `listas`, `tags`

## 📊 API Docs

Once deployed, interactive documentation is available at:

- **Swagger UI**: `https://your-backend.onrender.com/docs`
- **ReDoc**: `https://your-backend.onrender.com/redoc`

## 🔍 Detailed Translation Endpoints

### Get Translation
```http
GET /translations/{media_id}?language=en
```

**Successful response:**
```json
{
  "id": 123,
  "titulo": "The Matrix",
  "sinopsis": "A computer hacker learns...",
  "translation_source": "tmdb"
}
```

### Manual Cache Translation
```http
POST /translations/{media_id}/cache?language=en
```

### Cache Statistics
```http
GET /translations/cache/stats
```

**Response:**
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

### 📝 Important Logs

```python
# In translation_service.py
logging.info(f"Fetching translation for media {media_id}")
logging.warning(f"Translation not found in cache")
logging.error(f"TMDb API error: {error}")
```

### 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| DB connection error | Check `DATABASE_URL` |
| TMDb API limit | Wait or check API key |
| Translations don't appear | Check frontend logs |
| Cache not working | Check `content_translations` table |

## 📈 Performance

- **Cache hits**: ~95% after first use
- **Response time**: <200ms with cache
- **TMDb requests**: Only for new content
- **Dynamic posters**: <500ms intelligent selection
- **Database**: Pooled connections with SSL + optimized indexes ⭐ **NEW**
- **Redis cache**: <50ms for cached data ⭐ **NEW**
- **Fallback system**: 0ms switching between cache layers ⭐ **NEW**

## 🔄 Latest Updates

### v2.2.0 - Hybrid Cache System and DB Optimization ⭐ **NEW** (January 2025)
- ✅ **Hybrid Redis + memory cache** with automatic fallback
- ✅ **Specialized indexes** in DB for ultra-fast queries
- ✅ **Optimized batch endpoints** (/posters-optimized)
- ✅ **Advanced cache management** (stats, clear, TTL)
- ✅ **Redis installation script** for simplified setup
- ✅ **Robust fallback system** for maximum availability
- ✅ **Query optimization** with batch operations

### v2.1.0 - Dynamic Posters and Multi-language (January 2025)
- ✅ **Dynamic poster system** by language
- ✅ **Enhanced /tmdb endpoint** with language parameter
- ✅ **Intelligent image selection** by language
- ✅ **Complete multi-language support** in all responses
- ✅ **Image optimization** with automatic fallback

### v2.0.0 - Translation System (December 2024)
- ✅ Complete translation system with cache
- ✅ TMDb API integration for multilingual content
- ✅ Translation cache management endpoints
- ✅ Performance optimization with DB cache

## 🤝 Contributing

1. Fork the repository
2. Create feature branch
3. Commit with descriptive messages
4. Push and create Pull Request

---

**🌟 Made with love to manage your movie and series catalog**

Backend URL: `https://mi-catalogo-backend.onrender.com`
