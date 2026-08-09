"""
Servicios de negocio para BeneficioCumpleanos.
Gestión del beneficio de medio día por cumpleaños.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import List, Optional
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.features.attendance.beneficio_cumpleanos.models import BeneficioCumpleanos
from app.features.attendance.beneficio_cumpleanos.schemas import (
    BeneficioCumpleanosCreate,
    BeneficioCumpleanosUpdate
)
from app.features.attendance.vacaciones.models import Vacacion
from app.features.employees.empleado.models import Empleado


# Horas que aporta el beneficio de cumpleaños al saldo vacacional (medio día).
HORAS_BENEFICIO_CUMPLEANOS = Decimal("4.0")


def crear_beneficio_cumpleanos(
    db: Session,
    data: BeneficioCumpleanosCreate
) -> BeneficioCumpleanos:
    """
    Crea un nuevo beneficio de cumpleaños.
    Verifica que no exista uno para el mismo empleado y gestión.

    Esta función es llamada automáticamente por el worker diario.
    """
    # Verificar que no exista ya para este empleado y gestión
    existente = db.query(BeneficioCumpleanos).filter(
        BeneficioCumpleanos.id_empleado == data.id_empleado,
        BeneficioCumpleanos.gestion == data.gestion,
    ).first()

    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un beneficio de cumpleaños para el empleado {data.id_empleado} en la gestión {data.gestion}"
        )

    # Crear el beneficio
    nuevo_beneficio = BeneficioCumpleanos(
        id_empleado=data.id_empleado,
        gestion=data.gestion,
        fue_utilizado=False,
        transferido_a_vacacion=False
    )

    db.add(nuevo_beneficio)
    db.commit()
    db.refresh(nuevo_beneficio)

    return nuevo_beneficio


def obtener_beneficio(db: Session, id: int) -> BeneficioCumpleanos:
    """Obtiene un beneficio por ID."""
    beneficio = db.query(BeneficioCumpleanos).filter(BeneficioCumpleanos.id == id).first()

    if not beneficio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Beneficio con ID {id} no encontrado"
        )

    return beneficio


def obtener_beneficio_por_empleado_gestion(
    db: Session,
    id_empleado: int,
    gestion: int
) -> Optional[BeneficioCumpleanos]:
    """Obtiene el beneficio de un empleado para una gestión específica."""
    return db.query(BeneficioCumpleanos).filter(
        BeneficioCumpleanos.id_empleado == id_empleado,
        BeneficioCumpleanos.gestion == gestion,
    ).first()


def listar_beneficios(
    db: Session,
    gestion: Optional[int] = None,
    fue_utilizado: Optional[bool] = None,
    transferido_a_vacacion: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100
) -> List[BeneficioCumpleanos]:
    """Lista beneficios con filtros opcionales."""
    query = db.query(BeneficioCumpleanos)

    if gestion is not None:
        query = query.filter(BeneficioCumpleanos.gestion == gestion)

    if fue_utilizado is not None:
        query = query.filter(BeneficioCumpleanos.fue_utilizado == fue_utilizado)

    if transferido_a_vacacion is not None:
        query = query.filter(BeneficioCumpleanos.transferido_a_vacacion == transferido_a_vacacion)

    return query.order_by(
        BeneficioCumpleanos.gestion.desc(),
        BeneficioCumpleanos.id_empleado,
    ).offset(skip).limit(limit).all()


def marcar_como_utilizado(
    db: Session,
    id: int,
    id_justificacion: Optional[int] = None
) -> BeneficioCumpleanos:
    """
    Marca un beneficio como utilizado.
    Opcionalmente vincula con una justificación.
    """
    beneficio = obtener_beneficio(db, id)

    if beneficio.fue_utilizado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este beneficio ya fue utilizado"
        )

    beneficio.fue_utilizado = True
    beneficio.fecha_uso = datetime.now()
    if id_justificacion:
        beneficio.id_justificacion = id_justificacion

    db.commit()
    db.refresh(beneficio)

    return beneficio


def _base_horas_vacacion_lgt(db: Session, fecha_ingreso: date, gestion: int) -> Decimal:
    """
    Calcula las horas de vacación que corresponden por LGT a un empleado al
    cierre de una gestión, delegando en la función SQL `rrhh.fn_horas_vacacion_lgt`.

    Es la misma fuente que usa el trigger `trg_compensacion_horas_extra_a_vacacion`
    (migración 122bc6566cae) para crear una vacación inexistente, de modo que un
    saldo creado por transferencia de cumpleaños y otro creado por compensación
    de horas extra partan siempre de la misma base.
    """
    base = db.execute(
        text("SELECT rrhh.fn_horas_vacacion_lgt(:ingreso, :corte)"),
        {"ingreso": fecha_ingreso, "corte": date(gestion, 12, 31)},
    ).scalar()

    return Decimal(str(base)) if base is not None else Decimal("0.0")


def transferir_a_vacacion(
    db: Session,
    id: int
) -> BeneficioCumpleanos:
    """
    Transfiere el beneficio de cumpleaños no utilizado al saldo vacacional.

    Acredita 4h a `vacacion.horas_correspondientes` y `vacacion.horas_goce_haber`
    de la gestión del beneficio Y marca `transferido_a_vacacion = True` en la
    MISMA transacción: o se aplican ambos efectos, o ninguno. Antes esta función
    solo levantaba el flag y las 4h quedaban delegadas a un worker de fin de año
    que nunca existió, así que el beneficio se perdía.

    Si el empleado todavía no tiene registro de vacación para esa gestión, se
    crea con la base LGT (`rrhh.fn_horas_vacacion_lgt`) más las 4h.
    """
    beneficio = obtener_beneficio(db, id)

    if beneficio.transferido_a_vacacion:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este beneficio ya fue transferido a vacaciones"
        )

    vacacion = db.query(Vacacion).filter(
        Vacacion.id_empleado == beneficio.id_empleado,
        Vacacion.gestion == beneficio.gestion,
    ).first()

    if vacacion:
        vacacion.horas_correspondientes += HORAS_BENEFICIO_CUMPLEANOS
        vacacion.horas_goce_haber += HORAS_BENEFICIO_CUMPLEANOS
    else:
        empleado = db.query(Empleado).filter(
            Empleado.id == beneficio.id_empleado
        ).first()

        if not empleado:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Empleado con ID {beneficio.id_empleado} no encontrado"
            )

        base_horas = _base_horas_vacacion_lgt(db, empleado.fecha_ingreso, beneficio.gestion)

        vacacion = Vacacion(
            id_empleado=beneficio.id_empleado,
            gestion=beneficio.gestion,
            horas_correspondientes=base_horas + HORAS_BENEFICIO_CUMPLEANOS,
            horas_goce_haber=HORAS_BENEFICIO_CUMPLEANOS,
            horas_sin_goce_haber=Decimal("0.0"),
            horas_tomadas=Decimal("0.0"),
            observacion=(
                f"Creada al transferir el beneficio de cumpleaños "
                f"(gestión {beneficio.gestion})"
            ),
        )
        db.add(vacacion)

    beneficio.transferido_a_vacacion = True

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"No se pudo transferir el beneficio a vacaciones: {exc.orig}"
        )

    db.refresh(beneficio)

    return beneficio


def actualizar_beneficio(
    db: Session,
    id: int,
    data: BeneficioCumpleanosUpdate
) -> BeneficioCumpleanos:
    """Actualiza un beneficio existente."""
    beneficio = obtener_beneficio(db, id)

    if data.fue_utilizado is not None:
        beneficio.fue_utilizado = data.fue_utilizado
    if data.fecha_uso is not None:
        beneficio.fecha_uso = data.fecha_uso
    if data.id_justificacion is not None:
        beneficio.id_justificacion = data.id_justificacion
    if data.transferido_a_vacacion is not None:
        beneficio.transferido_a_vacacion = data.transferido_a_vacacion

    db.commit()
    db.refresh(beneficio)

    return beneficio


def eliminar_beneficio(db: Session, id: int) -> None:
    """
    Elimina un beneficio.
    Solo usar en caso de error o para pruebas.
    """
    beneficio = obtener_beneficio(db, id)
    db.delete(beneficio)
    db.commit()
