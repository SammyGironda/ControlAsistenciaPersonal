"""
Schemas Pydantic para Usuario.
Define los DTOs para requests y responses de la API.

IMPORTANTE:
- password solo se envía en create/update, nunca se retorna en responses
- password_hash NO se expone en ninguna respuesta
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr, ConfigDict


# ============================================================
# SCHEMAS DE REQUEST (Input)
# ============================================================

class UsuarioCreate(BaseModel):
    """Schema para crear un nuevo usuario."""
    username: str = Field(..., min_length=3, max_length=50, description="Nombre de usuario único")
    password: str = Field(..., min_length=6, max_length=100, description="Contraseña (será hasheada)")
    id_rol: int = Field(..., gt=0, description="ID del rol asignado")
    id_empleado: Optional[int] = Field(None, gt=0, description="ID del empleado vinculado (NULL para usuarios externos)")
    email: Optional[EmailStr] = None
    activo: bool = Field(default=True, description="Estado del usuario")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "juan.perez",
                "password": "Password123!",
                "id_rol": 2,
                "id_empleado": 5,
                "email": "juan.perez@empresa.com",
                "activo": True
            }
        }
    )


class UsuarioUpdate(BaseModel):
    """
    Schema para actualizar un usuario existente.
    Todos los campos son opcionales.
    """
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    password: Optional[str] = Field(None, min_length=6, max_length=100, description="Nueva contraseña")
    id_rol: Optional[int] = Field(None, gt=0)
    id_empleado: Optional[int] = Field(None, gt=0)
    email: Optional[EmailStr] = None
    activo: Optional[bool] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "email": "nuevo.email@empresa.com",
                "activo": False
            }
        }
    )


class UsuarioChangePassword(BaseModel):
    """Schema para cambio de contraseña."""
    password_actual: str = Field(..., min_length=6)
    password_nueva: str = Field(..., min_length=6)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "password_actual": "OldPassword123!",
                "password_nueva": "NewPassword456!"
            }
        }
    )


# ============================================================
# SCHEMAS DE RESPONSE (Output)
# ============================================================

class UsuarioRead(BaseModel):
    """
    Schema de respuesta para un usuario.
    NUNCA expone el password_hash por seguridad.
    """
    id: int
    username: str
    id_rol: int
    id_empleado: Optional[int]
    email: Optional[str]
    activo: bool
    ultimo_acceso: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UsuarioReadWithRol(BaseModel):
    """Schema de respuesta de usuario con información del rol."""
    id: int
    username: str
    id_rol: int
    rol_nombre: str  # Nombre del rol incluido
    id_empleado: Optional[int]
    email: Optional[str]
    activo: bool
    ultimo_acceso: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UsuarioReadSimple(BaseModel):
    """Schema simplificado de usuario (para uso en otras entidades)."""
    id: int
    username: str
    activo: bool

    model_config = ConfigDict(from_attributes=True)
