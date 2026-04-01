"""
Services (lógica de negocio) para Horario y AsignacionHorario.
Operaciones CRUD + validación de solapamientos y horario vigente.
"""

from typing import List, Optional
from datetime import date, datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_
from fastapi import HTTPException, status

from app.features.employees.horario.models import Horario, AsignacionHorario
from app.features.employees.horario.schemas import (
    HorarioCreate,
    HorarioUpdate,
    HorarioResponse,
    AsignacionHorarioCreate,
    AsignacionHorarioUpdate,
    AsignacionHorarioResponse,
    AsignacionHorarioConDetalle
)


# ========== HORARIO SERVICES ==========

def create_horario(db: Session, data: HorarioCreate) -> Horario:
    """Crea un nuevo horario."""
    horario = Horario(**data.model_dump())
    db.add(horario)
    db.commit()
    db.refresh(horario)
    return horario


def get_horario_by_id(db: Session, horario_id: int) -> Optional[Horario]:
    """Obtiene un horario por ID."""
    return db.query(Horario).filter(Horario.id == horario_id).first()


def get_all_horarios(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    activo_only: bool = False
) -> List[Horario]:
    """
    Obtiene todos los horarios con paginación.
    
    Args:
        skip: Offset para paginación
        limit: Cantidad máxima de resultados
        activo_only: Si TRUE, solo devuelve horarios activos
    """
    query = db.query(Horario)
    
    if activo_only:
        query = query.filter(Horario.activo == True)
    
    return query.offset(skip).limit(limit).all()


def update_horario(
    db: Session,
    horario_id: int,
    data: HorarioUpdate
) -> Horario:
    """Actualiza un horario existente."""
    horario = get_horario_by_id(db, horario_id)
    if not horario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el horario con id {horario_id}"
        )
    
    # Aplicar cambios
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(horario, field, value)
    
    db.commit()
    db.refresh(horario)
    return horario


def delete_horario(db: Session, horario_id: int) -> bool:
    """
    Elimina un horario (soft delete).
    
    Validaciones:
    - No se puede eliminar si tiene asignaciones activas
    """
    horario = get_horario_by_id(db, horario_id)
    if not horario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el horario con id {horario_id}"
        )
    
    # Validar que no tenga asignaciones activas
    asignaciones_count = db.query(AsignacionHorario).filter(
        AsignacionHorario.id_horario == horario_id,
        AsignacionHorario.es_activo == True
    ).count()
    
    if asignaciones_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede eliminar el horario porque tiene {asignaciones_count} asignación(es) activa(s)"
        )
    
    # Realizar soft delete
    horario.activo = False
    db.commit()
    return True


# ========== ASIGNACION HORARIO SERVICES ==========

def create_asignacion_horario(db: Session, data: AsignacionHorarioCreate) -> AsignacionHorario:
    """
    Crea una nueva asignación de horario a un empleado.
    
    Validaciones:
    - El empleado debe existir y estar activo
    - El horario debe existir y estar activo
    - No puede haber solapamiento de fechas para el mismo empleado
    """
    # Validar empleado
    from app.features.employees.empleado.models import Empleado
    empleado = db.query(Empleado).filter(Empleado.id == data.id_empleado).first()
    if not empleado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el empleado con id {data.id_empleado}"
        )
    if empleado.estado != "activo":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede asignar horario a un empleado inactivo o dado de baja"
        )
    
    # Validar horario
    horario = get_horario_by_id(db, data.id_horario)
    if not horario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el horario con id {data.id_horario}"
        )
    if not horario.activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede asignar un horario inactivo"
        )
    
    # Validar que no haya solapamiento de fechas
    fecha_fin = data.fecha_fin if data.fecha_fin else date(9999, 12, 31)
    
    solapamiento = db.query(AsignacionHorario).filter(
        AsignacionHorario.id_empleado == data.id_empleado,
        AsignacionHorario.es_activo == True,
        or_(
            # Caso 1: Nueva asignación inicia durante otra existente
            and_(
                AsignacionHorario.fecha_inicio <= data.fecha_inicio,
                or_(
                    AsignacionHorario.fecha_fin.is_(None),
                    AsignacionHorario.fecha_fin >= data.fecha_inicio
                )
            ),
            # Caso 2: Nueva asignación termina durante otra existente
            and_(
                AsignacionHorario.fecha_inicio <= fecha_fin,
                or_(
                    AsignacionHorario.fecha_fin.is_(None),
                    AsignacionHorario.fecha_fin >= fecha_fin
                )
            ),
            # Caso 3: Nueva asignación engloba completamente otra existente
            and_(
                AsignacionHorario.fecha_inicio >= data.fecha_inicio,
                or_(
                    AsignacionHorario.fecha_fin.is_(None),
                    AsignacionHorario.fecha_fin <= fecha_fin
                )
            )
        )
    ).first()
    
    if solapamiento:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe una asignación de horario para este empleado que se solapa con el rango de fechas especificado"
        )
    
    # Crear asignación
    asignacion = AsignacionHorario(**data.model_dump())
    db.add(asignacion)
    db.commit()
    db.refresh(asignacion)
    return asignacion


