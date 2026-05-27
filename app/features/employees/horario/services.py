"""
Services (lógica de negocio) para Horario y AsignacionHorario.
Operaciones CRUD + validación de solapamientos y horario vigente.
Todas las operaciones usan UTC internamente, la zona horaria de La Paz es UTC-4.
"""

from typing import List, Optional
from datetime import date, datetime, time
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
from app.features.employees.empleado.models import Empleado
from app.features.contracts.contrato.models import Contrato, EstadoContratoEnum
from app.core.timezone import get_utc_now, get_lapaz_now, utc_to_lapaz


# ========== HELPER FUNCTIONS ==========

def calcular_horas_semanales(hora_entrada: time, hora_salida: time, dias_laborables: List[int]) -> float:
    """
    Calcula automáticamente las horas semanales.

    Args:
        hora_entrada: Hora de entrada
        hora_salida: Hora de salida
        dias_laborables: Lista de días laborables [1-7]

    Returns:
        Total de horas semanales (horas_por_día * cantidad_días)
    """
    # Convertir times a datetime para calcular diferencia
    fecha_ref = datetime(2000, 1, 1)
    dt_entrada = datetime.combine(fecha_ref.date(), hora_entrada)
    dt_salida = datetime.combine(fecha_ref.date(), hora_salida)

    # Calcular horas por día
    horas_por_dia = (dt_salida - dt_entrada).total_seconds() / 3600

    # Calcular cantidad de días laborables
    cantidad_dias = len(dias_laborables)

    # Calcular total de horas semanales
    horas_semanales = horas_por_dia * cantidad_dias

    return round(horas_semanales, 1)


# ========== HORARIO SERVICES ==========

