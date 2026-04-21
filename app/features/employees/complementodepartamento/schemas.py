"""
Schemas Pydantic para ComplementoDep.
"""

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class ComplementoDepBase(BaseModel):
    """Schema base para ComplementoDep."""
    codigo: str = Field(..., min_length=2, max_length=2, description="Codigo departamento SEGIP (LP, CB, SC, etc.)")
    nombre_departamento: str = Field(..., min_length=3, max_length=50)
    activo: bool = True


class ComplementoDepCreate(ComplementoDepBase):
    """Schema para crear un complemento de departamento."""
    pass


class ComplementoDepUpdate(BaseModel):
    """Schema para actualizar un complemento de departamento."""
    nombre_departamento: Optional[str] = Field(None, min_length=3, max_length=50)
    activo: Optional[bool] = None


class ComplementoDepResponse(ComplementoDepBase):
    """Schema de respuesta para ComplementoDep."""

    model_config = ConfigDict(from_attributes=True)
