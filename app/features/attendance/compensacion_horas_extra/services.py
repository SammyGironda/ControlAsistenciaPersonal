"""
Servicios para CompensacionHorasExtra.

Este módulo no tiene router propio: hoy es un efecto interno disparado por
la aprobación de justificaciones de tipo 'viaje_trabajo' (ver
justificacion/services.py). El trigger de Neon
`trg_compensacion_horas_extra_a_vacacion` es quien realmente acredita las
horas a `vacacion` al insertarse una fila aquí.
"""

from datetime import date
from decimal import Decimal
from typing import Optional
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.features.attendance.compensacion_horas_extra.models import CompensacionHorasExtra


def registrar_compensacion(
    db: Session,
    id_empleado: int,
    fecha: date,
    horas: Decimal,
    motivo: str,
    id_registrado_por: Optional[int] = None,
) -> Optional[CompensacionHorasExtra]:
    """
    Inserta una compensación de horas extra (dispara el trigger que acredita
    vacación). Si ya existe una compensación para ese empleado+fecha
    (UniqueConstraint), hace rollback y retorna None en vez de propagar el
    error — evita romper un loop de aprobación por un día ya compensado.
    """
    compensacion = CompensacionHorasExtra(
        id_empleado=id_empleado,
        fecha=fecha,
        horas=horas,
        motivo=motivo,
        gestion=fecha.year,
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
