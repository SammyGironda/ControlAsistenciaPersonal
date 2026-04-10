"""
Router del modulo de reportes.
Semana 8: generacion de reportes XLSX/PDF y consulta de bitacora.
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.reports.reporte import services
from app.features.reports.reporte.models import TipoReporteEnum, FormatoReporteEnum
from app.features.reports.reporte.schemas import (
    ReporteAsistenciaMensualRequest,
    ReporteIndividualRequest,
    ReportePlanillaRequest,
    ReporteResponse,
    ReporteUpdate,
    ReporteVacacionesRequest,
)


router = APIRouter(prefix="/reportes", tags=["Reportes"])


@router.post(
    "/asistencia-mensual",
    response_model=ReporteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generar reporte de asistencia mensual (XLSX)",
)
def generar_asistencia_mensual(data: ReporteAsistenciaMensualRequest, db: Session = Depends(get_db)):
    """Genera y registra reporte de asistencia mensual."""

    return services.generar_reporte_asistencia_mensual(db, data)


@router.post(
    "/planilla",
    response_model=ReporteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generar reporte de planilla (XLSX)",
)
def generar_planilla(data: ReportePlanillaRequest, db: Session = Depends(get_db)):
    """Genera y registra reporte mensual de planilla."""

    return services.generar_reporte_planilla(db, data)


@router.post(
    "/vacaciones",
    response_model=ReporteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generar reporte de vacaciones (XLSX)",
)
def generar_vacaciones(data: ReporteVacacionesRequest, db: Session = Depends(get_db)):
    """Genera y registra reporte de vacaciones por gestion."""

    return services.generar_reporte_vacaciones(db, data)


@router.post(
    "/individual/{id_empleado:int}",
    response_model=ReporteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generar reporte individual por empleado (PDF)",
)
def generar_individual(id_empleado: int, data: ReporteIndividualRequest, db: Session = Depends(get_db)):
    """Genera y registra reporte individual de un empleado en PDF."""

    return services.generar_reporte_individual_pdf(db, id_empleado, data)


@router.get(
    "/{reporte_id:int}",
    response_model=ReporteResponse,
    summary="Obtener reporte por ID",
)
def obtener_reporte(reporte_id: int, db: Session = Depends(get_db)):
    """Obtiene un registro de reporte por ID."""

    return services.obtener_reporte(db, reporte_id)


@router.get(
    "/",
    response_model=List[ReporteResponse],
    summary="Listar reportes con filtros",
)
def listar_reportes(
    tipo_reporte: Optional[TipoReporteEnum] = Query(None, description="Filtro por tipo de reporte"),
    formato: Optional[FormatoReporteEnum] = Query(None, description="Filtro por formato"),
    id_generado_por: Optional[int] = Query(None, gt=0, description="Filtro por usuario generador"),
    activo: Optional[bool] = Query(None, description="Filtro por estado activo/inactivo"),
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: int = Query(100, ge=1, le=500, description="Limite de resultados"),
    db: Session = Depends(get_db),
):
    """Lista reportes generados con filtros opcionales."""

    return services.listar_reportes(
        db,
        tipo_reporte=tipo_reporte,
        formato=formato,
        id_generado_por=id_generado_por,
        activo=activo,
        skip=skip,
        limit=limit,
    )


@router.put(
    "/{reporte_id:int}",
    response_model=ReporteResponse,
    summary="Actualizar reporte",
)
def actualizar_reporte(reporte_id: int, data: ReporteUpdate, db: Session = Depends(get_db)):
    """Actualiza datos editables de un reporte."""

    return services.actualizar_reporte(db, reporte_id, data)


@router.delete(
    "/{reporte_id:int}",
    response_model=ReporteResponse,
    summary="Desactivar reporte (soft delete)",
)
def eliminar_reporte(reporte_id: int, db: Session = Depends(get_db)):
    """Realiza soft delete del reporte."""

    return services.eliminar_reporte(db, reporte_id)


@router.delete(
    "/{reporte_id:int}/permanente",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar reporte permanentemente (hard delete)",
)
def eliminar_reporte_permanente(reporte_id: int, db: Session = Depends(get_db)):
    """Elimina el registro de reporte de forma permanente."""

    services.eliminar_reporte_permanente(db, reporte_id)
    return None


@router.get(
    "/{reporte_id:int}/descargar",
    summary="Descargar archivo generado",
)
def descargar_reporte(reporte_id: int, db: Session = Depends(get_db)):
    """Descarga el archivo fisico del reporte generado."""

    ruta = services.ruta_reporte_descarga(db, reporte_id)
    return FileResponse(path=str(ruta), filename=ruta.name)
