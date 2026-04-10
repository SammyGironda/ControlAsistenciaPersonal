"""
Schemas Pydantic para Marcaciones, Archivos Excel e Incidencias.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from decimal import Decimal


# ============================================================
# MARCACION
# ============================================================

class MarcacionBase(BaseModel):
    """Campos comunes para marcación."""
    id_empleado: int = Field(..., gt=0)
    fecha_hora_marcacion: datetime
    tipo_marcacion: str = Field(..., pattern="^(ENTRADA|SALIDA)$")
    origen_dato: str = Field(default="Excel", pattern="^(Excel|API_Biometrico|Manual)$")
    id_archivo_excel: Optional[int] = Field(None, gt=0)
    observacion: Optional[str] = Field(None, max_length=5000)


class MarcacionCreate(MarcacionBase):
    """Schema para crear una marcación."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id_empleado": 1,
                "fecha_hora_marcacion": "2026-01-15T08:00:00",
                "tipo_marcacion": "ENTRADA",
                "origen_dato": "Excel",
                "id_archivo_excel": 1,
                "observacion": "Importado desde Excel enero"
            }
        }
    )


class MarcacionResponse(MarcacionBase):
    """Schema de respuesta de marcación."""
    id: int
    id_marcacion_par: Optional[int]
    es_duplicada: bool
    es_huerfana: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MarcacionConEmpleado(MarcacionResponse):
    """Schema de marcación con información del empleado."""
    empleado_nombre: str
    empleado_ci: str

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# ARCHIVO EXCEL
# ============================================================

class ArchivoExcelCreate(BaseModel):
    """Schema para registrar archivo Excel subido."""
    nombre_archivo: str = Field(..., max_length=255)
    ruta_storage: str = Field(..., max_length=255)
    id_subido_por: Optional[int] = Field(None, gt=0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "nombre_archivo": "Asistencia_Enero_2026.xlsx",
                "ruta_storage": "/uploads/marcaciones/2026/01/asistencia_enero.xlsx",
                "id_subido_por": 1
            }
        }
    )


class ArchivoExcelResponse(BaseModel):
    """Schema de respuesta de archivo Excel."""
    id: int
    nombre_archivo: str
    ruta_storage: str
    id_subido_por: Optional[int]
    fecha_subida: datetime
    estado_procesamiento: str
    total_filas: Optional[int]
    filas_procesadas: Optional[int]
    filas_con_error: Optional[int]
    log_errores: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ArchivoExcelUpdate(BaseModel):
    """Schema para actualizar estado de procesamiento."""
    estado_procesamiento: Optional[str] = Field(None, pattern="^(pendiente|procesando|completado|error)$")
    total_filas: Optional[int] = Field(None, ge=0)
    filas_procesadas: Optional[int] = Field(None, ge=0)
    filas_con_error: Optional[int] = Field(None, ge=0)
    log_errores: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "estado_procesamiento": "completado",
                "total_filas": 500,
                "filas_procesadas": 495,
                "filas_con_error": 5,
                "log_errores": "[{\"fila\": 23, \"error\": \"CI no encontrado\"}]"
            }
        }
    )


# ============================================================
# INCIDENCIA MARCACION
# ============================================================

class IncidenciaMarcacionBase(BaseModel):
    """Campos comunes para incidencia."""
    tipo_incidencia: str = Field(..., pattern="^(huerfana|duplicada|inconsistente)$")
    evidencia_url: Optional[str] = Field(None, max_length=255)
    descripcion_resolucion: Optional[str] = Field(None, max_length=5000)


class IncidenciaMarcacionCreate(IncidenciaMarcacionBase):
    """Schema para crear incidencia manualmente."""
    id_marcacion: int = Field(..., gt=0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id_marcacion": 123,
                "tipo_incidencia": "huerfana",
                "descripcion_resolucion": "Empleado olvidó marcar salida"
            }
        }
    )


class IncidenciaMarcacionResponse(IncidenciaMarcacionBase):
    """Schema de respuesta de incidencia."""
    id: int
    id_marcacion: int
    estado_resolucion: str
    id_resuelto_por: Optional[int]
    fecha_resolucion: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IncidenciaMarcacionUpdate(BaseModel):
    """Schema para resolver incidencia."""
    estado_resolucion: str = Field(..., pattern="^(pendiente|resuelto|ignorado)$")
    evidencia_url: Optional[str] = Field(None, max_length=255)
    descripcion_resolucion: Optional[str] = Field(None, max_length=5000)
    id_resuelto_por: Optional[int] = Field(None, gt=0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "estado_resolucion": "resuelto",
                "descripcion_resolucion": "Se corrigió la marcación de salida manualmente",
                "id_resuelto_por": 1,
                "evidencia_url": "/docs/evidencias/incidencia_123.pdf"
            }
        }
    )


# ============================================================
# SCHEMAS ADICIONALES PARA UPLOAD
# ============================================================

class UploadExcelResponse(BaseModel):
    """Response del endpoint de upload."""
    archivo_id: int
    nombre_archivo: str
    estado: str
    mensaje: str
    total_filas: Optional[int] = None
    filas_procesadas: Optional[int] = None
    filas_con_error: Optional[int] = None
    errores: Optional[list] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "archivo_id": 1,
                "nombre_archivo": "Asistencia_Enero_2026.xlsx",
                "estado": "completado",
                "mensaje": "Archivo procesado exitosamente",
                "total_filas": 500,
                "filas_procesadas": 495,
                "filas_con_error": 5,
                "errores": [
                    {"fila": 23, "error": "CI 1234567-LP no encontrado"},
                    {"fila": 45, "error": "Fecha inválida"}
                ]
            }
        }
    )
