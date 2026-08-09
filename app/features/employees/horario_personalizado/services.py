"""
Services (lógica de negocio) para HorarioPersonalizadoEmpleado.
Upsert 1:1 por empleado + soft delete (activo=FALSE) para no perder historial.
"""

from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.features.employees.horario_personalizado.models import HorarioPersonalizadoEmpleado
from app.features.employees.horario_personalizado.schemas import HorarioPersonalizadoEmpleadoUpsert
from app.features.employees.empleado.models import Empleado


def _get_empleado_or_404(db: Session, id_empleado: int) -> Empleado:
    empleado = db.query(Empleado).filter(Empleado.id == id_empleado).first()
    if not empleado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el empleado con id {id_empleado}"
        )
    return empleado


def get_by_empleado_id(db: Session, id_empleado: int) -> Optional[HorarioPersonalizadoEmpleado]:
    """Devuelve el registro de override (exista o no, activo o no)."""
    return db.query(HorarioPersonalizadoEmpleado).filter(
        HorarioPersonalizadoEmpleado.id_empleado == id_empleado
    ).first()


def get_activo_by_empleado_id(db: Session, id_empleado: int) -> Optional[HorarioPersonalizadoEmpleado]:
    """
    Devuelve el override SOLO si existe y está activo.
    Usado por el cálculo de asistencia diaria: si devuelve None, se debe
    usar el horario general vía asignacion_horario sin cambio de comportamiento.
    """
    return db.query(HorarioPersonalizadoEmpleado).filter(
        HorarioPersonalizadoEmpleado.id_empleado == id_empleado,
        HorarioPersonalizadoEmpleado.activo == True,
    ).first()


def get_horario_personalizado_response(db: Session, id_empleado: int) -> Optional[HorarioPersonalizadoEmpleado]:
    """
    Para el GET: valida que el empleado exista y devuelve el override solo
    si está activo (si está inactivo, el empleado usa el horario general,
    por lo que el endpoint debe responder null igual que si no existiera).
    """
    _get_empleado_or_404(db, id_empleado)
    return get_activo_by_empleado_id(db, id_empleado)


def upsert_horario_personalizado(
    db: Session,
    id_empleado: int,
    data: HorarioPersonalizadoEmpleadoUpsert,
) -> HorarioPersonalizadoEmpleado:
    """Crea el override si no existe, o actualiza el existente (incluye reactivarlo)."""
    _get_empleado_or_404(db, id_empleado)

    override = get_by_empleado_id(db, id_empleado)
    campos = data.model_dump()

    if override:
        for field, value in campos.items():
            setattr(override, field, value)
    else:
        override = HorarioPersonalizadoEmpleado(id_empleado=id_empleado, **campos)
        db.add(override)

    db.commit()
    db.refresh(override)
    return override


def desactivar_horario_personalizado(db: Session, id_empleado: int) -> bool:
    """
    Desactiva el override (activo=FALSE). NO borra el registro, para
    conservar el historial. El empleado vuelve a regirse por el horario
    general en el siguiente cálculo de asistencia.
    """
    override = get_by_empleado_id(db, id_empleado)
    if not override:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"El empleado {id_empleado} no tiene un horario personalizado registrado"
        )

    override.activo = False
    db.commit()
    return True
