"""
Services para Marcaciones - Lógica de negocio.
Incluye procesamiento de archivos Excel con Pandas.
"""

from datetime import datetime, date, timedelta, time
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import and_, or_, func
from fastapi import HTTPException, status, UploadFile
import pandas as pd
import json
import logging
from pathlib import Path

from app.features.attendance.marcacion.models import (
    Marcacion, ArchivoExcel, IncidenciaMarcacion,
    OrigenDatoEnum, TipoMarcacionEnum, EstadoProcesamientoEnum,
    TipoIncidenciaEnum, EstadoResolucionEnum
)
from app.features.attendance.marcacion.schemas import (
    MarcacionCreate, ArchivoExcelCreate, ArchivoExcelUpdate,
    IncidenciaMarcacionCreate, IncidenciaMarcacionUpdate
)
from app.features.employees.empleado.models import Empleado
from app.features.employees.cargo.models import Cargo
from app.features.auth.usuario.models import Usuario
from app.features.employees.horario.models import AsignacionHorario
from app.features.attendance.asistencia_diaria import services as asistencia_services


# ============================================================
# MARCACIONES - CRUD
# ============================================================

def create_marcacion(db: Session, data: MarcacionCreate) -> Marcacion:
    """
    Crea una nueva marcación.

    Validaciones:
    - El empleado debe existir y estar activo
    - No se permite crear marcaciones duplicadas exactas (mismo empleado, mismo timestamp)
    """
    # Verificar empleado
    empleado = db.query(Empleado).filter(Empleado.id == data.id_empleado).first()
    if not empleado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el empleado con ID {data.id_empleado}"
        )

    # Verificar duplicado exacto
    duplicado = db.query(Marcacion).filter(
        and_(
            Marcacion.id_empleado == data.id_empleado,
            Marcacion.fecha_hora_marcacion == data.fecha_hora_marcacion,
            Marcacion.tipo_marcacion == data.tipo_marcacion
        )
    ).first()

    if duplicado:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ya existe una marcación idéntica para este empleado en esta fecha/hora"
        )

    # Crear marcación
    marcacion = Marcacion(**data.model_dump())
    db.add(marcacion)
    db.commit()
    db.refresh(marcacion)

    # Detectar si es huérfana o duplicada
    _detectar_incidencias(db, marcacion)

    return marcacion


def get_marcaciones_by_empleado(
    db: Session,
    empleado_id: int,
    fecha_desde: Optional[date] = None,
    fecha_hasta: Optional[date] = None,
    skip: int = 0,
    limit: int = 100
) -> List[Marcacion]:
    """Obtiene marcaciones de un empleado con filtros de fecha."""
    query = db.query(Marcacion).filter(Marcacion.id_empleado == empleado_id)

    if fecha_desde:
        query = query.filter(Marcacion.fecha_hora_marcacion >= fecha_desde)
    if fecha_hasta:
        # Agregar 1 día para incluir todo el día hasta
        fecha_hasta_inclusive = datetime.combine(fecha_hasta, datetime.max.time())
        query = query.filter(Marcacion.fecha_hora_marcacion <= fecha_hasta_inclusive)

    return query.order_by(Marcacion.fecha_hora_marcacion.desc()).offset(skip).limit(limit).all()


def get_marcaciones_huerfanas(db: Session, skip: int = 0, limit: int = 100) -> List[Marcacion]:
    """Obtiene todas las marcaciones huérfanas."""
    return db.query(Marcacion).filter(Marcacion.es_huerfana == True).offset(skip).limit(limit).all()


def get_marcaciones_duplicadas(db: Session, skip: int = 0, limit: int = 100) -> List[Marcacion]:
    """Obtiene todas las marcaciones duplicadas."""
    return db.query(Marcacion).filter(Marcacion.es_duplicada == True).offset(skip).limit(limit).all()


# ============================================================
# ARCHIVOS EXCEL - CRUD
# ============================================================

def create_archivo_excel(db: Session, data: ArchivoExcelCreate) -> ArchivoExcel:
    """Crea registro de archivo Excel."""
    archivo = ArchivoExcel(**data.model_dump())
    db.add(archivo)
    db.commit()
    db.refresh(archivo)
    return archivo


def get_archivo_by_id(db: Session, archivo_id: int) -> Optional[ArchivoExcel]:
    """Obtiene un archivo por ID."""
    return db.query(ArchivoExcel).filter(ArchivoExcel.id == archivo_id).first()


def update_archivo(db: Session, archivo_id: int, data: ArchivoExcelUpdate) -> ArchivoExcel:
    """Actualiza el estado de procesamiento de un archivo."""
    try:
        archivo = get_archivo_by_id(db, archivo_id)
        if not archivo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No existe el archivo con ID {archivo_id}"
            )

        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(archivo, key, value)

        db.commit()
        db.refresh(archivo)
        return archivo
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar archivo: {str(e)}"
        )


