"""
Schemas Pydantic para Horario y AsignacionHorario.
Validación de entrada/salida de datos con reglas de negocio.
"""

from datetime import datetime, time, date
from typing import Optional, List
from pydantic import BaseModel, Field, field_validator, ConfigDict


# ========== Horario Schemas ==========

class HorarioBase(BaseModel):
    """Schema base para Horario."""
    nombre: str = Field(..., min_length=3, max_length=100, description="Ej: 'Turno Oficina'")
    hora_entrada: time
    hora_salida: time
    tolerancia_minutos: int = Field(default=5, ge=0, le=60, description="Minutos de gracia")
    jornada_semanal_horas: float = Field(default=40.0, gt=0, le=48.0, description="Máx 48h según LGT Art. 46")
    dias_laborables: List[int] = Field(default=[1, 2, 3, 4, 5], description="[1=Lun, 2=Mar, ..., 7=Dom]")
    tipo_jornada: str = Field(default="continua", pattern="^(continua|discontinua)$")
    activo: bool = True

    @field_validator('hora_salida')
    @classmethod
    def validar_hora_salida(cls, v: time, info) -> time:
        """Validar que hora_salida sea posterior a hora_entrada."""
        if 'hora_entrada' in info.data:
            hora_entrada = info.data['hora_entrada']
            if v <= hora_entrada:
                raise ValueError('La hora de salida debe ser posterior a la hora de entrada')
        return v

    @field_validator('dias_laborables')
    @classmethod
    def validar_dias_laborables(cls, v: List[int]) -> List[int]:
        """Validar que los días estén en rango 1-7."""
        if not v:
            raise ValueError('Debe especificar al menos un día laborable')
        for dia in v:
            if dia < 1 or dia > 7:
                raise ValueError('Los días deben estar entre 1 (Lunes) y 7 (Domingo)')
        return v


class HorarioCreate(HorarioBase):
    """Schema para crear un horario."""
    pass


class HorarioUpdate(BaseModel):
    """Schema para actualizar un horario."""
    nombre: Optional[str] = Field(None, min_length=3, max_length=100)
    hora_entrada: Optional[time] = None
    hora_salida: Optional[time] = None
    tolerancia_minutos: Optional[int] = Field(None, ge=0, le=60)
    jornada_semanal_horas: Optional[float] = Field(None, gt=0, le=48.0)
    dias_laborables: Optional[List[int]] = None
    tipo_jornada: Optional[str] = Field(None, pattern="^(continua|discontinua)$")
    activo: Optional[bool] = None


class HorarioResponse(HorarioBase):
    """Schema de respuesta para Horario."""
    id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


# ========== AsignacionHorario Schemas ==========

class AsignacionHorarioBase(BaseModel):
    """Schema base para AsignacionHorario."""
    id_empleado: int = Field(..., gt=0)
    id_horario: int = Field(..., gt=0)
    fecha_inicio: date
    fecha_fin: Optional[date] = Field(None, description="NULL = vigente indefinidamente")
    es_activo: bool = True
    observacion: Optional[str] = Field(None, max_length=500)

    @field_validator('fecha_fin')
    @classmethod
    def validar_fecha_fin(cls, v: Optional[date], info) -> Optional[date]:
        """Validar que fecha_fin sea posterior a fecha_inicio."""
        if v is not None and 'fecha_inicio' in info.data:
            fecha_inicio = info.data['fecha_inicio']
            if v <= fecha_inicio:
                raise ValueError('La fecha fin debe ser posterior a la fecha de inicio')
        return v


class AsignacionHorarioCreate(AsignacionHorarioBase):
    """Schema para crear una asignación de horario."""
    pass


class AsignacionHorarioUpdate(BaseModel):
    """Schema para actualizar una asignación de horario."""
    id_horario: Optional[int] = Field(None, gt=0)
    fecha_inicio: Optional[date] = None
    fecha_fin: Optional[date] = None
    es_activo: Optional[bool] = None
    observacion: Optional[str] = Field(None, max_length=500)


class AsignacionHorarioResponse(AsignacionHorarioBase):
    """Schema de respuesta para AsignacionHorario."""
    id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class AsignacionHorarioConDetalle(AsignacionHorarioResponse):
    """Schema de asignación con detalles del horario incluidos."""
    horario: HorarioResponse
    
    model_config = ConfigDict(from_attributes=True)
