"""
Router para endpoints de Departamento.
Todos los endpoints están abiertos (sin autenticación hasta Semana 9).
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.employees.departamento import services
from app.features.employees.departamento.schemas import (
    DepartamentoCreate,
    DepartamentoUpdate,
    DepartamentoResponse,
    DepartamentoConHijos
)

router = APIRouter(
    prefix="/departamentos",
    tags=["Departamentos"]
)


@router.post(
    "/",
    response_model=DepartamentoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear departamento",
    description="Crea un nuevo departamento organizacional. Puede ser raíz (id_padre=NULL) o hijo."
)
def create_departamento(
    data: DepartamentoCreate,
    db: Session = Depends(get_db)
):
    """
    Crea un nuevo departamento.
    
    - **nombre**: Nombre del departamento
    - **codigo**: Código único del departamento
    - **id_padre**: ID del departamento padre (NULL = raíz)
    - **activo**: Estado del departamento
    """
    return services.create_departamento(db, data)


@router.get(
    "/",
    response_model=List[DepartamentoResponse],
    summary="Listar departamentos",
    description="Obtiene todos los departamentos con paginación opcional"
)
def get_all_departamentos(
    skip: int = Query(0, ge=0, description="Offset para paginación"),
    limit: int = Query(100, ge=1, le=500, description="Cantidad máxima de resultados"),
    activo_only: bool = Query(False, description="Solo departamentos activos"),
    db: Session = Depends(get_db)
):
    """Lista todos los departamentos con filtros opcionales."""
    return services.get_all_departamentos(db, skip=skip, limit=limit, activo_only=activo_only)


@router.get(
    "/raiz",
    response_model=List[DepartamentoConHijos],
    summary="Obtener árbol organizacional completo",
    description="Retorna todos los departamentos raíz con su jerarquía completa de hijos"
)
def get_departamentos_raiz(db: Session = Depends(get_db)):
    """
    Obtiene el árbol organizacional completo.
    
    Retorna solo los departamentos raíz (id_padre=NULL),
    pero cada uno incluye recursivamente todos sus hijos.
    """
    return services.get_departamentos_raiz(db)


@router.get(
    "/{departamento_id}",
    response_model=DepartamentoResponse,
    summary="Obtener departamento por ID",
    description="Retorna un departamento específico por su ID"
)
def get_departamento(
    departamento_id: int,
    db: Session = Depends(get_db)
):
    """Obtiene un departamento por ID."""
    departamento = services.get_departamento_by_id(db, departamento_id)
    if not departamento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el departamento con id {departamento_id}"
        )
    return departamento


@router.get(
    "/{departamento_id}/jerarquia",
    response_model=DepartamentoConHijos,
    summary="Obtener departamento con jerarquía de hijos",
    description="Retorna un departamento con todos sus subdepartamentos (recursivo)"
)
def get_jerarquia_departamento(
    departamento_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene un departamento con toda su jerarquía de hijos.
    
    Útil para visualizar la estructura organizacional
    debajo de un departamento específico.
    """
    return services.get_jerarquia_departamento(db, departamento_id)


@router.put(
    "/{departamento_id}",
    response_model=DepartamentoResponse,
    summary="Actualizar departamento",
    description="Actualiza los datos de un departamento existente"
)
def update_departamento(
    departamento_id: int,
    data: DepartamentoUpdate,
    db: Session = Depends(get_db)
):
    """Actualiza un departamento existente."""
    return services.update_departamento(db, departamento_id, data)


@router.delete(
    "/{departamento_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar departamento",
    description="Elimina (soft delete) un departamento. No permite eliminar si tiene hijos, cargos o empleados activos."
)
def delete_departamento(
    departamento_id: int,
    db: Session = Depends(get_db)
):
    """
    Elimina un departamento (soft delete).
    
    Validaciones:
    - No puede tener subdepartamentos activos
    - No puede tener cargos asignados
    - No puede tener empleados activos
    """
    services.delete_departamento(db, departamento_id)
    return None
