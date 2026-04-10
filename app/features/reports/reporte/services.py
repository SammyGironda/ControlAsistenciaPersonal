"""
Servicios de negocio para el modulo de reportes.
Genera archivos XLSX/PDF y registra bitacora en tabla rrhh.reporte.
"""

from calendar import monthrange
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from fastapi import HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.features.employees.empleado.models import Empleado
from app.features.reports.reporte.models import Reporte, TipoReporteEnum, FormatoReporteEnum
from app.features.reports.reporte.schemas import (
    ReporteAsistenciaMensualRequest,
    ReporteIndividualRequest,
    ReportePlanillaRequest,
    ReporteUpdate,
    ReporteVacacionesRequest,
)

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
except Exception:
    letter = None
    canvas = None


settings = get_settings()


def _periodo_mes(anio: int, mes: int) -> tuple[date, date]:
    """Calcula fecha de inicio y fin de mes."""

    ultimo_dia = monthrange(anio, mes)[1]
    return date(anio, mes, 1), date(anio, mes, ultimo_dia)


def _asegurar_carpeta(tipo_reporte: TipoReporteEnum) -> Path:
    """Crea y retorna la carpeta de salida para un tipo de reporte."""

    carpeta = Path(settings.REPORTS_DIR) / tipo_reporte.value
    carpeta.mkdir(parents=True, exist_ok=True)
    return carpeta


def _nombre_archivo(tipo_reporte: TipoReporteEnum, extension: str) -> str:
    """Construye nombre unico para archivo exportado."""

    marca_tiempo = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{tipo_reporte.value}_{marca_tiempo}.{extension}"


def _registrar_reporte(
    db: Session,
    *,
    nombre: str,
    tipo_reporte: TipoReporteEnum,
    id_generado_por: Optional[int],
    id_departamento: Optional[int],
    id_empleado: Optional[int],
    periodo_inicio: date,
    periodo_fin: date,
    ruta_archivo: str,
    formato: FormatoReporteEnum,
) -> Reporte:
    """Inserta registro de bitacora en rrhh.reporte."""

    reporte = Reporte(
        nombre=nombre,
        tipo_reporte=tipo_reporte,
        id_generado_por=id_generado_por,
        id_departamento=id_departamento,
        id_empleado=id_empleado,
        periodo_inicio=periodo_inicio,
        periodo_fin=periodo_fin,
        ruta_archivo=ruta_archivo,
        formato=formato,
        fecha_generacion=datetime.now(),
        activo=True,
    )
    db.add(reporte)
    db.commit()
    db.refresh(reporte)
    return reporte


def _exportar_xlsx(filas: list[dict], ruta_archivo: Path, nombre_hoja: str) -> None:
    """Exporta un listado de diccionarios a archivo XLSX."""

    dataframe = pd.DataFrame(filas)
    dataframe.to_excel(ruta_archivo, index=False, sheet_name=nombre_hoja)


def obtener_reporte(db: Session, reporte_id: int) -> Reporte:
    """Obtiene reporte por ID o lanza 404."""

    reporte = db.query(Reporte).filter(Reporte.id == reporte_id).first()
    if not reporte:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reporte con ID {reporte_id} no encontrado",
        )
    return reporte


def listar_reportes(
    db: Session,
    *,
    tipo_reporte: Optional[TipoReporteEnum] = None,
    formato: Optional[FormatoReporteEnum] = None,
    id_generado_por: Optional[int] = None,
    activo: Optional[bool] = None,
    skip: int = 0,
    limit: int = 100,
) -> list[Reporte]:
    """Lista reportes con filtros opcionales."""

    query = db.query(Reporte)

    if tipo_reporte is not None:
        query = query.filter(Reporte.tipo_reporte == tipo_reporte)

    if formato is not None:
        query = query.filter(Reporte.formato == formato)

    if id_generado_por is not None:
        query = query.filter(Reporte.id_generado_por == id_generado_por)

    if activo is not None:
        query = query.filter(Reporte.activo == activo)

    return query.order_by(Reporte.fecha_generacion.desc()).offset(skip).limit(limit).all()


def actualizar_reporte(db: Session, reporte_id: int, data: ReporteUpdate) -> Reporte:
    """Actualiza atributos editables del reporte."""

    reporte = obtener_reporte(db, reporte_id)

    if data.activo is not None:
        reporte.activo = data.activo

    db.commit()
    db.refresh(reporte)
    return reporte


def eliminar_reporte(db: Session, reporte_id: int) -> Reporte:
    """Soft delete de reporte (marca activo=False)."""

    reporte = obtener_reporte(db, reporte_id)
    reporte.activo = False
    db.commit()
    db.refresh(reporte)
    return reporte


def eliminar_reporte_permanente(db: Session, reporte_id: int) -> None:
    """Hard delete de reporte."""

    reporte = obtener_reporte(db, reporte_id)
    db.delete(reporte)
    db.commit()


