"""
Servicios de negocio para Vacacion y DetalleVacacion.
CRUD completo con cálculo de saldo y gestión del ciclo de vida de solicitudes.
"""

from datetime import date
from typing import List, Optional
from decimal import Decimal
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.features.attendance.vacaciones.models import (
    Vacacion,
    DetalleVacacion,
    TipoVacacionEnum,
    EstadoDetalleVacacionEnum
)
from app.features.attendance.vacaciones.schemas import (
    VacacionCreate,
    VacacionUpdate,
    DetalleVacacionCreate,
    DetalleVacacionUpdate,
    CambiarEstadoRequest
)


# ===== SERVICIOS PARA VACACION =====

def crear_vacacion(db: Session, data: VacacionCreate) -> Vacacion:
    """
    Crea un nuevo registro de vacación anual.
    Valida que no exista un registro para el mismo empleado y gestión.
    """
    # Verificar duplicados
    existente = db.query(Vacacion).filter(
        Vacacion.id_empleado == data.id_empleado,
        Vacacion.gestion == data.gestion,
    ).first()

    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un registro de vacación para el empleado {data.id_empleado} en la gestión {data.gestion}"
        )

    # Crear el registro de vacación
    nueva_vacacion = Vacacion(
        id_empleado=data.id_empleado,
        gestion=data.gestion,
        horas_correspondientes=data.horas_correspondientes,
        horas_goce_haber=data.horas_goce_haber or Decimal("0.0"),
        horas_sin_goce_haber=data.horas_sin_goce_haber or Decimal("0.0"),
        horas_tomadas=Decimal("0.0"),
        observacion=data.observacion
    )

    db.add(nueva_vacacion)
    db.commit()
    db.refresh(nueva_vacacion)

    return nueva_vacacion


def obtener_vacacion(db: Session, id: int) -> Vacacion:
    """Obtiene un registro de vacación por ID."""
    vacacion = db.query(Vacacion).filter(Vacacion.id == id).first()

    if not vacacion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Vacación con ID {id} no encontrada"
        )

    return vacacion


def obtener_vacacion_por_empleado_gestion(
    db: Session,
    id_empleado: int,
    gestion: int
) -> Optional[Vacacion]:
    """Obtiene el registro de vacación de un empleado para una gestión específica."""
    return db.query(Vacacion).filter(
        Vacacion.id_empleado == id_empleado,
        Vacacion.gestion == gestion,
    ).first()


def listar_vacaciones(
    db: Session,
    id_empleado: Optional[int] = None,
    gestion: Optional[int] = None,
    skip: int = 0,
    limit: int = 100
) -> List[Vacacion]:
    """
    Lista registros de vacación con filtros opcionales.

    Args:
        id_empleado: Filtrar por empleado
        gestion: Filtrar por gestión/año
    """
    query = db.query(Vacacion)

    if id_empleado is not None:
        query = query.filter(Vacacion.id_empleado == id_empleado)

    if gestion is not None:
        query = query.filter(Vacacion.gestion == gestion)

    return query.order_by(Vacacion.gestion.desc(), Vacacion.id_empleado).offset(skip).limit(limit).all()


def actualizar_vacacion(
    db: Session,
    id: int,
    data: VacacionUpdate
) -> Vacacion:
    """
    Actualiza un registro de vacación existente.
    Solo permite actualizar horas_goce_haber, horas_sin_goce_haber y observacion.
    """
    vacacion = obtener_vacacion(db, id)

    # Aplicar cambios
    if data.horas_goce_haber is not None:
        vacacion.horas_goce_haber = data.horas_goce_haber
    if data.horas_sin_goce_haber is not None:
        vacacion.horas_sin_goce_haber = data.horas_sin_goce_haber
    if data.observacion is not None:
        vacacion.observacion = data.observacion

    db.commit()
    db.refresh(vacacion)

    return vacacion


def eliminar_vacacion(db: Session, id: int) -> None:
    """
    Elimina un registro de vacación.
    El CASCADE eliminará automáticamente todos los detalles asociados.
    """
    vacacion = obtener_vacacion(db, id)

    db.delete(vacacion)
    db.commit()


