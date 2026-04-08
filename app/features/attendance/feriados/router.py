"""
Router para DiaFestivo - Endpoints REST para gestión de feriados.
"""

from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.features.attendance.feriados import services
from app.features.attendance.feriados.schemas import (
    DiaFestivoCreate,
    DiaFestivoUpdate,
    DiaFestivoResponse,
    AmbitoFestivoEnum
)

router = APIRouter(prefix="/feriados", tags=["Feriados"])


@router.post(
    "/",
    response_model=DiaFestivoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nuevo feriado"
)
async def crear_feriado(
    data: DiaFestivoCreate,
    db: AsyncSession = Depends(get_db)
):
    """
    Crea un nuevo feriado nacional o departamental.

    **Validaciones:**
    - Si ambito es DEPARTAMENTAL, codigo_departamento es obligatorio
    - Si ambito es NACIONAL, codigo_departamento debe ser NULL
    - No puede haber duplicados (fecha, ambito, codigo_departamento)
    """
    return await services.crear_dia_festivo(db, data)


@router.get(
    "/{id}",
    response_model=DiaFestivoResponse,
    summary="Obtener feriado por ID"
)
async def obtener_feriado(
    id: int,
    db: AsyncSession = Depends(get_db)
):
    """Obtiene un feriado específico por su ID."""
    return await services.obtener_dia_festivo(db, id)


@router.get(
    "/",
    response_model=List[DiaFestivoResponse],
    summary="Listar feriados con filtros"
)
async def listar_feriados(
    activo: Optional[bool] = Query(None, description="Filtrar por estado activo"),
    ambito: Optional[AmbitoFestivoEnum] = Query(None, description="Filtrar por ámbito"),
    anio: Optional[int] = Query(None, description="Filtrar por año"),
    codigo_departamento: Optional[str] = Query(None, description="Filtrar por código departamento"),
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: int = Query(100, ge=1, le=500, description="Límite de registros"),
    db: AsyncSession = Depends(get_db)
):
    """
    Lista feriados con filtros opcionales.

    **Filtros disponibles:**
    - `activo`: true/false para filtrar por estado
    - `ambito`: NACIONAL o DEPARTAMENTAL
    - `anio`: filtrar por año específico
    - `codigo_departamento`: LP, CB, SC, OR, PT, TJ, CH, BE, PA
    """
    return await services.listar_dias_festivos(
        db,
        activo=activo,
        ambito=ambito,
        anio=anio,
        codigo_departamento=codigo_departamento,
        skip=skip,
        limit=limit
    )


@router.get(
    "/aplicables/{fecha}/{codigo_departamento}",
    response_model=List[DiaFestivoResponse],
    summary="Obtener feriados aplicables a fecha y departamento"
)
async def obtener_feriados_aplicables(
    fecha: date,
    codigo_departamento: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Obtiene feriados que aplican a una fecha y departamento específico.

    Retorna:
    - Feriados NACIONALES en esa fecha
    - Feriados DEPARTAMENTALES del departamento indicado en esa fecha

    Este endpoint es usado por el worker de asistencia_diaria.
    """
    return await services.obtener_feriados_aplicables(db, fecha, codigo_departamento)


@router.put(
    "/{id}",
    response_model=DiaFestivoResponse,
    summary="Actualizar feriado"
)
async def actualizar_feriado(
    id: int,
    data: DiaFestivoUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Actualiza los datos de un feriado existente."""
    return await services.actualizar_dia_festivo(db, id, data)


@router.delete(
    "/{id}",
    response_model=DiaFestivoResponse,
    summary="Desactivar feriado (soft delete)"
)
async def eliminar_feriado(
    id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Desactiva un feriado (soft delete).

    No elimina el registro, solo lo marca como inactivo.
    Los feriados históricos se conservan para auditoría.
    """
    return await services.eliminar_dia_festivo(db, id)


@router.delete(
    "/{id}/permanente",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar feriado permanentemente (hard delete)"
)
async def eliminar_feriado_permanente(
    id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Elimina permanentemente un feriado de la base de datos.

    **ADVERTENCIA:** Esta acción es irreversible.
    Solo usar si el feriado fue creado por error y no hay datos relacionados.
    """
    await services.eliminar_permanente(db, id)
    return None