def ruta_reporte_descarga(db: Session, reporte_id: int) -> Path:
    """Valida existencia fisica del archivo y retorna su ruta."""

    reporte = obtener_reporte(db, reporte_id)
    ruta = Path(reporte.ruta_archivo)

    if not ruta.exists() or not ruta.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El archivo fisico del reporte no existe en almacenamiento",
        )

    return ruta


def generar_reporte_asistencia_mensual(db: Session, data: ReporteAsistenciaMensualRequest) -> Reporte:
    """Genera reporte mensual de asistencia en formato XLSX."""

    periodo_inicio, periodo_fin = _periodo_mes(data.anio, data.mes)

    sql = text(
        """
        SELECT
            v.id_empleado,
            v.nombre_completo,
            v.cargo,
            v.es_cargo_confianza,
            d.id AS id_departamento,
            v.departamento,
            CAST(v.mes AS DATE) AS mes,
            COALESCE(v.total_dias_registro, 0) AS total_dias_registro,
            COALESCE(v.dias_presente, 0) AS dias_presente,
            COALESCE(v.dias_presente_exento, 0) AS dias_presente_exento,
            COALESCE(v.dias_ausente, 0) AS dias_ausente,
            COALESCE(v.dias_feriado, 0) AS dias_feriado,
            COALESCE(v.dias_permiso_parcial, 0) AS dias_permiso_parcial,
            COALESCE(v.dias_licencia_medica, 0) AS dias_licencia_medica,
            COALESCE(v.dias_descanso, 0) AS dias_descanso,
            COALESCE(v.total_minutos_retraso, 0) AS total_minutos_retraso,
            COALESCE(v.total_minutos_trabajados, 0) AS total_minutos_trabajados,
            COALESCE(v.total_horas_extra, 0) AS total_horas_extra,
            COALESCE(v.dias_trabajados_en_feriado, 0) AS dias_trabajados_en_feriado
        FROM rrhh.v_asistencia_mensual v
        JOIN rrhh.empleado e ON e.id = v.id_empleado
        JOIN rrhh.departamento d ON d.id = e.id_departamento
        WHERE v.mes = DATE_TRUNC('month', :periodo_inicio::date)
          AND (:id_departamento IS NULL OR d.id = :id_departamento)
          AND (:id_empleado IS NULL OR v.id_empleado = :id_empleado)
        ORDER BY v.departamento, v.nombre_completo
        """
    )

    filas = db.execute(
        sql,
        {
            "periodo_inicio": periodo_inicio,
            "id_departamento": data.id_departamento,
            "id_empleado": data.id_empleado,
        },
    ).mappings().all()

    carpeta = _asegurar_carpeta(TipoReporteEnum.asistencia_mensual)
    nombre_archivo = _nombre_archivo(TipoReporteEnum.asistencia_mensual, "xlsx")
    ruta_archivo = carpeta / nombre_archivo
    _exportar_xlsx([dict(fila) for fila in filas], ruta_archivo, "AsistenciaMensual")

    return _registrar_reporte(
        db,
        nombre=f"Reporte Asistencia Mensual {data.anio}-{str(data.mes).zfill(2)}",
        tipo_reporte=TipoReporteEnum.asistencia_mensual,
        id_generado_por=data.id_generado_por,
        id_departamento=data.id_departamento,
        id_empleado=data.id_empleado,
        periodo_inicio=periodo_inicio,
        periodo_fin=periodo_fin,
        ruta_archivo=str(ruta_archivo),
        formato=FormatoReporteEnum.XLSX,
    )


def generar_reporte_planilla(db: Session, data: ReportePlanillaRequest) -> Reporte:
    """Genera reporte de planilla mensual en formato XLSX."""

    periodo_inicio, periodo_fin = _periodo_mes(data.anio, data.mes)

    sql = text(
        """
        SELECT
            id_empleado,
            nombre_completo,
            cargo,
            id_departamento,
            departamento,
            mes,
            salario_base,
            minutos_retraso_mes,
            dias_ausente_mes,
            descuento_retraso_bs,
            descuento_ausencia_bs,
            salario_descuento_preimpuestos,
            porcentaje_afp_laboral,
            monto_afp_laboral,
            porcentaje_rc_iva,
            monto_rc_iva,
            total_descuentos,
            salario_neto_estimado
        FROM rrhh.v_saldo_impuestos_planilla
        WHERE mes = DATE_TRUNC('month', :periodo_inicio::date)
          AND (:id_departamento IS NULL OR id_departamento = :id_departamento)
          AND (:id_empleado IS NULL OR id_empleado = :id_empleado)
        ORDER BY departamento, nombre_completo
        """
    )

    filas = db.execute(
        sql,
        {
            "periodo_inicio": periodo_inicio,
            "id_departamento": data.id_departamento,
            "id_empleado": data.id_empleado,
        },
    ).mappings().all()

    carpeta = _asegurar_carpeta(TipoReporteEnum.planilla)
    nombre_archivo = _nombre_archivo(TipoReporteEnum.planilla, "xlsx")
    ruta_archivo = carpeta / nombre_archivo
    _exportar_xlsx([dict(fila) for fila in filas], ruta_archivo, "Planilla")

    return _registrar_reporte(
        db,
        nombre=f"Reporte Planilla {data.anio}-{str(data.mes).zfill(2)}",
        tipo_reporte=TipoReporteEnum.planilla,
        id_generado_por=data.id_generado_por,
        id_departamento=data.id_departamento,
        id_empleado=data.id_empleado,
        periodo_inicio=periodo_inicio,
        periodo_fin=periodo_fin,
        ruta_archivo=str(ruta_archivo),
        formato=FormatoReporteEnum.XLSX,
    )