def incrementar_horas_correspondientes(
    db: Session,
    id_empleado: int,
    gestion: int,
    horas_adicionales: Decimal
) -> Vacacion:
    """
    Incrementa las horas correspondientes de un empleado en una gestión.
    Usado cuando se trabaja un feriado (+8h) o se transfiere beneficio cumpleaños (+4h).
    """
    vacacion = obtener_vacacion_por_empleado_gestion(db, id_empleado, gestion)

    if not vacacion:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe registro de vacación para empleado {id_empleado} en gestión {gestion}"
        )

    vacacion.horas_correspondientes += horas_adicionales

    db.commit()
    db.refresh(vacacion)

    return vacacion


def incrementar_horas(db: Session, id_vacacion: int, horas: Decimal, tipo: str = "goce_haber") -> Vacacion:
    """Incrementa horas en un registro de vacación existente."""
    vacacion = obtener_vacacion(db, id_vacacion)

    vacacion.horas_correspondientes += horas
    if tipo == "sin_goce_haber":
        vacacion.horas_sin_goce_haber += horas
    else:
        vacacion.horas_goce_haber += horas

    db.commit()
    db.refresh(vacacion)
    return vacacion


# ===== SERVICIOS PARA DETALLE_VACACION =====

def crear_detalle_vacacion(
    db: Session,
    id_vacacion: int,
    data: DetalleVacacionCreate
) -> DetalleVacacion:
    """
    Crea una nueva solicitud de vacación.

    Valida:
    - Que el registro de vacación exista
    - Que haya suficiente saldo disponible
    """
    # Verificar que la vacación exista
    vacacion = obtener_vacacion(db, id_vacacion)

    # Validar saldo disponible
    horas_pendientes = vacacion.horas_pendientes

    if data.horas_habiles > horas_pendientes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Saldo insuficiente. Horas solicitadas: {data.horas_habiles}, Horas disponibles: {horas_pendientes}"
        )

    # Validar que si es licencia_accidente, tenga id_justificacion
    if data.tipo_vacacion == TipoVacacionEnum.licencia_accidente and not data.id_justificacion:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tipo_vacacion='licencia_accidente' requiere id_justificacion"
        )

    # Crear el detalle
    nuevo_detalle = DetalleVacacion(
        id_vacacion=id_vacacion,
        id_justificacion=data.id_justificacion,
        fecha_inicio=data.fecha_inicio,
        fecha_fin=data.fecha_fin,
        horas_habiles=data.horas_habiles,
        tipo_vacacion=data.tipo_vacacion,
        estado=EstadoDetalleVacacionEnum.solicitado,
        observacion=data.observacion
    )

    db.add(nuevo_detalle)
    db.commit()
    db.refresh(nuevo_detalle)

    return nuevo_detalle


def obtener_detalle_vacacion(db: Session, id: int) -> DetalleVacacion:
    """Obtiene un detalle de vacación por ID."""
    detalle = db.query(DetalleVacacion).filter(DetalleVacacion.id == id).first()

    if not detalle:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Detalle de vacación con ID {id} no encontrado"
        )

    return detalle


def listar_detalles_vacacion(
    db: Session,
    id_vacacion: Optional[int] = None,
    estado: Optional[EstadoDetalleVacacionEnum] = None,
    tipo_vacacion: Optional[TipoVacacionEnum] = None,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    skip: int = 0,
    limit: int = 100
) -> List[DetalleVacacion]:
    """
    Lista detalles de vacación con filtros opcionales.

    Args:
        id_vacacion: Filtrar por registro de vacación
        estado: Filtrar por estado
        tipo_vacacion: Filtrar por tipo
        fecha_desde: Filtrar por fecha_inicio >= fecha_desde
        fecha_hasta: Filtrar por fecha_fin <= fecha_hasta
    """
    query = db.query(DetalleVacacion)

    if id_vacacion is not None:
        query = query.filter(DetalleVacacion.id_vacacion == id_vacacion)

    if estado is not None:
        query = query.filter(DetalleVacacion.estado == estado)

    if tipo_vacacion is not None:
        query = query.filter(DetalleVacacion.tipo_vacacion == tipo_vacacion)

    if fecha_desde is not None:
        query = query.filter(DetalleVacacion.fecha_inicio >= fecha_desde)

    if fecha_hasta is not None:
        query = query.filter(DetalleVacacion.fecha_fin <= fecha_hasta)

    return query.order_by(DetalleVacacion.fecha_inicio.desc()).offset(skip).limit(limit).all()