def get_all_archivos(db: Session, skip: int = 0, limit: int = 100) -> List[ArchivoExcel]:
    """Lista todos los archivos subidos."""
    return db.query(ArchivoExcel).order_by(ArchivoExcel.fecha_subida.desc()).offset(skip).limit(limit).all()


# ============================================================
# INCIDENCIAS - CRUD
# ============================================================

def _resolver_hora_correccion(horario, tipo_marcacion: TipoMarcacionEnum, hora_correccion=None):
    """Resuelve la hora de corrección usando el horario del empleado cuando no viene explícita."""
    if hora_correccion:
        if isinstance(hora_correccion, datetime):
            return hora_correccion.time()
        if isinstance(hora_correccion, time):
            return hora_correccion
        if isinstance(hora_correccion, str):
            try:
                hh, mm = [int(p) for p in hora_correccion.split(":", 1)]
                return time(hour=hh, minute=mm)
            except ValueError:
                return None
        return None

    if not horario:
        return None

    if tipo_marcacion == TipoMarcacionEnum.SALIDA:
        return horario.hora_salida

    return horario.hora_entrada


def _seleccionar_marcacion_duplicada(marcaciones, hora_esperada: time, tipo_marcacion: TipoMarcacionEnum):
    """Selecciona qué marcador duplicado conservar según el tipo de marcación y la hora esperada."""
    if not marcaciones:
        return None
    if len(marcaciones) == 1:
        return marcaciones[0]

    marcaciones_ordenadas = sorted(marcaciones, key=lambda m: m.fecha_hora_marcacion)

    if tipo_marcacion == TipoMarcacionEnum.SALIDA:
        return marcaciones_ordenadas[-1]

    return marcaciones_ordenadas[0]


def _obtener_horario_empleado(db: Session, id_empleado: int, fecha: date):
    """
    Obtiene la asignación de horario vigente para un empleado en una fecha.

    Solo considera asignaciones activas (delete_asignacion_horario es un
    soft-delete que no toca fecha_fin) y, ante solapamiento, devuelve la más
    reciente para que el resultado sea determinista.
    """
    asignacion = db.query(AsignacionHorario).options(joinedload(AsignacionHorario.horario)).filter(
        and_(
            AsignacionHorario.id_empleado == id_empleado,
            AsignacionHorario.es_activo == True,
            AsignacionHorario.fecha_inicio <= fecha,
            or_(
                AsignacionHorario.fecha_fin.is_(None),
                AsignacionHorario.fecha_fin >= fecha,
            ),
        )
    ).order_by(AsignacionHorario.fecha_inicio.desc()).first()

    return asignacion.horario if asignacion else None


def _recalcular_asistencia_dia(db: Session, id_empleado: int, fecha: date) -> tuple[bool, Optional[str]]:
    """Recalcula la asistencia diaria para un empleado en una fecha.

    La importación de marcaciones no debe perderse si un empleado no tiene
    horario asignado. Por eso se informa el error al flujo que invoca esta
    función y se continúa con los demás empleados.
    """
    try:
        asistencia_services.calcular_asistencia_dia(db, id_empleado, fecha)
        return True, None
    except HTTPException as exc:
        if "no tiene horario asignado" in str(exc.detail).lower():
            try:
                asistencia_services.registrar_asistencia_importada_sin_horario(
                    db, id_empleado, fecha
                )
                return True, "Asistencia registrada sin horario asignado"
            except Exception as fallback_exc:
                db.rollback()
                return False, str(fallback_exc)
        return False, exc.detail
    except Exception as exc:
        db.rollback()
        return False, str(exc)


def _obtener_empleados_confianza_activos(db: Session) -> list[Empleado]:
    """Empleados activos con cargo de confianza (exentos de marcar huella)."""
    return db.query(Empleado).join(Cargo).filter(
        Cargo.es_cargo_confianza == True,
        Empleado.estado == "activo",
    ).all()


def _generar_asistencia_confianza(
    db: Session,
    fecha_desde: Optional[date],
    fecha_hasta: Optional[date],
    empleados_fechas_procesadas: set,
) -> tuple[int, list]:
    """Genera `presente_exento` para empleados de cargo de confianza en [fecha_desde, fecha_hasta].

    Estos empleados están exentos de marcar huella, por lo que nunca aparecen
    como marcación en el Excel ni en `empleados_fechas_procesadas` — sin este
    paso nunca se les generaría `asistencia_diaria` (ver CLAUDE.md, sección
    "Decisión arquitectónica activa"). Reutiliza `_recalcular_asistencia_dia`
    (mismo wrapper con `db.rollback()` por fallo que usa el resto del pipeline).

    Retorna (empleados_procesados, errores) — `errores` con la misma forma
    ({"empleado_id", "fecha", "error"}) que `errores_asistencia` en
    `procesar_archivo_excel`.
    """
    procesados = 0
    errores: list = []

    if not fecha_desde or not fecha_hasta:
        return procesados, errores

    empleados_confianza = _obtener_empleados_confianza_activos(db)
    if not empleados_confianza:
        return procesados, errores

    dia = fecha_desde
    while dia <= fecha_hasta:
        periodo_dia = asistencia_services.get_periodo_asistencia(db, dia.year, dia.month)
        periodo_cerrado = periodo_dia is not None and periodo_dia.estado.value == "cerrado"

        for empleado_confianza in empleados_confianza:
            if (empleado_confianza.id, dia) in empleados_fechas_procesadas:
                continue  # ya recalculado en el loop principal del Excel

            if periodo_cerrado:
                errores.append({
                    "empleado_id": empleado_confianza.id,
                    "fecha": str(dia),
                    "error": f"El período {dia.year}-{dia.month:02d} está cerrado. Reábralo antes de importar marcaciones.",
                })
                continue

            calculada, detalle_error = _recalcular_asistencia_dia(db, empleado_confianza.id, dia)
            if calculada:
                procesados += 1
            else:
                errores.append({
                    "empleado_id": empleado_confianza.id,
                    "fecha": str(dia),
                    "error": detalle_error,
                })

        dia += timedelta(days=1)

    return procesados, errores


