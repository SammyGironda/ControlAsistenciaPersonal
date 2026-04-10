"""
Lógica de negocio para Asistencia Diaria.
Incluye cálculo automático de retrasos, minutos trabajados y tipo de día.
"""

from datetime import date, datetime, time, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, func, or_, text
from fastapi import HTTPException, status

from app.features.attendance.asistencia_diaria.models import AsistenciaDiaria, EstadoDiaEnum
from app.features.attendance.asistencia_diaria.schemas import (
    AsistenciaDiariaCreate, AsistenciaDiariaUpdate, ResultadoProcesamiento
)
from app.features.employees.empleado.models import Empleado
from app.features.employees.cargo.models import Cargo
from app.features.employees.horario.models import Horario, AsignacionHorario
from app.features.attendance.marcacion.models import Marcacion, TipoMarcacionEnum
from app.features.attendance.feriados.models import DiaFestivo, AmbitoFestivoEnum
from app.features.attendance.justificacion.models import JustificacionAusencia, EstadoAprobacionEnum, TipoJustificacionEnum


# ============================================================
# CRUD BÁSICO
# ============================================================

def get_asistencia_by_id(db: Session, asistencia_id: int) -> Optional[AsistenciaDiaria]:
    """Obtener asistencia por ID con relaciones cargadas."""
    return db.query(AsistenciaDiaria).options(
        joinedload(AsistenciaDiaria.empleado),
        joinedload(AsistenciaDiaria.marcacion_entrada),
        joinedload(AsistenciaDiaria.marcacion_salida)
    ).filter(AsistenciaDiaria.id == asistencia_id).first()


def get_asistencia_by_empleado(
    db: Session,
    id_empleado: int,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    tipo_dia: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> List[AsistenciaDiaria]:
    """
    Obtener asistencias de un empleado con filtros opcionales.
    
    Args:
        db: Sesión de base de datos
        id_empleado: ID del empleado
        fecha_desde: Filtro de fecha inicial (opcional)
        fecha_hasta: Filtro de fecha final (opcional)
        tipo_dia: Filtro por tipo de día (opcional)
        skip: Registros a saltar (paginación)
        limit: Límite de registros
    """
    query = db.query(AsistenciaDiaria).options(
        joinedload(AsistenciaDiaria.empleado),
        joinedload(AsistenciaDiaria.marcacion_entrada),
        joinedload(AsistenciaDiaria.marcacion_salida)
    ).filter(AsistenciaDiaria.id_empleado == id_empleado)
    
    if fecha_desde:
        query = query.filter(AsistenciaDiaria.fecha >= fecha_desde)
    if fecha_hasta:
        query = query.filter(AsistenciaDiaria.fecha <= fecha_hasta)
    if tipo_dia:
        query = query.filter(AsistenciaDiaria.tipo_dia == tipo_dia)
    
    return query.order_by(AsistenciaDiaria.fecha.desc()).offset(skip).limit(limit).all()


def create_asistencia(db: Session, data: AsistenciaDiariaCreate) -> AsistenciaDiaria:
    """
    Crear registro de asistencia manualmente (correcciones RRHH).
    Valida que no exista duplicado para el mismo empleado y fecha.
    """
    # Verificar que el empleado existe
    empleado = db.query(Empleado).filter(Empleado.id == data.id_empleado).first()
    if not empleado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Empleado con ID {data.id_empleado} no encontrado"
        )
    
    # Verificar que no exista registro para esta fecha
    existente = db.query(AsistenciaDiaria).filter(
        and_(
            AsistenciaDiaria.id_empleado == data.id_empleado,
            AsistenciaDiaria.fecha == data.fecha
        )
    ).first()
    
    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe registro de asistencia para el empleado {data.id_empleado} en la fecha {data.fecha}"
        )
    
    # Crear registro
    asistencia = AsistenciaDiaria(**data.model_dump())
    db.add(asistencia)
    db.commit()
    db.refresh(asistencia)
    return asistencia


