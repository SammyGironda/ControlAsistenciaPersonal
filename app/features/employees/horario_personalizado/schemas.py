"""
Schemas Pydantic para HorarioPersonalizadoEmpleado.
Zona horaria: Todas las horas se almacenan en UTC en la base de datos.
La Paz, Bolivia: UTC-4 (sin horario de verano).
"""

from datetime import datetime, time, timedelta, timezone
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict, computed_field, field_serializer

# Zona horaria de La Paz (UTC-4)
LA_PAZ_TIMEZONE = timezone(timedelta(hours=-4))


class HorarioPersonalizadoEmpleadoUpsert(BaseModel):
    """
    Schema para el PUT (crear o actualizar) del override de horario.
    Todos los campos son opcionales de forma independiente: un admin puede
    ajustar solo la tolerancia, o solo activar salida_flexible, sin tener
    que reenviar el resto.
    """
    tolerancia_minutos: Optional[int] = Field(None, ge=0, le=180, description="Minutos de gracia propios")
    hora_entrada: Optional[time] = Field(None, description="Formato: HH:MM (ej: 09:30)")
    hora_salida: Optional[time] = Field(
        None,
        description="Formato: HH:MM (ej: 17:30). Solo referencial, nunca se usa para horas_extra pagables",
    )
    salida_flexible: bool = False
    activo: bool = True
    observacion: Optional[str] = Field(None, max_length=500)

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
    def validate_coherencia(self) -> 'HorarioPersonalizadoEmpleadoUpsert':
        if self.hora_entrada is not None and self.hora_salida is not None:
            if self.hora_salida <= self.hora_entrada:
                raise ValueError('La hora de salida debe ser posterior a la hora de entrada')
        if self.salida_flexible and self.hora_salida is not None:
            raise ValueError('Si salida_flexible es TRUE, no debe especificarse hora_salida')
        return self


class HorarioPersonalizadoEmpleadoResponse(BaseModel):
    """Schema de respuesta. Timestamps en UTC."""
    id: int
    id_empleado: int
    tolerancia_minutos: Optional[int]
    hora_entrada: Optional[time]
    hora_salida: Optional[time]
    salida_flexible: bool
    activo: bool
    observacion: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer('hora_entrada', 'hora_salida', when_used='json')
    def serialize_time_simple(self, value: Optional[time]) -> Optional[str]:
        """Serializa time como 'HH:MM' en JSON."""
        if value is None:
            return None
        return value.strftime("%H:%M")

    @computed_field
    @property
    def updated_at_lapaz(self) -> Optional[datetime]:
        """Timestamp updated_at convertido a La Paz (UTC-4)."""
        if self.updated_at is None:
            return None
        dt = self.updated_at if self.updated_at.tzinfo else self.updated_at.replace(tzinfo=timezone.utc)
        return dt.astimezone(LA_PAZ_TIMEZONE)
