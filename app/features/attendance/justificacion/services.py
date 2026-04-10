"""
Servicios de negocio para JustificacionAusencia.
CRUD completo con cálculo automático de horas y flujo de aprobación.
"""

from datetime import date, datetime
from typing import List, Optional
from decimal import Decimal
from sqlalchemy import and_
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.features.attendance.justificacion.models import (
    JustificacionAusencia,
    TipoJustificacionEnum,
    EstadoAprobacionEnum
)
from app.features.attendance.justificacion.schemas import (
    JustificacionAusenciaCreate,
    JustificacionAusenciaUpdate,
    AprobacionRequest
)


def calcular_horas_permiso(hora_inicio, hora_fin) -> Decimal:
    """
    Calcula las horas entre dos times.
    Retorna un Decimal con 1 decimal de precisión.
    """
    # Convertir time a datetime para hacer la resta
    fecha_ref = datetime.now().date()
    dt_inicio = datetime.combine(fecha_ref, hora_inicio)
    dt_fin = datetime.combine(fecha_ref, hora_fin)

    diferencia = dt_fin - dt_inicio
    horas = Decimal(str(diferencia.total_seconds() / 3600))
    return round(horas, 1)


def crear_justificacion(
    db: Session,
    data: JustificacionAusenciaCreate
) -> JustificacionAusencia:
    """
    Crea una nueva justificación de ausencia.

    Si es_por_horas=TRUE, calcula automáticamente total_horas_permiso.
    """
    # Calcular total_horas_permiso si es por horas
    total_horas = None
    if data.es_por_horas:
        if not data.hora_inicio_permiso or not data.hora_fin_permiso:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="hora_inicio_permiso y hora_fin_permiso son obligatorios para permisos por horas"
            )
        total_horas = calcular_horas_permiso(data.hora_inicio_permiso, data.hora_fin_permiso)

    # Crear la justificación
    nueva_justificacion = JustificacionAusencia(
        id_empleado=data.id_empleado,
        fecha_inicio=data.fecha_inicio,
        fecha_fin=data.fecha_fin,
        tipo_justificacion=data.tipo_justificacion,
        tipo_permiso=data.tipo_permiso,
        es_por_horas=data.es_por_horas,
        hora_inicio_permiso=data.hora_inicio_permiso,
        hora_fin_permiso=data.hora_fin_permiso,
        total_horas_permiso=total_horas,
        descripcion=data.descripcion,
        documento_url=data.documento_url,
        estado_aprobacion=EstadoAprobacionEnum.pendiente
    )

    db.add(nueva_justificacion)
    db.commit()
    db.refresh(nueva_justificacion)

    return nueva_justificacion


def obtener_justificacion(db: Session, id: int) -> JustificacionAusencia:
    """Obtiene una justificación por ID."""
    justificacion = db.query(JustificacionAusencia).filter(JustificacionAusencia.id == id).first()

    if not justificacion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Justificación con ID {id} no encontrada"
        )

    return justificacion


def listar_justificaciones(
    db: Session,
    id_empleado: Optional[int] = None,
    tipo_justificacion: Optional[TipoJustificacionEnum] = None,
    estado_aprobacion: Optional[EstadoAprobacionEnum] = None,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    skip: int = 0,
    limit: int = 100
) -> List[JustificacionAusencia]:
    """Lista justificaciones con filtros opcionales."""
    query = db.query(JustificacionAusencia)

    if id_empleado:
        query = query.filter(JustificacionAusencia.id_empleado == id_empleado)

    if tipo_justificacion:
        query = query.filter(JustificacionAusencia.tipo_justificacion == tipo_justificacion)

    if estado_aprobacion:
        query = query.filter(JustificacionAusencia.estado_aprobacion == estado_aprobacion)

    if fecha_desde:
        query = query.filter(JustificacionAusencia.fecha_inicio >= fecha_desde)

    if fecha_hasta:
        query = query.filter(JustificacionAusencia.fecha_fin <= fecha_hasta)

    return query.order_by(JustificacionAusencia.fecha_inicio.desc()).offset(skip).limit(limit).all()


