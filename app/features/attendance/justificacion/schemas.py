"""
Schemas Pydantic para JustificacionAusencia.
Validación de datos para permisos y licencias.
"""

from datetime import date, datetime, time
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from enum import Enum
from decimal import Decimal


class TipoJustificacionEnum(str, Enum):
    """Tipos de justificación de ausencia."""
    permiso_personal = "permiso_personal"
    licencia_medica_accidente = "licencia_medica_accidente"
    cumpleanos = "cumpleanos"
    vacacion_por_horas = "vacacion_por_horas"


class TipoPermisoEnum(str, Enum):
    """Duración del permiso."""
    dia_completo = "dia_completo"
    por_horas = "por_horas"


class EstadoAprobacionEnum(str, Enum):
    """Estado de aprobación."""
    pendiente = "pendiente"
    aprobado = "aprobado"
    rechazado = "rechazado"


class JustificacionAusenciaBase(BaseModel):
    """Schema base con campos comunes."""
    id_empleado: int = Field(..., gt=0, description="ID del empleado")
    fecha_inicio: date = Field(..., description="Primer día de ausencia")
    fecha_fin: date = Field(..., description="Último día de ausencia")
    tipo_justificacion: TipoJustificacionEnum = Field(..., description="Tipo de justificación")
    tipo_permiso: TipoPermisoEnum = Field(TipoPermisoEnum.dia_completo, description="Tipo de permiso")
    es_por_horas: bool = Field(False, description="Si el permiso es por horas")
    hora_inicio_permiso: Optional[time] = Field(None, description="Hora de inicio (solo si es_por_horas)")
    hora_fin_permiso: Optional[time] = Field(None, description="Hora de fin (solo si es_por_horas)")
    descripcion: Optional[str] = Field(None, max_length=5000, description="Descripción o motivo")
    documento_url: Optional[str] = Field(None, max_length=255, description="URL del documento de respaldo")

    @field_validator('fecha_fin')
    @classmethod
    def validar_fechas(cls, v, info):
        """Validar que fecha_fin >= fecha_inicio."""
        fecha_inicio = info.data.get('fecha_inicio')
        if fecha_inicio and v < fecha_inicio:
            raise ValueError("fecha_fin debe ser mayor o igual a fecha_inicio")
        return v

    @field_validator('hora_fin_permiso')
    @classmethod
    def validar_horas(cls, v, info):
        """Validar coherencia de campos según es_por_horas."""
        es_por_horas = info.data.get('es_por_horas')
        hora_inicio = info.data.get('hora_inicio_permiso')

        if es_por_horas:
            if not hora_inicio or not v:
                raise ValueError("hora_inicio_permiso y hora_fin_permiso son obligatorios si es_por_horas=TRUE")
            if v <= hora_inicio:
                raise ValueError("hora_fin_permiso debe ser mayor que hora_inicio_permiso")
        else:
            if hora_inicio or v:
                raise ValueError("hora_inicio_permiso y hora_fin_permiso deben ser NULL si es_por_horas=FALSE")

        return v


class JustificacionAusenciaCreate(JustificacionAusenciaBase):
    """Schema para crear una nueva justificación."""
    pass


class JustificacionAusenciaUpdate(BaseModel):
    """Schema para actualizar una justificación existente."""
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    tipo_justificacion: Optional[TipoJustificacionEnum] = None
    tipo_permiso: Optional[TipoPermisoEnum] = None
    es_por_horas: Optional[bool] = None
    hora_inicio_permiso: Optional[time] = None
    hora_fin_permiso: Optional[time] = None
    descripcion: Optional[str] = Field(None, max_length=5000)
    documento_url: Optional[str] = Field(None, max_length=255)


class AprobacionRequest(BaseModel):
    """Schema para aprobar o rechazar una justificación."""
    estado: EstadoAprobacionEnum = Field(..., description="aprobado o rechazado")
    id_aprobado_por: int = Field(..., gt=0, description="ID del aprobador")
    observacion: Optional[str] = Field(None, max_length=500, description="Comentarios del aprobador")


class JustificacionAusenciaResponse(JustificacionAusenciaBase):
    """Schema de respuesta."""
    id: int
    total_horas_permiso: Optional[Decimal]
    estado_aprobacion: EstadoAprobacionEnum
    id_aprobado_por: Optional[int]
    fecha_aprobacion: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
