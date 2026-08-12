"""
Servicios de negocio para Vacacion y DetalleVacacion.
CRUD completo con cálculo de saldo y gestión del ciclo de vida de solicitudes.
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from sqlalchemy import and_, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload
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
    CambiarEstadoRequest,
    CalculoHorasHabilesResponse,
    DiaExcluido,
    MotivoExclusionEnum,
)
from app.features.employees.empleado.models import Empleado
from app.features.employees.horario.models import Horario, AsignacionHorario
from app.features.attendance.feriados.models import DiaFestivo, AmbitoFestivoEnum

# Se reutiliza el parser de días laborables de asistencia_diaria en vez de
# duplicarlo: ya maneja el JSON [1..7], los strings "L-V" / "L,MI,V" y el
# default lunes-viernes. asistencia_diaria NO importa vacaciones, así que este
# import no cierra ningún ciclo.
from app.features.attendance.asistencia_diaria.services import _parse_dias_laborables


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


def _resolver_campo_saldo(
    detalle: DetalleVacacion,
    cubrir_con_saldo_vacacional: bool
) -> Optional[str]:
    """
    Indica de qué campo de `vacacion` se descuentan las horas de un detalle al
    pasar a 'tomado', o None si el detalle no debe consumir saldo.

    `licencia_accidente` solo descuenta cuando RRHH y el empleado acordaron
    explícitamente cubrirla con el saldo vacacional. Sin esa confirmación la
    licencia se registra pero no consume vacaciones: antes se descontaba
    siempre, de forma automática y silenciosa.
    """
    if detalle.tipo_vacacion == TipoVacacionEnum.goce_de_haber:
        return "horas_goce_haber"

    if detalle.tipo_vacacion == TipoVacacionEnum.sin_goce_de_haber:
        return "horas_sin_goce_haber"

    if detalle.tipo_vacacion == TipoVacacionEnum.licencia_accidente:
        return "horas_goce_haber" if cubrir_con_saldo_vacacional else None

    return None


def _anexar_observacion(detalle: DetalleVacacion, estado: str, texto: str) -> None:
    """Agrega una línea a la observación del detalle, preservando el historial."""
    entrada = f"[{estado}] {texto}"

    if detalle.observacion:
        detalle.observacion += f"\n---\n{entrada}"
    else:
        detalle.observacion = entrada


def cambiar_estado_detalle(
    db: Session,
    id: int,
    data: CambiarEstadoRequest,
    id_aprobado_por: Optional[int] = None,
) -> DetalleVacacion:
    """
    Cambia el estado de una solicitud de vacación.

    id_aprobado_por es el id_empleado del usuario autenticado (resuelto en el
    router); puede venir en None si ese usuario no tiene empleado vinculado —
    la validación de abajo lo exige solo cuando el estado lo requiere.

    Flujo de estados permitidos:
    - solicitado -> aprobado (requiere id_aprobado_por)
    - solicitado -> rechazado (requiere id_aprobado_por)
    - solicitado -> cancelado
    - aprobado -> tomado (actualiza vacacion.horas_tomadas)
    - aprobado -> cancelado

    Lógica de negocio:
    1. Al cambiar a 'aprobado': valida saldo disponible
    2. Al cambiar a 'tomado': descuenta horas de vacacion.horas_tomadas y del
       saldo correspondiente, SALVO que sea una licencia por accidente sin
       `cubrir_con_saldo_vacacional=true` (ver `_resolver_campo_saldo`)
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
        if not id_aprobado_por:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Tu usuario no está vinculado a un empleado; no puede cambiar el estado a "
                    f"'{nuevo_estado}'"
                )
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
    nota_automatica = None

    if nuevo_estado == EstadoDetalleVacacionEnum.tomado:
        campo_saldo = _resolver_campo_saldo(detalle, data.cubrir_con_saldo_vacacional)

        if campo_saldo is None:
            # licencia_accidente sin confirmación explícita: la licencia por
            # accidente NO es una vacación, así que no consume saldo. Se deja
            # traza en la observación del detalle para que quede auditable.
            nota_automatica = (
                "Licencia por accidente registrada sin descontar saldo vacacional "
                "(cubrir_con_saldo_vacacional=false)"
            )
        else:
            # Validar ANTES de mutar: así un rechazo deja la vacación intacta,
            # sin necesidad de rollback ni de saldos negativos transitorios.
            saldo_actual = getattr(vacacion, campo_saldo)

            if detalle.horas_habiles > saldo_actual:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Operación resultaría en {campo_saldo} negativas. "
                        f"Horas solicitadas: {detalle.horas_habiles}, disponibles: {saldo_actual}"
                    )
                )

            # Tope global, distinto del chequeo de aprobación de más arriba:
            # aprobar no reserva nada (horas_tomadas solo se mueve aquí), así que
            # N solicitudes pueden aprobarse todas contra el mismo saldo y recién
            # chocarían al tomarse. Espeja el CHECK chk_vacacion_no_excede
            # (migración 3d9a17c4b8e2) para devolver un 400 legible en vez de un
            # IntegrityError de Postgres.
            horas_tomadas_resultantes = vacacion.horas_tomadas + detalle.horas_habiles

            if horas_tomadas_resultantes > vacacion.horas_correspondientes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Las horas tomadas excederían las horas correspondientes de la gestión. "
                        f"Tomadas: {vacacion.horas_tomadas}, solicitadas: {detalle.horas_habiles}, "
                        f"correspondientes: {vacacion.horas_correspondientes}"
                    )
                )

            vacacion.horas_tomadas += detalle.horas_habiles
            setattr(vacacion, campo_saldo, saldo_actual - detalle.horas_habiles)

    # Aplicar el cambio de estado
    detalle.estado = nuevo_estado

    if id_aprobado_por:
        detalle.id_aprobado_por = id_aprobado_por

    # Agregar observación
    if nota_automatica:
        _anexar_observacion(detalle, nuevo_estado, nota_automatica)

    if data.observacion:
        _anexar_observacion(detalle, nuevo_estado, data.observacion)

    db.commit()
    db.refresh(detalle)
    db.refresh(vacacion)

    return detalle


