"""
Router para Asistencia Diaria - Endpoints REST.
Incluye procesamiento manual de días específicos y consultas de resumen.
"""

from typing import List, Optional
from datetime import date
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.attendance.asistencia_diaria import services
from app.features.attendance.asistencia_diaria.schemas import (
    AsistenciaDiariaCreate, AsistenciaDiariaUpdate,
    AsistenciaDiariaResponse, AsistenciaDiariaConDetalles,
    ResultadoProcesamiento, ResumenAsistenciaMensual
)

router = APIRouter(
    prefix="/asistencia",
    tags=["Asistencia Diaria"]
)


# ============================================================
# CONSULTAS DE ASISTENCIA
# ============================================================

@router.get(
    "/empleado/{id_empleado}",
    response_model=List[AsistenciaDiariaResponse],
    summary="Obtener asistencias de un empleado",
    description="Retorna asistencias de un empleado con filtros opcionales de fecha y tipo de día"
)
def get_asistencias_empleado(
    id_empleado: int = Path(..., gt=0, description="ID del empleado"),
    fecha_desde: Optional[date] = Query(None, description="Fecha desde (inclusive)"),
    fecha_hasta: Optional[date] = Query(None, description="Fecha hasta (inclusive)"),
    tipo_dia: Optional[str] = Query(
        None,
        pattern="^(presente|ausente|feriado|permiso_parcial|presente_exento|licencia_medica|descanso)$",
        description="Filtrar por tipo de día"
    ),
    skip: int = Query(0, ge=0, description="Registros a saltar"),
    limit: int = Query(100, ge=1, le=500, description="Límite de registros"),
    db: Session = Depends(get_db)
):
    """
    Obtiene las asistencias de un empleado con filtros opcionales.
    
    Ejemplos:
    - `/asistencia/empleado/5` - Todas las asistencias del empleado 5
    - `/asistencia/empleado/5?fecha_desde=2026-01-01&fecha_hasta=2026-01-31` - Enero 2026
    - `/asistencia/empleado/5?tipo_dia=ausente` - Solo ausencias
    """
    asistencias = services.get_asistencia_by_empleado(
        db=db,
        id_empleado=id_empleado,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        tipo_dia=tipo_dia,
        skip=skip,
        limit=limit
    )
    
    return asistencias


@router.get(
    "/{asistencia_id}",
    response_model=AsistenciaDiariaResponse,
    summary="Obtener asistencia por ID",
    description="Retorna una asistencia específica con todos sus detalles"
)
def get_asistencia(
    asistencia_id: int = Path(..., gt=0, description="ID de la asistencia"),
    db: Session = Depends(get_db)
):
    """Obtiene una asistencia específica por su ID."""
    asistencia = services.get_asistencia_by_id(db, asistencia_id)
    
    if not asistencia:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asistencia con ID {asistencia_id} no encontrada"
        )
    
    return asistencia


# ============================================================
# CREAR/ACTUALIZAR ASISTENCIA MANUAL
# ============================================================

@router.post(
    "/",
    response_model=AsistenciaDiariaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear registro de asistencia manual",
    description="Crea manualmente un registro de asistencia (correcciones RRHH)"
)
def create_asistencia_manual(
    data: AsistenciaDiariaCreate,
    db: Session = Depends(get_db)
):
    """
    Crea un registro de asistencia manualmente.
    
    **Uso típico:** Correcciones de RRHH cuando el worker automático falló
    o cuando se necesita crear un registro especial.
    
    **Validaciones:**
    - El empleado debe existir
    - No puede existir registro previo para el mismo empleado y fecha
    """
    return services.create_asistencia(db, data)


@router.put(
    "/{asistencia_id}",
    response_model=AsistenciaDiariaResponse,
    summary="Actualizar registro de asistencia",
    description="Actualiza un registro de asistencia existente (actualización parcial)"
)
def update_asistencia(
    asistencia_id: int = Path(..., gt=0, description="ID de la asistencia"),
    data: AsistenciaDiariaUpdate = ...,
    db: Session = Depends(get_db)
):
    """
    Actualiza un registro de asistencia existente.
    
    Solo se actualizan los campos proporcionados (actualización parcial).
    Los campos omitidos mantienen su valor actual.
    """
    return services.update_asistencia(db, asistencia_id, data)