def _aplicar_resolucion_incidencia(db: Session, incidencia: IncidenciaMarcacion, data: IncidenciaMarcacionUpdate):
    """Aplica una corrección real a las marcaciones cuando la incidencia se resuelve."""
    if not incidencia.marcacion:
        return

    marcacion = incidencia.marcacion
    fecha = marcacion.fecha_hora_marcacion.date()
    horario = _obtener_horario_empleado(db, marcacion.id_empleado, fecha)

    if incidencia.tipo_incidencia == TipoIncidenciaEnum.huerfana:
        accion = data.accion_resolucion or "completar"
        if accion != "completar":
            return

        tipo_marcacion_correccion = data.tipo_marcacion_correccion or (
            TipoMarcacionEnum.SALIDA if marcacion.tipo_marcacion == TipoMarcacionEnum.ENTRADA else TipoMarcacionEnum.ENTRADA
        )
        hora_correccion = _resolver_hora_correccion(
            horario=horario,
            tipo_marcacion=tipo_marcacion_correccion,
            hora_correccion=data.hora_correccion,
        )
        if not hora_correccion:
            return

        nueva_marcacion = Marcacion(
            id_empleado=marcacion.id_empleado,
            fecha_hora_marcacion=datetime.combine(fecha, hora_correccion),
            tipo_marcacion=tipo_marcacion_correccion,
            origen_dato=OrigenDatoEnum.Manual,
            observacion="Marcación creada por resolución manual de incidencia",
        )
        db.add(nueva_marcacion)
        db.flush()
        return

    if incidencia.tipo_incidencia == TipoIncidenciaEnum.duplicada:
        tipo_marcacion = marcacion.tipo_marcacion
        marcaciones_dia = db.query(Marcacion).filter(
            and_(
                Marcacion.id_empleado == marcacion.id_empleado,
                Marcacion.tipo_marcacion == tipo_marcacion,
                func.date(Marcacion.fecha_hora_marcacion) == fecha,
            )
        ).all()

        if not marcaciones_dia:
            return

        accion = data.accion_resolucion or "auto"
        if accion == "conservar_primera":
            mantener = sorted(marcaciones_dia, key=lambda m: m.fecha_hora_marcacion)[0]
        elif accion == "conservar_ultima":
            mantener = sorted(marcaciones_dia, key=lambda m: m.fecha_hora_marcacion)[-1]
        else:
            mantener = _seleccionar_marcacion_duplicada(
                marcaciones_dia,
                hora_esperada=_resolver_hora_correccion(horario, tipo_marcacion, None),
                tipo_marcacion=tipo_marcacion,
            )

        if incidencia.id_marcacion != mantener.id:
            incidencia.id_marcacion = mantener.id

        for otra in marcaciones_dia:
            if otra.id != mantener.id:
                db.delete(otra)
        db.flush()
        return

    if incidencia.tipo_incidencia == TipoIncidenciaEnum.inconsistente:
        accion = data.accion_resolucion or "corregir_entrada"
        hora_correccion = _resolver_hora_correccion(
            horario=horario,
            tipo_marcacion=marcacion.tipo_marcacion,
            hora_correccion=data.hora_correccion,
        )
        if not hora_correccion:
            return

        if accion == "eliminar_ambas":
            marcaciones_dia = db.query(Marcacion).filter(
                and_(
                    Marcacion.id_empleado == marcacion.id_empleado,
                    func.date(Marcacion.fecha_hora_marcacion) == fecha,
                )
            ).all()
            for otra in marcaciones_dia:
                db.delete(otra)
            db.flush()
            return

        if accion in {"corregir_entrada", "corregir_salida"}:
            marcacion.fecha_hora_marcacion = datetime.combine(fecha, hora_correccion)
            marcacion.origen_dato = OrigenDatoEnum.Manual
            marcacion.observacion = "Marcación ajustada por resolución manual de incidencia"
            db.add(marcacion)
            db.flush()
            return


