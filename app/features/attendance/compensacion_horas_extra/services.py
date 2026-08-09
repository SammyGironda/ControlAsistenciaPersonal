"""
Servicios para CompensacionHorasExtra.

Además del efecto interno disparado por la aprobación de justificaciones de
tipo 'viaje_trabajo' (ver justificacion/services.py), este módulo respalda
el endpoint admin para registrar compensación manual por trabajo en fin de
semana/feriado no planeado (ver router.py). El trigger de Neon
`trg_compensacion_horas_extra_a_vacacion` es quien realmente acredita las
horas a `vacacion` al insertarse una fila aquí — este service solo inserta.
"""

from datetime import date
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.features.attendance.compensacion_horas_extra.models import CompensacionHorasExtra
from app.features.employees.empleado.models import Empleado


def _get_empleado_or_404(db: Session, id_empleado: int) -> Empleado:
    empleado = db.query(Empleado).filter(Empleado.id == id_empleado).first()
    if not empleado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el empleado con id {id_empleado}"
        )
    return empleado


def registrar_compensacion(
    db: Session,
    id_empleado: int,
    fecha: date,
    horas: Decimal,
    motivo: str,
    gestion: Optional[int] = None,
    id_registrado_por: Optional[int] = None,
) -> Optional[CompensacionHorasExtra]:
    """
    Inserta una compensación de horas extra (dispara el trigger que acredita
    vacación). No depende de que exista asistencia_diaria para esa fecha:
    solo inserta la fila en compensacion_horas_extra.

    `gestion` es opcional: si se omite, se usa el año de `fecha` (criterio
    usado por el caller interno de justificacion). Si ya existe una
    compensación para ese empleado+fecha (UniqueConstraint), hace rollback y
    retorna None en vez de propagar el error — el caller decide cómo
    reaccionar (el batch de justificacion la ignora y sigue; el endpoint
    admin la traduce a 409).
    """
    compensacion = CompensacionHorasExtra(
        id_empleado=id_empleado,
        fecha=fecha,
        horas=horas,
        motivo=motivo,
        gestion=gestion if gestion is not None else fecha.year,
        id_registrado_por=id_registrado_por,
    )

    db.add(compensacion)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        return None

    db.refresh(compensacion)
    return compensacion


def listar_compensaciones(
    db: Session,
    id_empleado: Optional[int] = None,
    gestion: Optional[int] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[CompensacionHorasExtra]:
    """Lista compensaciones de horas extra, filtrables por empleado y/o gestión."""
    query = db.query(CompensacionHorasExtra)

    if id_empleado is not None:
        query = query.filter(CompensacionHorasExtra.id_empleado == id_empleado)

    if gestion is not None:
        query = query.filter(CompensacionHorasExtra.gestion == gestion)

    return (
        query.order_by(CompensacionHorasExtra.fecha.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
