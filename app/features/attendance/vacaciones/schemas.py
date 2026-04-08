"""
Schemas Pydantic para Vacacion y DetalleVacacion.
Validación de datos para el saldo vacacional.
"""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from enum import Enum
from decimal import Decimal


class TipoVacacionEnum(str, Enum):
    """Tipo de vacación según goce de haber."""
    goce_de_haber = "goce_de_haber"
    sin_goce_de_haber = "sin_goce_de_haber"
    licencia_accidente = "licencia_accidente"


class EstadoDetalleVacacionEnum(str, Enum):
    """Estado del ciclo de vida de la solicitud."""
    solicitado = "solicitado"
    aprobado = "aprobado"
    tomado = "tomado"
    rechazado = "rechazado"
    cancelado = "cancelado"


# ===== SCHEMAS PARA VACACION =====

class VacacionBase(BaseModel):
    """Schema base para Vacacion."""
    id_empleado: int = Field(..., gt=0, description="ID del empleado")
    gestion: int = Field(..., ge=2020, le=2100, description="Año de la gestión")
    horas_correspondientes: Decimal = Field(Decimal("0.0"), ge=0, description="Horas totales asignadas")
    horas_goce_haber: Decimal = Field(Decimal("0.0"), ge=0, description="Horas con goce de haber")
    horas_sin_goce_haber: Decimal = Field(Decimal("0.0"), ge=0, description="Horas sin goce de haber")
    horas_tomadas: Decimal = Field(Decimal("0.0"), ge=0, description="Horas consumidas")
    observacion: Optional[str] = Field(None, max_length=5000)


class VacacionCreate(BaseModel):
    """Schema para crear un registro de vacación."""
    id_empleado: int = Field(..., gt=0)
    gestion: int = Field(..., ge=2020, le=2100)
    horas_correspondientes: Decimal = Field(..., ge=0, description="Calculado con fn_horas_vacacion_lgt")
    horas_goce_haber: Optional[Decimal] = Field(Decimal("0.0"), ge=0)
    horas_sin_goce_haber: Optional[Decimal] = Field(Decimal("0.0"), ge=0)
    observacion: Optional[str] = Field(None, max_length=5000)


class VacacionUpdate(BaseModel):
    """Schema para actualizar un registro de vacación."""
    horas_goce_haber: Optional[Decimal] = Field(None, ge=0)
    horas_sin_goce_haber: Optional[Decimal] = Field(None, ge=0)
    observacion: Optional[str] = Field(None, max_length=5000)


class VacacionResponse(VacacionBase):
    """Schema de respuesta para Vacacion."""
    id: int
    horas_pendientes: Decimal = Field(..., description="horas_correspondientes - horas_tomadas")
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ===== SCHEMAS PARA DETALLE_VACACION =====

class DetalleVacacionBase(BaseModel):
    """Schema base para DetalleVacacion."""
    id_vacacion: int = Field(..., gt=0, description="ID del registro de vacación")
    id_justificacion: Optional[int] = Field(None, description="ID de justificación (solo para licencia_accidente)")
    fecha_inicio: date = Field(..., description="Primer día de vacaciones")
    fecha_fin: date = Field(..., description="Último día de vacaciones")
    horas_habiles: Decimal = Field(..., gt=0, description="Horas hábiles de vacación")
    tipo_vacacion: TipoVacacionEnum = Field(TipoVacacionEnum.goce_de_haber, description="Tipo de vacación")
    observacion: Optional[str] = Field(None, max_length=5000)

    @field_validator('fecha_fin')
    @classmethod
    def validar_fechas(cls, v, info):
        """Validar que fecha_fin >= fecha_inicio."""
        fecha_inicio = info.data.get('fecha_inicio')
        if fecha_inicio and v < fecha_inicio:
            raise ValueError("fecha_fin debe ser mayor o igual a fecha_inicio")
        return v


class DetalleVacacionCreate(DetalleVacacionBase):
    """Schema para crear una solicitud de vacación."""
    pass


class DetalleVacacionUpdate(BaseModel):
    """Schema para actualizar una solicitud de vacación."""
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    horas_habiles: Optional[Decimal] = Field(None, gt=0)
    tipo_vacacion: Optional[TipoVacacionEnum] = None
    observacion: Optional[str] = Field(None, max_length=5000)


class CambiarEstadoRequest(BaseModel):
    """Schema para cambiar el estado de una solicitud."""
    nuevo_estado: EstadoDetalleVacacionEnum = Field(..., description="Nuevo estado")
    id_aprobado_por: Optional[int] = Field(None, description="ID del aprobador (requerido para aprobar/rechazar)")
    observacion: Optional[str] = Field(None, max_length=500, description="Observaciones del cambio")


class DetalleVacacionResponse(DetalleVacacionBase):
    """Schema de respuesta para DetalleVacacion."""
    id: int
    estado: EstadoDetalleVacacionEnum
    id_aprobado_por: Optional[int]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
