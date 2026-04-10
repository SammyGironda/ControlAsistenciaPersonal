"""
Services para Marcaciones - Lógica de negocio.
Incluye procesamiento de archivos Excel con Pandas.
"""

from datetime import datetime, date, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from fastapi import HTTPException, status, UploadFile
import pandas as pd
import json
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


def get_all_archivos(db: Session, skip: int = 0, limit: int = 100) -> List[ArchivoExcel]:
    """Lista todos los archivos subidos."""
    return db.query(ArchivoExcel).order_by(ArchivoExcel.fecha_subida.desc()).offset(skip).limit(limit).all()


# ============================================================
# INCIDENCIAS - CRUD
# ============================================================

def get_incidencias_pendientes(db: Session, skip: int = 0, limit: int = 100) -> List[IncidenciaMarcacion]:
    """Obtiene incidencias pendientes de resolución."""
    return db.query(IncidenciaMarcacion).filter(
        IncidenciaMarcacion.estado_resolucion == EstadoResolucionEnum.pendiente
    ).offset(skip).limit(limit).all()


def update_incidencia(db: Session, incidencia_id: int, data: IncidenciaMarcacionUpdate) -> IncidenciaMarcacion:
    """Actualiza el estado de una incidencia."""
    incidencia = db.query(IncidenciaMarcacion).filter(IncidenciaMarcacion.id == incidencia_id).first()
    if not incidencia:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe la incidencia con ID {incidencia_id}"
        )

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(incidencia, key, value)

    # Si se marca como resuelta, agregar fecha
    if data.estado_resolucion == EstadoResolucionEnum.resuelto.value and not incidencia.fecha_resolucion:
        incidencia.fecha_resolucion = datetime.now()

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
    # Guardar archivo físicamente
    Path(upload_dir).mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_{file.filename}"
    filepath = Path(upload_dir) / filename

    with open(filepath, "wb") as f:
        f.write(file.file.read())

    # Crear registro en BD
    archivo = create_archivo_excel(db, ArchivoExcelCreate(
        nombre_archivo=file.filename,
        ruta_storage=str(filepath),
        id_subido_por=id_subido_por
    ))

    # Actualizar estado a procesando
    update_archivo(db, archivo.id, ArchivoExcelUpdate(estado_procesamiento="procesando"))

    try:
        # Leer Excel con Pandas
        df = pd.read_excel(filepath, engine='openpyxl')

        total_filas = len(df)
        filas_procesadas = 0
        filas_con_error = 0
        errores = []

        # Procesar cada fila
        for idx, row in df.iterrows():
            try:
                # Extraer datos
                ci_completo = str(row.iloc[0]).strip()  # Primera columna: CI
                fecha_str = str(row.iloc[1]).strip()     # Segunda columna: Fecha
                hora_entrada = str(row.iloc[2]).strip() if pd.notna(row.iloc[2]) else None
                hora_salida = str(row.iloc[3]).strip() if pd.notna(row.iloc[3]) else None

                # Buscar empleado por CI
                empleado = db.query(Empleado).filter(
                    func.concat(
                        Empleado.ci_numero, '-', Empleado.complemento_dep
                    ) == ci_completo
                ).first()

                if not empleado:
                    errores.append({
                        "fila": idx + 2,  # +2 porque Excel empieza en 1 y tiene header
                        "error": f"CI {ci_completo} no encontrado"
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
                    except Exception as e:
                        errores.append({
                            "fila": idx + 2,
                            "error": f"Hora salida inválida: {hora_salida} - {str(e)}"
                        })
                        filas_con_error += 1
                        continue

                filas_procesadas += 1

            except Exception as e:
                errores.append({
                    "fila": idx + 2,
                    "error": f"Error general: {str(e)}"
                })
                filas_con_error += 1

        # Commit de todas las marcaciones
        db.commit()

        # Actualizar archivo a completado
        update_archivo(db, archivo.id, ArchivoExcelUpdate(
            estado_procesamiento="completado" if filas_con_error == 0 else "error",
            total_filas=total_filas,
            filas_procesadas=filas_procesadas,
            filas_con_error=filas_con_error,
            log_errores=json.dumps(errores, ensure_ascii=False) if errores else None
        ))

        return {
            "archivo_id": archivo.id,
            "nombre_archivo": file.filename,
            "estado": "completado" if filas_con_error == 0 else "completado_con_errores",
            "mensaje": f"Procesado: {filas_procesadas}/{total_filas} filas",
            "total_filas": total_filas,
            "filas_procesadas": filas_procesadas,
            "filas_con_error": filas_con_error,
            "errores": errores if errores else None
        }

    except Exception as e:
        # Error catastrófico
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

def _detectar_incidencias(db: Session, marcacion: Marcacion):
    """
    Detecta incidencias en una marcación recién creada.

    Tipos de incidencia:
    - huerfana: No tiene pareja del tipo opuesto
    - duplicada: Dos marcaciones del mismo tipo consecutivas
    """
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

        # Crear incidencia si no existe
        incidencia_existente = db.query(IncidenciaMarcacion).filter(
            IncidenciaMarcacion.id_marcacion == marcacion.id
        ).first()

        if not incidencia_existente:
            incidencia = IncidenciaMarcacion(
                id_marcacion=marcacion.id,
                tipo_incidencia=TipoIncidenciaEnum.duplicada
            )
            db.add(incidencia)

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

        # Crear incidencia si no existe
        incidencia_existente = db.query(IncidenciaMarcacion).filter(
            IncidenciaMarcacion.id_marcacion == marcacion.id
        ).first()

        if not incidencia_existente:
            incidencia = IncidenciaMarcacion(
                id_marcacion=marcacion.id,
                tipo_incidencia=TipoIncidenciaEnum.huerfana
            )
            db.add(incidencia)

    db.commit()
