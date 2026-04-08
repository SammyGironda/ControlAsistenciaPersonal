"""
Servicios de negocio para DiaFestivo.
CRUD completo con lógica de validación y consultas especializadas.
"""

from datetime import date
from typing import List, Optional
from sqlalchemy import select, and_, extract
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.features.attendance.feriados.models import DiaFestivo, AmbitoFestivoEnum
from app.features.attendance.feriados.schemas import DiaFestivoCreate, DiaFestivoUpdate


async def crear_dia_festivo(db: AsyncSession, data: DiaFestivoCreate) -> DiaFestivo:
    """
    Crea un nuevo feriado.
    Valida que no exista un feriado con la misma (fecha, ambito, codigo_departamento).
    """
    # Verificar duplicados
    stmt = select(DiaFestivo).where(
        and_(
            DiaFestivo.fecha == data.fecha,
            DiaFestivo.ambito == data.ambito,
            DiaFestivo.codigo_departamento == data.codigo_departamento
        )
    )
    result = await db.execute(stmt)
    existente = result.scalar_one_or_none()

    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un feriado {data.ambito} en la fecha {data.fecha}"
        )

    # Crear el feriado
    nuevo_feriado = DiaFestivo(
        fecha=data.fecha,
        descripcion=data.descripcion,
        ambito=data.ambito,
        codigo_departamento=data.codigo_departamento,
        activo=data.activo
    )

    db.add(nuevo_feriado)
    await db.commit()
    await db.refresh(nuevo_feriado)

    return nuevo_feriado


async def obtener_dia_festivo(db: AsyncSession, id: int) -> DiaFestivo:
    """Obtiene un feriado por ID."""
    stmt = select(DiaFestivo).where(DiaFestivo.id == id)
    result = await db.execute(stmt)
    feriado = result.scalar_one_or_none()

    if not feriado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feriado con ID {id} no encontrado"
        )

    return feriado


async def listar_dias_festivos(
    db: AsyncSession,
    activo: Optional[bool] = None,
    ambito: Optional[AmbitoFestivoEnum] = None,
    anio: Optional[int] = None,
    codigo_departamento: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> List[DiaFestivo]:
    """
    Lista feriados con filtros opcionales.

    Args:
        activo: Filtrar por estado activo/inactivo
        ambito: Filtrar por NACIONAL o DEPARTAMENTAL
        anio: Filtrar por año
        codigo_departamento: Filtrar por código de departamento
    """
    stmt = select(DiaFestivo)

    # Aplicar filtros
    condiciones = []

    if activo is not None:
        condiciones.append(DiaFestivo.activo == activo)

    if ambito:
        condiciones.append(DiaFestivo.ambito == ambito)

    if anio:
        condiciones.append(extract('year', DiaFestivo.fecha) == anio)

    if codigo_departamento:
        condiciones.append(DiaFestivo.codigo_departamento == codigo_departamento)

    if condiciones:
        stmt = stmt.where(and_(*condiciones))

    stmt = stmt.order_by(DiaFestivo.fecha.desc()).offset(skip).limit(limit)

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def obtener_feriados_aplicables(
    db: AsyncSession,
    fecha: date,
    codigo_departamento: str
) -> List[DiaFestivo]:
    """
    Obtiene feriados aplicables a una fecha y departamento específico.

    Retorna feriados NACIONALES o DEPARTAMENTALES que aplican al departamento dado.
    Esta función es usada por el worker de asistencia_diaria.
    """
    stmt = select(DiaFestivo).where(
        and_(
            DiaFestivo.fecha == fecha,
            DiaFestivo.activo == True,
            (
                (DiaFestivo.ambito == AmbitoFestivoEnum.NACIONAL) |
                (
                    (DiaFestivo.ambito == AmbitoFestivoEnum.DEPARTAMENTAL) &
                    (DiaFestivo.codigo_departamento == codigo_departamento)
                )
            )
        )
    )

    result = await db.execute(stmt)
    return list(result.scalars().all())


async def actualizar_dia_festivo(
    db: AsyncSession,
    id: int,
    data: DiaFestivoUpdate
) -> DiaFestivo:
    """Actualiza un feriado existente."""
    feriado = await obtener_dia_festivo(db, id)

    # Aplicar cambios
    if data.fecha is not None:
        feriado.fecha = data.fecha
    if data.descripcion is not None:
        feriado.descripcion = data.descripcion
    if data.ambito is not None:
        feriado.ambito = data.ambito
    if data.codigo_departamento is not None:
        feriado.codigo_departamento = data.codigo_departamento
    if data.activo is not None:
        feriado.activo = data.activo

    await db.commit()
    await db.refresh(feriado)

    return feriado


async def eliminar_dia_festivo(db: AsyncSession, id: int) -> DiaFestivo:
    """
    Soft delete: marca el feriado como inactivo.
    Los feriados históricos deben conservarse para auditoría.
    """
    feriado = await obtener_dia_festivo(db, id)
    feriado.activo = False

    await db.commit()
    await db.refresh(feriado)

    return feriado


async def eliminar_permanente(db: AsyncSession, id: int) -> None:
    """
    Hard delete: Elimina permanentemente el feriado.
    Solo usar si el feriado fue creado por error y no hay datos relacionados.
    """
    feriado = await obtener_dia_festivo(db, id)

    await db.delete(feriado)
    await db.commit()
