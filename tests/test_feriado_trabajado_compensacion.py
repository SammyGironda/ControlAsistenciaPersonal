"""
Cobertura del feriado trabajado en `calcular_asistencia_dia`:
- se guardan los minutos realmente trabajados (antes siempre 0);
- se acreditan 8h de compensación, que el trigger vuelca al saldo vacacional;
- los cargos de confianza quedan fuera de esa acreditación.
"""

from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace

from app.features.attendance.asistencia_diaria import services
from app.features.attendance.asistencia_diaria.models import EstadoDiaEnum
from app.features.attendance.marcacion.models import TipoMarcacionEnum


FECHA = date(2026, 8, 6)


class FakeQuery:
    def __init__(self, resultado):
        self._resultado = resultado

    def options(self, *_, **__):
        return self

    def filter(self, *_, **__):
        return self

    def order_by(self, *_, **__):
        return self

    def first(self):
        return self._resultado


class FakeDb:
    def __init__(self, empleado, asignacion):
        self._empleado = empleado
        self._asignacion = asignacion

    def query(self, modelo):
        from app.features.employees.empleado.models import Empleado
        from app.features.employees.horario.models import AsignacionHorario

        if modelo is Empleado:
            return FakeQuery(self._empleado)
        if modelo is AsignacionHorario:
            return FakeQuery(self._asignacion)
        return FakeQuery(None)


def _marcacion(id_, hora, tipo):
    return SimpleNamespace(
        id=id_,
        tipo_marcacion=tipo,
        fecha_hora_marcacion=datetime.combine(FECHA, hora),
    )


def _preparar(monkeypatch, marcaciones, es_cargo_confianza=False):
    """Deja a calcular_asistencia_dia entrando en la rama de feriado."""
    empleado = SimpleNamespace(
        id=1,
        complemento_dep="LP",
        cargo=SimpleNamespace(es_cargo_confianza=es_cargo_confianza),
    )
    horario = SimpleNamespace(
        dias_laborables="1,2,3,4,5",
        hora_entrada=None,
        tolerancia_minutos=0,
    )
    asignacion = SimpleNamespace(horario=horario)
    db = FakeDb(empleado, asignacion)

    monkeypatch.setattr(services, "_get_horario_personalizado_activo", lambda *_: None)
    monkeypatch.setattr(services, "_obtener_justificacion_aprobada_dia", lambda *_: None)
    monkeypatch.setattr(services, "_parse_dias_laborables", lambda _: {0, 1, 2, 3, 4})
    monkeypatch.setattr(services, "_es_feriado", lambda *_: True)
    monkeypatch.setattr(services, "_obtener_marcaciones_dia", lambda *_: marcaciones)

    creadas = []
    monkeypatch.setattr(
        services,
        "_crear_o_actualizar_asistencia",
        lambda **kwargs: creadas.append(kwargs) or SimpleNamespace(**kwargs),
    )

    compensaciones = []
    monkeypatch.setattr(
        services.compensacion_services,
        "registrar_compensacion",
        lambda _db, **kwargs: compensaciones.append(kwargs),
    )

    return db, creadas, compensaciones


def test_feriado_trabajado_acredita_8h_y_guarda_minutos_reales(monkeypatch):
    from datetime import time

    marcaciones = [
        _marcacion(11, time(8, 0), TipoMarcacionEnum.ENTRADA),
        _marcacion(12, time(16, 0), TipoMarcacionEnum.SALIDA),
    ]
    db, creadas, compensaciones = _preparar(monkeypatch, marcaciones)

    services.calcular_asistencia_dia(db, 1, FECHA)

    assert len(creadas) == 1
    registro = creadas[0]
    assert registro["tipo_dia"] == EstadoDiaEnum.feriado
    assert registro["trabajo_en_feriado"] is True
    assert registro["minutos_trabajados"] == 480
    assert registro["id_marcacion_entrada"] == 11
    assert registro["id_marcacion_salida"] == 12

    assert len(compensaciones) == 1
    assert compensaciones[0]["horas"] == Decimal("8.0")
    assert compensaciones[0]["id_empleado"] == 1
    assert compensaciones[0]["fecha"] == FECHA


def test_feriado_sin_marcaciones_no_acredita_compensacion(monkeypatch):
    db, creadas, compensaciones = _preparar(monkeypatch, [])

    services.calcular_asistencia_dia(db, 1, FECHA)

    assert creadas[0]["trabajo_en_feriado"] is False
    assert creadas[0]["minutos_trabajados"] == 0
    assert compensaciones == []


def test_feriado_trabajado_por_cargo_de_confianza_no_acredita(monkeypatch):
    from datetime import time

    marcaciones = [
        _marcacion(11, time(8, 0), TipoMarcacionEnum.ENTRADA),
        _marcacion(12, time(16, 0), TipoMarcacionEnum.SALIDA),
    ]
    db, creadas, compensaciones = _preparar(monkeypatch, marcaciones, es_cargo_confianza=True)

    services.calcular_asistencia_dia(db, 1, FECHA)

    assert creadas[0]["trabajo_en_feriado"] is True
    assert compensaciones == []


def test_feriado_con_marcacion_incompleta_no_inventa_minutos(monkeypatch):
    from datetime import time

    marcaciones = [_marcacion(11, time(8, 0), TipoMarcacionEnum.ENTRADA)]
    db, creadas, compensaciones = _preparar(monkeypatch, marcaciones)

    services.calcular_asistencia_dia(db, 1, FECHA)

    assert creadas[0]["minutos_trabajados"] == 0
    assert creadas[0]["trabajo_en_feriado"] is True
    # Hubo presencia en el feriado, así que la compensación igual corresponde.
    assert len(compensaciones) == 1