# ===== CÁLCULO DE HORAS HÁBILES DE UN RANGO =====

# Tope de seguridad: una solicitud de vacaciones nunca cubre más de una gestión.
MAX_DIAS_RANGO = 366

# Solo se usa cuando el horario no permite derivar la jornada (discontinuo sin
# hora_entrada/hora_salida y sin jornada_semanal_horas). Es el mismo valor que
# usa la vista rrhh.v_resumen_vacaciones como divisor horas -> días.
HORAS_JORNADA_FALLBACK = Decimal("8.0")

NOMBRE_DIA_SEMANA = [
    "Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"
]


def _horas_por_jornada(horario: Horario) -> Decimal:
    """
    Deriva las horas de una jornada completa. No hay columna de horas diarias en
    `horario`, así que se calcula en cascada:

    1. hora_salida - hora_entrada, si ambas están presentes
    2. jornada_semanal_horas / cantidad de días laborables
    3. HORAS_JORNADA_FALLBACK

    Un turno que cruza medianoche (salida <= entrada) daría un valor negativo o
    cero, así que cae al paso 2 en vez de restar horas del total.
    """
    if horario.hora_entrada is not None and horario.hora_salida is not None:
        inicio = datetime.combine(date.min, horario.hora_entrada)
        fin = datetime.combine(date.min, horario.hora_salida)
        segundos = (fin - inicio).total_seconds()

        if segundos > 0:
            return Decimal(str(round(segundos / 3600.0, 1)))

    dias_laborables = _parse_dias_laborables(horario.dias_laborables)

    if horario.jornada_semanal_horas is not None and dias_laborables:
        semanales = float(horario.jornada_semanal_horas)
        return Decimal(str(round(semanales / len(dias_laborables), 1)))

    return HORAS_JORNADA_FALLBACK


def _feriados_en_rango(
    db: Session,
    fecha_inicio: date,
    fecha_fin: date,
    codigo_departamento: Optional[str]
) -> Dict[date, str]:
    """
    Trae los feriados del rango en UNA sola query, en vez de una por día.

    Match por fecha EXACTA (con año), igual que `_es_feriado` de
    asistencia_diaria — NO por día+mes como `obtener_feriados_aplicables`. El
    cálculo tiene que coincidir con lo que `calcular_asistencia_dia` va a
    registrar de verdad, no con el calendario recurrente de la UI.

    El feriado departamental se resuelve por `empleado.complemento_dep`, que es
    el departamento de emisión del CI, no la unidad organizacional.
    """
    filas = db.query(DiaFestivo).filter(
        DiaFestivo.fecha >= fecha_inicio,
        DiaFestivo.fecha <= fecha_fin,
        DiaFestivo.activo.is_(True),
        or_(
            DiaFestivo.ambito == AmbitoFestivoEnum.NACIONAL,
            and_(
                DiaFestivo.ambito == AmbitoFestivoEnum.DEPARTAMENTAL,
                DiaFestivo.codigo_departamento == codigo_departamento,
            ),
        ),
    ).all()

    return {fila.fecha: fila.descripcion for fila in filas}