def listar_pendientes_de_aprobacion(
    db: Session,
    skip: int = 0,
    limit: int = 100
) -> List[JustificacionAusencia]:
    """
    Lista todas las justificaciones pendientes de aprobación.
    Útil para supervisores y RRHH.
    """
    return db.query(JustificacionAusencia).filter(
        JustificacionAusencia.estado_aprobacion == EstadoAprobacionEnum.pendiente
    ).order_by(JustificacionAusencia.fecha_inicio.asc()).offset(skip).limit(limit).all()


def aprobar_o_rechazar(
    db: Session,
    id: int,
    data: AprobacionRequest
) -> JustificacionAusencia:
    """
    Aprueba o rechaza una justificación.

    Solo se puede cambiar el estado si está en 'pendiente'.
    """
    justificacion = obtener_justificacion(db, id)

    if justificacion.estado_aprobacion != EstadoAprobacionEnum.pendiente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"La justificación ya fue {justificacion.estado_aprobacion}"
        )

    if data.estado not in [EstadoAprobacionEnum.aprobado, EstadoAprobacionEnum.rechazado]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El estado debe ser 'aprobado' o 'rechazado'"
        )

    justificacion.estado_aprobacion = data.estado
    justificacion.id_aprobado_por = data.id_aprobado_por
    justificacion.fecha_aprobacion = datetime.now()

    if data.observacion:
        # Agregar observación del aprobador a la descripción
        if justificacion.descripcion:
            justificacion.descripcion += f"\n---\nObservación del aprobador: {data.observacion}"
        else:
            justificacion.descripcion = f"Observación del aprobador: {data.observacion}"

    db.commit()
    db.refresh(justificacion)

    return justificacion


def actualizar_justificacion(
    db: Session,
    id: int,
    data: JustificacionAusenciaUpdate
) -> JustificacionAusencia:
    """
    Actualiza una justificación existente.

    No se puede actualizar si ya fue aprobada o rechazada.
    """
    justificacion = obtener_justificacion(db, id)

    if justificacion.estado_aprobacion != EstadoAprobacionEnum.pendiente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede actualizar una justificación ya aprobada o rechazada"
        )

    # Aplicar cambios
    if data.id_empleado is not None:
        justificacion.id_empleado = data.id_empleado
    if data.fecha_inicio is not None:
        justificacion.fecha_inicio = data.fecha_inicio
    if data.fecha_fin is not None:
        justificacion.fecha_fin = data.fecha_fin
    if data.tipo_justificacion is not None:
        justificacion.tipo_justificacion = data.tipo_justificacion
    if data.tipo_permiso is not None:
        justificacion.tipo_permiso = data.tipo_permiso
    if data.es_por_horas is not None:
        justificacion.es_por_horas = data.es_por_horas
    if data.hora_inicio_permiso is not None:
        justificacion.hora_inicio_permiso = data.hora_inicio_permiso
    if data.hora_fin_permiso is not None:
        justificacion.hora_fin_permiso = data.hora_fin_permiso
    if data.descripcion is not None:
        justificacion.descripcion = data.descripcion
    if data.documento_url is not None:
        justificacion.documento_url = data.documento_url

    # Recalcular total_horas_permiso si cambió
    if justificacion.es_por_horas:
        if justificacion.hora_inicio_permiso and justificacion.hora_fin_permiso:
            justificacion.total_horas_permiso = calcular_horas_permiso(
                justificacion.hora_inicio_permiso,
                justificacion.hora_fin_permiso
            )
    else:
        justificacion.total_horas_permiso = None

    db.commit()
    db.refresh(justificacion)

    return justificacion


def eliminar_justificacion(db: Session, id: int) -> None:
    """
    Elimina una justificación.

    Solo se puede eliminar si está en estado 'pendiente'.
    """
    justificacion = obtener_justificacion(db, id)

    if justificacion.estado_aprobacion != EstadoAprobacionEnum.pendiente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede eliminar una justificación ya aprobada o rechazada"
        )

    db.delete(justificacion)
    db.commit()
