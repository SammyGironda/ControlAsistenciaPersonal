"""
Servicios de negocio para BeneficioCumpleanos.
Gestión del beneficio de medio día por cumpleaños.
"""

from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.features.attendance.beneficio_cumpleanos.models import BeneficioCumpleanos
from app.features.attendance.beneficio_cumpleanos.schemas import (
    BeneficioCumpleanosCreate,
    BeneficioCumpleanosUpdate
)


async def crear_beneficio_cumpleanos(
    db: AsyncSession,
    data: BeneficioCumpleanosCreate
) -> BeneficioCumpleanos:
    """
    Crea un nuevo beneficio de cumpleaños.
    Verifica que no exista uno para el mismo empleado y gestión.

    Esta función es llamada automáticamente por el worker diario.
    """
    # Verificar que no exista ya para este empleado y gestión
    stmt = select(BeneficioCumpleanos).where(
        and_(
            BeneficioCumpleanos.id_empleado == data.id_empleado,
            BeneficioCumpleanos.gestion == data.gestion
        )
    )
    result = await db.execute(stmt)
    existente = result.scalar_one_or_none()

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
    await db.commit()
    await db.refresh(nuevo_beneficio)

    return nuevo_beneficio


async def obtener_beneficio(db: AsyncSession, id: int) -> BeneficioCumpleanos:
    """Obtiene un beneficio por ID."""
    stmt = select(BeneficioCumpleanos).where(BeneficioCumpleanos.id == id)
    result = await db.execute(stmt)
    beneficio = result.scalar_one_or_none()

    if not beneficio:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Beneficio con ID {id} no encontrado"
        )

    return beneficio


async def obtener_beneficio_por_empleado_gestion(
    db: AsyncSession,
    id_empleado: int,
    gestion: int
) -> Optional[BeneficioCumpleanos]:
    """Obtiene el beneficio de un empleado para una gestión específica."""
    stmt = select(BeneficioCumpleanos).where(
        and_(
            BeneficioCumpleanos.id_empleado == id_empleado,
            BeneficioCumpleanos.gestion == gestion
        )
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def listar_beneficios(
    db: AsyncSession,
    gestion: Optional[int] = None,
    fue_utilizado: Optional[bool] = None,
    transferido_a_vacacion: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100
) -> List[BeneficioCumpleanos]:
    """Lista beneficios con filtros opcionales."""
    stmt = select(BeneficioCumpleanos)

    condiciones = []

    if gestion is not None:
        condiciones.append(BeneficioCumpleanos.gestion == gestion)

    if fue_utilizado is not None:
        condiciones.append(BeneficioCumpleanos.fue_utilizado == fue_utilizado)

    if transferido_a_vacacion is not None:
        condiciones.append(BeneficioCumpleanos.transferido_a_vacacion == transferido_a_vacacion)

    if condiciones:
        stmt = stmt.where(and_(*condiciones))

    stmt = stmt.order_by(BeneficioCumpleanos.gestion.desc(), BeneficioCumpleanos.id_empleado).offset(skip).limit(limit)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def marcar_como_utilizado(
    db: AsyncSession,
    id: int,
    id_justificacion: Optional[int] = None
) -> BeneficioCumpleanos:
    """
    Marca un beneficio como utilizado.
    Opcionalmente vincula con una justificación.
    """
    beneficio = await obtener_beneficio(db, id)

    if beneficio.fue_utilizado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este beneficio ya fue utilizado"
        )

    beneficio.fue_utilizado = True
    beneficio.fecha_uso = datetime.now()
    if id_justificacion:
        beneficio.id_justificacion = id_justificacion

    await db.commit()
    await db.refresh(beneficio)

    return beneficio


async def transferir_a_vacacion(
    db: AsyncSession,
    id: int
) -> BeneficioCumpleanos:
    """
    Marca un beneficio como transferido a vacaciones.
    Esta función es llamada por el worker de fin de año.

    El worker debe sumar 4h a vacacion.horas_goce_haber antes de llamar esta función.
    """
    beneficio = await obtener_beneficio(db, id)

    if beneficio.transferido_a_vacacion:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Este beneficio ya fue transferido a vacaciones"
        )

    beneficio.transferido_a_vacacion = True

    await db.commit()
    await db.refresh(beneficio)

    return beneficio


async def actualizar_beneficio(
    db: AsyncSession,
    id: int,
    data: BeneficioCumpleanosUpdate
) -> BeneficioCumpleanos:
    """Actualiza un beneficio existente."""
    beneficio = await obtener_beneficio(db, id)

    if data.fue_utilizado is not None:
        beneficio.fue_utilizado = data.fue_utilizado
    if data.fecha_uso is not None:
        beneficio.fecha_uso = data.fecha_uso
    if data.id_justificacion is not None:
        beneficio.id_justificacion = data.id_justificacion
    if data.transferido_a_vacacion is not None:
        beneficio.transferido_a_vacacion = data.transferido_a_vacacion

    await db.commit()
    await db.refresh(beneficio)

    return beneficio


async def eliminar_beneficio(db: AsyncSession, id: int) -> None:
    """
    Elimina un beneficio.
    Solo usar en caso de error o para pruebas.
    """
    beneficio = await obtener_beneficio(db, id)
    await db.delete(beneficio)
    await db.commit()
