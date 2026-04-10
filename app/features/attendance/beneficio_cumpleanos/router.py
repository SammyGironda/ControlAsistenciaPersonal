"""
Router para BeneficioCumpleanos - Endpoints REST para gestión del beneficio de cumpleaños.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status, Body
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.attendance.beneficio_cumpleanos import services
from app.features.attendance.beneficio_cumpleanos.schemas import (
    BeneficioCumpleanosCreate,
    BeneficioCumpleanosUpdate,
    BeneficioCumpleanosResponse
)

router = APIRouter(prefix="/beneficios-cumpleanos", tags=["Beneficios Cumpleaños"])


@router.post(
    "/",
    response_model=BeneficioCumpleanosResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear beneficio de cumpleaños"
)
def crear_beneficio(
    data: BeneficioCumpleanosCreate,
    db: Session = Depends(get_db)
):
    """
    Crea un nuevo beneficio de cumpleaños para un empleado.

    **Normalmente este endpoint es llamado automáticamente por el worker diario.**

    Validaciones:
    - No puede haber duplicados (id_empleado, gestion)
    """
    return services.crear_beneficio_cumpleanos(db, data)


@router.get(
    "/{id}",
    response_model=BeneficioCumpleanosResponse,
    summary="Obtener beneficio por ID"
)
def obtener_beneficio(
    id: int,
    db: Session = Depends(get_db)
):
    """Obtiene un beneficio específico por su ID."""
    return services.obtener_beneficio(db, id)


@router.get(
    "/empleado/{id_empleado}/gestion/{gestion}",
    response_model=Optional[BeneficioCumpleanosResponse],
    summary="Obtener beneficio de empleado por gestión"
)
def obtener_beneficio_empleado_gestion(
    id_empleado: int,
    gestion: int,
    db: Session = Depends(get_db)
):
    """Obtiene el beneficio de cumpleaños de un empleado para una gestión específica."""
    return services.obtener_beneficio_por_empleado_gestion(db, id_empleado, gestion)


@router.get(
    "/",
    response_model=List[BeneficioCumpleanosResponse],
    summary="Listar beneficios con filtros"
)
def listar_beneficios(
    gestion: Optional[int] = Query(None, description="Filtrar por año"),
    fue_utilizado: Optional[bool] = Query(None, description="Filtrar por estado de uso"),
    transferido_a_vacacion: Optional[bool] = Query(None, description="Filtrar por transferencia"),
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: int = Query(100, ge=1, le=500, description="Límite de registros"),
    db: Session = Depends(get_db)
):
    """
    Lista beneficios con filtros opcionales.

    **Filtros disponibles:**
    - `gestion`: filtrar por año
    - `fue_utilizado`: true/false si fue usado
    - `transferido_a_vacacion`: true/false si fue transferido
    """
    return services.listar_beneficios(
        db,
        gestion=gestion,
        fue_utilizado=fue_utilizado,
        transferido_a_vacacion=transferido_a_vacacion,
        skip=skip,
        limit=limit
    )


@router.post(
    "/{id}/marcar-utilizado",
    response_model=BeneficioCumpleanosResponse,
    summary="Marcar beneficio como utilizado"
)
def marcar_utilizado(
    id: int,
    id_justificacion: Optional[int] = Body(None, embed=True),
    db: Session = Depends(get_db)
):
    """
    Marca un beneficio como utilizado por el empleado.

    Opcionalmente se puede vincular con una justificación de ausencia.
    """
    return services.marcar_como_utilizado(db, id, id_justificacion)


@router.post(
    "/{id}/transferir-vacacion",
    response_model=BeneficioCumpleanosResponse,
    summary="Transferir beneficio a vacaciones"
)
def transferir_vacacion(
    id: int,
    db: Session = Depends(get_db)
):
    """
    Marca un beneficio como transferido a vacaciones.

    **Este endpoint es llamado automáticamente por el worker de fin de año.**

    El worker debe sumar 4h a vacacion.horas_goce_haber antes de llamar este endpoint.
    """
    return services.transferir_a_vacacion(db, id)


@router.put(
    "/{id}",
    response_model=BeneficioCumpleanosResponse,
    summary="Actualizar beneficio"
)
def actualizar_beneficio(
    id: int,
    data: BeneficioCumpleanosUpdate,
    db: Session = Depends(get_db)
):
    """Actualiza los datos de un beneficio existente."""
    return services.actualizar_beneficio(db, id, data)


@router.delete(
    "/{id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar beneficio"
)
def eliminar_beneficio(
    id: int,
    db: Session = Depends(get_db)
):
    """
    Elimina un beneficio de cumpleaños.

    Solo usar en caso de error o para pruebas.
    """
    services.eliminar_beneficio(db, id)
    return None