def _serializar_marcacion_incidencia(marcacion: Marcacion) -> Dict[str, Any]:
    """Expone el dato mínimo que RRHH necesita para revisar una huella."""
    return {
        "id": marcacion.id,
        "id_empleado": marcacion.id_empleado,
        "fecha_hora_marcacion": marcacion.fecha_hora_marcacion,
        "hora": marcacion.fecha_hora_marcacion.strftime("%H:%M"),
        "tipo_marcacion": marcacion.tipo_marcacion.value,
        "origen_dato": marcacion.origen_dato.value,
    }


def _obtener_marcaciones_incidencia(
    db: Session,
    incidencia: IncidenciaMarcacion,
) -> List[Marcacion]:
    """Obtiene la huella afectada y, si aplica, sus duplicados de la misma ventana."""
    marcacion = incidencia.marcacion
    if not marcacion:
        return []

    if incidencia.tipo_incidencia not in {
        TipoIncidenciaEnum.duplicada,
        TipoIncidenciaEnum.inconsistente,
    }:
        return [marcacion]

    delta = timedelta(minutes=5)
    return db.query(Marcacion).filter(
        and_(
            Marcacion.id_empleado == marcacion.id_empleado,
            Marcacion.tipo_marcacion == marcacion.tipo_marcacion,
            Marcacion.fecha_hora_marcacion.between(
                marcacion.fecha_hora_marcacion - delta,
                marcacion.fecha_hora_marcacion + delta,
            ),
        )
    ).order_by(Marcacion.fecha_hora_marcacion).all()


def get_incidencias_pendientes(db: Session, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """Obtiene incidencias pendientes con las horas reales de las huellas involucradas."""
    incidencias = db.query(IncidenciaMarcacion).options(
        joinedload(IncidenciaMarcacion.marcacion)
    ).filter(
        IncidenciaMarcacion.estado_resolucion == EstadoResolucionEnum.pendiente
    ).order_by(IncidenciaMarcacion.created_at.desc()).offset(skip).limit(limit).all()

    resultado = []
    for incidencia in incidencias:
        data = {
            "id": incidencia.id,
            "id_marcacion": incidencia.id_marcacion,
            "tipo_incidencia": incidencia.tipo_incidencia.value,
            "estado_resolucion": incidencia.estado_resolucion.value,
            "evidencia_url": incidencia.evidencia_url,
            "descripcion_resolucion": incidencia.descripcion_resolucion,
            "id_resuelto_por": incidencia.id_resuelto_por,
            "fecha_resolucion": incidencia.fecha_resolucion,
            "created_at": incidencia.created_at,
            "updated_at": incidencia.updated_at,
            "marcaciones": [
                _serializar_marcacion_incidencia(marcacion)
                for marcacion in _obtener_marcaciones_incidencia(db, incidencia)
            ],
        }
        resultado.append(data)

    return resultado


# Campos de IncidenciaMarcacionUpdate que sí son columnas de la tabla. El resto
# (accion_resolucion, hora_correccion, tipo_marcacion_correccion) son
# instrucciones para _aplicar_resolucion_incidencia, no atributos a persistir.
# id_resuelto_por no está acá: ya no llega en `data`, se asigna aparte desde
# el usuario autenticado (ver parámetro id_resuelto_por de esta función).
_CAMPOS_PERSISTIBLES_INCIDENCIA = frozenset({
    "estado_resolucion",
    "evidencia_url",
    "descripcion_resolucion",
})


def update_incidencia(
    db: Session, incidencia_id: int, data: IncidenciaMarcacionUpdate, id_resuelto_por: int
) -> IncidenciaMarcacion:
    """
    Actualiza el estado de una incidencia.

    Para pasar a 'resuelto' se exige evidencia: o viene en el body, o ya estaba
    guardada en la incidencia. Cerrar una incidencia es afirmar que la marcación
    fue corregida, y esa afirmación tiene que quedar respaldada.

    id_resuelto_por es el id_empleado del usuario autenticado (resuelto en el
    router vía get_actor_empleado_id) — toda actualización queda firmada por
    quien la tocó, sin importar a qué estado se mueva.
    """
    incidencia = db.query(IncidenciaMarcacion).filter(IncidenciaMarcacion.id == incidencia_id).first()
    if not incidencia:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe la incidencia con ID {incidencia_id}"
        )

    # Validar ANTES de escribir nada: si la validación fallara después del
    # setattr, la incidencia quedaría parcialmente mutada en la sesión.
    if data.estado_resolucion == EstadoResolucionEnum.resuelto.value:
        evidencia_efectiva = data.evidencia_url if data.evidencia_url is not None else incidencia.evidencia_url

        if not evidencia_efectiva or not evidencia_efectiva.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "No se puede resolver una incidencia sin evidencia_url. "
                    "Adjunte el respaldo de la corrección."
                )
            )

    for key, value in data.model_dump(exclude_unset=True).items():
        if key in _CAMPOS_PERSISTIBLES_INCIDENCIA:
            setattr(incidencia, key, value)

    incidencia.id_resuelto_por = id_resuelto_por

    if data.estado_resolucion == EstadoResolucionEnum.resuelto.value and not incidencia.fecha_resolucion:
        incidencia.fecha_resolucion = datetime.now()

    if data.estado_resolucion == EstadoResolucionEnum.resuelto.value:
        _aplicar_resolucion_incidencia(db, incidencia, data)

    db.commit()
    db.refresh(incidencia)

    return incidencia


