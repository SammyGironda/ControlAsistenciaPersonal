from datetime import date, datetime, time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.features.attendance.marcacion.models import TipoMarcacionEnum
from app.features.attendance.marcacion import services
from app.features.employees.horario.schemas import AsignacionHorarioCreate


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


def test_recalcular_asistencia_dia_crea_registro_manual_si_falta_horario(monkeypatch):
    class FakeDb:
        def rollback(self):
            raise AssertionError("No debe hacer rollback si el registro manual funciona")

    def sin_horario(*_):
        raise HTTPException(status_code=400, detail="Empleado 1 no tiene horario asignado")

    monkeypatch.setattr(services.asistencia_services, "calcular_asistencia_dia", sin_horario)
    llamadas = []
    monkeypatch.setattr(
        services.asistencia_services,
        "registrar_asistencia_importada_sin_horario",
        lambda _, empleado_id, fecha: llamadas.append((empleado_id, fecha)),
    )

    calculada, error = services._recalcular_asistencia_dia(FakeDb(), 1, datetime(2026, 1, 15).date())

    assert calculada is True
    assert error == "Asistencia registrada sin horario asignado"
    assert llamadas == [(1, datetime(2026, 1, 15).date())]


def test_asignacion_horario_permite_vigencia_de_un_solo_dia():
    asignacion = AsignacionHorarioCreate(
        id_empleado=1,
        id_horario=1,
        fecha_inicio=date(2026, 7, 23),
        fecha_fin=date(2026, 7, 23),
    )

    assert asignacion.fecha_fin == asignacion.fecha_inicio


def test_asignacion_horario_rechaza_fecha_fin_anterior_al_inicio():
    with pytest.raises(ValidationError, match="no puede ser anterior"):
        AsignacionHorarioCreate(
            id_empleado=1,
            id_horario=1,
            fecha_inicio=date(2026, 7, 23),
            fecha_fin=date(2026, 7, 22),
        )
