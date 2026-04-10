"""
Router para Vacacion y DetalleVacacion - Endpoints REST para gestión de vacaciones.
"""

from datetime import date
from typing import List, Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, Query, Body, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.attendance.vacaciones import services
from app.features.attendance.vacaciones.schemas import (
    VacacionCreate,
    VacacionUpdate,
    VacacionResponse,
    DetalleVacacionCreate,
    DetalleVacacionUpdate,
    DetalleVacacionResponse,
    CambiarEstadoRequest,
    TipoVacacionEnum,
    EstadoDetalleVacacionEnum
)

router = APIRouter(prefix="/vacaciones", tags=["Vacaciones"])


# ===== ENDPOINTS PARA VACACION =====

@router.post(
    "/",
    response_model=VacacionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear registro de vacación"
)
def crear_vacacion(
    data: VacacionCreate,
    db: Session = Depends(get_db)
):
    """
    Crea un nuevo registro de vacación para un empleado y gestión.

    **Normalmente este endpoint es llamado automáticamente por el worker de fin de año.**

    Validaciones:
    - No puede haber duplicados (id_empleado, gestion)
    - horas_correspondientes debe calcularse con fn_horas_vacacion_lgt
    """
    return services.crear_vacacion(db, data)


@router.get(
    "/{id:int}",
    response_model=VacacionResponse,
    summary="Obtener vacación por ID"
)
def obtener_vacacion(
    id: int,
    db: Session = Depends(get_db)
):
    """Obtiene un registro de vacación específico por su ID."""
    return services.obtener_vacacion(db, id)


