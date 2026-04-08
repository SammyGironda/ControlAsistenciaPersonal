"""
Schemas Pydantic para BeneficioCumpleanos.
Validación de datos para el beneficio de cumpleaños.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class BeneficioCumpleanosBase(BaseModel):
    """Schema base con campos comunes."""
    id_empleado: int = Field(..., gt=0, description="ID del empleado")
    gestion: int = Field(..., ge=2020, le=2100, description="Año de la gestión")
    fue_utilizado: bool = Field(False, description="Si el beneficio fue utilizado")
    fecha_uso: Optional[datetime] = Field(None, description="Fecha/hora en que se usó")
    id_justificacion: Optional[int] = Field(None, description="ID de la justificación asociada")
    transferido_a_vacacion: bool = Field(False, description="Si fue transferido a vacaciones")


class BeneficioCumpleanosCreate(BaseModel):
    """Schema para crear un beneficio (usado por worker automático)."""
    id_empleado: int = Field(..., gt=0)
    gestion: int = Field(..., ge=2020, le=2100)


class BeneficioCumpleanosUpdate(BaseModel):
    """Schema para actualizar un beneficio."""
    fue_utilizado: Optional[bool] = None
    fecha_uso: Optional[datetime] = None
    id_justificacion: Optional[int] = None
    transferido_a_vacacion: Optional[bool] = None


class BeneficioCumpleanosResponse(BeneficioCumpleanosBase):
    """Schema de respuesta."""
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
