"""
Router para endpoints de Ajuste Salarial, Decretos e Impuestos.

create_ajuste_salarial y aplicar_decreto exigen admin/rrhh y derivan
id_aprobado_por del usuario autenticado (get_actor_empleado_id).

Las 5 rutas de /parametros-impuesto están cerradas (2026-08-19): escritura
admin, lectura admin+rrhh. La lectura se puede cerrar por rol sin romper nada
porque esos GET no tienen otro consumidor — el frontend no tenía cliente de este
módulo, y el único uso de parametro_impuesto en el backend es la vista SQL
v_saldo_impuestos_planilla, que lee la tabla directamente y no por HTTP.

Los endpoints de ajustes (salvo POST /) y los de decretos siguen sin guard
(fuera de alcance de ese cambio). Ojo con POST /decretos, que es escritura de
datos salariales y está abierto.
"""

from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_actor_empleado_id, get_current_user, require_admin, require_roles
from app.features.auth.usuario.models import Usuario
from app.features.contracts.ajuste_salarial import services
from app.features.contracts.ajuste_salarial.schemas import (
    AjusteSalarialCreate,
    AjusteSalarialResponse,
    DecretoCreate,
    DecretoResponse,
    ParametroImpuestoCreate,
    ParametroImpuestoResponse,
    AplicarDecretoResponse
)

router = APIRouter(
    prefix="/ajustes-salariales",
    tags=["Ajustes Salariales y Decretos"]
)


# ============================================================
# AJUSTES SALARIALES
# ============================================================