def update_asistencia(db: Session, asistencia_id: int, data: AsistenciaDiariaUpdate) -> AsistenciaDiaria:
    """Actualizar registro de asistencia existente."""
    asistencia = get_asistencia_by_id(db, asistencia_id)
    if not asistencia:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asistencia con ID {asistencia_id} no encontrada"
        )
    
    # Actualizar solo campos no nulos
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(asistencia, key, value)
    
    asistencia.updated_at = datetime.now()
    db.commit()
    db.refresh(asistencia)
    return asistencia


def delete_asistencia(db: Session, asistencia_id: int) -> bool:
    """
    Eliminar registro de asistencia (HARD DELETE).
    Usar con precaución. Preferir UPDATE para correcciones.
    """
    asistencia = get_asistencia_by_id(db, asistencia_id)
    if not asistencia:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Asistencia con ID {asistencia_id} no encontrada"
        )
    
    db.delete(asistencia)
    db.commit()
    return True


# ============================================================
# LÓGICA DE CÁLCULO DE ASISTENCIA
# ============================================================

def calcular_asistencia_dia(
    db: Session,
    id_empleado: int,
    fecha: date
) -> AsistenciaDiaria:
    """
    Calcula la asistencia de un empleado para un día específico.
    
    Proceso:
    1. Obtener empleado + cargo
    2. Obtener horario asignado vigente
    3. Verificar si es día de descanso (según horario)
    4. Verificar si es feriado (Semana 7)
    5. Verificar si es cargo de confianza
    6. Buscar marcaciones del día (ENTRADA + SALIDA)
    7. Calcular retrasos y minutos trabajados
    8. Verificar justificaciones (Semana 7)
    9. Insertar/actualizar registro
    
    Args:
        db: Sesión de base de datos
        id_empleado: ID del empleado
        fecha: Fecha a procesar
    
    Returns:
        Registro de AsistenciaDiaria creado/actualizado
    
    Raises:
        HTTPException: Si el empleado no existe o no tiene horario asignado
    """
    # PASO 1: Obtener empleado + cargo
    empleado = db.query(Empleado).options(
        joinedload(Empleado.cargo)
    ).filter(Empleado.id == id_empleado).first()
    
    if not empleado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Empleado con ID {id_empleado} no encontrado"
        )
    
    cargo = empleado.cargo
    
    # PASO 2: Obtener horario asignado vigente
    asignacion = db.query(AsignacionHorario).options(
        joinedload(AsignacionHorario.horario)
    ).filter(
        and_(
            AsignacionHorario.id_empleado == id_empleado,
            AsignacionHorario.fecha_inicio <= fecha,
            or_(
                AsignacionHorario.fecha_fin.is_(None),
                AsignacionHorario.fecha_fin >= fecha
            )
        )
    ).first()
    
    if not asignacion:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Empleado {id_empleado} no tiene horario asignado para la fecha {fecha}"
        )
    
    horario = asignacion.horario
    
    # PASO 3: Verificar si hay justificación aprobada del día
    justificacion_aprobada = _obtener_justificacion_aprobada_dia(db, id_empleado, fecha)

    # PASO 4: Verificar si es día de descanso según horario
    dia_semana = fecha.weekday()  # 0=lunes, 6=domingo
    dias_laborables = _parse_dias_laborables(horario.dias_laborables)
    
    if dia_semana not in dias_laborables:
        # Es día de descanso (fin de semana u otro según horario)
        return _crear_o_actualizar_asistencia(
            db=db,
            id_empleado=id_empleado,
            fecha=fecha,
            tipo_dia=EstadoDiaEnum.descanso,
            minutos_retraso=0,
            minutos_trabajados=0
        )

    # PASO 5: Verificar si es feriado
    es_feriado = _es_feriado(db, fecha, empleado.complemento_dep)
    if es_feriado:
        marcaciones_feriado = _obtener_marcaciones_dia(db, id_empleado, fecha)
        trabajo_en_feriado = len(marcaciones_feriado) > 0
        return _crear_o_actualizar_asistencia(
            db=db,
            id_empleado=id_empleado,
            fecha=fecha,
            tipo_dia=EstadoDiaEnum.feriado,
            minutos_retraso=0,
            minutos_trabajados=0,
            id_justificacion=justificacion_aprobada.id if justificacion_aprobada else None,
            horas_permiso_usadas=float(justificacion_aprobada.total_horas_permiso) if justificacion_aprobada and justificacion_aprobada.total_horas_permiso else 0.0,
            trabajo_en_feriado=trabajo_en_feriado,
        )

    # PASO 6: Verificar si es cargo de confianza
    if cargo.es_cargo_confianza:
        # Cargo de confianza: exento de marcación
        return _crear_o_actualizar_asistencia(
            db=db,
            id_empleado=id_empleado,
            fecha=fecha,
            tipo_dia=EstadoDiaEnum.presente_exento,
            minutos_retraso=0,
            minutos_trabajados=0,
            id_justificacion=justificacion_aprobada.id if justificacion_aprobada else None,
            horas_permiso_usadas=float(justificacion_aprobada.total_horas_permiso) if justificacion_aprobada and justificacion_aprobada.total_horas_permiso else 0.0,
        )

    # PASO 7: Buscar marcaciones del día
    marcaciones = _obtener_marcaciones_dia(db, id_empleado, fecha)
    marcacion_entrada = next((m for m in marcaciones if m.tipo_marcacion == TipoMarcacionEnum.ENTRADA), None)
    marcacion_salida = next((m for m in marcaciones if m.tipo_marcacion == TipoMarcacionEnum.SALIDA), None)

    # PASO 8: Resolver por justificación aprobada antes de ausente
    if justificacion_aprobada:
        if justificacion_aprobada.tipo_justificacion == TipoJustificacionEnum.licencia_medica_accidente:
            return _crear_o_actualizar_asistencia(
                db=db,
                id_empleado=id_empleado,
                fecha=fecha,
                tipo_dia=EstadoDiaEnum.licencia_medica,
                minutos_retraso=0,
                minutos_trabajados=0,
                id_justificacion=justificacion_aprobada.id,
                horas_permiso_usadas=float(justificacion_aprobada.total_horas_permiso) if justificacion_aprobada.total_horas_permiso else 0.0,
            )

        if justificacion_aprobada.es_por_horas and marcacion_entrada and marcacion_salida:
            minutos_retraso = _calcular_minutos_retraso(
                hora_entrada_marcada=marcacion_entrada.fecha_hora_marcacion.time(),
                hora_entrada_esperada=horario.hora_entrada,
                tolerancia_minutos=horario.tolerancia_minutos,
            )
            minutos_trabajados = _calcular_minutos_trabajados(
                hora_entrada=marcacion_entrada.fecha_hora_marcacion,
                hora_salida=marcacion_salida.fecha_hora_marcacion,
            )
            return _crear_o_actualizar_asistencia(
                db=db,
                id_empleado=id_empleado,
                fecha=fecha,
                id_marcacion_entrada=marcacion_entrada.id,
                id_marcacion_salida=marcacion_salida.id,
                id_justificacion=justificacion_aprobada.id,
                tipo_dia=EstadoDiaEnum.permiso_parcial,
                minutos_retraso=minutos_retraso,
                minutos_trabajados=minutos_trabajados,
                horas_permiso_usadas=float(justificacion_aprobada.total_horas_permiso) if justificacion_aprobada.total_horas_permiso else 0.0,
            )

        if not marcacion_entrada and not marcacion_salida:
            tipo_justif = justificacion_aprobada.tipo_justificacion
            tipo_dia = EstadoDiaEnum.licencia_medica if tipo_justif == TipoJustificacionEnum.licencia_medica_accidente else EstadoDiaEnum.permiso_parcial
            return _crear_o_actualizar_asistencia(
                db=db,
                id_empleado=id_empleado,
                fecha=fecha,
                tipo_dia=tipo_dia,
                minutos_retraso=0,
                minutos_trabajados=0,
                id_justificacion=justificacion_aprobada.id,
                horas_permiso_usadas=float(justificacion_aprobada.total_horas_permiso) if justificacion_aprobada.total_horas_permiso else 0.0,
            )

    # PASO 9: Calcular según marcaciones
    if not marcacion_entrada and not marcacion_salida:
        # Sin marcaciones: AUSENTE
        return _crear_o_actualizar_asistencia(
            db=db,
            id_empleado=id_empleado,
            fecha=fecha,
            tipo_dia=EstadoDiaEnum.ausente,
            minutos_retraso=0,
            minutos_trabajados=0,
            id_justificacion=justificacion_aprobada.id if justificacion_aprobada else None,
            horas_permiso_usadas=float(justificacion_aprobada.total_horas_permiso) if justificacion_aprobada and justificacion_aprobada.total_horas_permiso else 0.0,
        )
    
    if marcacion_entrada and not marcacion_salida:
        # Solo entrada sin salida: marcación incompleta, considerar AUSENTE
        return _crear_o_actualizar_asistencia(
            db=db,
            id_empleado=id_empleado,
            fecha=fecha,
            id_marcacion_entrada=marcacion_entrada.id,
            id_justificacion=justificacion_aprobada.id if justificacion_aprobada else None,
            tipo_dia=EstadoDiaEnum.ausente,
            minutos_retraso=0,
            minutos_trabajados=0,
            horas_permiso_usadas=float(justificacion_aprobada.total_horas_permiso) if justificacion_aprobada and justificacion_aprobada.total_horas_permiso else 0.0,
            observacion="Marcación incompleta: solo tiene entrada"
        )
    
    if marcacion_entrada and marcacion_salida:
        # Marcación completa: calcular retraso y minutos trabajados
        minutos_retraso = _calcular_minutos_retraso(
            hora_entrada_marcada=marcacion_entrada.fecha_hora_marcacion.time(),
            hora_entrada_esperada=horario.hora_entrada,
            tolerancia_minutos=horario.tolerancia_minutos
        )
        
        minutos_trabajados = _calcular_minutos_trabajados(
            hora_entrada=marcacion_entrada.fecha_hora_marcacion,
            hora_salida=marcacion_salida.fecha_hora_marcacion
        )
        
        return _crear_o_actualizar_asistencia(
            db=db,
            id_empleado=id_empleado,
            fecha=fecha,
            id_marcacion_entrada=marcacion_entrada.id,
            id_marcacion_salida=marcacion_salida.id,
            id_justificacion=justificacion_aprobada.id if justificacion_aprobada else None,
            tipo_dia=EstadoDiaEnum.presente,
            minutos_retraso=minutos_retraso,
            minutos_trabajados=minutos_trabajados,
            horas_permiso_usadas=float(justificacion_aprobada.total_horas_permiso) if justificacion_aprobada and justificacion_aprobada.total_horas_permiso else 0.0,
        )
    
    # Caso edge: solo salida sin entrada (raro pero posible)
    return _crear_o_actualizar_asistencia(
        db=db,
        id_empleado=id_empleado,
        fecha=fecha,
        id_marcacion_salida=marcacion_salida.id if marcacion_salida else None,
        id_justificacion=justificacion_aprobada.id if justificacion_aprobada else None,
        tipo_dia=EstadoDiaEnum.ausente,
        minutos_retraso=0,
        minutos_trabajados=0,
        horas_permiso_usadas=float(justificacion_aprobada.total_horas_permiso) if justificacion_aprobada and justificacion_aprobada.total_horas_permiso else 0.0,
        observacion="Marcación incompleta: solo tiene salida"
    )


