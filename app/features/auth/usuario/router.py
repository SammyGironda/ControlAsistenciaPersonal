"""
Router para Usuario - Endpoints REST.
Todos los endpoints están abiertos hasta Semana 9 (NO JWT aún).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.auth.usuario import schemas, services

router = APIRouter(
    prefix="/usuarios",
    tags=["Usuarios"],
    responses={404: {"description": "No encontrado"}}
)


@router.post(
    "/",
    response_model=schemas.UsuarioRead,
    status_code=201,
    summary="Crear nuevo usuario"
)
def create_usuario(
    usuario: schemas.UsuarioCreate,
    db: Session = Depends(get_db)
):
    """
    Crea un nuevo usuario en el sistema.
    
    - **username**: Username único (3-50 caracteres)
    - **password**: Contraseña (mínimo 6 caracteres, será hasheada)
    - **id_rol**: ID del rol asignado
    - **id_empleado**: ID del empleado vinculado (opcional)
    - **email**: Email del usuario (opcional)
    """
    return services.create_usuario(db, usuario)


@router.get(
    "/",
    response_model=List[schemas.UsuarioRead],
    summary="Listar todos los usuarios"
)
def list_usuarios(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    solo_activos: bool = Query(False),
    id_rol: Optional[int] = Query(None, description="Filtrar por rol"),
    db: Session = Depends(get_db)
):
    """
    Lista todos los usuarios con paginación y filtros.
    
    Parámetros:
    - **skip**: Offset para paginación
    - **limit**: Límite de resultados
    - **solo_activos**: Solo usuarios activos
    - **id_rol**: Filtrar por rol específico
    """
    return services.get_usuarios(
        db, 
        skip=skip, 
        limit=limit, 
        solo_activos=solo_activos,
        id_rol=id_rol
    )


@router.get(
    "/{usuario_id}",
    response_model=schemas.UsuarioRead,
    summary="Obtener usuario por ID"
)
def get_usuario(
    usuario_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene un usuario específico por su ID.
    
    Retorna error 404 si no existe.
    """
    return services.get_usuario(db, usuario_id)


@router.get(
    "/{usuario_id}/with-rol",
    response_model=schemas.UsuarioReadWithRol,
    summary="Obtener usuario con info del rol"
)
def get_usuario_with_rol(
    usuario_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene un usuario con información expandida del rol.
    
    Incluye el nombre del rol además del id_rol.
    """
    return services.get_usuario_with_rol_info(db, usuario_id)


@router.put(
    "/{usuario_id}",
    response_model=schemas.UsuarioRead,
    summary="Actualizar usuario"
)
def update_usuario(
    usuario_id: int,
    usuario: schemas.UsuarioUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualiza un usuario existente.
    
    Solo se actualizan los campos enviados.
    Si se envía password, se hashea automáticamente.
    """
    return services.update_usuario(db, usuario_id, usuario)


@router.delete(
    "/{usuario_id}",
    summary="Eliminar usuario (hard delete)"
)
def delete_usuario(
    usuario_id: int,
    db: Session = Depends(get_db)
):
    """
    Elimina un usuario permanentemente de la base de datos.
    """
    return services.delete_usuario(db, usuario_id)


@router.patch(
    "/{usuario_id}/toggle-activo",
    response_model=schemas.UsuarioRead,
    summary="Activar/desactivar usuario"
)
def toggle_activo_usuario(
    usuario_id: int,
    db: Session = Depends(get_db)
):
    """
    Alterna el estado activo/inactivo de un usuario (soft delete).
    
    Alternativa más segura al hard delete.
    """
    return services.toggle_activo(db, usuario_id)


@router.post(
    "/{usuario_id}/change-password",
    summary="Cambiar contraseña"
)
def change_password(
    usuario_id: int,
    password_data: schemas.UsuarioChangePassword,
    db: Session = Depends(get_db)
):
    """
    Cambia la contraseña de un usuario.
    
    Requiere:
    - **password_actual**: Contraseña actual (para verificación)
    - **password_nueva**: Nueva contraseña
    
    Retorna error 400 si la contraseña actual no es correcta.
    """
    return services.change_password(db, usuario_id, password_data)


@router.post(
    "/verify-credentials",
    summary="Verificar credenciales"
)
def verify_credentials(
    username: str = Query(..., description="Username del usuario"),
    password: str = Query(..., description="Contraseña en texto plano"),
    db: Session = Depends(get_db)
):
    """
    Verifica las credenciales de un usuario.
    
    Útil para testing. En Semana 9 se usará con JWT.
    
    Retorna el usuario si las credenciales son correctas,
    o error 401 si no.
    """
    usuario = services.verify_credentials(db, username, password)
    
    if not usuario:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas"
        )
    
    return {
        "message": "Credenciales correctas",
        "usuario_id": usuario.id,
        "username": usuario.username,
        "rol_id": usuario.id_rol
    }
