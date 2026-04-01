"""
Schemas Pydantic para Contrato.
Validaciones de entrada y salida para endpoints REST.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict


# ============================================================
# SCHEMAS BASE
# ============================================================

class ContratoBase(BaseModel):
    """Campos comunes para creación y actualización de contrato."""
    tipo_contrato: str = Field(..., pattern="^(indefinido|plazo_fijo)$", description="Tipo de contrato")
    fecha_inicio: date = Field(..., description="Fecha de inicio del contrato")
    fecha_fin: Optional[date] = Field(None, description="Fecha fin (NULL para indefinidos)")
    salario_base: Decimal = Field(..., gt=0, max_digits=10, decimal_places=2, description="Salario inicial en Bs.")
    id_decreto_origen: Optional[int] = Field(None, description="ID del decreto si aplica")
    observacion: Optional[str] = Field(None, max_length=5000)
    
    @field_validator('fecha_fin')
    @classmethod
    def validar_fecha_fin(cls, v, info):
        """Valida que fecha_fin sea posterior a fecha_inicio."""
        if v is not None:
            fecha_inicio = info.data.get('fecha_inicio')
            if fecha_inicio and v <= fecha_inicio:
                raise ValueError('fecha_fin debe ser posterior a fecha_inicio')
        return v
    
    @field_validator('tipo_contrato')
    @classmethod
    def validar_plazo_fijo_tiene_fecha_fin(cls, v, info):
        """Si es plazo_fijo, debe tener fecha_fin."""
        if v == 'plazo_fijo':
            fecha_fin = info.data.get('fecha_fin')
            if fecha_fin is None:
                raise ValueError('Contrato plazo_fijo debe tener fecha_fin')
        return v


# ============================================================
# SCHEMAS DE ENTRADA (REQUEST)
# ============================================================

class ContratoCreate(ContratoBase):
    """Schema para crear un nuevo contrato."""
    id_empleado: int = Field(..., gt=0, description="ID del empleado")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id_empleado": 1,
                "tipo_contrato": "indefinido",
                "fecha_inicio": "2024-01-01",
                "fecha_fin": None,
                "salario_base": 3500.00,
                "observacion": "Contrato inicial"
            }
        }
    )


class ContratoUpdate(BaseModel):
    """Schema para actualizar un contrato (solo campos editables)."""
    estado: Optional[str] = Field(None, pattern="^(activo|finalizado|rescindido)$")
    observacion: Optional[str] = Field(None, max_length=5000)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "estado": "finalizado",
                "observacion": "Finalizado por mutuo acuerdo"
            }
        }
    )


class ContratoRenovacion(BaseModel):
    """Schema para renovar un contrato plazo_fijo."""
    fecha_inicio: date = Field(..., description="Fecha inicio del nuevo contrato")
    fecha_fin: date = Field(..., description="Fecha fin del nuevo contrato")
    salario_base: Decimal = Field(..., gt=0, max_digits=10, decimal_places=2, description="Nuevo salario en Bs.")
    observacion: Optional[str] = Field(None, max_length=5000)
    
    @field_validator('fecha_fin')
    @classmethod
    def validar_fecha_fin(cls, v, info):
        fecha_inicio = info.data.get('fecha_inicio')
        if fecha_inicio and v <= fecha_inicio:
            raise ValueError('fecha_fin debe ser posterior a fecha_inicio')
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "fecha_inicio": "2025-01-01",
                "fecha_fin": "2025-12-31",
                "salario_base": 3850.00,
                "observacion": "Renovación con incremento del 10%"
            }
        }
    )


# ============================================================
# SCHEMAS DE SALIDA (RESPONSE)
# ============================================================

class ContratoResponse(ContratoBase):
    """Schema de respuesta con todos los campos del contrato."""
    id: int
    id_empleado: int
    estado: str
    created_at: datetime
    updated_at: datetime
    
    # Campos calculados
    es_vigente: bool = Field(description="True si el contrato está activo y no ha finalizado")
    
    model_config = ConfigDict(from_attributes=True)


class ContratoConEmpleado(ContratoResponse):
    """Schema de respuesta con información básica del empleado."""
    empleado_nombre: str = Field(description="Nombre completo del empleado")
    empleado_ci: str = Field(description="CI del empleado")
    
    model_config = ConfigDict(from_attributes=True)
