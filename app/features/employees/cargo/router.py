"""
Router para endpoints de Cargo.
Todos los endpoints están abiertos (sin autenticación hasta Semana 9).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.employees.cargo import services
from app.features.employees.cargo.schemas import (
    CargoCreate,
    CargoUpdate,
    CargoResponse
)

router = APIRouter(
    prefix="/cargos",
    tags=["Cargos"]
)


@router.post(
    "/",
    response_model=CargoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear cargo",
    description="Crea un nuevo cargo dentro de un departamento"
)
def create_cargo(
    data: CargoCreate,
    db: Session = Depends(get_db)
):
    """
    Crea un nuevo cargo.
    
    - **nombre**: Nombre del cargo
    - **codigo**: Código único del cargo
    - **nivel**: Nivel jerárquico (1=más alto, 10=más bajo)
    - **es_cargo_confianza**: Si TRUE, exento de marcar huella biométrica
    - **id_departamento**: ID del departamento al que pertenece
    """
    return services.create_cargo(db, data)


@router.get(
    "/",
    response_model=List[CargoResponse],
    summary="Listar cargos",
    description="Obtiene todos los cargos con paginación y filtros opcionales"
)
def get_all_cargos(
    skip: int = Query(0, ge=0, description="Offset para paginación"),
    limit: int = Query(100, ge=1, le=500, description="Cantidad máxima de resultados"),
    id_departamento: Optional[int] = Query(None, description="Filtrar por departamento"),
    activo_only: bool = Query(True, description="Solo cargos activos"),
    db: Session = Depends(get_db)
):
    """Lista todos los cargos con filtros opcionales."""
    return services.get_all_cargos(
        db,
        skip=skip,
        limit=limit,
        id_departamento=id_departamento,
        activo_only=activo_only
    )


@router.get(
    "/{cargo_id}",
    response_model=CargoResponse,
    summary="Obtener cargo por ID",
    description="Retorna un cargo específico por su ID"
)
def get_cargo(
    cargo_id: int,
    db: Session = Depends(get_db)
):
    """Obtiene un cargo por ID."""
    cargo = services.get_cargo_by_id(db, cargo_id)
    if not cargo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el cargo con id {cargo_id}"
        )
    return cargo


@router.put(
    "/{cargo_id}",
    response_model=CargoResponse,
    summary="Actualizar cargo",
    description="Actualiza los datos de un cargo existente"
)
def update_cargo(
    cargo_id: int,
    data: CargoUpdate,
    db: Session = Depends(get_db)
):
    """Actualiza un cargo existente."""
    return services.update_cargo(db, cargo_id, data)


@router.delete(
    "/{cargo_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar cargo",
    description="Elimina (soft delete) un cargo. No permite eliminar si tiene empleados activos."
)
def delete_cargo(
    cargo_id: int,
    db: Session = Depends(get_db)
):
    """
    Elimina un cargo (soft delete).
    
    Validaciones:
    - No puede tener empleados activos asignados
    """
    services.delete_cargo(db, cargo_id)
    return None