def listar_detalles_por_vacacion(
    db: Session,
    id_vacacion: int,
    estado: Optional[EstadoDetalleVacacionEnum] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[DetalleVacacion]:
    """Lista detalles filtrados por id_vacacion."""
    return listar_detalles_vacacion(
        db,
        id_vacacion=id_vacacion,
        estado=estado,
        skip=skip,
        limit=limit,
    )


def listar_todos_detalles(
    db: Session,
    id_empleado: Optional[int] = None,
    estado: Optional[EstadoDetalleVacacionEnum] = None,
    tipo_vacacion: Optional[TipoVacacionEnum] = None,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    skip: int = 0,
    limit: int = 100,
) -> List[DetalleVacacion]:
    """Lista detalles con filtro opcional por empleado."""
    query = db.query(DetalleVacacion).join(Vacacion, DetalleVacacion.id_vacacion == Vacacion.id)

    if id_empleado is not None:
        query = query.filter(Vacacion.id_empleado == id_empleado)
    if estado is not None:
        query = query.filter(DetalleVacacion.estado == estado)
    if tipo_vacacion is not None:
        query = query.filter(DetalleVacacion.tipo_vacacion == tipo_vacacion)
    if fecha_desde is not None:
        query = query.filter(DetalleVacacion.fecha_inicio >= fecha_desde)
    if fecha_hasta is not None:
        query = query.filter(DetalleVacacion.fecha_fin <= fecha_hasta)

    return query.order_by(DetalleVacacion.fecha_inicio.desc()).offset(skip).limit(limit).all()


def listar_detalles_pendientes(
    db: Session,
    skip: int = 0,
    limit: int = 100
) -> List[DetalleVacacion]:
    """
    Lista todas las solicitudes pendientes de aprobación.
    Útil para supervisores y RRHH.
    """
    return db.query(DetalleVacacion).filter(
        DetalleVacacion.estado == EstadoDetalleVacacionEnum.solicitado
    ).order_by(DetalleVacacion.fecha_inicio.asc()).offset(skip).limit(limit).all()


def actualizar_detalle_vacacion(
    db: Session,
    id: int,
    data: DetalleVacacionUpdate
) -> DetalleVacacion:
    """
    Actualiza un detalle de vacación existente.
    Solo se puede actualizar si está en estado 'solicitado'.
    """
    detalle = obtener_detalle_vacacion(db, id)

    if detalle.estado != EstadoDetalleVacacionEnum.solicitado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede actualizar un detalle en estado '{detalle.estado}'. Solo se permite actualizar en estado 'solicitado'"
        )

    # Aplicar cambios
    if data.fecha_inicio is not None:
        detalle.fecha_inicio = data.fecha_inicio
    if data.fecha_fin is not None:
        detalle.fecha_fin = data.fecha_fin
    if data.horas_habiles is not None:
        # Validar saldo disponible con las nuevas horas
        vacacion = obtener_vacacion(db, detalle.id_vacacion)
        horas_pendientes = vacacion.horas_pendientes

        if data.horas_habiles > horas_pendientes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Saldo insuficiente. Horas solicitadas: {data.horas_habiles}, Horas disponibles: {horas_pendientes}"
            )

        detalle.horas_habiles = data.horas_habiles
    if data.tipo_vacacion is not None:
        detalle.tipo_vacacion = data.tipo_vacacion
    if data.observacion is not None:
        detalle.observacion = data.observacion

    # Validar fechas
    if detalle.fecha_fin < detalle.fecha_inicio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fecha_fin debe ser mayor o igual a fecha_inicio"
        )

    db.commit()
    db.refresh(detalle)

    return detalle


def eliminar_detalle_vacacion(db: Session, id: int) -> None:
    """
    Elimina un detalle de vacación.
    Solo se puede eliminar si está en estado 'solicitado'.
    """
    detalle = obtener_detalle_vacacion(db, id)

    if detalle.estado != EstadoDetalleVacacionEnum.solicitado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede eliminar un detalle en estado '{detalle.estado}'. Solo se permite eliminar en estado 'solicitado'"
        )

    db.delete(detalle)
    db.commit()


