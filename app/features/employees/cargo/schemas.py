"""
Schemas Pydantic para Cargo.
Validación de entrada/salida de datos.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict


class CargoBase(BaseModel):
    """Schema base para Cargo."""
    nombre: str = Field(..., min_length=3, max_length=100)
    codigo: str = Field(..., min_length=2, max_length=20, description="Código único del cargo")
    nivel: int = Field(default=5, ge=1, le=10, description="Nivel jerárquico (1=más alto, 10=más bajo)")
    es_cargo_confianza: bool = Field(default=False, description="Si TRUE, exento de marcar huella")
    id_departamento: int = Field(..., gt=0, description="ID del departamento al que pertenece")
    activo: bool = True


class CargoCreate(CargoBase):
    """Schema para crear un cargo."""
    pass


class CargoUpdate(BaseModel):
    """Schema para actualizar un cargo."""
    nombre: Optional[str] = Field(None, min_length=3, max_length=100)
    codigo: Optional[str] = Field(None, min_length=2, max_length=20)
    nivel: Optional[int] = Field(None, ge=1, le=10)
    es_cargo_confianza: Optional[bool] = None
    id_departamento: Optional[int] = Field(None, gt=0)
    activo: Optional[bool] = None


class CargoResponse(CargoBase):
    """Schema de respuesta para Cargo."""
    id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
