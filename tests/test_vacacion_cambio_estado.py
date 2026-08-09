"""
Cobertura de `cambiar_estado_detalle`: qué saldos consume cada tipo de vacación
al pasar a 'tomado'.

La licencia por accidente solo descuenta saldo vacacional cuando RRHH lo
confirma explícitamente con `cubrir_con_saldo_vacacional=true`.
"""

from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.features.attendance.vacaciones import services
from app.features.attendance.vacaciones.models import (
    EstadoDetalleVacacionEnum,
    TipoVacacionEnum,
)
from app.features.attendance.vacaciones.schemas import CambiarEstadoRequest


class FakeDb:
    def __init__(self):
        self.commits = 0

    def commit(self):
        self.commits += 1

    def refresh(self, _):
        pass


def _detalle(tipo, horas="8.0"):
    return SimpleNamespace(
        id=1,
        id_vacacion=10,
        estado=EstadoDetalleVacacionEnum.aprobado,
        tipo_vacacion=tipo,
        horas_habiles=Decimal(horas),
        observacion=None,
        id_aprobado_por=None,
    )


def _vacacion(correspondientes="120.0", goce="40.0", sin_goce="16.0", tomadas="0.0"):
    return SimpleNamespace(
        id=10,
        horas_correspondientes=Decimal(correspondientes),
        horas_goce_haber=Decimal(goce),
        horas_sin_goce_haber=Decimal(sin_goce),
        horas_tomadas=Decimal(tomadas),
        horas_pendientes=Decimal(correspondientes) - Decimal(tomadas),
    )


def _tomar(monkeypatch, detalle, vacacion, **kwargs):
    monkeypatch.setattr(services, "obtener_detalle_vacacion", lambda *_: detalle)
    monkeypatch.setattr(services, "obtener_vacacion", lambda *_: vacacion)
    data = CambiarEstadoRequest(nuevo_estado=EstadoDetalleVacacionEnum.tomado, **kwargs)
    return services.cambiar_estado_detalle(FakeDb(), 1, data)


def test_licencia_accidente_sin_flag_no_toca_ningun_saldo(monkeypatch):
    detalle = _detalle(TipoVacacionEnum.licencia_accidente)
    vacacion = _vacacion()

    resultado = _tomar(monkeypatch, detalle, vacacion)

    assert vacacion.horas_tomadas == Decimal("0.0")
    assert vacacion.horas_goce_haber == Decimal("40.0")
    assert vacacion.horas_sin_goce_haber == Decimal("16.0")
    assert resultado.estado == EstadoDetalleVacacionEnum.tomado
    assert "sin descontar saldo vacacional" in resultado.observacion.lower()


def test_licencia_accidente_con_flag_descuenta_como_goce_de_haber(monkeypatch):
    detalle = _detalle(TipoVacacionEnum.licencia_accidente)
    vacacion = _vacacion()

    _tomar(monkeypatch, detalle, vacacion, cubrir_con_saldo_vacacional=True)

    assert vacacion.horas_tomadas == Decimal("8.0")
    assert vacacion.horas_goce_haber == Decimal("32.0")
    assert vacacion.horas_sin_goce_haber == Decimal("16.0")


def test_goce_de_haber_mantiene_su_comportamiento(monkeypatch):
    detalle = _detalle(TipoVacacionEnum.goce_de_haber)
    vacacion = _vacacion()

    _tomar(monkeypatch, detalle, vacacion)

    assert vacacion.horas_tomadas == Decimal("8.0")
    assert vacacion.horas_goce_haber == Decimal("32.0")


def test_sin_goce_de_haber_descuenta_de_su_propio_saldo(monkeypatch):
    detalle = _detalle(TipoVacacionEnum.sin_goce_de_haber)
    vacacion = _vacacion()

    _tomar(monkeypatch, detalle, vacacion)

    assert vacacion.horas_tomadas == Decimal("8.0")
    assert vacacion.horas_sin_goce_haber == Decimal("8.0")
    assert vacacion.horas_goce_haber == Decimal("40.0")


def test_no_se_puede_exceder_las_horas_correspondientes(monkeypatch):
    # Saldo de goce alcanza (40h), pero ya se tomaron 116h de 120h: tomar 8h más
    # rompería chk_vacacion_no_excede.
    detalle = _detalle(TipoVacacionEnum.goce_de_haber, horas="8.0")
    vacacion = _vacacion(correspondientes="120.0", goce="40.0", tomadas="116.0")

    with pytest.raises(HTTPException) as error:
        _tomar(monkeypatch, detalle, vacacion)

    assert error.value.status_code == 400
    assert "excederían las horas correspondientes" in error.value.detail
    assert vacacion.horas_tomadas == Decimal("116.0")
    assert vacacion.horas_goce_haber == Decimal("40.0")


def test_saldo_insuficiente_no_deja_la_vacacion_mutada(monkeypatch):
    detalle = _detalle(TipoVacacionEnum.goce_de_haber, horas="48.0")
    vacacion = _vacacion(goce="40.0")

    with pytest.raises(HTTPException) as error:
        _tomar(monkeypatch, detalle, vacacion)

    assert error.value.status_code == 400
    # La validación corre antes de mutar: nada cambió.
    assert vacacion.horas_goce_haber == Decimal("40.0")
    assert vacacion.horas_tomadas == Decimal("0.0")
    assert detalle.estado == EstadoDetalleVacacionEnum.aprobado
