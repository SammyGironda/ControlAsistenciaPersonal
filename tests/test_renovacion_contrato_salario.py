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
from app.features.contracts.contrato.schemas import ContratoCreate, ContratoRenovacion
from app.features.employees.empleado.models import EstadoEmpleadoEnum


class FakeQuery:
    def __init__(self, resultado):
        self._resultado = resultado

    def filter(self, *_, **__):
        return self

    def first(self):
        return self._resultado


class FakeDb:
    def __init__(self, empleado, contrato_activo=None):
        self._empleado = empleado
        self._contrato_activo = contrato_activo
        self.commits = 0
        self.agregados = []
        # Estado del empleado tal como quedó en el último commit. Sirve para
        # detectar cambios asignados DESPUÉS del commit, que no se persisten.
        self.empleado_al_commitear = None

    def query(self, modelo):
        from app.features.contracts.contrato.models import Contrato
        from app.features.employees.empleado.models import Empleado

        if modelo is Empleado:
            return FakeQuery(self._empleado)
        if modelo is Contrato:
            return FakeQuery(self._contrato_activo)
        return FakeQuery(None)

    def add(self, obj):
        self.agregados.append(obj)

    def commit(self):
        self.commits += 1
        if self._empleado is not None:
            self.empleado_al_commitear = {
                "estado": getattr(self._empleado, "estado", None),
                "salario_base": self._empleado.salario_base,
            }

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


def test_crear_contrato_activa_al_empleado_dentro_de_la_transaccion():
    """
    El cambio de estado debe estar aplicado ANTES del commit. Antes se asignaba
    después y el db.refresh(empleado) inmediato lo descartaba, así que un
    empleado 'por_habilitar' se quedaba sin activar.
    """
    empleado = SimpleNamespace(
        id=42,
        nombre_completo="Empleado 42",
        estado=EstadoEmpleadoEnum.por_habilitar,
        salario_base=Decimal("0.00"),
    )
    db = FakeDb(empleado)
    inicio = date.today()
    data = ContratoCreate(
        id_empleado=42,
        tipo_contrato="indefinido",
        fecha_inicio=inicio,
        fecha_fin=None,
        salario_base=Decimal("4200.00"),
    )

    services.create_contrato(db, data)

    assert empleado.estado == EstadoEmpleadoEnum.activo
    assert empleado.salario_base == Decimal("4200.00")
    assert db.commits == 1
    # Lo decisivo: ambos cambios ya estaban puestos cuando se hizo el commit.
    assert db.empleado_al_commitear == {
        "estado": EstadoEmpleadoEnum.activo,
        "salario_base": Decimal("4200.00"),
    }


def test_crear_contrato_no_toca_el_estado_de_un_empleado_ya_activo():
    empleado = SimpleNamespace(
        id=42,
        nombre_completo="Empleado 42",
        estado=EstadoEmpleadoEnum.activo,
        salario_base=Decimal("3000.00"),
    )
    db = FakeDb(empleado)
    data = ContratoCreate(
        id_empleado=42,
        tipo_contrato="indefinido",
        fecha_inicio=date.today(),
        fecha_fin=None,
        salario_base=Decimal("3500.00"),
    )

    services.create_contrato(db, data)

    assert empleado.estado == EstadoEmpleadoEnum.activo
    assert empleado.salario_base == Decimal("3500.00")


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
