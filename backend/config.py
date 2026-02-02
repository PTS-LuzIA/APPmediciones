"""
Configuración de APPmediciones Backend
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuración de la aplicación"""

    # Entorno
    ENV: str = "development"  # development | production

    # API
    API_TITLE: str = "APPmediciones API"
    API_VERSION: str = "1.0.0"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8005

    # Base de datos
    DATABASE_URL: str = "postgresql://imac@localhost:5432/appmediciones_db"

    # JWT
    JWT_SECRET: str = "dev-secret-key-change-in-production-12345"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_MINUTES: int = 480  # 8 horas

    # CORS
    CORS_ORIGINS: list = [
        "http://localhost:3016",
    ]

    # Paths
    BASE_DIR: Path = Path(__file__).parent  # backend/
    UPLOADS_DIR: Path = BASE_DIR / "uploads"
    LOGS_DIR: Path = BASE_DIR / "logs"

    # Logging
    LOG_LEVEL: str = "DEBUG"  # DEBUG | INFO | WARNING | ERROR
    LOG_FORMAT: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Límites
    MAX_UPLOAD_SIZE: int = 50 * 1024 * 1024  # 50 MB
    MAX_FILE_PAGES: int = 500  # Máximo de páginas en PDF

    # AI / LLM Services
    ANTHROPIC_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True


# Instancia global de configuración
settings = Settings()

# Crear directorios si no existen
settings.UPLOADS_DIR.mkdir(exist_ok=True, parents=True)
settings.LOGS_DIR.mkdir(exist_ok=True, parents=True)
