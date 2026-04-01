"""
Schemas Pydantic para Ajuste Salarial, Decreto e Impuestos.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict


# ============================================================
# AJUSTE SALARIAL
# ============================================================

class AjusteSalarialBase(BaseModel):
    """Campos comunes para ajuste salarial."""
    salario_anterior: Decimal = Field(..., gt=0, max_digits=10, decimal_places=2)
    salario_nuevo: Decimal = Field(..., gt=0, max_digits=10, decimal_places=2)
    fecha_vigencia: date = Field(..., description="Fecha desde la cual rige el nuevo salario")
    motivo: str = Field(..., pattern="^(decreto_anual|renovacion|merito|promocion)$")
    id_aprobado_por: Optional[int] = Field(None, description="ID del empleado que aprobó")
    observacion: Optional[str] = Field(None, max_length=5000)
    
    @field_validator('salario_nuevo')
    @classmethod
    def validar_salarios_distintos(cls, v, info):
        """Validar que el salario nuevo sea diferente al anterior."""
        salario_anterior = info.data.get('salario_anterior')
        if salario_anterior and v == salario_anterior:
            raise ValueError('salario_nuevo debe ser diferente a salario_anterior')
        return v


class AjusteSalarialCreate(AjusteSalarialBase):
    """Schema para crear un ajuste salarial."""
    id_empleado: int = Field(..., gt=0)
    id_contrato: int = Field(..., gt=0)
    id_condicion_decreto: Optional[int] = Field(None, description="ID de la condición de decreto aplicada")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id_empleado": 1,
                "id_contrato": 1,
                "salario_anterior": 3500.00,
                "salario_nuevo": 3850.00,
                "fecha_vigencia": "2024-05-01",
                "motivo": "decreto_anual",
                "id_condicion_decreto": 1,
                "observacion": "Aplicación DS 4984 - tramo 1"
            }
        }
    )


class AjusteSalarialResponse(AjusteSalarialBase):
    """Schema de respuesta de ajuste salarial."""
    id: int
    id_empleado: int
    id_contrato: int
    id_condicion_decreto: Optional[int]
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================
# CONDICION DECRETO
# ============================================================

class CondicionDecretoBase(BaseModel):
    """Campos comunes para condición de decreto."""
    orden: int = Field(..., ge=1, description="Orden de evaluación")
    salario_desde: Optional[Decimal] = Field(None, max_digits=10, decimal_places=2, description="NULL = sin límite inferior")
    salario_hasta: Optional[Decimal] = Field(None, max_digits=10, decimal_places=2, description="NULL = sin límite superior")
    porcentaje_incremento: Decimal = Field(..., ge=0, max_digits=5, decimal_places=2, description="Porcentaje (ej: 5.00 = 5%)")
    
    @field_validator('salario_hasta')
    @classmethod
    def validar_rango_salarios(cls, v, info):
        """Validar que salario_hasta sea mayor a salario_desde."""
        salario_desde = info.data.get('salario_desde')
        if salario_desde is not None and v is not None and v <= salario_desde:
            raise ValueError('salario_hasta debe ser mayor a salario_desde')
        return v


class CondicionDecretoCreate(CondicionDecretoBase):
    """Schema para crear una condición de decreto."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "orden": 1,
                "salario_desde": None,
                "salario_hasta": 2500.00,
                "porcentaje_incremento": 5.00
            }
        }
    )


class CondicionDecretoResponse(CondicionDecretoBase):
    """Schema de respuesta de condición."""
    id: int
    id_decreto: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================
# DECRETO INCREMENTO SALARIAL
# ============================================================

class DecretoBase(BaseModel):
    """Campos comunes para decreto."""
    anio: int = Field(..., ge=2000, le=2100, description="Año del decreto")
    nuevo_smn: Decimal = Field(..., gt=0, max_digits=10, decimal_places=2, description="Nuevo SMN en Bs.")
    fecha_vigencia: date = Field(..., description="Fecha desde la cual rige")
    referencia_decreto: str = Field(..., max_length=100, description="Ej: 'DS 4984'")


