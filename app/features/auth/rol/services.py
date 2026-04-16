"""
Services para Rol - Lógica de negocio.
Toda la lógica de negocio debe estar en los services, NO en los routers.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from fastapi import HTTPException, status

from app.features.auth.rol.models import Rol
from app.features.auth.rol import schemas
from app.features.auth.usuario.models import Usuario


# ============================================================
# CRUD BÁSICO
# ============================================================

def get_rol(db: Session, rol_id: int) -> Rol:
    """
    Obtiene un rol por ID (solo roles activos).

    Args:
        db: Sesión de base de datos
        rol_id: ID del rol a buscar

    Returns:
        Rol encontrado

    Raises:
        HTTPException 404: Si el rol no existe o está inactivo
    """
    stmt = select(Rol).where(Rol.id == rol_id).where(Rol.activo)
    rol = db.execute(stmt).scalar_one_or_none()
    if not rol:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Rol con ID {rol_id} no encontrado"
        )
    return rol


def get_rol_by_nombre(db: Session, nombre: str) -> Optional[Rol]:
    """
    Busca un rol por su nombre (solo roles activos).

    Args:
        db: Sesión de base de datos
        nombre: Nombre del rol

    Returns:
        Rol encontrado o None si no existe
    """
    stmt = select(Rol).where(func.lower(Rol.nombre) == nombre.lower()).where(Rol.activo)
    return db.execute(stmt).scalar_one_or_none()


def get_roles(
    db: Session,
    skip: int = 0,
    limit: int = 100
) -> List[Rol]:
    stmt = select(Rol).offset(skip).limit(limit)
    stmt = stmt.where(Rol.activo)

    return list(db.execute(stmt).scalars())


def create_rol(db: Session, rol_data: schemas.RolCreate) -> Rol:
    """
    Crea un nuevo rol.
    
    Args:
        db: Sesión de base de datos
        rol_data: Datos del rol a crear
        
    Returns:
        Rol creado
        
    Raises:
        HTTPException 400: Si el nombre ya existe
    """
    # Validar que el nombre no exista
    existing = get_rol_by_nombre(db, rol_data.nombre)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un rol con el nombre '{rol_data.nombre}'"
        )
    
    # Crear el rol
    rol = Rol(**rol_data.model_dump())
    db.add(rol)
    db.commit()
    db.refresh(rol)
    return rol


def update_rol(
    db: Session,
    rol_id: int,
    rol_data: schemas.RolUpdate
) -> Rol:
    """
    Actualiza un rol existente.
    
    Args:
        db: Sesión de base de datos
        rol_id: ID del rol a actualizar
        rol_data: Datos a actualizar (solo los campos presentes)
        
    Returns:
        Rol actualizado
        
    Raises:
        HTTPException 404: Si el rol no existe
        HTTPException 400: Si el nuevo nombre ya existe
    """
    rol = get_rol(db, rol_id)
    
    # Validar cambio de nombre si se está actualizando
    if rol_data.nombre and rol_data.nombre != rol.nombre:
        existing = get_rol_by_nombre(db, rol_data.nombre)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe un rol con el nombre '{rol_data.nombre}'"
            )
    
    # Actualizar solo los campos que vienen en el request
    update_data = rol_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(rol, field, value)
    
    db.commit()
    db.refresh(rol)
    return rol


def delete_rol(db: Session, rol_id: int) -> dict:
    """
    Elimina un rol existente.

    Args:
        db: Sesión de base de datos
        rol_id: ID del rol a eliminar

    Returns:
        Mensaje de confirmación

    Raises:
        HTTPException 404: Si el rol no existe
        HTTPException 400: Si el rol tiene usuarios asociados
    """
    rol = get_rol(db, rol_id)

    # Validar que no tenga usuarios asociados
    count = db.execute(
        select(func.count()).select_from(Usuario).where(Usuario.id_rol == rol_id)
    ).scalar()

    if count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede eliminar el rol porque tiene {count} usuario(s) asociado(s)"
        )

    db.delete(rol)
    db.commit()
    return {"message": f"Rol '{rol.nombre}' eliminado exitosamente"}


# ============================================================
# OPERACIONES ESPECÍFICAS DE NEGOCIO
# ============================================================

def toggle_activo(db: Session, rol_id: int) -> Rol:
    """
    Activa o desactiva un rol.

    Args:
        db: Sesión de base de datos
        rol_id: ID del rol a alternar

    Returns:
        Rol con estado actualizado

    Raises:
        HTTPException 404: Si el rol no existe
    """
    rol = get_rol(db, rol_id)
    rol.activo = not rol.activo
    db.commit()
    db.refresh(rol)
    return rol


def count_usuarios_by_rol(db: Session, rol_id: int) -> int:
    return db.execute(
        select(func.count()).where(Usuario.id_rol == rol_id)
    ).scalar()
