"""
Router para JustificacionAusencia - Endpoints REST para gestión de permisos y licencias.
"""

from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.attendance.justificacion import services
from app.features.attendance.justificacion.schemas import (
    JustificacionAusenciaCreate,
    JustificacionAusenciaUpdate,
    JustificacionAusenciaResponse,
    AprobacionRequest,
    TipoJustificacionEnum,
    EstadoAprobacionEnum
)

router = APIRouter(prefix="/justificaciones", tags=["Justificaciones de Ausencia"])


@router.post(
    "/",
    response_model=JustificacionAusenciaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nueva justificación de ausencia"
)
def crear_justificacion(
    data: JustificacionAusenciaCreate,
    db: Session = Depends(get_db)
):
    """
    Crea una nueva solicitud de permiso, licencia o vacación por horas.

    **Validaciones:**
    - Si es_por_horas=TRUE, hora_inicio y hora_fin son obligatorios
    - fecha_fin debe ser >= fecha_inicio
    - El sistema calcula automáticamente total_horas_permiso

    **Estado inicial:** pendiente (requiere aprobación)
    """
    return services.crear_justificacion(db, data)


@router.get(
    "/{id}",
    response_model=JustificacionAusenciaResponse,
    summary="Obtener justificación por ID"
)
def obtener_justificacion(
    id: int,
    db: Session = Depends(get_db)
):
    """Obtiene una justificación específica por su ID."""
    return services.obtener_justificacion(db, id)


@router.get(
    "/",
    response_model=List[JustificacionAusenciaResponse],
    summary="Listar justificaciones con filtros"
)
def listar_justificaciones(
    id_empleado: Optional[int] = Query(None, description="Filtrar por empleado"),
    tipo_justificacion: Optional[TipoJustificacionEnum] = Query(None, description="Filtrar por tipo"),
    estado_aprobacion: Optional[EstadoAprobacionEnum] = Query(None, description="Filtrar por estado"),
    fecha_desde: Optional[date] = Query(None, description="Filtrar desde fecha"),
    fecha_hasta: Optional[date] = Query(None, description="Filtrar hasta fecha"),
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: int = Query(100, ge=1, le=500, description="Límite de registros"),
    db: Session = Depends(get_db)
):
    """
    Lista justificaciones con filtros opcionales.

    **Filtros disponibles:**
    - `id_empleado`: filtrar por empleado específico
    - `tipo_justificacion`: permiso_personal, licencia_medica_accidente, cumpleanos, vacacion_por_horas
    - `estado_aprobacion`: pendiente, aprobado, rechazado
    - `fecha_desde` y `fecha_hasta`: rango de fechas
    """
    return services.listar_justificaciones(
        db,
        id_empleado=id_empleado,
        tipo_justificacion=tipo_justificacion,
        estado_aprobacion=estado_aprobacion,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        skip=skip,
        limit=limit
    )


@router.get(
    "/pendientes/aprobacion",
    response_model=List[JustificacionAusenciaResponse],
    summary="Listar justificaciones pendientes de aprobación"
)
def listar_pendientes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """
    Lista todas las justificaciones pendientes de aprobación.

    **Útil para supervisores y RRHH** para revisar solicitudes.
    """
    return services.listar_pendientes_de_aprobacion(db, skip, limit)


@router.post(
    "/{id}/aprobar",
    response_model=JustificacionAusenciaResponse,
    summary="Aprobar o rechazar justificación"
)
def aprobar_rechazar(
    id: int,
    data: AprobacionRequest,
    db: Session = Depends(get_db)
):
    """
    Aprueba o rechaza una justificación pendiente.

    **Requisitos:**
    - La justificación debe estar en estado 'pendiente'
    - Se requiere el ID del aprobador
    - Opcionalmente se pueden agregar observaciones

    **Efecto:**
    - Cambia el estado a 'aprobado' o 'rechazado'
    - Registra fecha de aprobación
    - Registra quién aprobó/rechazó
    """
    return services.aprobar_o_rechazar(db, id, data)


@router.put(
    "/{id}",
    response_model=JustificacionAusenciaResponse,
    summary="Actualizar justificación"
)
def actualizar_justificacion(
    id: int,
    data: JustificacionAusenciaUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualiza una justificación existente.

    **Restricción:** Solo se puede actualizar si está en estado 'pendiente'.
    Justificaciones aprobadas o rechazadas no se pueden modificar.
    """
    return services.actualizar_justificacion(db, id, data)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar justificación"
)
def eliminar_justificacion(
    id: int,
    db: Session = Depends(get_db)
):
    """
    Elimina una justificación.

    **Restricción:** Solo se puede eliminar si está en estado 'pendiente'.
    """
    services.eliminar_justificacion(db, id)
    return None