# ============================================================
# PROCESAMIENTO DE EXCEL
# ============================================================

def procesar_archivo_excel(
    db: Session,
    file: UploadFile,
    id_subido_por: Optional[int] = None,
    upload_dir: str = "./reportes_generados/marcaciones"
) -> Dict[str, Any]:
    """
    Procesa un archivo Excel de marcaciones con Pandas.

    Formato esperado del Excel:
    - Columna 1: CI (ej: 1234567-LP)
    - Columna 2: Fecha (ej: 2026-01-15)
    - Columna 3: Hora Entrada (ej: 08:00)
    - Columna 4: Hora Salida (ej: 18:00)

    Retorna:
    - archivo_id
    - estadísticas de procesamiento
    - log de errores
    """
    # Validar que id_subido_por existe
    if id_subido_por:
        usuario = db.query(Usuario).filter(Usuario.id == id_subido_por).first()
        if not usuario:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Usuario con ID {id_subido_por} no existe"
            )

    # Guardar archivo físicamente
    Path(upload_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{file.filename}"
    filepath = Path(upload_dir) / filename

    with open(filepath, "wb") as f:
        f.write(file.file.read())

    # Crear registro en BD
    try:
        archivo = create_archivo_excel(db, ArchivoExcelCreate(
            nombre_archivo=file.filename,
            ruta_storage=str(filepath),
            id_subido_por=id_subido_por
        ))
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al crear registro de archivo: {str(e)}"
        )

    # Actualizar estado a procesando
    try:
        update_archivo(db, archivo.id, ArchivoExcelUpdate(estado_procesamiento="procesando"))
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al actualizar estado: {str(e)}"
        )

    try:
        # Leer hojas disponibles en el Excel
        excel_file = pd.ExcelFile(filepath, engine='openpyxl')
        sheet_names = excel_file.sheet_names

        if not sheet_names:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El archivo Excel no contiene hojas"
            )

        # Usar la primera hoja
        df = excel_file.parse(sheet_names[0])

        extra_info = f" (hoja '{sheet_names[0]}')" if len(sheet_names) > 1 else ""

        total_filas = len(df)
        filas_procesadas = 0
        filas_con_error = 0
        errores = []
        empleados_fechas_procesadas = set()  # Para rastrear qué calcular después
        fechas_detectadas = set()  # Rango real del archivo, para empleados de confianza (ver abajo)
        asistencias_calculadas = 0
        errores_asistencia = []

        # Procesar cada fila
        for idx, row in df.iterrows():
            try:
                # Estructura del Excel: ID | NOMBRE | DEPARTAMENTO | FECHA | ENTRADA | SALIDA | ...
                empleado_id = str(row.iloc[0]).strip()      # Columna 0: ID
                fecha_str = str(row.iloc[3]).strip()         # Columna 3: FECHA
                hora_entrada = str(row.iloc[4]).strip() if pd.notna(row.iloc[4]) else None  # Columna 4
                hora_salida = str(row.iloc[5]).strip() if pd.notna(row.iloc[5]) else None    # Columna 5

                # Saltar si no hay datos
                if not fecha_str or (fecha_str.lower() == 'nan'):
                    continue

                # Buscar empleado por ID
                try:
                    emp_id = int(float(empleado_id))
                except (ValueError, TypeError):
                    errores.append({
                        "fila": idx + 2,
                        "error": f"ID de empleado inválido: {empleado_id}"
                    })
                    filas_con_error += 1
                    continue

                empleado = db.query(Empleado).filter(Empleado.id == emp_id).first()

                if not empleado:
                    errores.append({
                        "fila": idx + 2,
                        "error": f"Empleado con ID {emp_id} no encontrado"
                    })
                    filas_con_error += 1
                    continue

                # Parsear fecha
                try:
                    fecha = pd.to_datetime(fecha_str).date()
                except:
                    errores.append({
                        "fila": idx + 2,
                        "error": f"Fecha inválida: {fecha_str}"
                    })
                    filas_con_error += 1
                    continue

                # Rango real del archivo (independiente de si la fila termina en error),
                # usado más abajo para generar presente_exento a empleados de confianza.
                fechas_detectadas.add(fecha)

                periodo = asistencia_services.get_periodo_asistencia(db, fecha.year, fecha.month)
                if periodo and periodo.estado.value == "cerrado":
                    errores.append({
                        "fila": idx + 2,
                        "error": f"El período {fecha.year}-{fecha.month:02d} está cerrado. Reábralo antes de importar marcaciones.",
                    })
                    filas_con_error += 1
                    continue

                # Crear marcación de ENTRADA
                if hora_entrada and hora_entrada.lower() != 'nan':
                    try:
                        hora_entrada_time = pd.to_datetime(hora_entrada, format='%H:%M').time()
                        fecha_hora_entrada = datetime.combine(fecha, hora_entrada_time)

                        marcacion_entrada = Marcacion(
                            id_empleado=empleado.id,
                            fecha_hora_marcacion=fecha_hora_entrada,
                            tipo_marcacion=TipoMarcacionEnum.ENTRADA,
                            origen_dato=OrigenDatoEnum.Excel,
                            id_archivo_excel=archivo.id
                        )
                        db.add(marcacion_entrada)
                        empleados_fechas_procesadas.add((empleado.id, fecha))
                    except Exception as e:
                        errores.append({
                            "fila": idx + 2,
                            "error": f"Hora entrada inválida: {hora_entrada} - {str(e)}"
                        })
                        filas_con_error += 1
                        continue

                # Crear marcación de SALIDA
                if hora_salida and hora_salida.lower() != 'nan':
                    try:
                        hora_salida_time = pd.to_datetime(hora_salida, format='%H:%M').time()
                        fecha_hora_salida = datetime.combine(fecha, hora_salida_time)

                        marcacion_salida = Marcacion(
                            id_empleado=empleado.id,
                            fecha_hora_marcacion=fecha_hora_salida,
                            tipo_marcacion=TipoMarcacionEnum.SALIDA,
                            origen_dato=OrigenDatoEnum.Excel,
                            id_archivo_excel=archivo.id
                        )
                        db.add(marcacion_salida)
                        empleados_fechas_procesadas.add((empleado.id, fecha))
                    except Exception as e:
                        errores.append({
                            "fila": idx + 2,
                            "error": f"Hora salida inválida: {hora_salida} - {str(e)}"
                        })
                        filas_con_error += 1
                        continue

                # ═══════════════════════════════════════════════════════════
                # FIX 3: COLUMNAS G-H — Solo 1 turno, si hay datos = duplicado
                # No se procesan como marcaciones, se registran como advertencia
                # ═══════════════════════════════════════════════════════════
                hora_entrada2 = str(row.iloc[6]).strip() if len(row) > 6 and pd.notna(row.iloc[6]) else None
                hora_salida2  = str(row.iloc[7]).strip() if len(row) > 7 and pd.notna(row.iloc[7]) else None

                tiene_entrada2 = hora_entrada2 and hora_entrada2.lower() != 'nan'
                tiene_salida2  = hora_salida2  and hora_salida2.lower()  != 'nan'

                if tiene_entrada2 or tiene_salida2:
                    errores.append({
                        "fila": idx + 2,
                        "empleado_id": empleado.id,
                        "fecha": str(fecha),
                        "error": (
                            f"Posible duplicado detectado en columnas G-H: "
                            f"Entrada2='{hora_entrada2 if tiene_entrada2 else '-'}', "
                            f"Salida2='{hora_salida2 if tiene_salida2 else '-'}'. "
                            f"Sistema de 1 turno: revisar manualmente."
                        ),
                        "tipo": "advertencia_duplicado"
                    })
                    filas_con_error += 1

                filas_procesadas += 1

            except Exception as e:
                errores.append({
                    "fila": idx + 2,
                    "error": f"Error general: {str(e)}"
                })
                filas_con_error += 1

        # Commit de todas las marcaciones
        try:
            db.commit()
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al guardar marcaciones: {str(e)}"
            )

        # Detectar incidencias (huérfanas y duplicadas) para todas las marcaciones procesadas
        logger = logging.getLogger(__name__)
        for id_empleado, fecha in empleados_fechas_procesadas:
            try:
                _detectar_incidencias_batch(db, id_empleado, fecha, archivo.id)
            except Exception as e:
                db.rollback()  # ← FIX 2: recuperar sesión para evitar "Session rolled back" en siguiente iteración
                logger.warning(
                    f"Error detectando incidencias para empleado {id_empleado} en {fecha}: {str(e)}"
                )

        # Recalcular asistencia diaria una vez que todas las marcaciones e
        # incidencias del archivo ya están persistidas. Equivale a ejecutar el
        # procesamiento/recalculo diario para cada empleado y fecha importados.
        for id_empleado, fecha in empleados_fechas_procesadas:
            calculada, detalle_error = _recalcular_asistencia_dia(db, id_empleado, fecha)
            if calculada:
                asistencias_calculadas += 1
            else:
                error_asistencia = {
                    "empleado_id": id_empleado,
                    "fecha": str(fecha),
                    "error": detalle_error,
                }
                errores_asistencia.append(error_asistencia)
                logger.warning(
                    f"No se pudo recalcular asistencia para empleado {id_empleado} en {fecha}: {detalle_error}"
                )

        # Generar presente_exento para empleados de cargo de confianza en el rango
        # de fechas del archivo. Estos empleados están exentos de marcar huella,
        # por lo que nunca aparecen en `empleados_fechas_procesadas` — sin este
        # paso nunca se les generaría asistencia_diaria (ver CLAUDE.md, sección
        # "Decisión arquitectónica activa").
        fecha_desde = min(fechas_detectadas) if fechas_detectadas else None
        fecha_hasta = max(fechas_detectadas) if fechas_detectadas else None
        empleados_confianza_procesados, errores_confianza = _generar_asistencia_confianza(
            db, fecha_desde, fecha_hasta, empleados_fechas_procesadas
        )
        errores_asistencia.extend(errores_confianza)

        # Actualizar archivo: completado si no hay errores, error si los hay
        estado_final = "completado" if filas_con_error == 0 else "error"
        update_archivo(db, archivo.id, ArchivoExcelUpdate(
            estado_procesamiento=estado_final,
            total_filas=total_filas,
            filas_procesadas=filas_procesadas,
            filas_con_error=filas_con_error,
            log_errores=json.dumps(errores, ensure_ascii=False) if errores else None
        ))

        return {
            "archivo_id": archivo.id,
            "nombre_archivo": file.filename,
            "estado": "completado" if filas_con_error == 0 else "completado_con_errores",
            "mensaje": f"Procesado: {filas_procesadas}/{total_filas} filas{extra_info}",
            "total_filas": total_filas,
            "filas_procesadas": filas_procesadas,
            "filas_con_error": filas_con_error,
            "errores": errores if errores else None,
            "asistencias_calculadas": asistencias_calculadas,
            "errores_asistencia": errores_asistencia if errores_asistencia else None,
            "empleados_confianza_procesados": empleados_confianza_procesados,
            "fecha_desde": str(fecha_desde) if fecha_desde else None,
            "fecha_hasta": str(fecha_hasta) if fecha_hasta else None,
        }

    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        update_archivo(db, archivo.id, ArchivoExcelUpdate(
            estado_procesamiento="error",
            log_errores=json.dumps({"error_general": str(e)}, ensure_ascii=False)
        ))

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error al procesar archivo Excel: {str(e)}"
        )


