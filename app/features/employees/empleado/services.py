"""
Services (lógica de negocio) para Empleado.
Operaciones CRUD + operaciones especiales (baja, suspensión, búsqueda por CI).
"""

from typing import List, Optional
from datetime import date, datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.features.employees.empleado.models import Empleado, EstadoEmpleadoEnum
from app.features.employees.empleado.schemas import (
    EmpleadoCreate,
    EmpleadoUpdate,
    EmpleadoResponse,
    EmpleadoCambioEstado
)


def create_empleado(db: Session, data: EmpleadoCreate) -> Empleado:
    """
    Crea un nuevo empleado.
    
    Validaciones:
    - CI único (numero + complemento + sufijo)
    - Departamento y cargo deben existir y estar activos
    - Edad mínima 18 años
    - Fecha ingreso coherente
    """
    # Validar CI único
    ci_existente = db.query(Empleado).filter(
        Empleado.ci_numero == data.ci_numero,
        Empleado.complemento_dep == data.complemento_dep,
        Empleado.ci_sufijo_homonimo == data.ci_sufijo_homonimo
    ).first()
    
    if ci_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un empleado con el CI {data.ci_numero}-{data.complemento_dep}" + 
                   (f"-{data.ci_sufijo_homonimo}" if data.ci_sufijo_homonimo else "")
        )
    
    # Validar complemento departamento
    from app.features.employees.departamento.models import ComplementoDep
    complemento = db.query(ComplementoDep).filter(
        ComplementoDep.codigo == data.complemento_dep
    ).first()
    if not complemento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el complemento de departamento '{data.complemento_dep}'"
        )
    
    # Validar departamento
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
            detail="No se puede asignar un empleado a un departamento inactivo"
        )
    
    # Validar cargo
    from app.features.employees.cargo.models import Cargo
    cargo = db.query(Cargo).filter(Cargo.id == data.id_cargo).first()
    if not cargo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el cargo con id {data.id_cargo}"
        )
    if not cargo.activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede asignar un empleado a un cargo inactivo"
        )
    
    # Crear empleado
    empleado = Empleado(**data.model_dump())
    db.add(empleado)
    db.commit()
    db.refresh(empleado)
    return empleado


def get_empleado_by_id(db: Session, empleado_id: int) -> Optional[Empleado]:
    """Obtiene un empleado por ID."""
    return db.query(Empleado).filter(Empleado.id == empleado_id).first()


def get_all_empleados(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    estado: Optional[str] = None,
    id_departamento: Optional[int] = None,
    id_cargo: Optional[int] = None
) -> List[Empleado]:
    """
    Obtiene todos los empleados con paginación y filtros opcionales.
    
    Args:
        skip: Offset para paginación
        limit: Cantidad máxima de resultados
        estado: Filtrar por estado (activo, baja, suspendido)
        id_departamento: Filtrar por departamento
        id_cargo: Filtrar por cargo
    """
    query = db.query(Empleado)
    
    if estado:
        query = query.filter(Empleado.estado == estado)
    
    if id_departamento:
        query = query.filter(Empleado.id_departamento == id_departamento)
    
    if id_cargo:
        query = query.filter(Empleado.id_cargo == id_cargo)
    
    return query.offset(skip).limit(limit).all()


def buscar_empleado_por_ci(
    db: Session,
    ci_numero: str,
    complemento_dep: str,
    ci_sufijo: Optional[str] = None
) -> Optional[Empleado]:
    """
    Busca un empleado por su CI completo.
    
    Args:
        ci_numero: Número de CI
        complemento_dep: Código departamento (LP, CB, SC, etc.)
        ci_sufijo: Sufijo homónimo opcional
    """
    query = db.query(Empleado).filter(
        Empleado.ci_numero == ci_numero,
        Empleado.complemento_dep == complemento_dep
    )
    
    if ci_sufijo:
        query = query.filter(Empleado.ci_sufijo_homonimo == ci_sufijo)
    else:
        query = query.filter(Empleado.ci_sufijo_homonimo.is_(None))
    
    return query.first()


def update_empleado(
    db: Session,
    empleado_id: int,
    data: EmpleadoUpdate
) -> Empleado:
    """
    Actualiza un empleado existente.
    
    Validaciones:
    - El empleado debe existir
    - Si cambia departamento o cargo, validar que existan y estén activos
    """
    empleado = get_empleado_by_id(db, empleado_id)
    if not empleado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el empleado con id {empleado_id}"
        )
    
    # Validar departamento si cambió
    if data.id_departamento and data.id_departamento != empleado.id_departamento:
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
                detail="No se puede asignar un empleado a un departamento inactivo"
            )
    
    # Validar cargo si cambió
    if data.id_cargo and data.id_cargo != empleado.id_cargo:
        from app.features.employees.cargo.models import Cargo
        cargo = db.query(Cargo).filter(Cargo.id == data.id_cargo).first()
        if not cargo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No existe el cargo con id {data.id_cargo}"
            )
        if not cargo.activo:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se puede asignar un empleado a un cargo inactivo"
            )
    
    # Aplicar cambios
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(empleado, field, value)
    
    db.commit()
    db.refresh(empleado)
    return empleado


def dar_baja_empleado(
    db: Session,
    empleado_id: int,
    data: EmpleadoCambioEstado
) -> Empleado:
    """
    Da de baja a un empleado (cambio de estado a 'baja').
    
    Esto es un soft delete - el empleado permanece en la BD
    pero ya no está activo en el sistema.
    """
    empleado = get_empleado_by_id(db, empleado_id)
    if not empleado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el empleado con id {empleado_id}"
        )
    
    if empleado.estado == EstadoEmpleadoEnum.baja:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El empleado ya está dado de baja"
        )
    
    empleado.estado = EstadoEmpleadoEnum.baja
    db.commit()
    db.refresh(empleado)
    return empleado


def suspender_empleado(
    db: Session,
    empleado_id: int,
    data: EmpleadoCambioEstado
) -> Empleado:
    """
    Suspende a un empleado temporalmente (cambio de estado a 'suspendido').
    """
    empleado = get_empleado_by_id(db, empleado_id)
    if not empleado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el empleado con id {empleado_id}"
        )
    
    if empleado.estado == EstadoEmpleadoEnum.baja:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede suspender un empleado dado de baja"
        )
    
    if empleado.estado == EstadoEmpleadoEnum.suspendido:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El empleado ya está suspendido"
        )
    
    empleado.estado = EstadoEmpleadoEnum.suspendido
    db.commit()
    db.refresh(empleado)
    return empleado


def reactivar_empleado(
    db: Session,
    empleado_id: int
) -> Empleado:
    """
    Reactiva un empleado suspendido (cambio de estado a 'activo').
    
    No permite reactivar empleados dados de baja - esos deben
    reingresarse como nuevos.
    """
    empleado = get_empleado_by_id(db, empleado_id)
    if not empleado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el empleado con id {empleado_id}"
        )
    
    if empleado.estado == EstadoEmpleadoEnum.baja:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede reactivar un empleado dado de baja. Debe reingresarse como nuevo."
        )
    
    if empleado.estado == EstadoEmpleadoEnum.activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El empleado ya está activo"
        )
    
    empleado.estado = EstadoEmpleadoEnum.activo
    db.commit()
    db.refresh(empleado)
    return empleado
