"""
Router orquestador del módulo attendance.
Agrupa endpoints transversales de asistencia.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.attendance import services


router = APIRouter(prefix="/attendance", tags=["Attendance"])


@router.get("/health", summary="Salud del módulo attendance")
def health_attendance(db: Session = Depends(get_db)):
    """Estado operativo del módulo de asistencia."""
    return services.health_attendance(db)
