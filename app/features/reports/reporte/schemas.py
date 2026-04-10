"""
Schemas Pydantic para el modulo de reportes.
Semana 8: generacion de XLSX y PDF con bitacora en tabla reporte.
"""

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator, ConfigDict

from app.features.reports.reporte.models import TipoReporteEnum, FormatoReporteEnum


class ReporteAsistenciaMensualRequest(BaseModel):
    """Parametros para generar reporte de asistencia mensual en XLSX."""

    anio: int = Field(..., ge=2000, le=2100, description="Gestion a reportar")
    mes: int = Field(..., ge=1, le=12, description="Mes a reportar")
    id_departamento: Optional[int] = Field(None, gt=0, description="Filtro opcional por departamento")
    id_empleado: Optional[int] = Field(None, gt=0, description="Filtro opcional por empleado")
    id_generado_por: Optional[int] = Field(None, gt=0, description="Usuario que genera el reporte")


class ReportePlanillaRequest(BaseModel):
    """Parametros para generar reporte de planilla en XLSX."""

    anio: int = Field(..., ge=2000, le=2100, description="Gestion a reportar")
    mes: int = Field(..., ge=1, le=12, description="Mes a reportar")
    id_departamento: Optional[int] = Field(None, gt=0, description="Filtro opcional por departamento")
    id_empleado: Optional[int] = Field(None, gt=0, description="Filtro opcional por empleado")
    id_generado_por: Optional[int] = Field(None, gt=0, description="Usuario que genera el reporte")


class ReporteVacacionesRequest(BaseModel):
    """Parametros para generar reporte de vacaciones en XLSX."""

    gestion: int = Field(..., ge=2000, le=2100, description="Gestion a reportar")
    id_departamento: Optional[int] = Field(None, gt=0, description="Filtro opcional por departamento")
    id_empleado: Optional[int] = Field(None, gt=0, description="Filtro opcional por empleado")
    id_generado_por: Optional[int] = Field(None, gt=0, description="Usuario que genera el reporte")


class ReporteIndividualRequest(BaseModel):
    """Parametros para generar reporte individual por empleado en PDF."""

    fecha_inicio: date = Field(..., description="Fecha de inicio del periodo")
    fecha_fin: date = Field(..., description="Fecha de fin del periodo")
    id_generado_por: Optional[int] = Field(None, gt=0, description="Usuario que genera el reporte")

    @field_validator("fecha_fin")
    @classmethod
    def validar_rango_fechas(cls, value: date, info):
        """Valida que la fecha de fin no sea menor que la fecha de inicio."""

        fecha_inicio = info.data.get("fecha_inicio")
        if fecha_inicio and value < fecha_inicio:
            raise ValueError("fecha_fin debe ser mayor o igual a fecha_inicio")
        return value


class ReporteUpdate(BaseModel):
    """Actualizacion parcial de un reporte en bitacora."""

    activo: Optional[bool] = None


class ReporteResponse(BaseModel):
    """Respuesta estandar para registros de reporte."""

    id: int
    nombre: str
    tipo_reporte: TipoReporteEnum
    id_generado_por: Optional[int]
    id_departamento: Optional[int]
    id_empleado: Optional[int]
    periodo_inicio: date
    periodo_fin: date
    ruta_archivo: str
    formato: FormatoReporteEnum
    fecha_generacion: datetime
    activo: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