def cambiar_estado_detalle(
    db: Session,
    id: int,
    data: CambiarEstadoRequest
) -> DetalleVacacion:
    """
    Cambia el estado de una solicitud de vacación.

    Flujo de estados permitidos:
    - solicitado -> aprobado (requiere id_aprobado_por)
    - solicitado -> rechazado (requiere id_aprobado_por)
    - solicitado -> cancelado
    - aprobado -> tomado (actualiza vacacion.horas_tomadas)
    - aprobado -> cancelado

    Lógica de negocio:
    1. Al cambiar a 'aprobado': valida saldo disponible
    2. Al cambiar a 'tomado': descuenta horas de vacacion.horas_tomadas y del saldo correspondiente
    3. Al cambiar a 'rechazado' o 'cancelado': libera la reserva
    """
    detalle = obtener_detalle_vacacion(db, id)
    estado_anterior = detalle.estado
    nuevo_estado = data.nuevo_estado

    # Validar transiciones de estado permitidas
    transiciones_validas = {
        EstadoDetalleVacacionEnum.solicitado: [
            EstadoDetalleVacacionEnum.aprobado,
            EstadoDetalleVacacionEnum.rechazado,
            EstadoDetalleVacacionEnum.cancelado
        ],
        EstadoDetalleVacacionEnum.aprobado: [
            EstadoDetalleVacacionEnum.tomado,
            EstadoDetalleVacacionEnum.cancelado
        ]
    }

    if estado_anterior not in transiciones_validas:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No se puede cambiar el estado desde '{estado_anterior}'"
        )

    if nuevo_estado not in transiciones_validas[estado_anterior]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transición de estado no permitida: '{estado_anterior}' -> '{nuevo_estado}'"
        )

    # Validar id_aprobado_por para estados que lo requieren
    if nuevo_estado in [EstadoDetalleVacacionEnum.aprobado, EstadoDetalleVacacionEnum.rechazado]:
        if not data.id_aprobado_por:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"id_aprobado_por es requerido para cambiar a estado '{nuevo_estado}'"
            )

    # Obtener la vacación asociada
    vacacion = obtener_vacacion(db, detalle.id_vacacion)

    # Validar saldo disponible al aprobar
    if nuevo_estado == EstadoDetalleVacacionEnum.aprobado:
        horas_pendientes = vacacion.horas_pendientes

        if detalle.horas_habiles > horas_pendientes:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Saldo insuficiente. Horas solicitadas: {detalle.horas_habiles}, Horas disponibles: {horas_pendientes}"
            )

    # Lógica especial al cambiar a 'tomado'
    if nuevo_estado == EstadoDetalleVacacionEnum.tomado:
        # Incrementar horas_tomadas
        vacacion.horas_tomadas += detalle.horas_habiles

        # Descontar del saldo correspondiente según tipo_vacacion
        if detalle.tipo_vacacion == TipoVacacionEnum.goce_de_haber:
            vacacion.horas_goce_haber -= detalle.horas_habiles
        elif detalle.tipo_vacacion == TipoVacacionEnum.sin_goce_de_haber:
            vacacion.horas_sin_goce_haber -= detalle.horas_habiles
        # Para licencia_accidente, también descuenta de goce_haber
        elif detalle.tipo_vacacion == TipoVacacionEnum.licencia_accidente:
            vacacion.horas_goce_haber -= detalle.horas_habiles

        # Validar que no queden saldos negativos
        if vacacion.horas_goce_haber < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Operación resultaría en horas_goce_haber negativas"
            )
        if vacacion.horas_sin_goce_haber < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Operación resultaría en horas_sin_goce_haber negativas"
            )

    # Aplicar el cambio de estado
    detalle.estado = nuevo_estado

    if data.id_aprobado_por:
        detalle.id_aprobado_por = data.id_aprobado_por

    # Agregar observación
    if data.observacion:
        if detalle.observacion:
            detalle.observacion += f"\n---\n[{nuevo_estado}] {data.observacion}"
        else:
            detalle.observacion = f"[{nuevo_estado}] {data.observacion}"

    db.commit()
    db.refresh(detalle)
    db.refresh(vacacion)

    return detalle
