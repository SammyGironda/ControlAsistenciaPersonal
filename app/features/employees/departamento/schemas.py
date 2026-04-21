"""
Schemas Pydantic para Departamento.
Validacion de entrada/salida de datos.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


class DepartamentoBase(BaseModel):
    """Schema base para Departamento."""
    nombre: str = Field(..., min_length=3, max_length=100)
    codigo: str = Field(..., min_length=2, max_length=20, description="Código único del departamento")
    id_padre: Optional[int] = Field(None, description="ID del departamento padre (NULL = raíz)")
    activo: bool = True


class DepartamentoCreate(DepartamentoBase):
    """Schema para crear un departamento."""
    pass


class DepartamentoUpdate(BaseModel):
    """Schema para actualizar un departamento."""
    nombre: Optional[str] = Field(None, min_length=3, max_length=100)
    codigo: Optional[str] = Field(None, min_length=2, max_length=20)
    id_padre: Optional[int] = None
    activo: Optional[bool] = None


class DepartamentoResponse(DepartamentoBase):
    """Schema de respuesta para Departamento."""
    id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class DepartamentoConHijos(DepartamentoResponse):
    """Schema de departamento con su jerarquía de hijos (árbol recursivo)."""
    hijos: List["DepartamentoConHijos"] = []
    
    model_config = ConfigDict(from_attributes=True)


# Para resolver la referencia recursiva
DepartamentoConHijos.model_rebuild()