def _asignaciones_en_rango(
    db: Session,
    id_empleado: int,
    fecha_inicio: date,
    fecha_fin: date
) -> List[AsignacionHorario]:
    """
    Trae en UNA query todas las asignaciones de horario que solapan el rango.

    Filtra `es_activo == True` y ordena por `fecha_inicio DESC`: es la regla de
    "horario vigente determinístico" del resto de attendance/, necesaria porque
    `delete_asignacion_horario` es un soft-delete que apaga `es_activo` sin
    tocar `fecha_fin`.
    """
    return db.query(AsignacionHorario).options(
        joinedload(AsignacionHorario.horario)
    ).filter(
        AsignacionHorario.id_empleado == id_empleado,
        AsignacionHorario.es_activo.is_(True),
        AsignacionHorario.fecha_inicio <= fecha_fin,
        or_(
            AsignacionHorario.fecha_fin.is_(None),
            AsignacionHorario.fecha_fin >= fecha_inicio,
        ),
    ).order_by(AsignacionHorario.fecha_inicio.desc()).all()


def _asignacion_vigente(
    asignaciones: List[AsignacionHorario],
    fecha: date
) -> Optional[AsignacionHorario]:
    """
    Devuelve la asignación vigente en una fecha concreta. Asume la lista ya
    ordenada por `fecha_inicio DESC`, así que la primera que contiene la fecha
    es la más reciente: la asignación puede cambiar dentro del rango y hay que
    resolverla por fecha, no una sola vez para todo el rango.
    """
    for asignacion in asignaciones:
        empezo = asignacion.fecha_inicio <= fecha
        sigue = asignacion.fecha_fin is None or asignacion.fecha_fin >= fecha

        if empezo and sigue:
            return asignacion

    return None


def calcular_horas_habiles_rango(
    db: Session,
    id_empleado: int,
    fecha_inicio: date,
    fecha_fin: date
) -> CalculoHorasHabilesResponse:
    """
    Calcula las horas hábiles que consume un rango de fechas para un empleado.

    Existe para que el frontend pueda mostrar el costo real de una solicitud
    ANTES de crearla: `detalle_vacacion.horas_habiles` es un dato que envía el
    cliente y hasta ahora no había forma de derivarlo.

    Un día aporta horas solo si tiene horario vigente, cae en un día laborable
    de ese horario y no es feriado. La precedencia es la misma que en
    `calcular_asistencia_dia`: **descanso gana sobre feriado**, así que un
    feriado que cae en sábado no se cuenta ni se reporta dos veces.
    """
    if fecha_fin < fecha_inicio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fecha_fin debe ser mayor o igual a fecha_inicio"
        )

    dias_calendario = (fecha_fin - fecha_inicio).days + 1

    if dias_calendario > MAX_DIAS_RANGO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"El rango abarca {dias_calendario} días y el máximo es "
                f"{MAX_DIAS_RANGO}. Una solicitud de vacaciones no cubre más de una gestión."
            )
        )

    empleado = db.query(Empleado).filter(Empleado.id == id_empleado).first()

    if not empleado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Empleado con ID {id_empleado} no encontrado"
        )

    feriados = _feriados_en_rango(db, fecha_inicio, fecha_fin, empleado.complemento_dep)
    asignaciones = _asignaciones_en_rango(db, id_empleado, fecha_inicio, fecha_fin)

    # Cache por id de horario: _parse_dias_laborables y _horas_por_jornada se
    # resolverían una vez por día del rango sin esto.
    cache_horario: Dict[int, Tuple[List[int], Decimal]] = {}

    dias_excluidos: List[DiaExcluido] = []
    dias_habiles = 0
    horas_habiles = Decimal("0.0")
    horas_por_jornada: Optional[Decimal] = None
    jornadas_vistas = set()

    for offset in range(dias_calendario):
        fecha = fecha_inicio + timedelta(days=offset)
        asignacion = _asignacion_vigente(asignaciones, fecha)

        if asignacion is None or asignacion.horario is None:
            dias_excluidos.append(DiaExcluido(
                fecha=fecha,
                motivo=MotivoExclusionEnum.sin_horario,
                etiqueta="Sin horario asignado",
            ))
            continue

        horario = asignacion.horario

        if horario.id not in cache_horario:
            cache_horario[horario.id] = (
                _parse_dias_laborables(horario.dias_laborables),
                _horas_por_jornada(horario),
            )

        dias_laborables, horas_jornada = cache_horario[horario.id]

        if horas_por_jornada is None:
            horas_por_jornada = horas_jornada
        jornadas_vistas.add(horas_jornada)

        # PASO 1: descanso. Va antes que el feriado a propósito.
        if fecha.weekday() not in dias_laborables:
            dias_excluidos.append(DiaExcluido(
                fecha=fecha,
                motivo=MotivoExclusionEnum.descanso,
                etiqueta=NOMBRE_DIA_SEMANA[fecha.weekday()],
            ))
            continue

        # PASO 2: feriado
        descripcion_feriado = feriados.get(fecha)

        if descripcion_feriado:
            dias_excluidos.append(DiaExcluido(
                fecha=fecha,
                motivo=MotivoExclusionEnum.feriado,
                etiqueta=descripcion_feriado,
            ))
            continue

        dias_habiles += 1
        horas_habiles += horas_jornada

    # Si NINGUNA fecha del rango tuvo horario vigente, el problema no es el
    # rango: es que al empleado le falta la asignación. Se corta con un mensaje
    # accionable en vez de devolver 0 horas, que se leería como "no hay días
    # hábiles" y mandaría a RRHH a revisar el calendario equivocado.
    if horas_por_jornada is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"El empleado {id_empleado} no tiene horario asignado en el rango "
                f"{fecha_inicio} a {fecha_fin}; RRHH debe asignarlo antes de registrar "
                f"la solicitud."
            )
        )

    return CalculoHorasHabilesResponse(
        id_empleado=id_empleado,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        dias_calendario=dias_calendario,
        dias_habiles=dias_habiles,
        horas_por_jornada=horas_por_jornada,
        horario_uniforme=len(jornadas_vistas) <= 1,
        horas_habiles=horas_habiles,
        dias_excluidos=dias_excluidos,
    )


