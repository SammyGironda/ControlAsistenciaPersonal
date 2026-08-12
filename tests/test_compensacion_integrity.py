"""
Tests de registrar_compensacion(): qué IntegrityError se traduce a "duplicado"
y cuál se propaga.

Contexto: durante meses TODO insert en rrhh.compensacion_horas_extra falló con
un NotNullViolation lanzado por el trigger trg_compensacion_horas_extra_a_vacacion
(su INSERT en rrhh.vacacion omitía 4 columnas NOT NULL — corregido en la
migración e5f2a8c1d904). El fallo fue invisible porque este servicio atrapaba
CUALQUIER IntegrityError y devolvía None, y el router traducía ese None a un 409
"Ya existe una compensación registrada...". Los dos llamadores automáticos
ignoraban el retorno, así que no acreditaban nada y nadie se enteraba.

Ahora sólo el UNIQUE (id_empleado, fecha) devuelve None; el resto se propaga.

Unitarios, sin base de datos: se usa un doble de Session que levanta el
IntegrityError que cada test quiera, igual que el resto de la suite.
"""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from sqlalchemy.exc import IntegrityError

from app.features.attendance.compensacion_horas_extra import services


def _integrity_error(constraint_name):
    """
    IntegrityError con el nombre de constraint que reporta PostgreSQL en
    `error.orig.diag.constraint_name`. `constraint_name=None` imita un error sin
    constraint asociado.
    """
    orig = SimpleNamespace(diag=SimpleNamespace(constraint_name=constraint_name))
    return IntegrityError("INSERT ...", {}, orig)


class _SessionFalsa:
    """
    Doble de Session: registra las llamadas y falla en commit() con el error
    indicado (o no falla, si es None).
    """

    def __init__(self, error_al_commit=None):
        self.error_al_commit = error_al_commit
        self.rollbacks = 0
        self.commits = 0
        self.agregados = []

    def add(self, obj):
        self.agregados.append(obj)

    def commit(self):
        self.commits += 1
        if self.error_al_commit is not None:
            raise self.error_al_commit

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, obj):
        pass


def _registrar(db):
    return services.registrar_compensacion(
        db,
        id_empleado=3,
        fecha=date(2026, 8, 8),
        horas=Decimal("8.0"),
        motivo="Trabajo en sábado",
    )


# ============================================================
# El UNIQUE (id_empleado, fecha) sí es un duplicado
# ============================================================

def test_el_unique_de_empleado_fecha_devuelve_none():
    db = _SessionFalsa(_integrity_error(services.UNIQUE_EMPLEADO_FECHA))

    assert _registrar(db) is None
    assert db.rollbacks == 1


# ============================================================
# Cualquier otro IntegrityError se propaga
# ============================================================

@pytest.mark.parametrize(
    "constraint",
    [
        # El que rompía todo: lo levanta el trigger al escribir en rrhh.vacacion
        "vacacion_horas_sin_goce_haber_not_null",
        "chk_vacacion_no_excede",
        "fk_compensacion_horas_extra_id_empleado_empleado",
        "ck_compensacion_horas_extra_horas_positivas",
        None,
    ],
)
def test_otros_integrity_errors_se_propagan(constraint):
    db = _SessionFalsa(_integrity_error(constraint))

    with pytest.raises(IntegrityError):
        _registrar(db)

    # Se hace rollback igual: dejar la sesión rota rompería el resto del batch.
    assert db.rollbacks == 1


def test_un_notnullviolation_del_trigger_no_se_disfraza_de_duplicado():
    """
    La regresión concreta que este cambio evita: antes esto devolvía None y el
    endpoint respondía 409 "ya existe" sobre una tabla vacía.
    """
    db = _SessionFalsa(_integrity_error("vacacion_horas_sin_goce_haber_not_null"))

    with pytest.raises(IntegrityError):
        _registrar(db)


# ============================================================
# Camino feliz
# ============================================================

def test_sin_error_devuelve_la_compensacion():
    db = _SessionFalsa()

    compensacion = _registrar(db)

    assert compensacion is not None
    assert compensacion.id_empleado == 3
    assert db.commits == 1
    assert db.rollbacks == 0


def test_la_gestion_se_deriva_del_anio_de_la_fecha():
    db = _SessionFalsa()

    compensacion = services.registrar_compensacion(
        db,
        id_empleado=3,
        fecha=date(2025, 11, 15),
        horas=Decimal("4.5"),
        motivo="Trabajo en domingo",
    )

    assert compensacion.gestion == 2025


def test_la_gestion_explicita_gana_sobre_el_anio_de_la_fecha():
    """
    Caso real: un fin de semana de diciembre que se acredita a la gestión
    siguiente. El formulario lo expone como selector.
    """
    db = _SessionFalsa()

    compensacion = services.registrar_compensacion(
        db,
        id_empleado=3,
        fecha=date(2025, 12, 28),
        horas=Decimal("8.0"),
        motivo="Cierre de gestión",
        gestion=2026,
    )

    assert compensacion.gestion == 2026
