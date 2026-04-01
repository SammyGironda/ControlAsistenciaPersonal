"""
Schemas Pydantic para Empleado.
Validación de entrada/salida de datos con reglas de negocio.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict


class EmpleadoBase(BaseModel):
    """Schema base para Empleado."""
    ci_numero: str = Field(..., min_length=4, max_length=20, description="Número de CI sin complemento")
    complemento_dep: str = Field(..., min_length=2, max_length=2, description="Código departamento SEGIP")
    ci_sufijo_homonimo: Optional[str] = Field(None, max_length=10, description="Sufijo para homónimos")
    nombres: str = Field(..., min_length=2, max_length=100)
    apellidos: str = Field(..., min_length=2, max_length=100)
    fecha_nacimiento: date
    genero: str = Field(..., pattern="^(masculino|femenino|otro)$")
    fecha_ingreso: date
    id_cargo: int = Field(..., gt=0)
    id_departamento: int = Field(..., gt=0)
    salario_base: Decimal = Field(..., gt=0, decimal_places=2, description="Salario en Bolivianos")
    email: Optional[str] = Field(None, max_length=150)
    telefono: Optional[str] = Field(None, max_length=20)
    foto_url: Optional[str] = Field(None, max_length=255)

    @field_validator('fecha_nacimiento')
    @classmethod
    def validar_edad_minima(cls, v: date) -> date:
        """Validar que el empleado tenga al menos 18 años."""
        from datetime import datetime
        hoy = datetime.now().date()
        edad = (hoy - v).days // 365
        if edad < 18:
            raise ValueError('El empleado debe tener al menos 18 años de edad')
        if edad > 80:
            raise ValueError('La edad no puede superar los 80 años')
        return v

    @field_validator('fecha_ingreso')
    @classmethod
    def validar_fecha_ingreso(cls, v: date) -> date:
        """Validar que la fecha de ingreso no sea futura."""
        from datetime import datetime
        hoy = datetime.now().date()
        if v > hoy:
            raise ValueError('La fecha de ingreso no puede ser futura')
        return v


class EmpleadoCreate(EmpleadoBase):
    """Schema para crear un empleado."""
    estado: str = Field(default="activo", pattern="^(activo|baja|suspendido)$")


class EmpleadoUpdate(BaseModel):
    """Schema para actualizar un empleado."""
    nombres: Optional[str] = Field(None, min_length=2, max_length=100)
    apellidos: Optional[str] = Field(None, min_length=2, max_length=100)
    fecha_nacimiento: Optional[date] = None
    genero: Optional[str] = Field(None, pattern="^(masculino|femenino|otro)$")
    id_cargo: Optional[int] = Field(None, gt=0)
    id_departamento: Optional[int] = Field(None, gt=0)
    salario_base: Optional[Decimal] = Field(None, gt=0, decimal_places=2)
    email: Optional[str] = Field(None, max_length=150)
    telefono: Optional[str] = Field(None, max_length=20)
    foto_url: Optional[str] = Field(None, max_length=255)

    @field_validator('fecha_nacimiento')
    @classmethod
    def validar_edad_minima(cls, v: Optional[date]) -> Optional[date]:
        if v is None:
            return v
        from datetime import datetime
        hoy = datetime.now().date()
        edad = (hoy - v).days // 365
        if edad < 18:
            raise ValueError('El empleado debe tener al menos 18 años de edad')
        if edad > 80:
            raise ValueError('La edad no puede superar los 80 años')
        return v


class EmpleadoResponse(EmpleadoBase):
    """Schema de respuesta para Empleado."""
    id: int
    estado: str
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class EmpleadoCambioEstado(BaseModel):
    """Schema para cambio de estado de empleado (baja, suspensión, reactivación)."""
    motivo: Optional[str] = Field(None, max_length=500, description="Motivo del cambio de estado")
    fecha_efectiva: Optional[date] = Field(None, description="Fecha efectiva del cambio (default: hoy)")
