"""
Tests de `_generar_asistencia_confianza` (marcacion/services.py).

Cubre el hueco descrito en CLAUDE.md — "Decisión arquitectónica activa":
un empleado con `cargo.es_cargo_confianza = TRUE` está exento de marcar
huella, por lo tanto nunca aparece en el Excel de marcaciones subido. Sin
esta función, nunca se le generaría `asistencia_diaria` (`presente_exento`)
al migrar del worker diario a la carga mensual de Excel.
"""
from datetime import date
from types import SimpleNamespace

from app.features.attendance.asistencia_diaria.models import EstadoPeriodoAsistenciaEnum
from app.features.attendance.marcacion import services


def test_sin_rango_de_fechas_no_hace_nada(monkeypatch):
    monkeypatch.setattr(
        services, "_obtener_empleados_confianza_activos",
        lambda _: (_ for _ in ()).throw(AssertionError("no debería consultar empleados sin rango")),
    )

    procesados, errores = services._generar_asistencia_confianza(object(), None, None, set())

    assert (procesados, errores) == (0, [])


def test_genera_presente_exento_para_cada_dia_del_rango(monkeypatch):
    empleado_confianza = SimpleNamespace(id=99)
    monkeypatch.setattr(
        services, "_obtener_empleados_confianza_activos", lambda _: [empleado_confianza]
    )
    monkeypatch.setattr(
        services.asistencia_services, "get_periodo_asistencia", lambda *_: None
    )

    llamadas = []

    def recalcular(_, id_empleado, fecha):
        llamadas.append((id_empleado, fecha))
        return True, None

    monkeypatch.setattr(services, "_recalcular_asistencia_dia", recalcular)

    procesados, errores = services._generar_asistencia_confianza(
        object(), date(2026, 3, 1), date(2026, 3, 3), empleados_fechas_procesadas=set()
    )

    assert procesados == 3
    assert errores == []
    assert llamadas == [
        (99, date(2026, 3, 1)),
        (99, date(2026, 3, 2)),
        (99, date(2026, 3, 3)),
    ]


def test_no_reprocesa_pares_ya_cubiertos_por_el_excel(monkeypatch):
    empleado_confianza = SimpleNamespace(id=99)
    monkeypatch.setattr(
        services, "_obtener_empleados_confianza_activos", lambda _: [empleado_confianza]
    )
    monkeypatch.setattr(
        services.asistencia_services, "get_periodo_asistencia", lambda *_: None
    )

    llamadas = []
    monkeypatch.setattr(
        services, "_recalcular_asistencia_dia",
        lambda _, id_empleado, fecha: (llamadas.append((id_empleado, fecha)), (True, None))[1],
    )

    procesados, errores = services._generar_asistencia_confianza(
        object(),
        date(2026, 3, 1),
        date(2026, 3, 2),
        empleados_fechas_procesadas={(99, date(2026, 3, 1))},
    )

    # El día 1 ya vino del loop principal del Excel; solo se recalcula el día 2.
    assert llamadas == [(99, date(2026, 3, 2))]
    assert procesados == 1
    assert errores == []


def test_respeta_periodo_cerrado(monkeypatch):
    empleado_confianza = SimpleNamespace(id=99)
    monkeypatch.setattr(
        services, "_obtener_empleados_confianza_activos", lambda _: [empleado_confianza]
    )
    monkeypatch.setattr(
        services, "_recalcular_asistencia_dia",
        lambda *_: (_ for _ in ()).throw(AssertionError("no debe recalcular en período cerrado")),
    )
    monkeypatch.setattr(
        services.asistencia_services,
        "get_periodo_asistencia",
        lambda *_: SimpleNamespace(estado=EstadoPeriodoAsistenciaEnum.cerrado),
    )

    procesados, errores = services._generar_asistencia_confianza(
        object(), date(2026, 3, 1), date(2026, 3, 1), empleados_fechas_procesadas=set()
    )

    assert procesados == 0
    assert len(errores) == 1
    assert errores[0]["empleado_id"] == 99
    assert "cerrado" in errores[0]["error"].lower()


def test_acumula_error_sin_abortar_los_demas_dias(monkeypatch):
    empleado_confianza = SimpleNamespace(id=99)
    monkeypatch.setattr(
        services, "_obtener_empleados_confianza_activos", lambda _: [empleado_confianza]
    )
    monkeypatch.setattr(
        services.asistencia_services, "get_periodo_asistencia", lambda *_: None
    )

    resultados = iter([(False, "Empleado 99 no tiene horario asignado"), (True, None)])
    monkeypatch.setattr(
        services, "_recalcular_asistencia_dia", lambda *_: next(resultados)
    )

    procesados, errores = services._generar_asistencia_confianza(
        object(), date(2026, 3, 1), date(2026, 3, 2), empleados_fechas_procesadas=set()
    )

    assert procesados == 1
    assert len(errores) == 1
    assert errores[0] == {
        "empleado_id": 99,
        "fecha": str(date(2026, 3, 1)),
        "error": "Empleado 99 no tiene horario asignado",
    }