def procesar_asistencia_masiva(db: Session, fecha: date) -> ResultadoProcesamiento:
    """
    Procesa la asistencia de TODOS los empleados activos para una fecha.
    Usado por el worker diario automático.
    
    Args:
        db: Sesión de base de datos
        fecha: Fecha a procesar
    
    Returns:
        Estadísticas del procesamiento (éxitos, errores, skipped)
    """
    # Obtener todos los empleados activos
    empleados = db.query(Empleado).filter(Empleado.estado == "activo").all()
    
    procesados = 0
    errores_lista = []
    skipped = 0
    
    for empleado in empleados:
        try:
            calcular_asistencia_dia(db, empleado.id, fecha)
            procesados += 1
        except HTTPException as e:
            # Empleado sin horario asignado u otro error esperado
            errores_lista.append(f"Empleado {empleado.id}: {e.detail}")
            skipped += 1
        except Exception as e:
            # Error inesperado
            errores_lista.append(f"Empleado {empleado.id}: Error inesperado: {str(e)}")
            skipped += 1
    
    return ResultadoProcesamiento(
        fecha=fecha,
        empleados_procesados=procesados,
        empleados_con_error=len(errores_lista),
        empleados_skipped=skipped,
        errores=errores_lista
    )


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def _obtener_marcaciones_dia(db: Session, id_empleado: int, fecha: date) -> List[Marcacion]:
    """Obtiene todas las marcaciones de un empleado en una fecha específica."""
    fecha_inicio = datetime.combine(fecha, time.min)
    fecha_fin = datetime.combine(fecha, time.max)
    
    return db.query(Marcacion).filter(
        and_(
            Marcacion.id_empleado == id_empleado,
            Marcacion.fecha_hora_marcacion >= fecha_inicio,
            Marcacion.fecha_hora_marcacion <= fecha_fin
        )
    ).order_by(Marcacion.fecha_hora_marcacion).all()


