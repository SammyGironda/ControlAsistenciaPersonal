"""
Utilidades para manejo de zonas horarias.
La Paz, Bolivia: UTC-4 (sin horario de verano)
"""

from datetime import datetime, timezone, timedelta
from typing import Optional

# Zona horaria de La Paz, Bolivia: UTC-4
LA_PAZ_TIMEZONE = timezone(timedelta(hours=-4))


def get_utc_now() -> datetime:
    """Obtiene la hora actual en UTC."""
    return datetime.now(timezone.utc)


def get_lapaz_now() -> datetime:
    """Obtiene la hora actual en La Paz."""
    return datetime.now(LA_PAZ_TIMEZONE)


def utc_to_lapaz(dt: Optional[datetime]) -> Optional[datetime]:
    """Convierte un datetime UTC a La Paz."""
    if dt is None:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(LA_PAZ_TIMEZONE)


def lapaz_to_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Convierte un datetime de La Paz a UTC."""
    if dt is None:
        return None

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=LA_PAZ_TIMEZONE)

    return dt.astimezone(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """Asegura que un datetime esté en UTC. Si no tiene zona horaria, asume UTC."""
    if dt is None:
        return None

    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)
