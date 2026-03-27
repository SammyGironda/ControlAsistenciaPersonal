"""
Schemas Pydantic para Rol.
Define los DTOs para requests y responses de la API.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


# ============================================================
# SCHEMAS DE REQUEST (Input)
# ============================================================

class RolCreate(BaseModel):
    """Schema para crear un nuevo rol."""
    nombre: str = Field(..., min_length=1, max_length=50, description="Nombre del rol")
    descripcion: Optional[str] = Field(None, description="Descripción del rol")
    activo: bool = Field(default=True, description="Estado del rol")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "nombre": "RRHH",
                "descripcion": "Gestión de empleados y asistencia",
                "activo": True
            }
        }
    )


class RolUpdate(BaseModel):
    """Schema para actualizar un rol existente."""
    nombre: Optional[str] = Field(None, min_length=1, max_length=50)
    descripcion: Optional[str] = None
    activo: Optional[bool] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "nombre": "RRHH Manager",
                "descripcion": "Gestión de empleados, asistencia y reportes",
                "activo": True
            }
        }
    )


# ============================================================
# SCHEMAS DE RESPONSE (Output)
# ============================================================

class RolRead(BaseModel):
    """Schema de respuesta para un rol."""
    id: int
    nombre: str
    descripcion: Optional[str]
    activo: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RolReadSimple(BaseModel):
    """Schema simplificado de rol (para uso en otras entidades)."""
    id: int
    nombre: str
    activo: bool

    model_config = ConfigDict(from_attributes=True)
