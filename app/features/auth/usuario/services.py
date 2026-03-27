"""
Services para Usuario - Lógica de negocio.
Incluye manejo de contraseñas con bcrypt.

IMPORTANTE:
- JWT se activa en Semana 9
- Por ahora, endpoints abiertos
"""

from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, func
from fastapi import HTTPException, status

from app.features.auth.usuario.models import Usuario
from app.features.auth.usuario import schemas
from app.features.auth.rol.services import get_rol


# ============================================================
# CRUD BÁSICO
# ============================================================

def get_usuario(db: Session, usuario_id: int, with_rol: bool = False) -> Usuario:
    if with_rol:
        stmt = select(Usuario).options(joinedload(Usuario.rol)).where(Usuario.id == usuario_id)
        usuario = db.execute(stmt).scalar_one_or_none()
    else:
        usuario = db.get(Usuario, usuario_id)
    
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {usuario_id} no encontrado"
        )
    return usuario


def get_usuario_by_username(db: Session, username: str) -> Optional[Usuario]:
    stmt = select(Usuario).where(func.lower(Usuario.username) == username.lower())
    return db.execute(stmt).scalar_one_or_none()


def get_usuarios(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    solo_activos: bool = False,
    id_rol: Optional[int] = None
) -> List[Usuario]:
    stmt = select(Usuario).options(joinedload(Usuario.rol)).offset(skip).limit(limit)
    
    if solo_activos:
        stmt = stmt.where(Usuario.activo == True)
    
    if id_rol:
        stmt = stmt.where(Usuario.id_rol == id_rol)
    
    return list(db.execute(stmt).scalars().all())


def create_usuario(db: Session, usuario_data: schemas.UsuarioCreate) -> Usuario:
    existing = get_usuario_by_username(db, usuario_data.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un usuario con el username '{usuario_data.username}'"
        )
    
    get_rol(db, usuario_data.id_rol)
    
    if usuario_data.id_empleado:
        stmt = select(Usuario).where(Usuario.id_empleado == usuario_data.id_empleado)
        existing_usuario = db.execute(stmt).scalar_one_or_none()
        if existing_usuario:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"El empleado con ID {usuario_data.id_empleado} ya tiene un usuario asociado"
            )
    
    data = usuario_data.model_dump(exclude={"password"})
    usuario = Usuario(**data)
    usuario.set_password(usuario_data.password)
    
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def update_usuario(
    db: Session,
    usuario_id: int,
    usuario_data: schemas.UsuarioUpdate
) -> Usuario:
    usuario = get_usuario(db, usuario_id)
    
    if usuario_data.username and usuario_data.username != usuario.username:
        existing = get_usuario_by_username(db, usuario_data.username)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe un usuario con el username '{usuario_data.username}'"
            )
    
    if usuario_data.id_rol:
        get_rol(db, usuario_data.id_rol)
    
    update_data = usuario_data.model_dump(exclude_unset=True, exclude={"password"})
    for field, value in update_data.items():
        setattr(usuario, field, value)
    
    if usuario_data.password:
        usuario.set_password(usuario_data.password)
    
    db.commit()
    db.refresh(usuario)
    return usuario


def delete_usuario(db: Session, usuario_id: int) -> dict:
    usuario = get_usuario(db, usuario_id)
    db.delete(usuario)
    db.commit()
    return {"message": f"Usuario '{usuario.username}' eliminado exitosamente"}


def toggle_activo(db: Session, usuario_id: int) -> Usuario:
    usuario = get_usuario(db, usuario_id)
    usuario.activo = not usuario.activo
    db.commit()
    db.refresh(usuario)
    return usuario


def change_password(
    db: Session,
    usuario_id: int,
    password_data: schemas.UsuarioChangePassword
) -> dict:
    usuario = get_usuario(db, usuario_id)
    
    if not usuario.check_password(password_data.password_actual):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual no es correcta"
        )
    
    usuario.set_password(password_data.password_nueva)
    db.commit()
    
    return {"message": "Contraseña actualizada exitosamente"}


def verify_credentials(db: Session, username: str, password: str) -> Optional[Usuario]:
    usuario = get_usuario_by_username(db, username)
    
    if not usuario or not usuario.activo:
        return None
    
    if not usuario.check_password(password):
        return None
    
    usuario.ultimo_acceso = datetime.now()
    db.commit()
    
    return usuario


def get_usuario_with_rol_info(db: Session, usuario_id: int) -> dict:
    usuario = get_usuario(db, usuario_id, with_rol=True)
    
    return {
        "id": usuario.id,
        "username": usuario.username,
        "id_rol": usuario.id_rol,
        "rol_nombre": usuario.rol.nombre,
        "id_empleado": usuario.id_empleado,
        "email": usuario.email,
        "activo": usuario.activo,
        "ultimo_acceso": usuario.ultimo_acceso,
        "created_at": usuario.created_at,
        "updated_at": usuario.updated_at
    }