# ============================================================
# DETECCIÓN DE INCIDENCIAS
# ============================================================

def _detectar_incidencias_batch(db: Session, id_empleado: int, fecha: date, id_archivo_excel: Optional[int] = None):
    """
    Detecta y recalcula incidencias para un empleado en una fecha específica.
    Se ejecuta DESPUÉS de procesar todas las marcaciones de un archivo.

    IMPORTANTE: La búsqueda de parejas y duplicadas se hace sobre TODAS las
    marcaciones del día (sin filtrar por archivo), para reflejar la realidad
    de la jornada completa.

    Tipos de incidencia:
    - huerfana: entrada sin salida o viceversa en el día completo
    - duplicada: dos del mismo tipo en ventana de 5 minutos (en el día completo)
    - inconsistente: es tanto huérfana como duplicada
    """
    from datetime import time

    fecha_inicio = datetime.combine(fecha, time.min)
    fecha_fin = datetime.combine(fecha, time.max)

    # Obtener marcaciones a evaluar:
    # Si se especifica archivo → solo las del archivo actual (las recién insertadas)
    # Si no → todas las del día
    filtros_base = [
        Marcacion.id_empleado == id_empleado,
        Marcacion.fecha_hora_marcacion >= fecha_inicio,
        Marcacion.fecha_hora_marcacion <= fecha_fin,
    ]
    if id_archivo_excel is not None:
        filtros_base.append(Marcacion.id_archivo_excel == id_archivo_excel)

    marcaciones_a_evaluar = db.query(Marcacion).filter(
        and_(*filtros_base)
    ).order_by(Marcacion.fecha_hora_marcacion).all()

    if not marcaciones_a_evaluar:
        return

    # --- Primera pasada: detectar y asignar flags en ORM ---
    resultados = []
    for marcacion in marcaciones_a_evaluar:
        es_duplicada = False
        es_huerfana = False

        # --- Detectar duplicadas ---
        # Busca en TODAS las marcaciones del día (no solo del archivo)
        delta = timedelta(minutes=5)
        duplicadas = db.query(Marcacion).filter(
            and_(
                Marcacion.id_empleado == id_empleado,
                Marcacion.tipo_marcacion == marcacion.tipo_marcacion,
                Marcacion.id != marcacion.id,
                Marcacion.fecha_hora_marcacion.between(
                    marcacion.fecha_hora_marcacion - delta,
                    marcacion.fecha_hora_marcacion + delta,
                ),
            )
        ).count()

        if duplicadas > 0:
            marcacion.es_duplicada = True
            es_duplicada = True
        else:
            marcacion.es_duplicada = False

        # --- Detectar huérfanas ---
        # Busca en TODAS las marcaciones del día (no solo del archivo)
        tipo_opuesto = (
            TipoMarcacionEnum.SALIDA
            if marcacion.tipo_marcacion == TipoMarcacionEnum.ENTRADA
            else TipoMarcacionEnum.ENTRADA
        )

        pareja = db.query(Marcacion).filter(
            and_(
                Marcacion.id_empleado == id_empleado,
                Marcacion.tipo_marcacion == tipo_opuesto,
                func.date(Marcacion.fecha_hora_marcacion) == fecha,
            )
        ).first()

        if not pareja:
            marcacion.es_huerfana = True
            es_huerfana = True
        else:
            marcacion.es_huerfana = False

        resultados.append((marcacion.id, es_huerfana, es_duplicada))

    # Flush para enviar UPDATEs a la BD (dispara trigger de es_huerfana si existe)
    db.flush()

    # --- Segunda pasada: crear/actualizar/eliminar incidencias ---
    for marcacion_id, es_huerfana, es_duplicada in resultados:
        necesita_incidencia = es_huerfana or es_duplicada

        if necesita_incidencia:
            if es_huerfana and es_duplicada:
                tipo_incidencia = TipoIncidenciaEnum.inconsistente
            elif es_duplicada:
                tipo_incidencia = TipoIncidenciaEnum.duplicada
            else:
                tipo_incidencia = TipoIncidenciaEnum.huerfana

            incidencia_actual = db.query(IncidenciaMarcacion).filter(
                IncidenciaMarcacion.id_marcacion == marcacion_id
            ).first()

            if incidencia_actual:
                if incidencia_actual.tipo_incidencia != tipo_incidencia:
                    incidencia_actual.tipo_incidencia = tipo_incidencia
            else:
                db.add(IncidenciaMarcacion(
                    id_marcacion=marcacion_id,
                    tipo_incidencia=tipo_incidencia,
                ))
        else:
            incidencia_actual = db.query(IncidenciaMarcacion).filter(
                IncidenciaMarcacion.id_marcacion == marcacion_id
            ).first()
            if incidencia_actual:
                db.delete(incidencia_actual)

    db.commit()


