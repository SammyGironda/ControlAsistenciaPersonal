"""
Router para endpoints de Contrato.
Todos los endpoints están abiertos (sin autenticación hasta Semana 9).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.contracts.contrato import services
from app.features.contracts.contrato.schemas import (
    ContratoCreate,
    ContratoUpdate,
    ContratoResponse,
    ContratoRenovacion
)

router = APIRouter(
    prefix="/contratos",
    tags=["Contratos"]
)


@router.post(
    "/",
    response_model=ContratoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear contrato",
    description="Registra un nuevo contrato laboral"
)
def create_contrato(
    data: ContratoCreate,
    db: Session = Depends(get_db)
):
    """
    Crea un nuevo contrato.
    
    Validaciones:
    - El empleado debe existir y estar activo
    - No debe tener otro contrato activo
    - Si es plazo_fijo, debe tener fecha_fin
    """
    return services.create_contrato(db, data)


@router.get(
    "/",
    response_model=List[ContratoResponse],
    summary="Listar contratos",
    description="Obtiene todos los contratos con paginación y filtros opcionales"
)
def get_all_contratos(
    skip: int = Query(0, ge=0, description="Offset para paginación"),
    limit: int = Query(100, ge=1, le=500, description="Cantidad máxima de resultados"),
    tipo_contrato: Optional[str] = Query(None, pattern="^(indefinido|plazo_fijo)$", description="Filtrar por tipo"),
    estado: Optional[str] = Query(None, pattern="^(activo|finalizado|rescindido)$", description="Filtrar por estado"),
    db: Session = Depends(get_db)
):
    """Lista todos los contratos con filtros opcionales."""
    return services.get_all_contratos(
        db,
        skip=skip,
        limit=limit,
        tipo_contrato=tipo_contrato,
        estado=estado
    )


@router.get(
    "/empleado/{empleado_id}",
    response_model=List[ContratoResponse],
    summary="Obtener contratos de un empleado",
    description="Retorna todos los contratos (historial completo) de un empleado"
)
def get_contratos_empleado(
    empleado_id: int = Path(..., gt=0),
    solo_activos: bool = Query(False, description="Si True, solo retorna contratos activos"),
    db: Session = Depends(get_db)
):
    """Obtiene todos los contratos de un empleado."""
    return services.get_contratos_by_empleado(db, empleado_id, solo_activos)


@router.get(
    "/empleado/{empleado_id}/activo",
    response_model=Optional[ContratoResponse],
    summary="Obtener contrato activo de un empleado",
    description="Retorna el contrato activo vigente del empleado (o None si no tiene)"
)
def get_contrato_activo_empleado(
    empleado_id: int = Path(..., gt=0),
    db: Session = Depends(get_db)
):
    """Obtiene el contrato activo actual de un empleado."""
    return services.get_contrato_activo_empleado(db, empleado_id)


@router.get(
    "/{contrato_id}",
    response_model=ContratoResponse,
    summary="Obtener contrato por ID",
    description="Retorna un contrato específico por su ID"
)
def get_contrato(
    contrato_id: int = Path(..., gt=0),
    db: Session = Depends(get_db)
):
    """Obtiene un contrato por ID."""
    contrato = services.get_contrato_by_id(db, contrato_id)
    if not contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el contrato con ID {contrato_id}"
        )
    return contrato


@router.put(
    "/{contrato_id}",
    response_model=ContratoResponse,
    summary="Actualizar contrato",
    description="Actualiza campos específicos de un contrato"
)
def update_contrato(
    contrato_id: int = Path(..., gt=0),
    data: ContratoUpdate = ...,
    db: Session = Depends(get_db)
):
    """Actualiza un contrato existente."""
    return services.update_contrato(db, contrato_id, data)


@router.put(
    "/{contrato_id}/finalizar",
    response_model=ContratoResponse,
    summary="Finalizar contrato",
    description="Cambia el estado del contrato a 'finalizado' (finalización normal)"
)
def finalizar_contrato(
    contrato_id: int = Path(..., gt=0),
    observacion: Optional[str] = Query(None, max_length=500, description="Motivo de finalización"),
    db: Session = Depends(get_db)
):
    """
    Finaliza un contrato de forma normal.
    
    Se usa cuando el contrato termina según lo previsto (ej: vencimiento plazo_fijo).
    """
    return services.finalizar_contrato(db, contrato_id, observacion)


@router.put(
    "/{contrato_id}/rescindir",
    response_model=ContratoResponse,
    summary="Rescindir contrato",
    description="Cambia el estado del contrato a 'rescindido' (finalización anticipada)"
)
def rescindir_contrato(
    contrato_id: int = Path(..., gt=0),
    observacion: Optional[str] = Query(None, max_length=500, description="Motivo de rescisión"),
    db: Session = Depends(get_db)
):
    """
    Rescinde un contrato de forma anticipada o forzada.
    
    Se usa para terminaciones inesperadas, despidos, renuncias, etc.
    """
    return services.rescindir_contrato(db, contrato_id, observacion)


@router.post(
    "/{contrato_id}/renovar",
    response_model=ContratoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Renovar contrato plazo_fijo",
    description="Crea un NUEVO contrato para renovación de plazo_fijo con salario incrementado"
)
def renovar_contrato(
    contrato_id: int = Path(..., gt=0),
    data: ContratoRenovacion = ...,
    db: Session = Depends(get_db)
):
    """
    Renueva un contrato plazo_fijo.
    
    - Finaliza el contrato anterior
    - Crea un nuevo contrato con el nuevo salario
    
    NOTA: Solo para contratos plazo_fijo. Para indefinidos usar ajuste_salarial.
    """
    return services.renovar_contrato_plazo_fijo(db, contrato_id, data)