def _parse_dias_laborables(dias_str: object) -> List[int]:
    """
    Parsea días laborables a índices Python de semana (0=lunes, 6=domingo).

    Soporta:
    - Lista JSON: [1, 2, 3, 4, 5]  (1=lunes ... 7=domingo)
    - String de rango: "L-V"
    - String por lista: "L,MI,V"
    """
    dias_default = [0, 1, 2, 3, 4]

    if dias_str is None:
        return dias_default

    if isinstance(dias_str, (list, tuple, set)):
        dias = []
        for item in dias_str:
            try:
                numero = int(item)
            except (TypeError, ValueError):
                continue
            if 1 <= numero <= 7:
                dias.append(numero - 1)
        return sorted(set(dias)) or dias_default

    if not isinstance(dias_str, str):
        return dias_default

    valor = dias_str.strip().upper()
    if not valor:
        return dias_default

    dia_map = {
        "L": 0,
        "M": 1,
        "MI": 2,
        "J": 3,
        "V": 4,
        "S": 5,
        "D": 6,
    }

    if "-" in valor:
        inicio_str, fin_str = valor.split("-", 1)
        inicio = dia_map.get(inicio_str.strip())
        fin = dia_map.get(fin_str.strip())
        if inicio is None or fin is None:
            return dias_default
        if inicio <= fin:
            return list(range(inicio, fin + 1))
        return list(range(inicio, 7)) + list(range(0, fin + 1))

    dias = []
    for token in valor.split(","):
        numero = dia_map.get(token.strip())
        if numero is not None:
            dias.append(numero)
    return sorted(set(dias)) or dias_default