def _detectar_incidencias(db: Session, marcacion: Marcacion):
    """
    Detecta incidencias en una marcación recién creada.

    Tipos de incidencia:
    - huerfana: No tiene pareja del tipo opuesto
    - duplicada: Dos marcaciones del mismo tipo consecutivas
    - inconsistente: Es tanto huérfana como duplicada
    """
    es_duplicada = False
    es_huerfana = False

    # Detectar duplicadas (mismo tipo en ventana de 5 minutos)
    delta = timedelta(minutes=5)
    duplicadas = db.query(Marcacion).filter(
        and_(
            Marcacion.id_empleado == marcacion.id_empleado,
            Marcacion.tipo_marcacion == marcacion.tipo_marcacion,
            Marcacion.id != marcacion.id,
            Marcacion.fecha_hora_marcacion.between(
                marcacion.fecha_hora_marcacion - delta,
                marcacion.fecha_hora_marcacion + delta
            )
        )
    ).count()

    if duplicadas > 0:
        marcacion.es_duplicada = True
        es_duplicada = True

    # Detectar huérfanas (sin pareja en el día)
    fecha = marcacion.fecha_hora_marcacion.date()
    tipo_opuesto = TipoMarcacionEnum.SALIDA if marcacion.tipo_marcacion == TipoMarcacionEnum.ENTRADA else TipoMarcacionEnum.ENTRADA

    pareja = db.query(Marcacion).filter(
        and_(
            Marcacion.id_empleado == marcacion.id_empleado,
            Marcacion.tipo_marcacion == tipo_opuesto,
            func.date(Marcacion.fecha_hora_marcacion) == fecha
        )
    ).first()

    if not pareja:
        marcacion.es_huerfana = True
        es_huerfana = True

    # Flush para enviar UPDATEs a la BD (dispara trigger de es_huerfana si existe)
    db.flush()

    # Crear o actualizar incidencia después del flush para que el trigger
    # de BD (si existe) ya haya creado la fila y evitar UniqueViolation.
    if es_huerfana or es_duplicada:
        if es_huerfana and es_duplicada:
            tipo_incidencia = TipoIncidenciaEnum.inconsistente
        elif es_duplicada:
            tipo_incidencia = TipoIncidenciaEnum.duplicada
        else:
            tipo_incidencia = TipoIncidenciaEnum.huerfana

        incidencia_existente = db.query(IncidenciaMarcacion).filter(
            IncidenciaMarcacion.id_marcacion == marcacion.id
        ).first()

        if incidencia_existente:
            if incidencia_existente.tipo_incidencia != tipo_incidencia:
                incidencia_existente.tipo_incidencia = tipo_incidencia
        else:
            incidencia = IncidenciaMarcacion(
                id_marcacion=marcacion.id,
                tipo_incidencia=tipo_incidencia
            )
            db.add(incidencia)

    db.commit()
