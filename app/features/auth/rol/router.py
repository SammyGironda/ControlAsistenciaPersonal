"""
Router para Rol - Endpoints REST.
Todos los endpoints están abiertos hasta Semana 9.
"""

from typing import List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.auth.rol import schemas, services

# Crear router con documentación
router = APIRouter(
    prefix="/roles",
    tags=["Roles"],
    responses={404: {"description": "No encontrado"}}
)


@router.post(
    "/",
    response_model=schemas.RolRead,
    status_code=201,
    summary="Crear nuevo rol"
)
def create_rol(
    rol: schemas.RolCreate,
    db: Session = Depends(get_db)
):
    """
    Crea un nuevo rol en el sistema.
    
    - **nombre**: Nombre único del rol (ej: ADMIN, RRHH, CONSULTA)
    - **descripcion**: Descripción opcional del rol
    - **activo**: Estado del rol (True por defecto)
    """
    return services.create_rol(db, rol)


@router.get(
    "/",
    response_model=List[schemas.RolRead],
    summary="Listar todos los roles"
)
def list_roles(
    skip: int = Query(0, ge=0, description="Cantidad de registros a saltar"),
    limit: int = Query(100, ge=1, le=1000, description="Cantidad máxima de registros"),
    solo_activos: bool = Query(False, description="Filtrar solo roles activos"),
    db: Session = Depends(get_db)
):
    """
    Lista todos los roles del sistema con paginación.
    
    Parámetros de consulta:
    - **skip**: Offset para paginación
    - **limit**: Límite de resultados
    - **solo_activos**: Si es True, solo retorna roles activos
    """
    return services.get_roles(db, skip=skip, limit=limit, solo_activos=solo_activos)


@router.get(
    "/{rol_id}",
    response_model=schemas.RolRead,
    summary="Obtener rol por ID"
)
def get_rol(
    rol_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene un rol específico por su ID.
    
    Retorna error 404 si el rol no existe.
    """
    return services.get_rol(db, rol_id)


@router.put(
    "/{rol_id}",
    response_model=schemas.RolRead,
    summary="Actualizar rol"
)
def update_rol(
    rol_id: int,
    rol: schemas.RolUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualiza un rol existente.
    
    Solo se actualizan los campos que se envían en el request.
    """
    return services.update_rol(db, rol_id, rol)


@router.delete(
    "/{rol_id}",
    summary="Eliminar rol (hard delete)"
)
def delete_rol(
    rol_id: int,
    db: Session = Depends(get_db)
):
    """
    Elimina un rol permanentemente.
    
    **IMPORTANTE**: No se puede eliminar si tiene usuarios asociados.
    
    Retorna error 400 si el rol tiene usuarios.
    """
    return services.delete_rol(db, rol_id)


@router.patch(
    "/{rol_id}/toggle-activo",
    response_model=schemas.RolRead,
    summary="Activar/desactivar rol"
)
def toggle_activo_rol(
    rol_id: int,
    db: Session = Depends(get_db)
):
    """
    Alterna el estado activo/inactivo de un rol (soft delete).
    
    Esta es una alternativa más segura al hard delete.
    """
    return services.toggle_activo(db, rol_id)


@router.get(
    "/{rol_id}/usuarios/count",
    summary="Contar usuarios del rol"
)
def count_usuarios(
    rol_id: int,
    db: Session = Depends(get_db)
):
    """
    Retorna la cantidad de usuarios asignados a un rol.
    
    Útil para validar antes de eliminar un rol.
    """
    count = services.count_usuarios_by_rol(db, rol_id)
    return {"rol_id": rol_id, "cantidad_usuarios": count}
