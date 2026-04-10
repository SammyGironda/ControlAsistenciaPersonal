"""
Router para Marcaciones - Endpoints REST.
Incluye endpoint de upload de Excel con procesamiento async.
"""

from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, UploadFile, File, Body
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.attendance.marcacion import services
from app.features.attendance.marcacion.schemas import (
    MarcacionCreate, MarcacionResponse, MarcacionConEmpleado,
    ArchivoExcelResponse, ArchivoExcelUpdate,
    IncidenciaMarcacionResponse, IncidenciaMarcacionUpdate,
    UploadExcelResponse
)

router = APIRouter(
    prefix="/marcaciones",
    tags=["Marcaciones y Asistencia"]
)


# ============================================================
# UPLOAD DE EXCEL
# ============================================================

@router.post(
    "/upload-excel",
    response_model=UploadExcelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload de archivo Excel con marcaciones",
    description="Procesa un archivo Excel con marcaciones biométricas usando Pandas"
)
async def upload_excel_marcaciones(
    file: UploadFile = File(..., description="Archivo Excel (.xls o .xlsx)"),
    id_subido_por: Optional[int] = Query(None, description="ID del usuario que sube el archivo"),
    db: Session = Depends(get_db)
):
    """
    Procesa un archivo Excel de marcaciones.

    Formato esperado:
    - Columna 1: CI (ej: 1234567-LP)
    - Columna 2: Fecha (ej: 2026-01-15)
    - Columna 3: Hora Entrada (ej: 08:00)
    - Columna 4: Hora Salida (ej: 18:00)

    Retorna estadísticas de procesamiento y log de errores.
    """
    # Validar extensión
    if not file.filename.endswith(('.xls', '.xlsx')):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se permiten archivos Excel (.xls o .xlsx)"
        )

    # Procesar archivo
    resultado = services.procesar_archivo_excel(db, file, id_subido_por)
    return UploadExcelResponse(**resultado)


# ============================================================
# MARCACIONES - CRUD
# ============================================================

@router.post(
    "/",
    response_model=MarcacionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear marcación manual",
    description="Registra una marcación manual (corrección de RRHH)"
)
def create_marcacion(
    data: MarcacionCreate,
    db: Session = Depends(get_db)
):
    """
    Crea una marcación manual.

    Se usa para correcciones de RRHH cuando el empleado olvidó marcar.
    """
    return services.create_marcacion(db, data)


@router.get(
    "/empleado/{empleado_id}",
    response_model=List[MarcacionResponse],
    summary="Marcaciones de un empleado",
    description="Obtiene todas las marcaciones de un empleado con filtros de fecha"
)
def get_marcaciones_empleado(
    empleado_id: int = Path(..., gt=0),
    fecha_desde: Optional[date] = Query(None, description="Fecha desde (inclusive)"),
    fecha_hasta: Optional[date] = Query(None, description="Fecha hasta (inclusive)"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Obtiene marcaciones de un empleado con filtros opcionales de fecha."""
    return services.get_marcaciones_by_empleado(db, empleado_id, fecha_desde, fecha_hasta, skip, limit)


@router.get(
    "/huerfanas",
    response_model=List[MarcacionResponse],
    summary="Marcaciones huérfanas",
    description="Obtiene todas las marcaciones sin pareja (entrada sin salida o viceversa)"
)
def get_marcaciones_huerfanas(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """
    Obtiene marcaciones huérfanas.

    Una marcación es huérfana cuando no tiene su pareja del tipo opuesto en el mismo día.
    """
    return services.get_marcaciones_huerfanas(db, skip, limit)


@router.get(
    "/duplicadas",
    response_model=List[MarcacionResponse],
    summary="Marcaciones duplicadas",
    description="Obtiene todas las marcaciones marcadas como duplicadas"
)
def get_marcaciones_duplicadas(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """
    Obtiene marcaciones duplicadas.

    Una marcación es duplicada cuando hay dos del mismo tipo en ventana de 5 minutos.
    """
    return services.get_marcaciones_duplicadas(db, skip, limit)


# ============================================================
# ARCHIVOS EXCEL - CRUD
# ============================================================

@router.get(
    "/archivos",
    response_model=List[ArchivoExcelResponse],
    summary="Listar archivos subidos",
    description="Obtiene el historial de archivos Excel procesados"
)
def get_archivos_excel(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """Lista todos los archivos Excel subidos, ordenados por fecha de subida descendente."""
    return services.get_all_archivos(db, skip, limit)


@router.get(
    "/archivos/{archivo_id}",
    response_model=ArchivoExcelResponse,
    summary="Obtener archivo por ID",
    description="Retorna información detallada de un archivo específico"
)
def get_archivo_excel(
    archivo_id: int = Path(..., gt=0),
    db: Session = Depends(get_db)
):
    """Obtiene un archivo Excel por ID."""
    archivo = services.get_archivo_by_id(db, archivo_id)
    if not archivo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el archivo con ID {archivo_id}"
        )
    return archivo


@router.put(
    "/archivos/{archivo_id}",
    response_model=ArchivoExcelResponse,
    summary="Actualizar estado de archivo",
    description="Actualiza el progreso de procesamiento de un archivo"
)
def update_archivo_excel(
    archivo_id: int = Path(..., gt=0),
    data: ArchivoExcelUpdate = Body(...),
    db: Session = Depends(get_db)
):
    """Actualiza el estado de un archivo Excel."""
    return services.update_archivo(db, archivo_id, data)


# ============================================================
# INCIDENCIAS - CRUD
# ============================================================

@router.get(
    "/incidencias/pendientes",
    response_model=List[IncidenciaMarcacionResponse],
    summary="Incidencias pendientes",
    description="Obtiene todas las incidencias que requieren revisión"
)
def get_incidencias_pendientes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """
    Obtiene incidencias pendientes de resolución.

    Retorna marcaciones huérfanas, duplicadas o inconsistentes
    que aún no han sido revisadas por RRHH.
    """
    return services.get_incidencias_pendientes(db, skip, limit)


@router.put(
    "/incidencias/{incidencia_id}",
    response_model=IncidenciaMarcacionResponse,
    summary="Resolver incidencia",
    description="Actualiza el estado de resolución de una incidencia"
)
def resolver_incidencia(
    incidencia_id: int = Path(..., gt=0),
    data: IncidenciaMarcacionUpdate = Body(...),
    db: Session = Depends(get_db)
):
    """
    Resuelve una incidencia de marcación.

    Permite cambiar el estado, agregar evidencia y descripción de resolución.
    """
    return services.update_incidencia(db, incidencia_id, data)