def _calcular_minutos_retraso(
    hora_entrada_marcada: time,
    hora_entrada_esperada: time,
    tolerancia_minutos: int
) -> int:
    """
    Calcula minutos de retraso considerando tolerancia.
    
    Args:
        hora_entrada_marcada: Hora real de marcación
        hora_entrada_esperada: Hora esperada según horario
        tolerancia_minutos: Minutos de gracia
    
    Returns:
        Minutos de retraso (0 si llegó a tiempo)
    """
    # Convertir a minutos desde medianoche
    minutos_marcada = hora_entrada_marcada.hour * 60 + hora_entrada_marcada.minute
    minutos_esperada = hora_entrada_esperada.hour * 60 + hora_entrada_esperada.minute
    
    diferencia = minutos_marcada - minutos_esperada - tolerancia_minutos
    return max(0, diferencia)


def _calcular_minutos_trabajados(hora_entrada: datetime, hora_salida: datetime) -> int:
    """
    Calcula minutos netos trabajados (sin descuento de almuerzo).
    
    Args:
        hora_entrada: Datetime de entrada
        hora_salida: Datetime de salida
    
    Returns:
        Minutos trabajados
    """
    diferencia = hora_salida - hora_entrada
    return int(diferencia.total_seconds() / 60)


def _crear_o_actualizar_asistencia(
    db: Session,
    id_empleado: int,
    fecha: date,
    tipo_dia: EstadoDiaEnum,
    id_marcacion_entrada: Optional[int] = None,
    id_marcacion_salida: Optional[int] = None,
    id_justificacion: Optional[int] = None,
    minutos_retraso: int = 0,
    minutos_trabajados: int = 0,
    horas_extra: float = 0.0,
    horas_permiso_usadas: float = 0.0,
    trabajo_en_feriado: bool = False,
    observacion: Optional[str] = None
) -> AsistenciaDiaria:
    """
    Crea o actualiza un registro de asistencia diaria.
    Si ya existe para el empleado + fecha, lo actualiza.
    Si no existe, lo crea.
    """
    # Buscar registro existente
    existente = db.query(AsistenciaDiaria).filter(
        and_(
            AsistenciaDiaria.id_empleado == id_empleado,
            AsistenciaDiaria.fecha == fecha
        )
    ).first()
    
    if existente:
        # Actualizar
        existente.id_marcacion_entrada = id_marcacion_entrada
        existente.id_marcacion_salida = id_marcacion_salida
        existente.id_justificacion = id_justificacion
        existente.tipo_dia = tipo_dia.value
        existente.minutos_retraso = minutos_retraso
        existente.minutos_trabajados = minutos_trabajados
        existente.horas_extra = horas_extra
        existente.horas_permiso_usadas = horas_permiso_usadas
        existente.trabajo_en_feriado = trabajo_en_feriado
        if observacion:
            existente.observacion = observacion
        existente.updated_at = datetime.now()
        
        db.commit()
        db.refresh(existente)
        return existente
    else:
        # Crear nuevo
        nueva_asistencia = AsistenciaDiaria(
            id_empleado=id_empleado,
            fecha=fecha,
            id_marcacion_entrada=id_marcacion_entrada,
            id_marcacion_salida=id_marcacion_salida,
            id_justificacion=id_justificacion,
            tipo_dia=tipo_dia.value,
            minutos_retraso=minutos_retraso,
            minutos_trabajados=minutos_trabajados,
            horas_extra=horas_extra,
            horas_permiso_usadas=horas_permiso_usadas,
            trabajo_en_feriado=trabajo_en_feriado,
            observacion=observacion
        )
        
        db.add(nueva_asistencia)
        db.commit()
        db.refresh(nueva_asistencia)
        return nueva_asistencia


