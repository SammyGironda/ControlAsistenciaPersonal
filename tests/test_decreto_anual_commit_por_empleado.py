"""
Cobertura de `aplicar_decreto_anual`: el commit es por empleado, así que un
fallo aislado no descarta los ajustes de los empleados ya procesados.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from app.features.contracts.ajuste_salarial import services


class FakeQuery:
    def __init__(self, db, modelo):
        self._db = db
        self._modelo = modelo

    def join(self, *_, **__):
        return self

    def filter(self, *_, **__):
        return self

    def order_by(self, *_, **__):
        return self

    def distinct(self):
        self._db.distinct_aplicado = True
        return self

    def all(self):
        return self._db.empleados

    def first(self):
        from app.features.contracts.contrato.models import Contrato
        from app.features.contracts.ajuste_salarial.models import CondicionDecreto
        from app.features.employees.empleado.models import Empleado

        if self._modelo is Empleado:
            return SimpleNamespace(id=99, nombre_completo="Aprobador")
        if self._modelo is Contrato:
            return SimpleNamespace(id=1)
        if self._modelo is CondicionDecreto:
            return SimpleNamespace(id=5)
        return None


class FakeDb:
    def __init__(self, empleados):
        self.empleados = empleados
        self.eventos = []
        self.ajustes_confirmados = []
        self._pendientes = []
        self.distinct_aplicado = False

    def query(self, modelo):
        return FakeQuery(self, modelo)

    def add(self, obj):
        self._pendientes.append(obj)

    def commit(self):
        self.eventos.append("commit")
        self.ajustes_confirmados.extend(self._pendientes)
        self._pendientes = []

    def rollback(self):
        self.eventos.append("rollback")
        self._pendientes = []


def _empleado(id_, salario="5000.00"):
    return SimpleNamespace(
        id=id_,
        nombre_completo=f"Empleado {id_}",
        salario_base=Decimal(salario),
    )


def _preparar(monkeypatch, db, porcentaje_por_empleado):
    """Parchea las dependencias externas de aplicar_decreto_anual."""
    decreto = SimpleNamespace(
        id=1,
        fecha_vigencia=date(2026, 1, 1),
        referencia_decreto="DS-1234",
    )
    monkeypatch.setattr(services, "get_decreto_by_id", lambda *_: decreto)

    def porcentaje(_db, _decreto_id, salario_base):
        del _db, _decreto_id
        return porcentaje_por_empleado(salario_base)

    monkeypatch.setattr(services, "calcular_porcentaje_incremento", porcentaje)


def test_fallo_de_un_empleado_no_descarta_los_anteriores(monkeypatch):
    empleados = [_empleado(1), _empleado(2, "0.00"), _empleado(3)]
    db = FakeDb(empleados)

    def porcentaje(salario_base):
        if salario_base == Decimal("0.00"):
            raise ValueError("Salario fuera de todos los tramos del decreto")
        return Decimal("5.0")

    _preparar(monkeypatch, db, porcentaje)

    resultado = services.aplicar_decreto_anual(db, decreto_id=1, id_aprobado_por=99)

    assert resultado["empleados_procesados"] == 3
    # Solo los empleados 1 y 3 generaron ajuste; el 2 falló.
    assert resultado["ajustes_creados"] == 2
    assert len(resultado["errores"]) == 1
    assert "Empleado ID 2 (Empleado 2)" in resultado["errores"][0]

    # Los ajustes de los empleados anteriores al fallo sobrevivieron.
    assert [a.id_empleado for a in db.ajustes_confirmados] == [1, 3]
    assert db.eventos == ["commit", "rollback", "commit"]


def test_todos_ok_hace_un_commit_por_empleado(monkeypatch):
    db = FakeDb([_empleado(1), _empleado(2)])
    _preparar(monkeypatch, db, lambda _: Decimal("10.0"))

    resultado = services.aplicar_decreto_anual(db, decreto_id=1, id_aprobado_por=99)

    assert resultado["ajustes_creados"] == 2
    assert resultado["errores"] == []
    assert db.eventos == ["commit", "commit"]
    assert db.distinct_aplicado is True
    # 5000 + 10% = 5500.00
    assert db.ajustes_confirmados[0].salario_nuevo == Decimal("5500.00")
