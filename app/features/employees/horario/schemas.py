"""
Schemas Pydantic para Horario y AsignacionHorario.
Validación de entrada/salida de datos con reglas de negocio.
"""

from datetime import datetime, time, date, timedelta
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


# ========== Horario Schemas ==========

class HorarioBase(BaseModel):
    """Schema base para Horario."""
    nombre: str = Field(..., min_length=3, max_length=100, description="Ej: 'Turno Oficina'")
    hora_entrada: Optional[time] = None
    hora_salida: Optional[time] = None
    tolerancia_minutos: int = Field(default=5, ge=0, le=60, description="Minutos de gracia")
    dias_laborables: List[int] = Field(default=[1, 2, 3, 4, 5], description="[1=Lun, 2=Mar, ..., 7=Dom]")
    tipo_jornada: Literal["continua", "discontinua"] = Field(default="continua", description="continua | discontinua")
    activo: bool = True
    horas_trabajadas: Optional[float] = Field(None, description="Horas trabajadas calculadas automáticamente por día (NULL para jornada discontinua)")
    jornada_semanal_horas: Optional[float] = Field(None, description="Total horas semanales (máx 48 según LGT Art. 46) - calculado automáticamente")

    @model_validator(mode='after')
    def validate_horario_fields(self) -> 'HorarioBase':
        if self.tipo_jornada == "discontinua":
            if self.hora_entrada is not None or self.hora_salida is not None:
                raise ValueError('Para jornada discontinua, hora_entrada y hora_salida no deben ser especificadas')
            self.horas_trabajadas = None
            self.jornada_semanal_horas = None
        elif self.tipo_jornada == "continua":
            if self.hora_entrada is None or self.hora_salida is None:
                raise ValueError('Para jornada continua, hora_entrada y hora_salida son requeridas')
            if self.hora_salida <= self.hora_entrada:
                raise ValueError('La hora de salida debe ser posterior a la hora de entrada para jornada continua')
            
            # Calculate daily worked hours
            dummy_date = date(2000, 1, 1)
            dt_entrada = datetime.combine(dummy_date, self.hora_entrada)
            dt_salida = datetime.combine(dummy_date, self.hora_salida)
            
            time_diff = dt_salida - dt_entrada
            self.horas_trabajadas = round(time_diff.total_seconds() / 3600, 2)
            
            # Calculate weekly worked hours
            self.jornada_semanal_horas = round(self.horas_trabajadas * len(self.dias_laborables), 2)
            if self.jornada_semanal_horas > 48.0:
                raise ValueError('La jornada semanal no puede exceder las 48 horas según la LGT Art. 46')
        return self

    @field_validator('dias_laborables')
    @classmethod
    def validar_dias_laborables(cls, v: List[int]) -> List[int]:
        """Validar que los días estén en rango 1-7."""
        if not v:
            raise ValueError('Debe especificar al menos un día laborable')
        for dia in v:
            if dia < 1 or dia > 7:
                raise ValueError('Los días deben estar entre 1 (Lunes) y 7 (Domingo)')
        # Ensure unique days
        if len(v) != len(set(v)):
            raise ValueError('Los días laborables deben ser únicos')
        return sorted(v)

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
    """Schema para crear un horario. Las horas semanales se calculan automáticamente."""
    pass


class HorarioUpdate(BaseModel):
    """Schema para actualizar un horario. Las horas semanales se recalculan automáticamente si cambian horas o días."""
    nombre: Optional[str] = Field(None, min_length=3, max_length=100)
    hora_entrada: Optional[time] = None
    hora_salida: Optional[time] = None
    tolerancia_minutos: Optional[int] = Field(None, ge=0, le=60)
    dias_laborables: Optional[List[int]] = None
    tipo_jornada: Optional[Literal["continua", "discontinua"]] = None
    activo: Optional[bool] = None
    horas_trabajadas: Optional[float] = Field(None, description="Horas trabajadas calculadas automáticamente por día (NULL para jornada discontinua)")
    jornada_semanal_horas: Optional[float] = Field(None, description="Total horas semanales (máx 48 según LGT Art. 46) - calculado automáticamente")

    @model_validator(mode='after')
    def validate_horario_fields_update(self) -> 'HorarioUpdate':
        # Retrieve current values for validation if not provided in update data
        # This part requires fetching the existing object from DB, which happens in the service layer.
        # Here, we only validate the fields provided in the update, but ensure consistency.
        
        # If tipo_jornada is being updated, or if hora_entrada/salida are being updated for a continua jornada
        # we need to re-evaluate the horas_trabajadas and jornada_semanal_horas
        # However, for Pydantic, the model_validator only sees the data provided for the current update.
        # The full validation of consistency with existing data will occur in the service layer.
        
        if self.tipo_jornada == "discontinua":
            if self.hora_entrada is not None or self.hora_salida is not None:
                raise ValueError('Para jornada discontinua, hora_entrada y hora_salida no deben ser especificadas')
            self.horas_trabajadas = None
            self.jornada_semanal_horas = None
        elif self.tipo_jornada == "continua":
            # If both hora_entrada and hora_salida are provided, recalculate
            if self.hora_entrada is not None and self.hora_salida is not None:
                if self.hora_salida <= self.hora_entrada:
                    raise ValueError('La hora de salida debe ser posterior a la hora de entrada para jornada continua')
                
                dummy_date = date(2000, 1, 1)
                dt_entrada = datetime.combine(dummy_date, self.hora_entrada)
                dt_salida = datetime.combine(dummy_date, self.hora_salida)
                
                time_diff = dt_salida - dt_entrada
                self.horas_trabajadas = round(time_diff.total_seconds() / 3600, 2)
                
                # If dias_laborables is also provided, calculate jornada_semanal_horas
                if self.dias_laborables is not None:
                    self.jornada_semanal_horas = round(self.horas_trabajadas * len(self.dias_laborables), 2)
                    if self.jornada_semanal_horas > 48.0:
                        raise ValueError('La jornada semanal no puede exceder las 48 horas según la LGT Art. 46')
                else:
                    # If dias_laborables is not provided in the update, cannot calculate jornada_semanal_horas yet
                    self.jornada_semanal_horas = None
            else:
                # If one of hora_entrada/salida is missing, cannot calculate horas_trabajadas/jornada_semanal_horas fully
                self.horas_trabajadas = None
                self.jornada_semanal_horas = None
        
        # Validate dias_laborables if provided
        if self.dias_laborables is not None:
            if not self.dias_laborables:
                raise ValueError('Debe especificar al menos un día laborable')
            for dia in self.dias_laborables:
                if dia < 1 or dia > 7:
                    raise ValueError('Los días deben estar entre 1 (Lunes) y 7 (Domingo)')
            if len(self.dias_laborables) != len(set(self.dias_laborables)):
                raise ValueError('Los días laborables deben ser únicos')
            self.dias_laborables = sorted(self.dias_laborables)

        return self


class HorarioResponse(HorarioBase):
    """Schema de respuesta para Horario."""
    id: int
    jornada_semanal_horas: float
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HorarioCreateResponse(HorarioResponse):
    """Schema de respuesta específica para POST (crear horario)."""
    pass


class HorarioUpdateResponse(HorarioResponse):
    """Schema de respuesta específica para PUT (actualizar horario)."""
    pass


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