@router.get(
    "/empleado/{id_empleado}/gestion/{gestion}",
    response_model=Optional[VacacionResponse],
    summary="Obtener vacación de empleado por gestión"
)
def obtener_vacacion_empleado_gestion(
    id_empleado: int,
    gestion: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene el registro de vacación de un empleado para una gestión específica.

    Retorna None si no existe el registro para esa combinación.
    """
    return services.obtener_vacacion_por_empleado_gestion(db, id_empleado, gestion)


@router.get(
    "/",
    response_model=List[VacacionResponse],
    summary="Listar vacaciones con filtros"
)
def listar_vacaciones(
    id_empleado: Optional[int] = Query(None, description="Filtrar por empleado"),
    gestion: Optional[int] = Query(None, description="Filtrar por año"),
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: int = Query(100, ge=1, le=500, description="Límite de registros"),
    db: Session = Depends(get_db)
):
    """
    Lista registros de vacaciones con filtros opcionales.

    **Filtros disponibles:**
    - `id_empleado`: filtrar por empleado específico
    - `gestion`: filtrar por año
    """
    return services.listar_vacaciones(
        db,
        id_empleado=id_empleado,
        gestion=gestion,
        skip=skip,
        limit=limit
    )


@router.put(
    "/{id:int}",
    response_model=VacacionResponse,
    summary="Actualizar registro de vacación"
)
def actualizar_vacacion(
    id: int,
    data: VacacionUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualiza los datos de un registro de vacación existente.

    Permite modificar las horas de goce/sin goce de haber y observaciones.
    """
    return services.actualizar_vacacion(db, id, data)


@router.delete(
    "/{id:int}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar vacación (CASCADE)"
)
def eliminar_vacacion(
    id: int,
    db: Session = Depends(get_db)
):
    """
    Elimina un registro de vacación y todos sus detalles asociados (CASCADE).

    **ADVERTENCIA:** Esta acción elimina también todos los DetalleVacacion asociados.
    Solo usar en caso de error o para pruebas.
    """
    services.eliminar_vacacion(db, id)
    return None


@router.post(
    "/{id:int}/incrementar-horas",
    response_model=VacacionResponse,
    summary="Incrementar horas de vacación"
)
def incrementar_horas(
    id: int,
    horas: Decimal = Body(..., embed=True, gt=0, description="Horas a incrementar"),
    tipo: str = Body("goce_haber", embed=True, description="Tipo: 'goce_haber' o 'sin_goce_haber'"),
    db: Session = Depends(get_db)
):
    """
    Incrementa las horas de vacación de un registro.

    **Casos de uso:**
    - Transferencia de beneficio de cumpleaños (+4h goce de haber)
    - Compensación por trabajo en feriado (horas variables)

    **Parámetros:**
    - `horas`: cantidad de horas a sumar
    - `tipo`: 'goce_haber' (default) o 'sin_goce_haber'
    """
    return services.incrementar_horas(db, id, horas, tipo)


# ===== ENDPOINTS PARA DETALLE_VACACION =====

@router.post(
    "/{id_vacacion}/detalles",
    response_model=DetalleVacacionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear solicitud de vacación"
)
def crear_detalle_vacacion(
    id_vacacion: int,
    data: DetalleVacacionCreate,
    db: Session = Depends(get_db)
):
    """
    Crea una nueva solicitud de vacación para un registro de vacación.

    **Validaciones:**
    - fecha_fin debe ser >= fecha_inicio
    - horas_habiles debe ser > 0
    - El empleado debe tener suficientes horas disponibles
    - El registro de vacación debe existir

    **Estado inicial:** solicitado (requiere aprobación)
    """
    return services.crear_detalle_vacacion(db, id_vacacion, data)


@router.get(
    "/detalles/{id:int}",
    response_model=DetalleVacacionResponse,
    summary="Obtener detalle de vacación por ID"
)
def obtener_detalle_vacacion(
    id: int,
    db: Session = Depends(get_db)
):
    """Obtiene un detalle de vacación específico por su ID."""
    return services.obtener_detalle_vacacion(db, id)


@router.get(
    "/{id_vacacion}/detalles",
    response_model=List[DetalleVacacionResponse],
    summary="Listar detalles de una vacación"
)
def listar_detalles_vacacion(
    id_vacacion: int,
    estado: Optional[EstadoDetalleVacacionEnum] = Query(None, description="Filtrar por estado"),
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: int = Query(100, ge=1, le=500, description="Límite de registros"),
    db: Session = Depends(get_db)
):
    """
    Lista todos los detalles de vacación asociados a un registro de vacación.

    **Filtros disponibles:**
    - `estado`: solicitado, aprobado, tomado, rechazado, cancelado
    """
    return services.listar_detalles_por_vacacion(
        db,
        id_vacacion=id_vacacion,
        estado=estado,
        skip=skip,
        limit=limit
    )


@router.get(
    "/detalles/",
    response_model=List[DetalleVacacionResponse],
    summary="Listar todos los detalles con filtros"
)
def listar_todos_detalles(
    id_empleado: Optional[int] = Query(None, description="Filtrar por empleado"),
    estado: Optional[EstadoDetalleVacacionEnum] = Query(None, description="Filtrar por estado"),
    tipo_vacacion: Optional[TipoVacacionEnum] = Query(None, description="Filtrar por tipo"),
    fecha_desde: Optional[date] = Query(None, description="Filtrar desde fecha"),
    fecha_hasta: Optional[date] = Query(None, description="Filtrar hasta fecha"),
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: int = Query(100, ge=1, le=500, description="Límite de registros"),
    db: Session = Depends(get_db)
):
    """
    Lista todos los detalles de vacación con filtros opcionales.

    **Filtros disponibles:**
    - `id_empleado`: filtrar por empleado específico
    - `estado`: solicitado, aprobado, tomado, rechazado, cancelado
    - `tipo_vacacion`: goce_de_haber, sin_goce_de_haber, licencia_accidente
    - `fecha_desde` y `fecha_hasta`: rango de fechas de inicio
    """
    return services.listar_todos_detalles(
        db,
        id_empleado=id_empleado,
        estado=estado,
        tipo_vacacion=tipo_vacacion,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        skip=skip,
        limit=limit
    )


@router.get(
    "/detalles/pendientes",
    response_model=List[DetalleVacacionResponse],
    summary="Listar solicitudes pendientes de aprobación"
)
def listar_detalles_pendientes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """
    Lista todas las solicitudes de vacación pendientes de aprobación.

    **Útil para supervisores y RRHH** para revisar solicitudes.
    """
    return services.listar_detalles_pendientes(db, skip, limit)


@router.put(
    "/detalles/{id:int}",
    response_model=DetalleVacacionResponse,
    summary="Actualizar detalle de vacación"
)
def actualizar_detalle_vacacion(
    id: int,
    data: DetalleVacacionUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualiza un detalle de vacación existente.

    **Restricción:** Solo se puede actualizar si está en estado 'solicitado'.
    Solicitudes aprobadas o tomadas no se pueden modificar.
    """
    return services.actualizar_detalle_vacacion(db, id, data)


@router.post(
    "/detalles/{id:int}/cambiar-estado",
    response_model=DetalleVacacionResponse,
    summary="Cambiar estado de solicitud de vacación"
)
def cambiar_estado_detalle(
    id: int,
    data: CambiarEstadoRequest,
    db: Session = Depends(get_db)
):
    """
    Cambia el estado de una solicitud de vacación.

    **Transiciones válidas:**
    - solicitado → aprobado (requiere id_aprobado_por)
    - solicitado → rechazado (requiere id_aprobado_por)
    - aprobado → tomado (cuando el empleado efectivamente toma la vacación)
    - solicitado/aprobado → cancelado (cancelación voluntaria)

    **Validaciones:**
    - Para aprobar/rechazar se requiere id_aprobado_por
    - Al aprobar se valida que haya horas disponibles
    - Al tomar se descuentan las horas del saldo
    - Al cancelar se recalcula el saldo si estaba aprobado
    """
    return services.cambiar_estado_detalle(db, id, data)


@router.delete(
    "/detalles/{id:int}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar detalle de vacación"
)
def eliminar_detalle_vacacion(
    id: int,
    db: Session = Depends(get_db)
):
    """
    Elimina un detalle de vacación.

    **Restricción:** Solo se puede eliminar si está en estado 'solicitado' o 'rechazado'.
    No se pueden eliminar solicitudes aprobadas o tomadas.
    """
    services.eliminar_detalle_vacacion(db, id)
    return None
