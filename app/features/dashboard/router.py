"""
Router para endpoints de dashboard y estadisticas de asistencia.
"""

from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.dashboard import services
from app.features.dashboard.schemas import (
    CumpleanosProximoResponse,
    HorasTrabajadasMesResponse,
    RetrasoPorMesResponse,
)


router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "/retrasos-por-mes",
    response_model=List[RetrasoPorMesResponse],
    summary="Retrasos agrupados por mes",
    description="Retorna metricas de retrasos para los ultimos meses con registros",
)
def get_retrasos_por_mes(
    meses_atras: int = Query(5, ge=1, le=24, description="Cantidad de meses hacia atras"),
    db: Session = Depends(get_db),
):
    """Obtiene total de dias, dias con retraso y minutos por mes."""

    return services.get_retrasos_por_mes(db, meses_atras)


@router.get(
    "/horas-trabajadas-mes",
    response_model=HorasTrabajadasMesResponse,
    summary="Horas trabajadas por empleado en un mes",
    description="Retorna detalle por empleado y resumen global para un mes y anio",
)
def get_horas_trabajadas_mes(
    mes: int = Query(..., ge=1, le=12, description="Mes de consulta (1-12)"),
    anio: int = Query(..., ge=2000, le=2100, description="Anio de consulta"),
    db: Session = Depends(get_db),
):
    """Obtiene estadisticas de horas trabajadas del mes."""

    return services.get_horas_trabajadas_mes(db, anio, mes)


@router.get(
    "/cumpleanos-proximos",
    response_model=List[CumpleanosProximoResponse],
    summary="Cumpleanos proximos de empleados activos",
    description="Retorna cumpleanos proximos incluyendo cruce de anio",
)
def get_cumpleanos_proximos(
    dias_adelante: int = Query(30, ge=1, le=365, description="Rango de dias desde hoy"),
    db: Session = Depends(get_db),
):
    """Obtiene empleados activos que cumplen anios en los proximos dias."""

    return services.get_cumpleanos_proximos(db, dias_adelante)
