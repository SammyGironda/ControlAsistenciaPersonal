"""
Tests de RBAC: require_admin() y require_roles() en app/core/deps.py.

Unitarios, sin base de datos ni FastAPI TestClient: se invoca la función
interna de cada dependencia directamente con un doble (SimpleNamespace) de
Usuario, igual que test_jwt_auth.py. get_current_user ya está cubierto por
esa suite; acá solo se prueba la capa de comparación de rol que corre
después de resolverlo.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core import deps


def _usuario_con_rol(nombre_rol: str) -> SimpleNamespace:
    return SimpleNamespace(id=1, username="test", rol=SimpleNamespace(nombre=nombre_rol))


# ============================================================
# require_admin
# ============================================================

def test_require_admin_permite_rol_admin():
    usuario = _usuario_con_rol("admin")
    assert deps.require_admin(current_user=usuario) is usuario


def test_require_admin_es_case_insensitive():
    usuario = _usuario_con_rol("Admin")
    assert deps.require_admin(current_user=usuario) is usuario


def test_require_admin_rechaza_otros_roles():
    usuario = _usuario_con_rol("rrhh")

    with pytest.raises(HTTPException) as exc:
        deps.require_admin(current_user=usuario)

    assert exc.value.status_code == 403


@pytest.mark.parametrize("rol", ["rrhh", "supervisor", "empleado", "consulta"])
def test_require_admin_rechaza_todos_los_roles_no_admin(rol):
    usuario = _usuario_con_rol(rol)

    with pytest.raises(HTTPException) as exc:
        deps.require_admin(current_user=usuario)

    assert exc.value.status_code == 403


# ============================================================
# require_roles
# ============================================================

def test_require_roles_permite_cualquier_rol_de_la_lista():
    guard = deps.require_roles("admin", "rrhh")

    for rol in ("admin", "rrhh", "RRHH", "Admin"):
        usuario = _usuario_con_rol(rol)
        assert guard(current_user=usuario) is usuario


def test_require_roles_rechaza_rol_fuera_de_la_lista():
    guard = deps.require_roles("admin", "supervisor", "rrhh")
    usuario = _usuario_con_rol("empleado")

    with pytest.raises(HTTPException) as exc:
        guard(current_user=usuario)

    assert exc.value.status_code == 403
    assert "admin" in exc.value.detail
    assert "supervisor" in exc.value.detail
    assert "rrhh" in exc.value.detail


def test_require_roles_con_un_solo_rol_equivale_a_require_admin():
    guard = deps.require_roles("admin")
    usuario_admin = _usuario_con_rol("admin")
    usuario_rrhh = _usuario_con_rol("rrhh")

    assert guard(current_user=usuario_admin) is usuario_admin
    with pytest.raises(HTTPException):
        guard(current_user=usuario_rrhh)


def test_require_roles_instancias_independientes_no_comparten_estado():
    """Cada llamada a require_roles(...) arma su propio set de roles permitidos."""
    guard_aprobacion = deps.require_roles("admin", "supervisor", "rrhh")
    guard_admin_rrhh = deps.require_roles("admin", "rrhh")

    usuario_supervisor = _usuario_con_rol("supervisor")

    assert guard_aprobacion(current_user=usuario_supervisor) is usuario_supervisor
    with pytest.raises(HTTPException):
        guard_admin_rrhh(current_user=usuario_supervisor)
