"""
Cobertura de `transferir_a_vacacion`: la acreditación de las 4h y el flag
`transferido_a_vacacion` deben ocurrir en una sola transacción.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.features.attendance.beneficio_cumpleanos import services


class FakeQuery:
    """Query encadenable que devuelve un resultado fijo para `.first()`."""

    def __init__(self, resultado):
        self._resultado = resultado

    def filter(self, *_, **__):
        return self

    def first(self):
        return self._resultado


class FakeDb:
    def __init__(self, vacacion=None, empleado=None):
        self._vacacion = vacacion
        self._empleado = empleado
        self.commits = 0
        self.rollbacks = 0
        self.agregados = []

    def query(self, modelo):
        from app.features.attendance.vacaciones.models import Vacacion
        from app.features.employees.empleado.models import Empleado

        if modelo is Vacacion:
            return FakeQuery(self._vacacion)
        if modelo is Empleado:
            return FakeQuery(self._empleado)
        raise AssertionError(f"Query inesperada sobre {modelo}")

    def execute(self, *_, **__):
        return SimpleNamespace(scalar=lambda: Decimal("120.0"))

    def add(self, obj):
        self.agregados.append(obj)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, _):
        pass


def _beneficio(transferido=False):
    return SimpleNamespace(
        id=7,
        id_empleado=42,
        gestion=2026,
        fue_utilizado=False,
        transferido_a_vacacion=transferido,
    )


def test_transferencia_suma_4h_a_vacacion_existente_en_un_solo_commit(monkeypatch):
    beneficio = _beneficio()
    vacacion = SimpleNamespace(
        horas_correspondientes=Decimal("120.0"),
        horas_goce_haber=Decimal("10.0"),
    )
    db = FakeDb(vacacion=vacacion)
    monkeypatch.setattr(services, "obtener_beneficio", lambda *_: beneficio)

    resultado = services.transferir_a_vacacion(db, 7)

    assert vacacion.horas_correspondientes == Decimal("124.0")
    assert vacacion.horas_goce_haber == Decimal("14.0")
    assert resultado.transferido_a_vacacion is True
    assert db.commits == 1
    assert db.agregados == []


def test_transferencia_crea_la_vacacion_con_base_lgt_si_no_existe(monkeypatch):
    beneficio = _beneficio()
    empleado = SimpleNamespace(id=42, fecha_ingreso=date(2020, 3, 1))
    db = FakeDb(vacacion=None, empleado=empleado)
    monkeypatch.setattr(services, "obtener_beneficio", lambda *_: beneficio)

    services.transferir_a_vacacion(db, 7)

    assert len(db.agregados) == 1
    nueva = db.agregados[0]
    # base LGT (120.0, devuelta por FakeDb.execute) + 4h del beneficio
    assert nueva.horas_correspondientes == Decimal("124.0")
    assert nueva.horas_goce_haber == Decimal("4.0")
    assert nueva.id_empleado == 42
    assert nueva.gestion == 2026
    assert beneficio.transferido_a_vacacion is True
    assert db.commits == 1


def test_transferencia_rechaza_beneficio_ya_transferido(monkeypatch):
    beneficio = _beneficio(transferido=True)
    vacacion = SimpleNamespace(
        horas_correspondientes=Decimal("120.0"),
        horas_goce_haber=Decimal("10.0"),
    )
    db = FakeDb(vacacion=vacacion)
    monkeypatch.setattr(services, "obtener_beneficio", lambda *_: beneficio)

    with pytest.raises(HTTPException) as error:
        services.transferir_a_vacacion(db, 7)

    assert error.value.status_code == 400
    assert vacacion.horas_correspondientes == Decimal("120.0")
    assert db.commits == 0
