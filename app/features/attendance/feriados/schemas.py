"""
Schemas Pydantic para DiaFestivo.
Validación de datos de entrada y salida para el módulo de feriados.
"""

from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from enum import Enum


class AmbitoFestivoEnum(str, Enum):
    """Ámbito de aplicación del feriado."""
    NACIONAL = "NACIONAL"
    DEPARTAMENTAL = "DEPARTAMENTAL"


class DiaFestivoBase(BaseModel):
    """Schema base con campos comunes."""
    fecha: date = Field(..., description="Fecha del feriado")
    descripcion: str = Field(..., min_length=3, max_length=150, description="Descripción del feriado")
    ambito: AmbitoFestivoEnum = Field(..., description="NACIONAL o DEPARTAMENTAL")
    codigo_departamento: Optional[str] = Field(None, min_length=2, max_length=2, description="Código de departamento (solo para DEPARTAMENTAL)")
    activo: bool = Field(True, description="Estado del feriado")

    @field_validator('codigo_departamento')
    @classmethod
    def validar_codigo_departamento(cls, v, info):
        """Validar que si ambito es DEPARTAMENTAL, codigo_departamento es obligatorio."""
        ambito = info.data.get('ambito')
        if ambito == AmbitoFestivoEnum.DEPARTAMENTAL and not v:
            raise ValueError("codigo_departamento es obligatorio para feriados DEPARTAMENTALES")
        if ambito == AmbitoFestivoEnum.NACIONAL and v:
            raise ValueError("codigo_departamento debe ser NULL para feriados NACIONALES")
        return v


class DiaFestivoCreate(DiaFestivoBase):
    """Schema para crear un nuevo feriado."""
    pass


class DiaFestivoUpdate(BaseModel):
    """Schema para actualizar un feriado existente."""
    fecha: Optional[date] = None
    descripcion: Optional[str] = Field(None, min_length=3, max_length=150)
    ambito: Optional[AmbitoFestivoEnum] = None
    codigo_departamento: Optional[str] = Field(None, min_length=2, max_length=2)
    activo: Optional[bool] = None


class DiaFestivoResponse(DiaFestivoBase):
    """Schema de respuesta para un feriado."""
    id: int

    class Config:
        from_attributes = True
