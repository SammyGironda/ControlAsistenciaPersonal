"""
Router para DiaFestivo - Endpoints REST para gestión de feriados.
"""

from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_admin
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
def crear_feriado(
    data: DiaFestivoCreate,
    db: Session = Depends(get_db)
):
    """
    Crea un nuevo feriado nacional o departamental.

    **Validaciones:**
    - Si ambito es DEPARTAMENTAL, codigo_departamento es obligatorio
    - Si ambito es NACIONAL, codigo_departamento debe ser NULL
    - No puede haber duplicados (fecha, ambito, codigo_departamento)
    """
    return services.crear_dia_festivo(db, data)


@router.get(
    "/{id}",
    response_model=DiaFestivoResponse,
    summary="Obtener feriado por ID"
)
def obtener_feriado(
    id: int,
    db: Session = Depends(get_db)
):
    """Obtiene un feriado específico por su ID."""
    return services.obtener_dia_festivo(db, id)


@router.get(
    "/",
    response_model=List[DiaFestivoResponse],
    summary="Listar feriados con filtros"
)
def listar_feriados(
    activo: Optional[bool] = Query(None, description="Filtrar por estado activo"),
    ambito: Optional[AmbitoFestivoEnum] = Query(None, description="Filtrar por ámbito"),
    anio: Optional[int] = Query(None, description="Filtrar por año"),
    codigo_departamento: Optional[str] = Query(None, description="Filtrar por código departamento"),
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: int = Query(100, ge=1, le=500, description="Límite de registros"),
    db: Session = Depends(get_db)
):
    """
    Lista feriados con filtros opcionales.

    **Filtros disponibles:**
    - `activo`: true/false para filtrar por estado
    - `ambito`: NACIONAL o DEPARTAMENTAL
    - `anio`: filtrar por año específico
    - `codigo_departamento`: LP, CB, SC, OR, PT, TJ, CH, BE, PD
    """
    return services.listar_dias_festivos(
        db,
        activo=activo,
        ambito=ambito,
        anio=anio,
        codigo_departamento=codigo_departamento,
        skip=skip,
        limit=limit
    )


@router.get(
    "/aplicables/{dia}/{mes}/{codigo_departamento}",
    response_model=List[DiaFestivoResponse],
    summary="Obtener feriados aplicables a mes/día y departamento"
)
def obtener_feriados_aplicables(
    dia: int,
    mes: int,
    codigo_departamento: str,
    db: Session = Depends(get_db)
):
    """
    Obtiene feriados que aplican a un mes/día específico (recurrente anualmente).

    **Formato:**
    - `dia`: día del mes (1-31)
    - `mes`: mes del año (1-12)
    - `codigo_departamento`: LP, CB, SC, OR, PT, TJ, CH, BE, PD

    **Ejemplo:**
    - `/api/v1/feriados/aplicables/28/05/LP` → Feriados del 28 de mayo en La Paz
    - `/api/v1/feriados/aplicables/01/01/LP` → Feriados del 1 de enero en La Paz

    Retorna:
    - Feriados NACIONALES en ese mes/día
    - Feriados DEPARTAMENTALES del departamento indicado en ese mes/día

    **Nota:** Los feriados se buscan por mes y día, no por año específico.
    Se supone que los feriados se repiten anualmente.

    Este endpoint es usado por el worker de asistencia_diaria.
    """
    return services.obtener_feriados_aplicables(db, dia, mes, codigo_departamento)


@router.put(
    "/{id}",
    response_model=DiaFestivoResponse,
    summary="Actualizar feriado"
)
def actualizar_feriado(
    id: int,
    data: DiaFestivoUpdate,
    db: Session = Depends(get_db)
):
    """Actualiza los datos de un feriado existente."""
    return services.actualizar_dia_festivo(db, id, data)


@router.delete(
    "/{id}",
    response_model=DiaFestivoResponse,
    summary="Desactivar feriado (soft delete)"
)
def eliminar_feriado(
    id: int,
    db: Session = Depends(get_db)
):
    """
    Desactiva un feriado (soft delete).

    No elimina el registro, solo lo marca como inactivo.
    Los feriados históricos se conservan para auditoría.
    """
    return services.eliminar_dia_festivo(db, id)


@router.delete(
    "/{id}/permanente",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar feriado permanentemente (hard delete)",
    dependencies=[Depends(require_admin)],
)
def eliminar_feriado_permanente(
    id: int,
    db: Session = Depends(get_db)
):
    """
    Elimina permanentemente un feriado de la base de datos.

    **ADVERTENCIA:** Esta acción es irreversible.
    Solo usar si el feriado fue creado por error y no hay datos relacionados.
    """
    services.eliminar_permanente(db, id)
    return None
