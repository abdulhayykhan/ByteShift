import os
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import List


class Settings:
    """Application configuration settings."""
    BASE_DIR: Path = Path(__file__).resolve().parent
    STATIC_DIR: Path = BASE_DIR / "static"
    TEMPLATES_DIR: Path = BASE_DIR / "templates"
    
    # Application
    APP_NAME: str = os.getenv("APP_NAME", "ByteShift")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # CORS
    CORS_ORIGINS: List[str] = os.getenv(
        "CORS_ORIGINS", 
        "http://localhost:3000,http://127.0.0.1:3000"
    ).split(",")
    CORS_ALLOW_CREDENTIALS: bool = os.getenv("CORS_ALLOW_CREDENTIALS", "True").lower() == "true"
    
    # File Upload Limits (in bytes)
    MAX_UPLOAD_SIZE_IMAGE: int = int(os.getenv("MAX_UPLOAD_SIZE_IMAGE", "50")) * 1024 * 1024
    MAX_UPLOAD_SIZE_DOCUMENT: int = int(os.getenv("MAX_UPLOAD_SIZE_DOCUMENT", "100")) * 1024 * 1024
    MAX_UPLOAD_SIZE_AUDIO: int = int(os.getenv("MAX_UPLOAD_SIZE_AUDIO", "500")) * 1024 * 1024
    MAX_UPLOAD_SIZE_VIDEO: int = int(os.getenv("MAX_UPLOAD_SIZE_VIDEO", "2048")) * 1024 * 1024
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    ALLOWED_HOSTS: List[str] = os.getenv("ALLOWED_HOSTS", "*").split(",")
    
    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "/tmp/byteshift.log")

    # Filesystem
    TEMP_DIR: str = os.getenv("BYTESHIFT_TEMP_DIR", "/tmp")
    
    # Worker Configuration
    WORKERS: int = int(os.getenv("WORKERS", "4"))
    WORKER_CLASS: str = os.getenv("WORKER_CLASS", "uvicorn.workers.UvicornWorker")
    TIMEOUT: int = int(os.getenv("TIMEOUT", "300"))


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()


def _is_writable_directory(path: Path) -> bool:
    """Return True if the path exists and the process can write to it."""
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = tempfile.NamedTemporaryFile(dir=str(path), delete=True)
        probe.close()
        return True
    except Exception:
        return False


def configure_runtime() -> None:
    """Configure runtime filesystem paths for read-only deployment environments."""
    preferred = Path(settings.TEMP_DIR).expanduser()
    if _is_writable_directory(preferred):
        tempfile.tempdir = str(preferred)
        return

    fallback = Path(tempfile.gettempdir())
    fallback.mkdir(parents=True, exist_ok=True)
    tempfile.tempdir = str(fallback)
