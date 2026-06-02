"""
Servicios de negocio para metricas de dashboard.

VERSIÓN: 2.0.1 - Fix para error 500 en horas-trabajadas-mes
"""

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session


def get_retrasos_por_mes(db: Session, meses_atras: int = 5) -> list[dict[str, Any]]:
    """Obtiene metricas de retraso por mes para los ultimos N meses con datos."""

    sql = text(
        """
        SELECT
            TO_CHAR(metricas.mes, 'YYYY-MM') AS mes,
            metricas.total_dias_registrados,
            metricas.dias_con_retraso,
            metricas.total_minutos_retraso,
            metricas.promedio_minutos_retraso
        FROM (
            SELECT
                DATE_TRUNC('month', ad.fecha)::date AS mes,
                COUNT(*)::int AS total_dias_registrados,
                COUNT(*) FILTER (WHERE ad.minutos_retraso > 0)::int AS dias_con_retraso,
                COALESCE(SUM(ad.minutos_retraso), 0)::int AS total_minutos_retraso,
                COALESCE(
                    ROUND(
                        AVG(ad.minutos_retraso) FILTER (WHERE ad.minutos_retraso > 0),
                        2
                    ),
                    0
                ) AS promedio_minutos_retraso
            FROM rrhh.asistencia_diaria ad
            GROUP BY DATE_TRUNC('month', ad.fecha)
            ORDER BY DATE_TRUNC('month', ad.fecha) DESC
            LIMIT :meses_atras
        ) AS metricas
        ORDER BY metricas.mes ASC
        """
    )

    rows = db.execute(sql, {"meses_atras": meses_atras}).mappings().all()

    return [
        {
            "mes": row["mes"],
            "total_dias": int(row["total_dias_registrados"] or 0),
            "dias_con_retraso": int(row["dias_con_retraso"] or 0),
            "total_minutos": int(row["total_minutos_retraso"] or 0),
            "promedio_minutos": float(row["promedio_minutos_retraso"] or 0),
        }
        for row in rows
    ]


def get_horas_trabajadas_mes(db: Session, anio: int, mes: int) -> dict[str, Any]:
    """Obtiene detalle por empleado y resumen global de horas trabajadas del mes."""

    try:
        inicio_mes = date(anio, mes, 1)
    except ValueError as e:
        raise ValueError(f"Parámetros de fecha inválidos: año={anio}, mes={mes}. Error: {e}")

    # Consulta que incluye solo empleados con registros en asistencia_diaria
    sql = text(
        """
        SELECT
            e.id AS id_empleado,
            e.nombres,
            e.apellidos,
            e.id_cargo,
            e.id_departamento,
            COALESCE(SUM(ad.minutos_trabajados), 0)::integer AS total_minutos_trabajados,
            ROUND(COALESCE(SUM(ad.minutos_trabajados), 0)::numeric / 60.0, 2) AS total_horas_trabajadas,
            COUNT(*) FILTER (WHERE ad.tipo_dia IN ('presente', 'presente_exento'))::integer AS dias_presentes,
            COUNT(*) FILTER (WHERE COALESCE(ad.horas_extra, 0) > 0)::integer AS dias_con_horas_extra,
            COALESCE(ROUND(SUM(ad.horas_extra), 2), 0.0) AS total_horas_extra
        FROM rrhh.asistencia_diaria ad
        INNER JOIN rrhh.empleado e ON e.id = ad.id_empleado
        WHERE EXTRACT(YEAR FROM ad.fecha) = :anio
          AND EXTRACT(MONTH FROM ad.fecha) = :mes
        GROUP BY e.id, e.nombres, e.apellidos, e.id_cargo, e.id_departamento
        ORDER BY total_horas_trabajadas DESC, e.apellidos, e.nombres
        """
    )

    rows = db.execute(sql, {"anio": anio, "mes": mes}).mappings().all()

    por_empleado = [_map_horas_empleado_row(row) for row in rows]

    total_horas_empresa = sum(item["total_horas_trabajadas"] for item in por_empleado)
    promedio_horas = round(total_horas_empresa / len(por_empleado), 2) if por_empleado else 0.0

    top_3 = [
        {
            "id_empleado": item["id_empleado"],
            "nombre_completo": item["nombre_completo"],
            "total_horas_trabajadas": item["total_horas_trabajadas"],
        }
        for item in por_empleado[:3]
    ]

    bottom_3_source = sorted(
        por_empleado,
        key=lambda item: (item["total_horas_trabajadas"], item["nombre_completo"]),
    )
    bottom_3 = [
        {
            "id_empleado": item["id_empleado"],
            "nombre_completo": item["nombre_completo"],
            "total_horas_trabajadas": item["total_horas_trabajadas"],
        }
        for item in bottom_3_source[:3]
    ]

    return {
        "resumen": {
            "promedio_horas_por_empleado": round(promedio_horas, 2),
            "total_horas_empresa": round(total_horas_empresa, 2),
            "empleados_con_mas_horas": top_3,
            "empleados_con_menos_horas": bottom_3,
        },
        "por_empleado": por_empleado,
    }