def get_asignacion_by_id(db: Session, asignacion_id: int) -> Optional[AsignacionHorario]:
    """Obtiene una asignación por ID."""
    return db.query(AsignacionHorario).filter(AsignacionHorario.id == asignacion_id).first()


def get_all_asignaciones(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    id_empleado: Optional[int] = None,
    activo_only: bool = False
) -> List[AsignacionHorario]:
    """
    Obtiene todas las asignaciones con paginación y filtros.
    
    Args:
        skip: Offset para paginación
        limit: Cantidad máxima de resultados
        id_empleado: Filtrar por empleado específico
        activo_only: Si TRUE, solo devuelve asignaciones activas
    """
    query = db.query(AsignacionHorario).options(joinedload(AsignacionHorario.horario))
    
    if id_empleado:
        query = query.filter(AsignacionHorario.id_empleado == id_empleado)
    
    if activo_only:
        query = query.filter(AsignacionHorario.es_activo == True)
    
    return query.offset(skip).limit(limit).all()


def update_asignacion_horario(
    db: Session,
    asignacion_id: int,
    data: AsignacionHorarioUpdate
) -> AsignacionHorario:
    """Actualiza una asignación de horario existente."""
    asignacion = get_asignacion_by_id(db, asignacion_id)
    if not asignacion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe la asignación con id {asignacion_id}"
        )
    
    # Validar horario si cambió
    if data.id_horario and data.id_horario != asignacion.id_horario:
        horario = get_horario_by_id(db, data.id_horario)
        if not horario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No existe el horario con id {data.id_horario}"
            )
        if not horario.activo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede asignar un horario inactivo"
            )
    
    # Aplicar cambios
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(asignacion, field, value)
    
    db.commit()
    db.refresh(asignacion)
    return asignacion


def delete_asignacion_horario(db: Session, asignacion_id: int) -> bool:
    """Elimina una asignación de horario (marca como inactiva)."""
    asignacion = get_asignacion_by_id(db, asignacion_id)
    if not asignacion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe la asignación con id {asignacion_id}"
        )
    
    asignacion.es_activo = False
    db.commit()
    return True


def get_horario_actual_empleado(
    db: Session,
    id_empleado: int,
    fecha: Optional[date] = None
) -> Optional[AsignacionHorarioConDetalle]:
    """
    Obtiene el horario vigente de un empleado en una fecha específica.
    
    Args:
        id_empleado: ID del empleado
        fecha: Fecha de consulta (default: hoy)
    
    Returns:
        AsignacionHorarioConDetalle con los detalles del horario,
        o None si no hay horario asignado para esa fecha.
    """
    if fecha is None:
        fecha = datetime.now().date()
    
    # Validar empleado
    from app.features.employees.empleado.models import Empleado
    empleado = db.query(Empleado).filter(Empleado.id == id_empleado).first()
    if not empleado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el empleado con id {id_empleado}"
        )
    
    # Buscar asignación vigente
    asignacion = db.query(AsignacionHorario).options(
        joinedload(AsignacionHorario.horario)
    ).filter(
        AsignacionHorario.id_empleado == id_empleado,
        AsignacionHorario.es_activo == True,
        AsignacionHorario.fecha_inicio <= fecha,
        or_(
            AsignacionHorario.fecha_fin.is_(None),
            AsignacionHorario.fecha_fin >= fecha
        )
    ).first()
    
    if not asignacion:
        return None
    
    return AsignacionHorarioConDetalle.model_validate(asignacion)
