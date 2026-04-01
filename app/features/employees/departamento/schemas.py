"""
Schemas Pydantic para Departamento y ComplementoDep.
Validación de entrada/salida de datos.
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict


# ========== ComplementoDep Schemas ==========

class ComplementoDepBase(BaseModel):
    """Schema base para ComplementoDep."""
    codigo: str = Field(..., min_length=2, max_length=2, description="Código departamento SEGIP (LP, CB, SC, etc.)")
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


# ========== Departamento Schemas ==========

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