def get_cumpleanos_proximos(db: Session, dias_adelante: int = 30) -> list[dict[str, Any]]:
    """Obtiene empleados activos con cumpleanos proximos en el rango indicado."""

    hoy = date.today()

    sql = text(
        """
        SELECT
            e.id,
            e.nombres,
            e.apellidos,
            e.fecha_nacimiento,
            e.id_departamento,
            c.nombre AS cargo
        FROM rrhh.empleado e
        JOIN rrhh.cargo c ON c.id = e.id_cargo
        WHERE e.estado = 'activo'
        """
    )
    rows = db.execute(sql).mappings().all()

    resultados: list[dict[str, Any]] = []
    for row in rows:
        fecha_nacimiento = row["fecha_nacimiento"]
        proximo_cumple = _proximo_cumpleanos(fecha_nacimiento, hoy)
        dias_hasta = (proximo_cumple - hoy).days

        if 0 <= dias_hasta <= dias_adelante:
            resultados.append(
                {
                    "id": int(row["id"]),
                    "nombre": f"{row['nombres']} {row['apellidos']}",
                    "fecha_nacimiento": fecha_nacimiento,
                    "dias_hasta": dias_hasta,
                    "id_departamento": int(row["id_departamento"]),
                    "cargo": row["cargo"],
                }
            )

    resultados.sort(key=lambda item: (item["dias_hasta"], item["nombre"]))
    return resultados


def _map_horas_empleado_row(row: Any) -> dict[str, Any]:
    """Mapea una fila SQL a estructura del detalle por empleado."""

    total_horas = row["total_horas_trabajadas"]
    total_horas_extra = row["total_horas_extra"]

    if isinstance(total_horas, Decimal):
        total_horas = float(total_horas)
    if isinstance(total_horas_extra, Decimal):
        total_horas_extra = float(total_horas_extra)

    nombre_completo = f"{row['nombres']} {row['apellidos']}"

    return {
        "id_empleado": int(row["id_empleado"]),
        "nombres": row["nombres"],
        "apellidos": row["apellidos"],
        "nombre_completo": nombre_completo,
        "id_cargo": int(row["id_cargo"]),
        "id_departamento": int(row["id_departamento"]),
        "total_minutos_trabajados": int(row["total_minutos_trabajados"] or 0),
        "total_horas_trabajadas": float(total_horas or 0),
        "dias_presentes": int(row["dias_presentes"] or 0),
        "dias_con_horas_extra": int(row["dias_con_horas_extra"] or 0),
        "total_horas_extra": float(total_horas_extra or 0),
    }


def _proximo_cumpleanos(fecha_nacimiento: date, hoy: date) -> date:
    """Calcula la proxima fecha de cumpleanos de una persona desde una fecha base."""

    cumple_este_anio = _safe_birthday_date(hoy.year, fecha_nacimiento.month, fecha_nacimiento.day)
    if cumple_este_anio >= hoy:
        return cumple_este_anio
    return _safe_birthday_date(hoy.year + 1, fecha_nacimiento.month, fecha_nacimiento.day)


def _safe_birthday_date(year: int, month: int, day: int) -> date:
    """Construye fecha de cumpleanos ajustando 29/02 a 28/02 en anio no bisiesto."""

    try:
        return date(year, month, day)
    except ValueError:
        if month == 2 and day == 29:
            return date(year, 2, 28)
        raise
