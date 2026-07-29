import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    PERMANENT_SESSION_LIFETIME = 1800  # 30 min

    if not SECRET_KEY:
        raise RuntimeError("SECRET_KEY manquant dans .env — génère-en une avec secrets.token_hex(32)")

class DevelopmentConfig(Config):
    DEBUG = True
    SESSION_COOKIE_SECURE = False  # HTTP local autorisé en dev

class ProductionConfig(Config):
    DEBUG = False
    SESSION_COOKIE_SECURE = True  # cookies uniquement sur HTTPS

config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
}
