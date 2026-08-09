"""
Router para el override de horario personalizado de un empleado.
GET/DELETE quedan abiertos (mismo estado que el resto del backend hasta
que se active JWT); PUT y DELETE quedan detrás de require_admin() (SEMANA 9:
placeholder no-op, ver app/core/deps.py).
"""

from typing import Optional
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin
from app.features.employees.horario_personalizado import services
from app.features.employees.horario_personalizado.schemas import (
    HorarioPersonalizadoEmpleadoUpsert,
    HorarioPersonalizadoEmpleadoResponse,
)

router = APIRouter(
    prefix="/empleados",
    tags=["Horario Personalizado"]
)


@router.get(
    "/{empleado_id:int}/horario-personalizado",
    response_model=Optional[HorarioPersonalizadoEmpleadoResponse],
    summary="Obtener el horario personalizado de un empleado",
    description="Devuelve el override si existe y está activo, o null si el empleado usa el horario general"
)
def get_horario_personalizado(
    empleado_id: int,
    db: Session = Depends(get_db)
):
    """Obtiene el override activo del empleado, o null si no tiene (usa horario general)."""
    return services.get_horario_personalizado_response(db, empleado_id)


@router.put(
    "/{empleado_id:int}/horario-personalizado",
    response_model=HorarioPersonalizadoEmpleadoResponse,
    summary="Crear o actualizar el horario personalizado de un empleado",
    description="Upsert del override de horario. Solo admin. Afecta el cálculo de minutos_retraso en asistencia diaria",
    dependencies=[Depends(require_admin)],
)
def upsert_horario_personalizado(
    empleado_id: int,
    data: HorarioPersonalizadoEmpleadoUpsert,
    db: Session = Depends(get_db)
):
    """
    Crea o actualiza el override de horario del empleado.

    - **tolerancia_minutos** / **hora_entrada**: reemplazan a los del
      horario general asignado para calcular minutos_retraso.
    - **hora_salida**: solo referencial (minutos_trabajados/estadísticas),
      nunca se usa para horas_extra pagables.
    - **salida_flexible**: si TRUE, no hay hora de salida fija esperada.
    - **activo**: en FALSE equivale a no tener override (usa horario general).
    """
    return services.upsert_horario_personalizado(db, empleado_id, data)


@router.delete(
    "/{empleado_id:int}/horario-personalizado",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desactivar el horario personalizado de un empleado",
    description="Desactiva el override (activo=FALSE). Solo admin. NO borra el registro, conserva el historial",
    dependencies=[Depends(require_admin)],
)
def delete_horario_personalizado(
    empleado_id: int,
    db: Session = Depends(get_db)
):
    """Desactiva el override (soft delete). El empleado vuelve al horario general."""
    services.desactivar_horario_personalizado(db, empleado_id)
    return None
