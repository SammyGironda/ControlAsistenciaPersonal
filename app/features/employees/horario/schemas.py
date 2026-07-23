"""
Schemas Pydantic para Horario y AsignacionHorario.
Validación de entrada/salida de datos con reglas de negocio.
Zona horaria: Todas las horas se almacenan en UTC en la base de datos.
La Paz, Bolivia: UTC-4 (sin horario de verano)
Las timestamps se devuelven en UTC y opcionalmente pueden convertirse a La Paz.
"""

from datetime import datetime, time, date, timedelta, timezone
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict, computed_field, field_serializer

# Zona horaria de La Paz (UTC-4)
LA_PAZ_TIMEZONE = timezone(timedelta(hours=-4))


# ========== Horario Schemas ==========

class HorarioBase(BaseModel):
    """Schema base para Horario."""
    nombre: str = Field(..., min_length=3, max_length=100, description="Ej: 'Turno Oficina'")
    hora_entrada: Optional[time] = Field(None, description="Formato: HH:MM (ej: 09:30)")
    hora_salida: Optional[time] = Field(None, description="Formato: HH:MM (ej: 17:30)")
    tolerancia_minutos: int = Field(default=5, ge=0, le=60, description="Minutos de gracia")
    dias_laborables: List[int] = Field(default=[1, 2, 3, 4, 5], description="[1=Lun, 2=Mar, ..., 7=Dom]")
    tipo_jornada: Literal["continua", "discontinua"] = Field(default="continua", description="continua | discontinua")
    activo: bool = True
    jornada_semanal_horas: Optional[float] = Field(None, description="Total horas semanales (máx 48 según LGT Art. 46) - calculado automáticamente")

    @field_validator('hora_entrada', 'hora_salida', mode='before')
    @classmethod
    def parse_time_simple(cls, v):
        """Acepta formato HH:MM y lo convierte a time. Rellena segundos con :00."""
        if v is None:
            return None
        if isinstance(v, time):
            return v
        if isinstance(v, str):
            v = v.strip()
            if ':' not in v:
                raise ValueError('Formato debe ser HH:MM (ej: 09:30)')
            partes = v.split(':')
            if len(partes) == 2:
                try:
                    horas = int(partes[0])
                    minutos = int(partes[1])
                    return time(hour=horas, minute=minutos, second=0)
                except (ValueError, TypeError):
                    raise ValueError('Formato debe ser HH:MM con números válidos (ej: 09:30)')
            else:
                raise ValueError('Formato debe ser HH:MM (ej: 09:30)')
        raise ValueError('Formato debe ser HH:MM (ej: 09:30)')

    @model_validator(mode='after')
    def validate_horario_fields(self) -> 'HorarioBase':
        if self.tipo_jornada == "discontinua":
            if self.hora_entrada is not None or self.hora_salida is not None:
                raise ValueError('Para jornada discontinua, hora_entrada y hora_salida no deben ser especificadas')
        elif self.tipo_jornada == "continua":
            if self.hora_entrada is None or self.hora_salida is None:
                raise ValueError('Para jornada continua, hora_entrada y hora_salida son requeridas')
            if self.hora_salida <= self.hora_entrada:
                raise ValueError('La hora de salida debe ser posterior a la hora de entrada para jornada continua')
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
    jornada_semanal_horas: Optional[float] = Field(None, description="Total horas semanales (máx 48 según LGT Art. 46) - calculado automáticamente")

    @model_validator(mode='after')
    def validate_horario_fields_update(self) -> 'HorarioUpdate':
        if self.tipo_jornada == "discontinua":
            if self.hora_entrada is not None or self.hora_salida is not None:
                raise ValueError('Para jornada discontinua, hora_entrada y hora_salida no deben ser especificadas')
        elif self.tipo_jornada == "continua":
            if self.hora_entrada is not None and self.hora_salida is not None:
                if self.hora_salida <= self.hora_entrada:
                    raise ValueError('La hora de salida debe ser posterior a la hora de entrada para jornada continua')

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
    """Schema de respuesta para Horario. Timestamps en UTC."""
    id: int
    jornada_semanal_horas: float
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )

    @field_serializer('hora_entrada', 'hora_salida', when_used='json')
    def serialize_time_simple(self, value: Optional[time]) -> Optional[str]:
        """Serializa time como 'HH:MM' en JSON."""
        if value is None:
            return None
        return value.strftime("%H:%M")

    @computed_field
    @property
    def created_at_lapaz(self) -> Optional[datetime]:
        """Timestamp created_at convertido a La Paz (UTC-4)."""
        if self.created_at is None:
            return None
        if self.created_at.tzinfo is None:
            dt = self.created_at.replace(tzinfo=timezone.utc)
        else:
            dt = self.created_at
        return dt.astimezone(LA_PAZ_TIMEZONE)

    @computed_field
    @property
    def updated_at_lapaz(self) -> Optional[datetime]:
        """Timestamp updated_at convertido a La Paz (UTC-4)."""
        if self.updated_at is None:
            return None
        if self.updated_at.tzinfo is None:
            dt = self.updated_at.replace(tzinfo=timezone.utc)
        else:
            dt = self.updated_at
        return dt.astimezone(LA_PAZ_TIMEZONE)


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
        """Validar que fecha_fin no sea anterior a fecha_inicio.

        Una asignación puede tener vigencia de un solo día, por ejemplo
        cuando coincide con la fecha final de un contrato a plazo fijo.
        """
        if v is not None and 'fecha_inicio' in info.data:
            fecha_inicio = info.data['fecha_inicio']
            if v < fecha_inicio:
                raise ValueError('La fecha fin no puede ser anterior a la fecha de inicio')
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
    """Schema de respuesta para AsignacionHorario. Timestamps en UTC."""
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )

    @computed_field
    @property
    def created_at_lapaz(self) -> Optional[datetime]:
        """Timestamp created_at convertido a La Paz (UTC-4)."""
        if self.created_at is None:
            return None
        if self.created_at.tzinfo is None:
            dt = self.created_at.replace(tzinfo=timezone.utc)
        else:
            dt = self.created_at
        return dt.astimezone(LA_PAZ_TIMEZONE)

    @computed_field
    @property
    def updated_at_lapaz(self) -> Optional[datetime]:
        """Timestamp updated_at convertido a La Paz (UTC-4)."""
        if self.updated_at is None:
            return None
        if self.updated_at.tzinfo is None:
            dt = self.updated_at.replace(tzinfo=timezone.utc)
        else:
            dt = self.updated_at
        return dt.astimezone(LA_PAZ_TIMEZONE)


class AsignacionHorarioConDetalle(AsignacionHorarioResponse):
    """Schema de asignación con detalles del horario incluidos."""
    horario: HorarioResponse
    
    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={
            datetime: lambda v: v.isoformat() if v else None
        }
    )