# ===== SALDO DE LA GESTIÓN =====

def asegurar_vacacion_gestion(
    db: Session,
    id_empleado: int,
    gestion: int
) -> Tuple[Vacacion, bool]:
    """
    Devuelve el registro de vacación de un empleado para una gestión, creándolo
    con la base LGT si todavía no existe. Es idempotente: llamarla dos veces no
    duplica ni incrementa saldos.

    Existe porque `rrhh.vacacion` está prácticamente vacía y crear un
    `detalle_vacacion` exige un `id_vacacion`: sin esto, el formulario de
    solicitudes se trabaría para casi todos los empleados.

    Devuelve `(vacacion, fue_creada)`.

    `horas_goce_haber` se siembra con la base completa, NO con 0: al pasar un
    detalle a 'tomado', `_resolver_campo_saldo` descuenta de esa bolsa y
    `cambiar_estado_detalle` exige `horas_habiles <= horas_goce_haber`. Con la
    bolsa en 0 ninguna vacación con goce podría marcarse como tomada nunca.
    (`transferir_a_vacacion` la crea con solo las 4h del cumpleaños porque su
    caso de uso es acreditar ese beneficio, no habilitar el saldo anual.)
    """
    existente = db.query(Vacacion).filter(
        Vacacion.id_empleado == id_empleado,
        Vacacion.gestion == gestion,
    ).first()

    if existente:
        return existente, False

    empleado = db.query(Empleado).filter(Empleado.id == id_empleado).first()

    if not empleado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Empleado con ID {id_empleado} no encontrado"
        )

    # Misma fuente que usa el trigger trg_compensacion_horas_extra_a_vacacion y
    # que beneficio_cumpleanos._base_horas_vacacion_lgt, para que un saldo
    # creado por cualquiera de las tres rutas parta de la misma base.
    base = db.execute(
        text("SELECT rrhh.fn_horas_vacacion_lgt(:ingreso, :corte)"),
        {"ingreso": empleado.fecha_ingreso, "corte": date(gestion, 12, 31)},
    ).scalar()

    base_horas = Decimal(str(base)) if base is not None else Decimal("0.0")

    vacacion = Vacacion(
        id_empleado=id_empleado,
        gestion=gestion,
        horas_correspondientes=base_horas,
        horas_goce_haber=base_horas,
        horas_sin_goce_haber=Decimal("0.0"),
        horas_tomadas=Decimal("0.0"),
        observacion=(
            f"Creada automáticamente al registrar una solicitud de vacaciones. "
            f"Base por antigüedad (LGT Art. 44) al cierre de la gestión {gestion}."
        ),
    )

    db.add(vacacion)

    try:
        db.commit()
    except IntegrityError:
        # Carrera contra uq_vacacion_empleado_gestion: otra request creó el
        # mismo saldo entre el SELECT y el INSERT. Se devuelve el que ganó en
        # vez de fallar, que es lo que espera un endpoint idempotente.
        db.rollback()

        ganador = db.query(Vacacion).filter(
            Vacacion.id_empleado == id_empleado,
            Vacacion.gestion == gestion,
        ).first()

        if ganador:
            return ganador, False

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"No se pudo crear el saldo vacacional del empleado {id_empleado} "
                f"para la gestión {gestion}"
            )
        )

    db.refresh(vacacion)

    return vacacion, True
