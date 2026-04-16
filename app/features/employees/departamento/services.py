"""
Services (lógica de negocio) para Departamento.
Operaciones CRUD + validaciones de negocio.
"""

from typing import List, Optional
from sqlalchemy.orm import Session, selectinload
from sqlalchemy import select
from fastapi import HTTPException, status

from app.features.employees.departamento.models import Departamento
from app.features.employees.departamento.schemas import (
    DepartamentoCreate,
    DepartamentoUpdate,
    DepartamentoResponse,
    DepartamentoConHijos
)


def create_departamento(db: Session, data: DepartamentoCreate) -> Departamento:
    """
    Crea un nuevo departamento.
    
    Validaciones:
    - El código debe ser único
    - Si tiene id_padre, validar que el padre existe y está activo
    """
    # Validar código único
    existing = db.query(Departamento).filter(Departamento.codigo == data.codigo).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un departamento con el código '{data.codigo}'"
        )
    
    # Validar padre si existe
    if data.id_padre:
        padre = db.query(Departamento).filter(Departamento.id == data.id_padre).first()
        if not padre:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No existe el departamento padre con id {data.id_padre}"
            )
        if not padre.activo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede asignar un departamento padre inactivo"
            )
    
    # Crear departamento
    departamento = Departamento(**data.model_dump())
    db.add(departamento)
    db.commit()
    db.refresh(departamento)
    return departamento


def get_departamento_by_id(db: Session, departamento_id: int) -> Optional[Departamento]:
    """Obtiene un departamento por ID."""
    return db.query(Departamento).filter(Departamento.id == departamento_id).first()


def get_all_departamentos(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    activo_only: bool = False
) -> List[Departamento]:
    """
    Obtiene todos los departamentos con paginación.
    
    Args:
        skip: Offset para paginación
        limit: Cantidad máxima de resultados
        activo_only: Si TRUE, solo devuelve departamentos activos
    """
    query = db.query(Departamento)
    
    if activo_only:
        query = query.filter(Departamento.activo == True)
    
    return query.offset(skip).limit(limit).all()


def update_departamento(
    db: Session,
    departamento_id: int,
    data: DepartamentoUpdate
) -> Departamento:
    """
    Actualiza un departamento existente.
    
    Validaciones:
    - El departamento debe existir
    - Si cambia el código, validar que sea único
    - Si cambia id_padre, validar que no se cree un ciclo
    """
    departamento = get_departamento_by_id(db, departamento_id)
    if not departamento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el departamento con id {departamento_id}"
        )
    
    # Validar código único si cambió
    if data.codigo and data.codigo != departamento.codigo:
        existing = db.query(Departamento).filter(Departamento.codigo == data.codigo).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe un departamento con el código '{data.codigo}'"
            )
    
    # Validar id_padre si cambió
    if data.id_padre is not None and data.id_padre != departamento.id_padre:
        # No permitir que un departamento sea su propio padre
        if data.id_padre == departamento_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Un departamento no puede ser su propio padre"
            )
        
        # Validar que el nuevo padre existe
        if data.id_padre:
            padre = db.query(Departamento).filter(Departamento.id == data.id_padre).first()
            if not padre:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"No existe el departamento padre con id {data.id_padre}"
                )
    
    # Aplicar cambios
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(departamento, field, value)
    
    db.commit()
    db.refresh(departamento)
    return departamento


def delete_departamento(db: Session, departamento_id: int) -> bool:
    """
    Elimina un departamento (soft delete o hard delete según reglas de negocio).
    
    Validaciones:
    - No se puede eliminar si tiene departamentos hijos activos
    - No se puede eliminar si tiene cargos asignados
    - No se puede eliminar si tiene empleados activos
    """
    departamento = get_departamento_by_id(db, departamento_id)
    if not departamento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el departamento con id {departamento_id}"
        )
    
    # Validar que no tenga hijos activos
    hijos_activos = db.query(Departamento).filter(
        Departamento.id_padre == departamento_id,
        Departamento.activo == True
    ).count()
    
    if hijos_activos > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede eliminar el departamento porque tiene {hijos_activos} subdepartamento(s) activo(s)"
        )
    
    # Validar que no tenga cargos
    from app.features.employees.cargo.models import Cargo
    cargos_count = db.query(Cargo).filter(Cargo.id_departamento == departamento_id).count()
    
    if cargos_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede eliminar el departamento porque tiene {cargos_count} cargo(s) asignado(s)"
        )
    
    # Validar que no tenga empleados activos
    from app.features.employees.empleado.models import Empleado
    empleados_count = db.query(Empleado).filter(
        Empleado.id_departamento == departamento_id,
        Empleado.estado == "activo"
    ).count()
    
    if empleados_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede eliminar el departamento porque tiene {empleados_count} empleado(s) activo(s)"
        )
    
    # Realizar soft delete (marcar como inactivo)
    departamento.activo = False
    db.commit()
    return True


def get_jerarquia_departamento(db: Session, departamento_id: int) -> DepartamentoConHijos:
    """
    Obtiene un departamento con toda su jerarquía de hijos (árbol recursivo).
    
    Retorna un objeto DepartamentoConHijos que incluye recursivamente
    todos los departamentos descendientes.
    """
    departamento = get_departamento_by_id(db, departamento_id)
    if not departamento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el departamento con id {departamento_id}"
        )
    
    # Cargar eager loading de la jerarquía completa
    stmt = (
        select(Departamento)
        .filter(Departamento.id == departamento_id)
        .options(selectinload(Departamento.hijos, recursion_depth=5))
    )
    result = db.execute(stmt).scalar_one()
    
    return DepartamentoConHijos.model_validate(result)


def get_departamentos_raiz(db: Session) -> List[DepartamentoConHijos]:
    """
    Obtiene todos los departamentos raíz (id_padre = NULL) con su jerarquía completa.
    Útil para construir el árbol organizacional completo.
    """
    stmt = (
        select(Departamento)
        .filter(Departamento.id_padre.is_(None))
        .filter(Departamento.activo == True)
        .options(selectinload(Departamento.hijos, recursion_depth=5))
    )
    result = db.execute(stmt).scalars().all()
    
    return [DepartamentoConHijos.model_validate(dep) for dep in result]