def generar_reporte_vacaciones(db: Session, data: ReporteVacacionesRequest) -> Reporte:
    """Genera reporte de vacaciones por gestion en formato XLSX."""

    periodo_inicio = date(data.gestion, 1, 1)
    periodo_fin = date(data.gestion, 12, 31)

    sql = text(
        """
        SELECT
            vrv.id_empleado,
            vrv.nombre_completo,
            vrv.fecha_ingreso,
            vrv.cargo,
            vrv.es_cargo_confianza,
            e.id_departamento,
            d.nombre AS departamento,
            vrv.gestion,
            vrv.total_horas_asignadas,
            vrv.horas_goce_disponibles,
            vrv.horas_sin_goce_disponibles,
            vrv.total_horas_tomadas,
            vrv.horas_pendientes_total,
            vrv.dias_asignados,
            vrv.dias_tomados,
            vrv.dias_pendientes,
            vrv.horas_segun_antiguedad,
            vrv.observacion
        FROM rrhh.v_resumen_vacaciones vrv
        JOIN rrhh.empleado e ON e.id = vrv.id_empleado
        JOIN rrhh.departamento d ON d.id = e.id_departamento
        WHERE vrv.gestion = :gestion
          AND (:id_departamento IS NULL OR e.id_departamento = :id_departamento)
          AND (:id_empleado IS NULL OR vrv.id_empleado = :id_empleado)
        ORDER BY d.nombre, vrv.nombre_completo
        """
    )

    filas = db.execute(
        sql,
        {
            "gestion": data.gestion,
            "id_departamento": data.id_departamento,
            "id_empleado": data.id_empleado,
        },
    ).mappings().all()

    carpeta = _asegurar_carpeta(TipoReporteEnum.vacaciones)
    nombre_archivo = _nombre_archivo(TipoReporteEnum.vacaciones, "xlsx")
    ruta_archivo = carpeta / nombre_archivo
    _exportar_xlsx([dict(fila) for fila in filas], ruta_archivo, "Vacaciones")

    return _registrar_reporte(
        db,
        nombre=f"Reporte Vacaciones {data.gestion}",
        tipo_reporte=TipoReporteEnum.vacaciones,
        id_generado_por=data.id_generado_por,
        id_departamento=data.id_departamento,
        id_empleado=data.id_empleado,
        periodo_inicio=periodo_inicio,
        periodo_fin=periodo_fin,
        ruta_archivo=str(ruta_archivo),
        formato=FormatoReporteEnum.XLSX,
    )