@router.delete(
    "/{asistencia_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar registro de asistencia",
    description="Elimina un registro de asistencia (HARD DELETE - usar con precaución)"
)
def delete_asistencia(
    asistencia_id: int = Path(..., gt=0, description="ID de la asistencia"),
    db: Session = Depends(get_db)
):
    """
    Elimina un registro de asistencia (HARD DELETE).
    
    **⚠️ PRECAUCIÓN:** Esta es una eliminación permanente.
    Para correcciones, preferir usar PUT para actualizar.
    """
    services.delete_asistencia(db, asistencia_id)
    return None


# ============================================================
# PROCESAMIENTO AUTOMÁTICO
# ============================================================

@router.post(
    "/procesar-dia",
    response_model=ResultadoProcesamiento,
    status_code=status.HTTP_200_OK,
    summary="Procesar asistencia de un día específico",
    description="Procesa manualmente la asistencia de todos los empleados para una fecha"
)
def procesar_dia_manual(
    fecha: date = Query(..., description="Fecha a procesar (formato YYYY-MM-DD)"),
    id_empleado: Optional[int] = Query(
        None,
        gt=0,
        description="Procesar solo este empleado (opcional). Si se omite, procesa todos."
    ),
    db: Session = Depends(get_db)
):
    """
    Procesa la asistencia de un día específico.
    
    **Uso típico:**
    - Reprocesar un día cuando hubo errores
    - Procesar días pasados que no se calcularon
    - Forzar recálculo después de corregir marcaciones
    
    **Opciones:**
    - Sin `id_empleado`: Procesa TODOS los empleados activos
    - Con `id_empleado`: Procesa solo ese empleado
    
    **Respuesta:**
    - Estadísticas de procesamiento (éxitos, errores, skipped)
    - Lista de errores con detalles
    """
    if id_empleado:
        # Procesar solo un empleado
        try:
            asistencia = services.calcular_asistencia_dia(db, id_empleado, fecha)
            return ResultadoProcesamiento(
                fecha=fecha,
                empleados_procesados=1,
                empleados_con_error=0,
                empleados_skipped=0,
                errores=[]
            )
        except HTTPException as e:
            return ResultadoProcesamiento(
                fecha=fecha,
                empleados_procesados=0,
                empleados_con_error=1,
                empleados_skipped=1,
                errores=[f"Empleado {id_empleado}: {e.detail}"]
            )
    else:
        # Procesar todos los empleados
        return services.procesar_asistencia_masiva(db, fecha)


@router.post(
    "/recalcular/{id_empleado}",
    response_model=AsistenciaDiariaResponse,
    summary="Recalcular asistencia de un empleado en una fecha",
    description="Recalcula la asistencia de un empleado para una fecha específica"
)
def recalcular_asistencia_empleado(
    id_empleado: int = Path(..., gt=0, description="ID del empleado"),
    fecha: date = Query(..., description="Fecha a recalcular (formato YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Recalcula la asistencia de un empleado en una fecha específica.
    
    **Uso típico:**
    - Después de corregir marcaciones
    - Después de asignar nuevo horario retroactivo
    - Después de aprobar una justificación
    
    Si ya existe un registro, lo actualiza.
    Si no existe, lo crea.
    """
    return services.calcular_asistencia_dia(db, id_empleado, fecha)


# ============================================================
# RESÚMENES Y REPORTES
# ============================================================

@router.get(
    "/resumen-mensual/{id_empleado}/{anio}/{mes}",
    response_model=ResumenAsistenciaMensual,
    summary="Resumen mensual de asistencia",
    description="Retorna resumen mensual de asistencia de un empleado (basado en vista v_asistencia_mensual)"
)
def get_resumen_mensual(
    id_empleado: int = Path(..., gt=0, description="ID del empleado"),
    anio: int = Path(..., ge=2020, le=2100, description="Año (ej: 2026)"),
    mes: int = Path(..., ge=1, le=12, description="Mes (1-12)"),
    db: Session = Depends(get_db)
):
    """
    Obtiene el resumen mensual de asistencia de un empleado.
    
    **Datos incluidos:**
    - Total de días registrados
    - Conteo por tipo de día (presente, ausente, feriado, etc.)
    - Total de minutos de retraso
    - Total de minutos trabajados
    - Total de horas extra
    - Días trabajados en feriados
    
    **Nota:** Este endpoint consulta la vista `v_asistencia_mensual`
    que se crea en la migración de Semana 6.
    """
    resumen = services.get_resumen_mensual_desde_vista(db, id_empleado, anio, mes)
    if not resumen:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No existe resumen mensual para los parámetros solicitados"
        )
    return resumen
