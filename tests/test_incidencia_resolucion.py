from datetime import datetime, time
from types import SimpleNamespace

import pytest

from app.features.attendance.marcacion.models import TipoMarcacionEnum
from app.features.attendance.marcacion import services


def test_seleccionar_marcacion_duplicada_prefiere_la_mas_cercana_a_entrada():
    marcaciones = [
        SimpleNamespace(fecha_hora_marcacion=datetime(2026, 1, 15, 7, 58)),
        SimpleNamespace(fecha_hora_marcacion=datetime(2026, 1, 15, 8, 3)),
    ]

    seleccionada = services._seleccionar_marcacion_duplicada(
        marcaciones,
        hora_esperada=time(8, 0),
        tipo_marcacion=TipoMarcacionEnum.ENTRADA,
    )

    assert seleccionada.fecha_hora_marcacion == datetime(2026, 1, 15, 7, 58)


def test_seleccionar_marcacion_duplicada_prefiere_la_mas_cercana_a_salida():
    marcaciones = [
        SimpleNamespace(fecha_hora_marcacion=datetime(2026, 1, 15, 17, 58)),
        SimpleNamespace(fecha_hora_marcacion=datetime(2026, 1, 15, 18, 3)),
    ]

    seleccionada = services._seleccionar_marcacion_duplicada(
        marcaciones,
        hora_esperada=time(18, 0),
        tipo_marcacion=TipoMarcacionEnum.SALIDA,
    )

    assert seleccionada.fecha_hora_marcacion == datetime(2026, 1, 15, 18, 3)


def test_hora_correccion_usa_horario_cuando_no_viene_una_hora_explicitamente():
    horario = SimpleNamespace(hora_entrada=time(8, 0), hora_salida=time(18, 0))

    hora = services._resolver_hora_correccion(
        horario=horario,
        tipo_marcacion=TipoMarcacionEnum.SALIDA,
        hora_correccion=None,
    )

    assert hora == time(18, 0)
