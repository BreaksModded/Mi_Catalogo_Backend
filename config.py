import os

# Optional .env support (won't crash if not installed)
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    pass

# HTTP client settings
REQUEST_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "8"))

# TMDb
# Prefer a Bearer token (v4 auth). If not provided, fall back to API key if present.
TMDB_BEARER = os.getenv("TMDB_BEARER")
TMDB_API_KEY = os.getenv("TMDB_API_KEY")
TMDB_BASE_URL = os.getenv("TMDB_BASE_URL", "https://api.themoviedb.org/3")


def get_tmdb_auth_headers():
    """Return authorization headers for TMDb, preferring Bearer token."""
    headers = {}
    if TMDB_BEARER:
        headers["Authorization"] = f"Bearer {TMDB_BEARER}"
    return headers


# CORS
ALLOWED_ORIGINS_ENV = os.getenv("ALLOWED_ORIGINS", "")

def get_allowed_origins_default():
    """Default allowed origins suitable for local dev + known prod."""
    return [
        "https://mi-catalogo-oguv.vercel.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://192.168.0.25:3000",
        "http://192.168.0.25:5173",
    ]

def get_allowed_origins():
    """Merge env-provided origins with safe defaults for dev.
    This prevents accidental removal of localhost during prod deploys.
    """
    defaults = get_allowed_origins_default()
    if not ALLOWED_ORIGINS_ENV:
        return defaults
    env_list = [o.strip() for o in ALLOWED_ORIGINS_ENV.split(",") if o.strip()]
    # Merge without duplicates, keeping env first (so ops can override order if needed)
    merged = []
    for o in env_list + defaults:
        if o not in merged:
            merged.append(o)
    return merged

def get_lan_origin_regex():
    # Allow typical LAN ranges and localhost on common dev ports
    # 192.168.x.x, 10.x.x.x, 172.16-31.x.x + localhost/127.0.0.1 on 3000 or 5173
    return r"http://((192\.168|10\.|172\.(1[6-9]|2[0-9]|3[01]))\.(\d{1,3})\.(\d{1,3})|localhost|127\.0\.0\.1):(3000|5173)"