def create_horario(db: Session, data: HorarioCreate) -> Horario:
    """Crea un nuevo horario calculando automáticamente las horas semanales."""
    # Calcular horas semanales automáticamente
    horas_semanales = calcular_horas_semanales(
        data.hora_entrada,
        data.hora_salida,
        data.dias_laborables
    )

    # Validar que no excedan el máximo permitido
    if horas_semanales > 48.0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Las horas semanales calculadas ({horas_semanales}h) exceden el máximo permitido de 48h según LGT Art. 46"
        )

    # Crear horario con horas calculadas
    horario_data = data.model_dump()
    horario_data['jornada_semanal_horas'] = horas_semanales

    horario = Horario(**horario_data)
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
    """Actualiza un horario. Recalcula horas semanales si cambian hora_entrada, hora_salida o dias_laborables."""
    horario = get_horario_by_id(db, horario_id)
    if not horario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el horario con id {horario_id}"
        )

    # Aplicar cambios
    update_data = data.model_dump(exclude_unset=True)

    # Determinar si necesita recalcular horas
    necesita_recalculo = any(
        campo in update_data for campo in ['hora_entrada', 'hora_salida', 'dias_laborables']
    )

    if necesita_recalculo:
        # Usar valores actuales o nuevos
        hora_entrada = update_data.get('hora_entrada', horario.hora_entrada)
        hora_salida = update_data.get('hora_salida', horario.hora_salida)
        dias_laborables = update_data.get('dias_laborables', horario.dias_laborables)

        # Recalcular horas semanales
        horas_semanales = calcular_horas_semanales(hora_entrada, hora_salida, dias_laborables)

        if horas_semanales > 48.0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Las horas semanales calculadas ({horas_semanales}h) exceden el máximo permitido de 48h según LGT Art. 46"
            )

        update_data['jornada_semanal_horas'] = horas_semanales

    # Aplicar todos los cambios
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
    - La fecha fin no debe exceder la fecha fin del contrato activo del empleado
    """
    # Validar empleado
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

    # --- Lógica de validación de fecha fin con contrato (Punto 3) ---
    # Obtener el contrato activo del empleado
    contrato_activo = db.query(Contrato).filter(
        Contrato.id_empleado == data.id_empleado,
        Contrato.estado == EstadoContratoEnum.activo
    ).order_by(Contrato.fecha_inicio.desc()).first() # Obtener el más reciente si hay múltiples activos (debería ser solo 1)

    if not contrato_activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El empleado no tiene un contrato activo. No se puede asignar un horario."
        )

    if contrato_activo.fecha_fin:
        # Si el contrato tiene fecha fin (plazo fijo)
        if data.fecha_fin is None or data.fecha_fin > contrato_activo.fecha_fin:
            # Si la asignación es indefinida o excede el contrato, ajustarla a la fecha fin del contrato
            data.fecha_fin = contrato_activo.fecha_fin
            print(f"DEBUG: Fecha fin de asignación ajustada a la fecha fin del contrato: {data.fecha_fin}")
    elif data.fecha_fin is not None:
        # Si el contrato es indefinido pero la asignación tiene fecha fin, se respeta la asignación
        pass # No se hace nada, se mantiene la fecha fin proporcionada

    # Validar que no haya solapamiento de fechas
    fecha_fin_solapamiento = data.fecha_fin if data.fecha_fin else date(9999, 12, 31)
    
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
                AsignacionHorario.fecha_inicio <= fecha_fin_solapamiento,
                or_(
                    AsignacionHorario.fecha_fin.is_(None),
                    AsignacionHorario.fecha_fin >= fecha_fin_solapamiento
                )
            ),
            # Caso 3: Nueva asignación engloba completamente otra existente
            and_(
                AsignacionHorario.fecha_inicio >= data.fecha_inicio,
                or_(
                    AsignacionHorario.fecha_fin.is_(None),
                    AsignacionHorario.fecha_fin <= fecha_fin_solapamiento
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
    """
    Actualiza una asignación de horario existente.
    La fecha fin no debe exceder la fecha fin del contrato activo del empleado.
    """
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
    
    # --- Lógica de validación de fecha fin con contrato para actualizaciones (Punto 3) ---
    # Se aplica solo si fecha_fin está presente en la actualización o si el id_empleado cambia
    empleado_id_for_contract_check = data.id_empleado if data.id_empleado else asignacion.id_empleado

    if data.fecha_fin is not None or data.id_empleado is not None:
        empleado = db.query(Empleado).filter(Empleado.id == empleado_id_for_contract_check).first()
        if not empleado:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No existe el empleado con id {empleado_id_for_contract_check}"
            )
        
        contrato_activo = db.query(Contrato).filter(
            Contrato.id_empleado == empleado.id,
            Contrato.estado == EstadoContratoEnum.activo
        ).order_by(Contrato.fecha_inicio.desc()).first()

        if not contrato_activo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El empleado no tiene un contrato activo. No se puede actualizar la asignación de horario."
            )

        current_fecha_fin = data.fecha_fin if data.fecha_fin is not None else asignacion.fecha_fin
        
        if contrato_activo.fecha_fin:
            # Si el contrato tiene fecha fin (plazo fijo)
            if current_fecha_fin is None or current_fecha_fin > contrato_activo.fecha_fin:
                data.fecha_fin = contrato_activo.fecha_fin
                print(f"DEBUG: Fecha fin de asignación actualizada ajustada a la fecha fin del contrato: {data.fecha_fin}")
        elif data.fecha_fin is not None and data.fecha_fin < asignacion.fecha_inicio:
            # Si el contrato es indefinido, pero se intenta acortar la fecha_fin a antes de fecha_inicio
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="La fecha fin de la asignación no puede ser anterior a la fecha de inicio."
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
    Usa zona horaria de La Paz (UTC-4).

    Args:
        id_empleado: ID del empleado
        fecha: Fecha de consulta en La Paz (default: hoy en La Paz)

    Returns:
        AsignacionHorarioConDetalle con los detalles del horario,
        o None si no hay horario asignado para esa fecha.
    """
    if fecha is None:
        fecha = get_lapaz_now().date()

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
