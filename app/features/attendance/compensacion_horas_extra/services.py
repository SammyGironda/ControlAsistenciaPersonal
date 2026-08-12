"""
Servicios para CompensacionHorasExtra.

Además del efecto interno disparado por la aprobación de justificaciones de
tipo 'viaje_trabajo' (ver justificacion/services.py), este módulo respalda
el endpoint admin para registrar compensación manual por trabajo en fin de
semana/feriado no planeado (ver router.py). El trigger de Neon
`trg_compensacion_horas_extra_a_vacacion` es quien realmente acredita las
horas a `vacacion` al insertarse una fila aquí — este service solo inserta.
"""

import logging
from datetime import date
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.features.attendance.compensacion_horas_extra.models import CompensacionHorasExtra
from app.features.employees.empleado.models import Empleado

logger = logging.getLogger(__name__)

# El UNIQUE (id_empleado, fecha) declarado en models.py
UNIQUE_EMPLEADO_FECHA = "uq_compensacion_horas_extra_empleado_fecha"


def _es_duplicado_empleado_fecha(error: IntegrityError) -> bool:
    """
    True sólo si el IntegrityError vino de violar el UNIQUE (id_empleado, fecha).

    Se mira el nombre del constraint que reporta PostgreSQL, no el tipo de
    excepción: IntegrityError cubre también NOT NULL, FK y CHECK. Tratarlos a
    todos como "duplicado" fue lo que mantuvo invisible durante meses un
    NotNullViolation del trigger trg_compensacion_horas_extra_a_vacacion, que
    hacía fallar TODA compensación mientras la API respondía 409 "ya existe"
    (corregido en la migración e5f2a8c1d904).
    """
    diag = getattr(getattr(error, "orig", None), "diag", None)
    return getattr(diag, "constraint_name", None) == UNIQUE_EMPLEADO_FECHA


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

    Cualquier OTRO IntegrityError (NOT NULL, FK, CHECK — típicamente venido del
    trigger que escribe en `rrhh.vacacion`) se loguea y se propaga: no es un
    duplicado y silenciarlo devolvería un 409 que miente sobre la causa.
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
    except IntegrityError as error:
        db.rollback()

        if _es_duplicado_empleado_fecha(error):
            return None

        logger.error(
            "IntegrityError al registrar compensación (empleado=%s, fecha=%s, "
            "gestion=%s). No es un duplicado: %s",
            id_empleado,
            fecha,
            compensacion.gestion,
            error.orig,
        )
        raise

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
