from datetime import date

import pytest
from fastapi import HTTPException

from app.features.attendance.asistencia_diaria import services
from app.features.attendance.asistencia_diaria.models import EstadoPeriodoAsistenciaEnum


def test_obtener_rango_mes_incluye_anio_bisiesto():
    assert services.obtener_rango_mes(2028, 2) == (date(2028, 2, 1), date(2028, 2, 29))


def test_cerrar_periodo_rechaza_incidencias_pendientes(monkeypatch):
    monkeypatch.setattr(services, "get_periodo_asistencia", lambda *_: None)
    monkeypatch.setattr(services, "hay_incidencias_pendientes_periodo", lambda *_: True)

    with pytest.raises(HTTPException) as error:
        services.cerrar_periodo_asistencia(object(), 2026, 1, id_cerrado_por=9)

    assert error.value.status_code == 409


def test_cerrar_periodo_procesa_cada_dia_y_cierra(monkeypatch):
    class FakePeriodo:
        estado = EstadoPeriodoAsistenciaEnum.en_revision
        cerrado_en = None
        id_cerrado_por = None

    class FakeDb:
        def commit(self):
            pass

        def refresh(self, _):
            pass

    llamadas = []
    monkeypatch.setattr(services, "get_periodo_asistencia", lambda *_: FakePeriodo())
    monkeypatch.setattr(services, "hay_incidencias_pendientes_periodo", lambda *_: False)

    def procesar(_, fecha):
        llamadas.append(fecha)
        return services.ResultadoProcesamiento(
            fecha=fecha, empleados_procesados=2, empleados_con_error=0, empleados_skipped=0
        )

    monkeypatch.setattr(services, "procesar_asistencia_masiva", procesar)

    resultado = services.cerrar_periodo_asistencia(FakeDb(), 2026, 2, id_cerrado_por=9)

    assert len(llamadas) == 28
    assert resultado.dias_procesados == 28
    assert resultado.empleados_procesados == 56
    assert resultado.estado == "cerrado"