def generar_reporte_individual_pdf(
    db: Session, id_empleado: int, data: ReporteIndividualRequest
) -> Reporte:
    """Genera reporte individual de un empleado en formato PDF."""

    empleado = db.query(Empleado).filter(Empleado.id == id_empleado).first()
    if not empleado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Empleado con ID {id_empleado} no encontrado",
        )

    sql_resumen = text(
        """
        SELECT
            COALESCE(COUNT(*), 0) AS total_dias,
            COALESCE(COUNT(*) FILTER (WHERE ad.tipo_dia = 'presente'), 0) AS dias_presente,
            COALESCE(COUNT(*) FILTER (WHERE ad.tipo_dia = 'ausente'), 0) AS dias_ausente,
            COALESCE(COUNT(*) FILTER (WHERE ad.tipo_dia = 'feriado'), 0) AS dias_feriado,
            COALESCE(COUNT(*) FILTER (WHERE ad.tipo_dia = 'permiso_parcial'), 0) AS dias_permiso_parcial,
            COALESCE(COUNT(*) FILTER (WHERE ad.tipo_dia = 'licencia_medica'), 0) AS dias_licencia_medica,
            COALESCE(SUM(ad.minutos_retraso), 0) AS total_minutos_retraso,
            COALESCE(SUM(ad.minutos_trabajados), 0) AS total_minutos_trabajados
        FROM rrhh.asistencia_diaria ad
        WHERE ad.id_empleado = :id_empleado
          AND ad.fecha BETWEEN :fecha_inicio AND :fecha_fin
        """
    )
    resumen = db.execute(
        sql_resumen,
        {
            "id_empleado": id_empleado,
            "fecha_inicio": data.fecha_inicio,
            "fecha_fin": data.fecha_fin,
        },
    ).mappings().first()

    sql_vacacion = text(
        """
        SELECT
            v.gestion,
            v.horas_correspondientes,
            v.horas_goce_haber,
            v.horas_sin_goce_haber,
            v.horas_tomadas,
            (v.horas_correspondientes - v.horas_tomadas) AS horas_pendientes
        FROM rrhh.vacacion v
        WHERE v.id_empleado = :id_empleado
          AND v.gestion = :gestion
        LIMIT 1
        """
    )
    vacacion = db.execute(
        sql_vacacion,
        {"id_empleado": id_empleado, "gestion": data.fecha_fin.year},
    ).mappings().first()

    if not letter or not canvas:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=(
                "No se pudo generar PDF porque falta la dependencia 'reportlab'."
            ),
        )

    carpeta = _asegurar_carpeta(TipoReporteEnum.individual)
    nombre_archivo = _nombre_archivo(TipoReporteEnum.individual, "pdf")
    ruta_archivo = carpeta / nombre_archivo

    pdf = canvas.Canvas(str(ruta_archivo), pagesize=letter)
    ancho, alto = letter
    posicion_y = alto - 40

    def escribir_linea(texto: str, salto: int = 16) -> None:
        nonlocal posicion_y
        pdf.drawString(40, posicion_y, texto)
        posicion_y -= salto
        if posicion_y < 60:
            pdf.showPage()
            posicion_y = alto - 40

    pdf.setTitle("Reporte Individual de Empleado")
    pdf.setFont("Helvetica-Bold", 14)
    escribir_linea("REPORTE INDIVIDUAL DE EMPLEADO", salto=22)

    pdf.setFont("Helvetica", 10)
    escribir_linea(f"Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    escribir_linea(f"Periodo: {data.fecha_inicio} a {data.fecha_fin}")
    escribir_linea("")

    escribir_linea(f"Empleado ID: {empleado.id}")
    escribir_linea(f"Nombre: {empleado.nombres} {empleado.apellidos}")
    escribir_linea(f"CI: {empleado.ci_completo}")
    escribir_linea(f"Estado: {empleado.estado.value if hasattr(empleado.estado, 'value') else empleado.estado}")
    escribir_linea(f"Fecha ingreso: {empleado.fecha_ingreso}")
    escribir_linea(f"Salario base: Bs {empleado.salario_base}")
    escribir_linea("")

    escribir_linea("Resumen de asistencia")
    escribir_linea(f"- Total dias evaluados: {resumen['total_dias']}")
    escribir_linea(f"- Dias presente: {resumen['dias_presente']}")
    escribir_linea(f"- Dias ausente: {resumen['dias_ausente']}")
    escribir_linea(f"- Dias feriado: {resumen['dias_feriado']}")
    escribir_linea(f"- Dias permiso parcial: {resumen['dias_permiso_parcial']}")
    escribir_linea(f"- Dias licencia medica: {resumen['dias_licencia_medica']}")
    escribir_linea(f"- Minutos retraso: {resumen['total_minutos_retraso']}")
    escribir_linea(f"- Minutos trabajados: {resumen['total_minutos_trabajados']}")
    escribir_linea("")

    if vacacion:
        escribir_linea(f"Saldo vacacional gestion {vacacion['gestion']}")
        escribir_linea(f"- Horas correspondientes: {vacacion['horas_correspondientes']}")
        escribir_linea(f"- Horas goce de haber: {vacacion['horas_goce_haber']}")
        escribir_linea(f"- Horas sin goce de haber: {vacacion['horas_sin_goce_haber']}")
        escribir_linea(f"- Horas tomadas: {vacacion['horas_tomadas']}")
        escribir_linea(f"- Horas pendientes: {vacacion['horas_pendientes']}")
    else:
        escribir_linea(f"No existe saldo vacacional registrado para la gestion {data.fecha_fin.year}")

    pdf.save()

    return _registrar_reporte(
        db,
        nombre=f"Reporte Individual Empleado {id_empleado}",
        tipo_reporte=TipoReporteEnum.individual,
        id_generado_por=data.id_generado_por,
        id_departamento=empleado.id_departamento,
        id_empleado=id_empleado,
        periodo_inicio=data.fecha_inicio,
        periodo_fin=data.fecha_fin,
        ruta_archivo=str(ruta_archivo),
        formato=FormatoReporteEnum.PDF,
    )
