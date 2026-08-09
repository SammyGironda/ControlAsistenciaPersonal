"""
Cobertura de `renovar_contrato_plazo_fijo`: la renovación debe sincronizar
`empleado.salario_base` con el salario del contrato nuevo.

Para un plazo fijo no hay otra ruta que lo haga: el trigger
`trg_sync_salario_empleado` solo dispara al insertar en `ajuste_salarial`, y
`create_ajuste_salarial` rechaza los contratos no indefinidos.
"""

from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.features.contracts.contrato import services
from app.features.contracts.contrato.models import EstadoContratoEnum, TipoContratoEnum
from app.features.contracts.contrato.schemas import ContratoRenovacion


class FakeQuery:
    def __init__(self, resultado):
        self._resultado = resultado

    def filter(self, *_, **__):
        return self

    def first(self):
        return self._resultado


class FakeDb:
    def __init__(self, empleado):
        self._empleado = empleado
        self.commits = 0
        self.agregados = []

    def query(self, _modelo):
        return FakeQuery(self._empleado)

    def add(self, obj):
        self.agregados.append(obj)

    def commit(self):
        self.commits += 1

    def refresh(self, _):
        pass


def _contrato_anterior():
    return SimpleNamespace(
        id=1,
        id_empleado=42,
        tipo_contrato=TipoContratoEnum.plazo_fijo,
        estado=EstadoContratoEnum.activo,
        fecha_inicio=date(2025, 1, 1),
        fecha_fin=date(2026, 12, 31),
        observacion=None,
    )


def _renovacion(salario="7500.00"):
    inicio = date.today() + timedelta(days=1)
    return ContratoRenovacion(
        fecha_inicio=inicio,
        fecha_fin=inicio + timedelta(days=365),
        salario_base=Decimal(salario),
    )


def test_renovacion_sincroniza_salario_base_del_empleado(monkeypatch):
    anterior = _contrato_anterior()
    empleado = SimpleNamespace(id=42, salario_base=Decimal("5000.00"))
    db = FakeDb(empleado)
    monkeypatch.setattr(services, "get_contrato_by_id", lambda *_: anterior)

    nuevo = services.renovar_contrato_plazo_fijo(db, 1, _renovacion("7500.00"))

    assert empleado.salario_base == Decimal("7500.00")
    assert nuevo.salario_base == Decimal("7500.00")
    assert anterior.estado == EstadoContratoEnum.vencido
    # Un solo commit: vencer el anterior, crear el nuevo y sincronizar el
    # salario ocurren en la misma transacción.
    assert db.commits == 1
    assert len(db.agregados) == 1


def test_renovacion_falla_si_el_empleado_no_existe(monkeypatch):
    anterior = _contrato_anterior()
    db = FakeDb(empleado=None)
    monkeypatch.setattr(services, "get_contrato_by_id", lambda *_: anterior)

    with pytest.raises(HTTPException) as error:
        services.renovar_contrato_plazo_fijo(db, 1, _renovacion())

    assert error.value.status_code == 404
    # No se llegó a vencer el contrato anterior.
    assert anterior.estado == EstadoContratoEnum.activo
    assert db.commits == 0
