"""
Schemas Pydantic para Asistencia Diaria.
Validación de datos de entrada/salida para endpoints REST.
"""

from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
from decimal import Decimal


# --- Schemas de creación/actualización ---

class AsistenciaDiariaCreate(BaseModel):
    """
    Schema para crear manualmente un registro de asistencia (correcciones RRHH).
    Típicamente el worker automático crea estos registros, pero RRHH puede corregir.
    """
    id_empleado: int = Field(..., gt=0, description="ID del empleado")
    fecha: date = Field(..., description="Fecha del día de asistencia")
    id_marcacion_entrada: Optional[int] = Field(None, description="ID de la marcación de entrada")
    id_marcacion_salida: Optional[int] = Field(None, description="ID de la marcación de salida")
    id_justificacion: Optional[int] = Field(None, description="ID de la justificación (si aplica)")
    tipo_dia: str = Field(
        ...,
        pattern="^(presente|ausente|feriado|permiso_parcial|presente_exento|licencia_medica|descanso)$",
        description="Tipo de día: presente, ausente, feriado, etc."
    )
    minutos_retraso: int = Field(0, ge=0, description="Minutos de retraso")
    minutos_trabajados: int = Field(0, ge=0, description="Minutos netos trabajados")
    horas_extra: Decimal = Field(Decimal("0.0"), ge=0, description="Horas extra trabajadas")
    horas_permiso_usadas: Decimal = Field(Decimal("0.0"), ge=0, description="Horas de permiso usadas")
    trabajo_en_feriado: bool = Field(False, description="¿Trabajó en día feriado?")
    observacion: Optional[str] = Field(None, max_length=500, description="Observaciones adicionales")

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id_empleado": 5,
                "fecha": "2026-01-15",
                "id_marcacion_entrada": 1234,
                "id_marcacion_salida": 1235,
                "tipo_dia": "presente",
                "minutos_retraso": 15,
                "minutos_trabajados": 480,
                "horas_extra": 0.0,
                "observacion": "Empleado llegó tarde por tráfico"
            }
        }


class AsistenciaDiariaUpdate(BaseModel):
    """
    Schema para actualizar un registro de asistencia existente.
    Todos los campos opcionales para permitir actualización parcial.
    """
    tipo_dia: Optional[str] = Field(
        None,
        pattern="^(presente|ausente|feriado|permiso_parcial|presente_exento|licencia_medica|descanso)$"
    )
    minutos_retraso: Optional[int] = Field(None, ge=0)
    minutos_trabajados: Optional[int] = Field(None, ge=0)
    horas_extra: Optional[Decimal] = Field(None, ge=0)
    horas_permiso_usadas: Optional[Decimal] = Field(None, ge=0)
    trabajo_en_feriado: Optional[bool] = None
    observacion: Optional[str] = Field(None, max_length=500)

    class Config:
        from_attributes = True


# --- Schemas de respuesta ---

class AsistenciaDiariaResponse(BaseModel):
    """Schema base de respuesta para asistencia diaria."""
    id: int
    id_empleado: int
    fecha: date
    id_marcacion_entrada: Optional[int]
    id_marcacion_salida: Optional[int]
    id_justificacion: Optional[int]
    tipo_dia: str
    minutos_retraso: int
    minutos_trabajados: int
    horas_extra: Decimal
    horas_permiso_usadas: Decimal
    trabajo_en_feriado: bool
    observacion: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 123,
                "id_empleado": 5,
                "fecha": "2026-01-15",
                "id_marcacion_entrada": 1234,
                "id_marcacion_salida": 1235,
                "id_justificacion": None,
                "tipo_dia": "presente",
                "minutos_retraso": 15,
                "minutos_trabajados": 480,
                "horas_extra": 0.0,
                "horas_permiso_usadas": 0.0,
                "trabajo_en_feriado": False,
                "observacion": None,
                "created_at": "2026-01-15T23:59:30",
                "updated_at": "2026-01-15T23:59:30"
            }
        }


class EmpleadoSimple(BaseModel):
    """Datos básicos del empleado para respuestas anidadas."""
    id: int
    nombres: str
    apellidos: str
    ci_numero: str
    ci_depto_emision: str

    class Config:
        from_attributes = True


class MarcacionSimple(BaseModel):
    """Datos básicos de marcación para respuestas anidadas."""
    id: int
    fecha_hora_marcacion: datetime
    tipo_marcacion: str

    class Config:
        from_attributes = True


class AsistenciaDiariaConDetalles(AsistenciaDiariaResponse):
    """
    Respuesta completa con datos del empleado y marcaciones anidadas.
    Útil para endpoints de detalle y listados enriquecidos.
    """
    empleado: EmpleadoSimple
    marcacion_entrada_detalle: Optional[MarcacionSimple] = Field(
        None, description="Detalles de la marcación de entrada"
    )
    marcacion_salida_detalle: Optional[MarcacionSimple] = Field(
        None, description="Detalles de la marcación de salida"
    )

    class Config:
        from_attributes = True


# --- Schemas de resumen ---

class ResumenAsistenciaMensual(BaseModel):
    """
    Resumen mensual de asistencia de un empleado.
    Basado en la vista v_asistencia_mensual.
    """
    id_empleado: int
    nombre_completo: str
    cargo: str
    es_cargo_confianza: bool
    departamento: str
    mes: datetime  # DATE_TRUNC devuelve timestamp
    total_dias_registro: int
    dias_presente: int
    dias_presente_exento: int
    dias_ausente: int
    dias_feriado: int
    dias_permiso_parcial: int
    dias_licencia_medica: int
    dias_descanso: int
    total_minutos_retraso: int
    total_minutos_trabajados: int
    total_horas_extra: Decimal
    dias_trabajados_en_feriado: int

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id_empleado": 5,
                "nombre_completo": "Juan Pérez García",
                "cargo": "Desarrollador Senior",
                "es_cargo_confianza": False,
                "departamento": "Tecnología",
                "mes": "2026-01-01T00:00:00",
                "total_dias_registro": 22,
                "dias_presente": 20,
                "dias_presente_exento": 0,
                "dias_ausente": 1,
                "dias_feriado": 1,
                "dias_permiso_parcial": 0,
                "dias_licencia_medica": 0,
                "dias_descanso": 8,
                "total_minutos_retraso": 45,
                "total_minutos_trabajados": 9600,
                "total_horas_extra": 4.0,
                "dias_trabajados_en_feriado": 0
            }
        }


# --- Schemas de respuesta de procesamiento ---

class ResultadoProcesamiento(BaseModel):
    """Resultado del procesamiento masivo de asistencia."""
    fecha: date
    empleados_procesados: int
    empleados_con_error: int
    empleados_skipped: int
    errores: list[str] = Field(default_factory=list)
    
    class Config:
        json_schema_extra = {
            "example": {
                "fecha": "2026-01-15",
                "empleados_procesados": 150,
                "empleados_con_error": 2,
                "empleados_skipped": 5,
                "errores": [
                    "Empleado 123: No tiene horario asignado",
                    "Empleado 456: Error al calcular retraso"
                ]
            }
        }
