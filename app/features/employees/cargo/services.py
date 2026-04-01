"""
Services (lógica de negocio) para Cargo.
Operaciones CRUD + validaciones de negocio.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.features.employees.cargo.models import Cargo
from app.features.employees.cargo.schemas import (
    CargoCreate,
    CargoUpdate,
    CargoResponse
)


def create_cargo(db: Session, data: CargoCreate) -> Cargo:
    """
    Crea un nuevo cargo.
    
    Validaciones:
    - El código debe ser único
    - El departamento debe existir y estar activo
    """
    # Validar código único
    existing = db.query(Cargo).filter(Cargo.codigo == data.codigo).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un cargo con el código '{data.codigo}'"
        )
    
    # Validar que el departamento existe y está activo
    from app.features.employees.departamento.models import Departamento
    departamento = db.query(Departamento).filter(Departamento.id == data.id_departamento).first()
    if not departamento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el departamento con id {data.id_departamento}"
        )
    if not departamento.activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede asignar un cargo a un departamento inactivo"
        )
    
    # Crear cargo
    cargo = Cargo(**data.model_dump())
    db.add(cargo)
    db.commit()
    db.refresh(cargo)
    return cargo


def get_cargo_by_id(db: Session, cargo_id: int) -> Optional[Cargo]:
    """Obtiene un cargo por ID."""
    return db.query(Cargo).filter(Cargo.id == cargo_id).first()


def get_all_cargos(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    id_departamento: Optional[int] = None,
    activo_only: bool = False
) -> List[Cargo]:
    """
    Obtiene todos los cargos con paginación y filtros opcionales.
    
    Args:
        skip: Offset para paginación
        limit: Cantidad máxima de resultados
        id_departamento: Filtrar por departamento específico
        activo_only: Si TRUE, solo devuelve cargos activos
    """
    query = db.query(Cargo)
    
    if id_departamento:
        query = query.filter(Cargo.id_departamento == id_departamento)
    
    if activo_only:
        query = query.filter(Cargo.activo == True)
    
    return query.offset(skip).limit(limit).all()


def update_cargo(
    db: Session,
    cargo_id: int,
    data: CargoUpdate
) -> Cargo:
    """
    Actualiza un cargo existente.
    
    Validaciones:
    - El cargo debe existir
    - Si cambia el código, validar que sea único
    - Si cambia el departamento, validar que exista y esté activo
    """
    cargo = get_cargo_by_id(db, cargo_id)
    if not cargo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el cargo con id {cargo_id}"
        )
    
    # Validar código único si cambió
    if data.codigo and data.codigo != cargo.codigo:
        existing = db.query(Cargo).filter(Cargo.codigo == data.codigo).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe un cargo con el código '{data.codigo}'"
            )
    
    # Validar departamento si cambió
    if data.id_departamento and data.id_departamento != cargo.id_departamento:
        from app.features.employees.departamento.models import Departamento
        departamento = db.query(Departamento).filter(Departamento.id == data.id_departamento).first()
        if not departamento:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No existe el departamento con id {data.id_departamento}"
            )
        if not departamento.activo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede asignar un cargo a un departamento inactivo"
            )
    
    # Aplicar cambios
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(cargo, field, value)
    
    db.commit()
    db.refresh(cargo)
    return cargo


def delete_cargo(db: Session, cargo_id: int) -> bool:
    """
    Elimina un cargo (soft delete).
    
    Validaciones:
    - No se puede eliminar si tiene empleados activos asignados
    """
    cargo = get_cargo_by_id(db, cargo_id)
    if not cargo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el cargo con id {cargo_id}"
        )
    
    # Validar que no tenga empleados activos
    from app.features.employees.empleado.models import Empleado
    empleados_count = db.query(Empleado).filter(
        Empleado.id_cargo == cargo_id,
        Empleado.estado == "activo"
    ).count()
    
    if empleados_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede eliminar el cargo porque tiene {empleados_count} empleado(s) activo(s) asignado(s)"
        )
    
    # Realizar soft delete
    cargo.activo = False
    db.commit()
    return True
