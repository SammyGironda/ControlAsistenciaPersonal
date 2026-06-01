"""
Schemas Pydantic para endpoints de dashboard y estadisticas.
"""

from datetime import date
from typing import List

from pydantic import BaseModel, Field


class RetrasoPorMesResponse(BaseModel):
    """Metrica mensual agregada de retrasos."""

    mes: str = Field(..., description="Mes en formato YYYY-MM")
    total_dias: int = Field(..., ge=0, description="Total de dias registrados en el mes")
    dias_con_retraso: int = Field(..., ge=0, description="Dias con minutos_retraso > 0")
    total_minutos: int = Field(..., ge=0, description="Suma total de minutos de retraso")
    promedio_minutos: float = Field(..., ge=0, description="Promedio de minutos de retraso")


class HorasTrabajadasEmpleadoItem(BaseModel):
    """Totales de horas y asistencia por empleado en un mes."""

    id_empleado: int
    nombres: str
    apellidos: str
    nombre_completo: str
    id_cargo: int
    id_departamento: int
    total_minutos_trabajados: int = Field(..., ge=0)
    total_horas_trabajadas: float = Field(..., ge=0)
    dias_presentes: int = Field(..., ge=0)
    dias_con_horas_extra: int = Field(..., ge=0)
    total_horas_extra: float = Field(..., ge=0)


class EmpleadoHorasResumenItem(BaseModel):
    """Item resumido para top/bottom de horas trabajadas."""

    id_empleado: int
    nombre_completo: str
    total_horas_trabajadas: float = Field(..., ge=0)


class HorasTrabajadasMesResumen(BaseModel):
    """Resumen global de horas trabajadas en el mes consultado."""

    promedio_horas_por_empleado: float = Field(..., ge=0)
    total_horas_empresa: float = Field(..., ge=0)
    empleados_con_mas_horas: List[EmpleadoHorasResumenItem] = Field(default_factory=list)
    empleados_con_menos_horas: List[EmpleadoHorasResumenItem] = Field(default_factory=list)


class HorasTrabajadasMesResponse(BaseModel):
    """Respuesta del endpoint de horas trabajadas del mes."""

    resumen: HorasTrabajadasMesResumen
    por_empleado: List[HorasTrabajadasEmpleadoItem] = Field(default_factory=list)


class CumpleanosProximoResponse(BaseModel):
    """Empleado con cumpleanos proximo dentro del rango consultado."""

    id: int
    nombre: str
    fecha_nacimiento: date
    dias_hasta: int = Field(..., ge=0)
    id_departamento: int
    cargo: str
