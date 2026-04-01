"""
Router para endpoints de Horario y AsignacionHorario.
Todos los endpoints están abiertos (sin autenticación hasta Semana 9).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.employees.horario import services
from app.features.employees.horario.schemas import (
    HorarioCreate,
    HorarioUpdate,
    HorarioResponse,
    AsignacionHorarioCreate,
    AsignacionHorarioUpdate,
    AsignacionHorarioResponse
)

router = APIRouter(
    prefix="/horarios",
    tags=["Horarios y Asignaciones"]
)


# ========== HORARIO ENDPOINTS ==========

@router.post(
    "/",
    response_model=HorarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear horario",
    description="Crea un nuevo turno laboral"
)
def create_horario(
    data: HorarioCreate,
    db: Session = Depends(get_db)
):
    """
    Crea un nuevo horario.
    
    - **nombre**: Nombre descriptivo del horario
    - **hora_entrada**: Hora de entrada
    - **hora_salida**: Hora de salida
    - **tolerancia_minutos**: Minutos de gracia para retrasos
    - **jornada_semanal_horas**: Total de horas semanales (máx 48h según LGT)
    - **dias_laborables**: Array de días [1=Lun, 2=Mar, ..., 7=Dom]
    - **tipo_jornada**: continua | discontinua
    """
    return services.create_horario(db, data)


@router.get(
    "/",
    response_model=List[HorarioResponse],
    summary="Listar horarios",
    description="Obtiene todos los horarios con paginación"
)
def get_all_horarios(
    skip: int = Query(0, ge=0, description="Offset para paginación"),
    limit: int = Query(100, ge=1, le=500, description="Cantidad máxima de resultados"),
    activo_only: bool = Query(False, description="Solo horarios activos"),
    db: Session = Depends(get_db)
):
    """Lista todos los horarios con filtros opcionales."""
    return services.get_all_horarios(db, skip=skip, limit=limit, activo_only=activo_only)


@router.get(
    "/{horario_id}",
    response_model=HorarioResponse,
    summary="Obtener horario por ID",
    description="Retorna un horario específico por su ID"
)
def get_horario(
    horario_id: int,
    db: Session = Depends(get_db)
):
    """Obtiene un horario por ID."""
    horario = services.get_horario_by_id(db, horario_id)
    if not horario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el horario con id {horario_id}"
        )
    return horario


@router.put(
    "/{horario_id}",
    response_model=HorarioResponse,
    summary="Actualizar horario",
    description="Actualiza los datos de un horario existente"
)
def update_horario(
    horario_id: int,
    data: HorarioUpdate,
    db: Session = Depends(get_db)
):
    """Actualiza un horario existente."""
    return services.update_horario(db, horario_id, data)


@router.delete(
    "/{horario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar horario",
    description="Elimina (soft delete) un horario. No permite eliminar si tiene asignaciones activas."
)
def delete_horario(
    horario_id: int,
    db: Session = Depends(get_db)
):
    """
    Elimina un horario (soft delete).
    
    Validaciones:
    - No puede tener asignaciones activas
    """
    services.delete_horario(db, horario_id)
    return None


# ========== ASIGNACION HORARIO ENDPOINTS ==========

@router.post(
    "/asignaciones",
    response_model=AsignacionHorarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear asignación de horario",
    description="Asigna un horario a un empleado con vigencia temporal"
)
def create_asignacion(
    data: AsignacionHorarioCreate,
    db: Session = Depends(get_db)
):
    """
    Crea una nueva asignación de horario.
    
    - **id_empleado**: ID del empleado
    - **id_horario**: ID del horario
    - **fecha_inicio**: Fecha de inicio de vigencia
    - **fecha_fin**: Fecha de fin (NULL = indefinido)
    - **es_activo**: Estado de la asignación
    - **observacion**: Comentario opcional
    
    Validaciones:
    - No puede haber solapamiento de fechas para el mismo empleado
    """
    return services.create_asignacion_horario(db, data)


@router.get(
    "/asignaciones",
    response_model=List[AsignacionHorarioResponse],
    summary="Listar asignaciones de horario",
    description="Obtiene todas las asignaciones con paginación y filtros"
)
def get_all_asignaciones(
    skip: int = Query(0, ge=0, description="Offset para paginación"),
    limit: int = Query(100, ge=1, le=500, description="Cantidad máxima de resultados"),
    id_empleado: Optional[int] = Query(None, description="Filtrar por empleado"),
    activo_only: bool = Query(False, description="Solo asignaciones activas"),
    db: Session = Depends(get_db)
):
    """Lista todas las asignaciones con filtros opcionales."""
    return services.get_all_asignaciones(
        db,
        skip=skip,
        limit=limit,
        id_empleado=id_empleado,
        activo_only=activo_only
    )


@router.get(
    "/asignaciones/{asignacion_id}",
    response_model=AsignacionHorarioResponse,
    summary="Obtener asignación por ID",
    description="Retorna una asignación específica por su ID"
)
def get_asignacion(
    asignacion_id: int,
    db: Session = Depends(get_db)
):
    """Obtiene una asignación por ID."""
    asignacion = services.get_asignacion_by_id(db, asignacion_id)
    if not asignacion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe la asignación con id {asignacion_id}"
        )
    return asignacion


@router.put(
    "/asignaciones/{asignacion_id}",
    response_model=AsignacionHorarioResponse,
    summary="Actualizar asignación",
    description="Actualiza los datos de una asignación existente"
)
def update_asignacion(
    asignacion_id: int,
    data: AsignacionHorarioUpdate,
    db: Session = Depends(get_db)
):
    """Actualiza una asignación existente."""
    return services.update_asignacion_horario(db, asignacion_id, data)


@router.delete(
    "/asignaciones/{asignacion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar asignación",
    description="Elimina (marca como inactiva) una asignación de horario"
)
def delete_asignacion(
    asignacion_id: int,
    db: Session = Depends(get_db)
):
    """Elimina una asignación (marca como inactiva)."""
    services.delete_asignacion_horario(db, asignacion_id)
    return None
