"""
Schemas Pydantic para CompensacionHorasExtra.

Registro puntual de horas extra (trabajo en fin de semana/feriado no
planeado) que el trigger de Neon `trg_compensacion_horas_extra_a_vacacion`
acredita automáticamente a `vacacion.horas_correspondientes` y
`vacacion.horas_goce_haber` al insertarse. No hay validación de "fue
realmente un fin de semana/feriado" en esta capa: se confía en que el
admin lo carga correctamente.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class CompensacionHorasExtraCreate(BaseModel):
    """Schema para registrar una compensación de horas extra."""
    id_empleado: int = Field(..., gt=0, description="ID del empleado")
    fecha: date = Field(..., description="Fecha trabajada que se compensa")
    horas: Decimal = Field(Decimal("8.0"), gt=0, description="Horas a acreditar en vacacion.horas_goce_haber")
    motivo: str = Field(..., min_length=1, description="Motivo de la compensación (ej. trabajo en feriado no planeado)")
    gestion: Optional[int] = Field(
        None, ge=2020, le=2100,
        description="Gestión (año) de vacacion a la que se acredita. Si se omite, se usa el año de 'fecha'"
    )

    # id_registrado_por ya no se acepta del cliente: se deriva del usuario
    # autenticado (get_actor_empleado_id) en el router.


class CompensacionHorasExtraResponse(BaseModel):
    """Schema de respuesta para CompensacionHorasExtra."""
    id: int
    id_empleado: int
    fecha: date
    horas: Decimal
    motivo: str
    gestion: int
    id_registrado_por: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