class DecretoCreate(DecretoBase):
    """Schema para crear un decreto con sus condiciones."""
    condiciones: List[CondicionDecretoCreate] = Field(..., min_length=1, description="Lista de tramos salariales")
    
    @field_validator('condiciones')
    @classmethod
    def validar_ordenes_unicos(cls, v):
        """Validar que los órdenes sean únicos."""
        ordenes = [c.orden for c in v]
        if len(ordenes) != len(set(ordenes)):
            raise ValueError('Los valores de orden deben ser únicos')
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "anio": 2024,
                "nuevo_smn": 2500.00,
                "fecha_vigencia": "2024-05-01",
                "referencia_decreto": "DS 4984",
                "condiciones": [
                    {
                        "orden": 1,
                        "salario_desde": None,
                        "salario_hasta": 2500.00,
                        "porcentaje_incremento": 5.00
                    },
                    {
                        "orden": 2,
                        "salario_desde": 2501.00,
                        "salario_hasta": 5000.00,
                        "porcentaje_incremento": 3.00
                    },
                    {
                        "orden": 3,
                        "salario_desde": 5001.00,
                        "salario_hasta": None,
                        "porcentaje_incremento": 1.00
                    }
                ]
            }
        }
    )


class DecretoResponse(DecretoBase):
    """Schema de respuesta de decreto."""
    id: int
    created_at: datetime
    updated_at: datetime
    condiciones: List[CondicionDecretoResponse] = Field(default_factory=list)
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================
# PARAMETRO IMPUESTO
# ============================================================

class ParametroImpuestoBase(BaseModel):
    """Campos comunes para parámetro de impuesto."""
    nombre: str = Field(..., max_length=50, description="RC_IVA, AFP_LABORAL, etc.")
    porcentaje: Decimal = Field(..., ge=0, max_digits=5, decimal_places=2, description="Porcentaje (ej: 13.00 = 13%)")
    fecha_vigencia_inicio: date
    fecha_vigencia_fin: Optional[date] = Field(None, description="NULL = vigente indefinidamente")
    descripcion: Optional[str] = Field(None, max_length=1000)
    
    @field_validator('fecha_vigencia_fin')
    @classmethod
    def validar_fechas(cls, v, info):
        """Validar que fecha_fin sea posterior a fecha_inicio."""
        fecha_inicio = info.data.get('fecha_vigencia_inicio')
        if v is not None and fecha_inicio and v <= fecha_inicio:
            raise ValueError('fecha_vigencia_fin debe ser posterior a fecha_vigencia_inicio')
        return v


class ParametroImpuestoCreate(ParametroImpuestoBase):
    """Schema para crear parámetro de impuesto."""
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "nombre": "RC_IVA",
                "porcentaje": 13.00,
                "fecha_vigencia_inicio": "1992-01-01",
                "fecha_vigencia_fin": None,
                "descripcion": "Régimen Complementario al IVA"
            }
        }
    )


class ParametroImpuestoResponse(ParametroImpuestoBase):
    """Schema de respuesta de parámetro."""
    id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ============================================================
# SCHEMAS AUXILIARES
# ============================================================

class AplicarDecretoRequest(BaseModel):
    """Request para aplicar decreto a todos los empleados con contrato indefinido."""
    id_aprobado_por: int = Field(..., gt=0, description="ID del empleado que aprueba la aplicación masiva")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id_aprobado_por": 5
            }
        }
    )


class AplicarDecretoResponse(BaseModel):
    """Response de aplicación masiva de decreto."""
    decreto_id: int
    empleados_procesados: int
    ajustes_creados: int
    errores: List[str] = Field(default_factory=list)
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "decreto_id": 1,
                "empleados_procesados": 50,
                "ajustes_creados": 48,
                "errores": [
                    "Empleado ID 23: No tiene contrato activo",
                    "Empleado ID 45: No se encontró tramo aplicable"
                ]
            }
        }
    )
