"""
Configuración central de la aplicación.
Lee las variables de entorno desde .env usando pydantic-settings.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    """
    Configuración de la aplicación cargada desde variables de entorno.
    Pydantic valida automáticamente los tipos.
    """

    # --- Conexión a Base de Datos ---
    DATABASE_URL: str
    DB_SCHEMA: str = "rrhh"

    # --- Información de la App ---
    APP_NAME: str = "RRHH Bolivia MVP"
    APP_VERSION: str = "0.1.0"
    API_PREFIX: str = "/api/v1"

    # --- Modo Debug ---
    DEBUG: bool = False

    # --- Carpetas de Archivos ---
    UPLOAD_DIR: str = "uploads"
    REPORTS_DIR: str = "reportes_generados"

    # --- Seguridad JWT (Semana 9) ---
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # --- CORS ---
    # Lista de orígenes permitidos, separados por comas. El default es vacío
    # (ningún origen permitido): cada entorno declara los suyos en su .env, así
    # que un despliegue sin configurar nunca queda abierto por omisión.
    #
    # Se declara como str y no como list[str] a propósito: pydantic-settings
    # intenta parsear los campos de tipo lista como JSON, y un CSV plano en el
    # .env haría fallar el arranque de la app.
    ALLOWED_ORIGINS: str = ""

    @property
    def allowed_origins_list(self) -> List[str]:
        """Orígenes CORS normalizados: sin espacios sobrantes ni entradas vacías."""
        return [origen.strip() for origen in self.ALLOWED_ORIGINS.split(",") if origen.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    """
    Retorna la configuración cacheada (singleton).
    Se carga una sola vez y se reutiliza en toda la app.
    """
    return Settings()
