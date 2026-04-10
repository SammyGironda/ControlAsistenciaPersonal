"""
Servicios orquestadores del módulo attendance.
Contiene funciones utilitarias transversales para módulos de asistencia.
"""

from datetime import date
from sqlalchemy.orm import Session


def health_attendance(db: Session) -> dict:
    """Retorna estado básico del módulo de asistencia."""
    return {
        "modulo": "attendance",
        "status": "ok",
        "fecha": date.today().isoformat(),
    }