def _es_feriado(db: Session, fecha: date, codigo_departamento: Optional[str]) -> bool:
    """Valida si una fecha aplica como feriado para el departamento del empleado."""
    query = db.query(DiaFestivo).filter(
        DiaFestivo.fecha == fecha,
        DiaFestivo.activo.is_(True),
        or_(
            DiaFestivo.ambito == AmbitoFestivoEnum.NACIONAL,
            and_(
                DiaFestivo.ambito == AmbitoFestivoEnum.DEPARTAMENTAL,
                DiaFestivo.codigo_departamento == codigo_departamento,
            ),
        ),
    )
    return query.first() is not None


def _obtener_justificacion_aprobada_dia(
    db: Session,
    id_empleado: int,
    fecha: date,
) -> Optional[JustificacionAusencia]:
    """Obtiene una justificación aprobada que cubre la fecha consultada."""
    return db.query(JustificacionAusencia).filter(
        JustificacionAusencia.id_empleado == id_empleado,
        JustificacionAusencia.estado_aprobacion == EstadoAprobacionEnum.aprobado,
        JustificacionAusencia.fecha_inicio <= fecha,
        JustificacionAusencia.fecha_fin >= fecha,
    ).order_by(JustificacionAusencia.created_at.desc()).first()


def get_resumen_mensual_desde_vista(db: Session, id_empleado: int, anio: int, mes: int):
    """Consulta la vista rrhh.v_asistencia_mensual para un empleado y mes."""
    inicio_mes = date(anio, mes, 1)
    sql = text(
        """
        SELECT *
        FROM rrhh.v_asistencia_mensual
        WHERE id_empleado = :id_empleado
          AND mes = date_trunc('month', :inicio_mes::date)
        LIMIT 1
        """
    )
    row = db.execute(sql, {"id_empleado": id_empleado, "inicio_mes": inicio_mes}).mappings().first()
    if not row:
        return None
    return dict(row)