@router.post(
    "/",
    response_model=AjusteSalarialResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear ajuste salarial",
    description="Registra un nuevo ajuste salarial para contratos indefinidos a partir del ID del empleado. El backend resuelve el contrato vigente y el salario actual.",
    dependencies=[Depends(require_roles("admin", "rrhh"))],
)
def create_ajuste_salarial(
    data: AjusteSalarialCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Crea un nuevo ajuste salarial para contratos indefinidos.

    El backend obtiene el contrato vigente y el salario actual del empleado.
    El trigger trg_sync_salario_empleado actualiza automáticamente
    empleado.salario_base si fecha_vigencia <= hoy.

    id_aprobado_por se toma del usuario autenticado, no del body.
    """
    return services.create_ajuste_salarial(db, data, id_aprobado_por=get_actor_empleado_id(current_user))


@router.get(
    "/empleado/{empleado_id}/historial",
    response_model=List[AjusteSalarialResponse],
    summary="Historial de ajustes de un empleado",
    description="Retorna el historial completo de ajustes salariales"
)
def get_historial_ajustes(
    empleado_id: int = Path(..., gt=0),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Obtiene el historial completo de ajustes salariales de un empleado."""
    return services.get_ajustes_by_empleado(db, empleado_id, skip, limit)


@router.get(
    "/empleado/{empleado_id}/vigente",
    response_model=Optional[AjusteSalarialResponse],
    summary="Último ajuste vigente",
    description="Retorna el último ajuste salarial vigente del empleado"
)
def get_ajuste_vigente(
    empleado_id: int = Path(..., gt=0),
    db: Session = Depends(get_db)
):
    """Obtiene el ajuste vigente más reciente cuya fecha_vigencia ya sea aplicable."""
    return services.get_ultimo_ajuste_vigente(db, empleado_id)


# ============================================================
# DECRETOS
# ============================================================

@router.post(
    "/decretos",
    response_model=DecretoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear decreto",
    description="Crea un nuevo decreto con sus tramos salariales"
)
def create_decreto(
    data: DecretoCreate,
    db: Session = Depends(get_db)
):
    """
    Crea un decreto de incremento salarial con sus condiciones (tramos).
    
    El año debe ser único.
    """
    return services.create_decreto(db, data)


@router.get(
    "/decretos",
    response_model=List[DecretoResponse],
    summary="Listar decretos",
    description="Obtiene todos los decretos ordenados por año descendente"
)
def get_all_decretos(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Lista todos los decretos."""
    return services.get_all_decretos(db, skip, limit)


@router.get(
    "/decretos/{decreto_id}",
    response_model=DecretoResponse,
    summary="Obtener decreto por ID",
    description="Retorna un decreto con todas sus condiciones"
)
def get_decreto(
    decreto_id: int = Path(..., gt=0),
    db: Session = Depends(get_db)
):
    """Obtiene un decreto por ID."""
    decreto = services.get_decreto_by_id(db, decreto_id)
    if not decreto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el decreto con ID {decreto_id}"
        )
    return decreto


@router.get(
    "/decretos/anio/{anio}",
    response_model=DecretoResponse,
    summary="Obtener decreto por año",
    description="Retorna el decreto de un año específico"
)
def get_decreto_anio(
    anio: int = Path(..., ge=2000, le=2100),
    db: Session = Depends(get_db)
):
    """Obtiene el decreto de un año."""
    decreto = services.get_decreto_by_anio(db, anio)
    if not decreto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe decreto para el año {anio}"
        )
    return decreto


@router.post(
    "/decretos/{decreto_id}/aplicar",
    response_model=AplicarDecretoResponse,
    summary="Aplicar decreto a todos los empleados",
    description="Aplica el decreto a TODOS los empleados con contrato indefinido activo",
    dependencies=[Depends(require_admin)],
)
def aplicar_decreto(
    decreto_id: int = Path(..., gt=0),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Aplica un decreto anual a todos los empleados.

    Proceso:
    - Itera sobre empleados con contrato indefinido activo
    - Calcula el porcentaje de incremento según su salario
    - Crea ajuste_salarial para cada uno
    - El trigger actualiza empleado.salario_base automáticamente

    id_aprobado_por se toma del usuario autenticado, no del body.
    Retorna estadísticas de la aplicación.
    """
    resultado = services.aplicar_decreto_anual(db, decreto_id, get_actor_empleado_id(current_user))
    return AplicarDecretoResponse(**resultado)


# ============================================================
# PARÁMETROS DE IMPUESTOS
# ============================================================

@router.post(
    "/parametros-impuesto",
    response_model=ParametroImpuestoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear parámetro de impuesto",
    description=(
        "Registra una nueva tasa vigente (RC_IVA, AFP_LABORAL, etc.) y cierra la "
        "vigencia de la anterior del mismo concepto en la misma transacción."
    ),
    dependencies=[Depends(require_admin)],
)
def create_parametro_impuesto(
    data: ParametroImpuestoCreate,
    db: Session = Depends(get_db)
):
    """Crea un nuevo parámetro de impuesto y cierra la tasa anterior."""
    return services.create_parametro_impuesto(db, data)


@router.get(
    "/parametros-impuesto",
    response_model=List[ParametroImpuestoResponse],
    summary="Todas las tasas registradas",
    description="Retorna todas las tasas, vigentes e históricas, de todos los conceptos",
    dependencies=[Depends(require_roles("admin", "rrhh"))],
)
def get_all_parametros_impuesto(
    db: Session = Depends(get_db)
):
    """Todas las tasas, para la pantalla de impuestos (vigentes + historial)."""
    return services.get_all_parametros_impuesto(db)


@router.get(
    "/parametros-impuesto/vigente/{nombre}",
    response_model=Optional[ParametroImpuestoResponse],
    summary="Obtener parámetro vigente",
    description="Retorna la tasa vigente actual de un concepto",
    dependencies=[Depends(require_roles("admin", "rrhh"))],
)
def get_parametro_vigente(
    nombre: str = Path(..., description="Nombre del concepto (ej: RC_IVA, AFP_LABORAL)"),
    fecha: Optional[date] = Query(None, description="Fecha de consulta (default: hoy)"),
    db: Session = Depends(get_db)
):
    """Obtiene el parámetro vigente en una fecha."""
    parametro = services.get_parametro_vigente(db, nombre, fecha)
    if not parametro:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe parámetro vigente para '{nombre}' en la fecha indicada"
        )
    return parametro


@router.get(
    "/parametros-impuesto/historial/{nombre}",
    response_model=List[ParametroImpuestoResponse],
    summary="Historial de parámetro",
    description="Retorna el historial completo de cambios de un concepto",
    dependencies=[Depends(require_roles("admin", "rrhh"))],
)
def get_historial_parametro(
    nombre: str = Path(...),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Obtiene el historial de un parámetro."""
    return services.get_historial_parametro(db, nombre, skip, limit)


@router.get(
    "/parametros-impuesto/vigentes",
    response_model=List[ParametroImpuestoResponse],
    summary="Todos los parámetros vigentes",
    description="Retorna todos los parámetros vigentes actualmente",
    dependencies=[Depends(require_roles("admin", "rrhh"))],
)
def get_parametros_vigentes(
    db: Session = Depends(get_db)
):
    """Obtiene todos los parámetros vigentes."""
    return services.get_all_parametros_vigentes(db)
