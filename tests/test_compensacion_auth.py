"""
Tests de autorización de /api/v1/compensaciones-horas-extra.

El módulo tiene dos endpoints con guards DISTINTOS a propósito:

- POST  -> require_admin              (registrar acredita horas al saldo
                                       vacacional vía trigger y es irreversible
                                       desde la API: no hay PUT ni DELETE)
- GET   -> require_roles(admin, rrhh) (auditar lo cargado; es la razón de ser
                                       del listado, según su propio docstring)

Los guards se resuelven ENUMERANDO las rutas registradas, no leyendo el archivo:
es el método con el que se detectó, el 2026-08-09, que la nota de CLAUDE.md
sobre routers "sin exponer" era falsa. Cada guard encontrado se invoca después
con un doble de Usuario (SimpleNamespace), igual que test_rbac.py y
test_vacaciones_auth.py — sin base de datos ni TestClient.

Se enumera `router.routes` y NO `app.routes` a propósito: importar app.main
arrastra 4 DeprecationWarning de @app.on_event (deprecado a favor de lifespan,
ver CLAUDE.md) más uno de reportlab, y la suite quedó sin warnings el
2026-08-12. Las rutas de un APIRouter son los mismos objetos APIRoute con el
mismo `dependant`, así que lo único que este archivo no cubre es el montaje bajo
API_PREFIX en main.py — verificado a mano enumerando app.routes.
"""

import inspect
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.features.attendance.compensacion_horas_extra.router import router


PREFIJO = "/compensaciones-horas-extra"

# Ambos endpoints se declaran como "/" en el decorador, pero el APIRouter ya le
# antepone su prefijo al registrarlos. La barra final es parte de la ruta: sin
# ella FastAPI redirige (307).
RUTA = f"{PREFIJO}/"

TODOS_LOS_ROLES = ["admin", "rrhh", "supervisor", "empleado", "consulta"]


def _usuario_con_rol(nombre_rol: str) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        id_empleado=3,
        username="test",
        rol=SimpleNamespace(nombre=nombre_rol),
    )


def _ruta(metodo: str):
    """La ruta registrada en el router para ese método, o None si no existe."""
    for route in router.routes:
        if getattr(route, "path", None) == RUTA and metodo in getattr(route, "methods", set()):
            return route
    return None


def _guards_de_rol(metodo: str):
    """
    Las dependencias de la ruta que deciden por rol.

    Se detectan por su firma (reciben `current_user`), no por su nombre: así el
    test sigue valiendo si el guard se renombra, y no confunde a get_db ni a
    get_current_user, que resuelven otra cosa.
    """
    route = _ruta(metodo)
    assert route is not None, f"No hay ruta {metodo} {RUTA} registrada en el router"

    guards = []
    for dependencia in route.dependant.dependencies:
        parametros = inspect.signature(dependencia.call).parameters
        if "current_user" in parametros:
            guards.append(dependencia.call)
    return guards


# ============================================================
# Las dos rutas siguen registradas y ninguna quedó sin guard
# ============================================================

def test_el_prefijo_del_router_no_cambio():
    """El frontend arma la URL con este segmento; renombrarlo rompe la pantalla."""
    assert router.prefix == PREFIJO


def test_el_router_expone_exactamente_dos_rutas():
    """
    No hay PUT ni DELETE: una compensación no se puede editar ni anular desde la
    API, y el trigger que acredita al saldo vacacional sólo actúa en INSERT. Si
    algún día se agregan, hay que decidir su guard y revisar la UI, que hoy
    advierte al admin que la operación es definitiva.
    """
    assert len(router.routes) == 2


@pytest.mark.parametrize("metodo", ["POST", "GET"])
def test_la_ruta_existe(metodo):
    assert _ruta(metodo) is not None


@pytest.mark.parametrize("metodo", ["POST", "GET"])
def test_la_ruta_tiene_exactamente_un_guard_de_rol(metodo):
    assert len(_guards_de_rol(metodo)) == 1


# ============================================================
# POST: sigue siendo admin-only
# ============================================================

def test_post_acepta_admin():
    guard = _guards_de_rol("POST")[0]
    usuario = _usuario_con_rol("admin")

    assert guard(current_user=usuario) is usuario


@pytest.mark.parametrize("rol", ["rrhh", "supervisor", "empleado", "consulta"])
def test_post_rechaza_todo_rol_no_admin(rol):
    guard = _guards_de_rol("POST")[0]

    with pytest.raises(HTTPException) as exc:
        guard(current_user=_usuario_con_rol(rol))

    assert exc.value.status_code == 403


def test_post_no_se_amplio_a_rrhh_por_arrastre():
    """
    Guarda explícita del reparto: al ampliar el GET a rrhh, el POST NO debe
    ampliarse. Registrar acredita horas de forma irreversible.
    """
    guard = _guards_de_rol("POST")[0]

    with pytest.raises(HTTPException) as exc:
        guard(current_user=_usuario_con_rol("rrhh"))

    assert exc.value.status_code == 403


# ============================================================
# GET: admin + rrhh
# ============================================================

@pytest.mark.parametrize("rol", ["admin", "rrhh"])
def test_get_acepta_gestores(rol):
    guard = _guards_de_rol("GET")[0]
    usuario = _usuario_con_rol(rol)

    assert guard(current_user=usuario) is usuario


@pytest.mark.parametrize("rol", ["Admin", "RRHH", "rRhH"])
def test_get_es_case_insensitive(rol):
    """
    El rol viene de la base (rrhh.rol.nombre), no de un literal del código: en
    Neon se llamó 'RecursosHumanos' hasta el 2026-08-12. La comparación debe
    seguir siendo insensible a mayúsculas.
    """
    guard = _guards_de_rol("GET")[0]
    usuario = _usuario_con_rol(rol)

    assert guard(current_user=usuario) is usuario


@pytest.mark.parametrize("rol", ["supervisor", "empleado", "consulta"])
def test_get_rechaza_roles_sin_alcance_de_auditoria(rol):
    guard = _guards_de_rol("GET")[0]

    with pytest.raises(HTTPException) as exc:
        guard(current_user=_usuario_con_rol(rol))

    assert exc.value.status_code == 403


def test_get_menciona_ambos_roles_en_el_detalle():
    """
    El frontend muestra el `detail` del 403 tal cual (mensajeDeError en
    hooks/useVacaciones.js), así que tiene que decir quién sí puede.
    """
    guard = _guards_de_rol("GET")[0]

    with pytest.raises(HTTPException) as exc:
        guard(current_user=_usuario_con_rol("supervisor"))

    detail = exc.value.detail
    assert "admin" in detail
    assert "rrhh" in detail


# ============================================================
# Los roles cubiertos son todos los que existen en rrhh.rol
# ============================================================

@pytest.mark.parametrize("rol", TODOS_LOS_ROLES)
@pytest.mark.parametrize("metodo", ["POST", "GET"])
def test_ningun_rol_pasa_sin_decision_explicita(metodo, rol):
    """
    Todo rol de la base recibe un veredicto claro: o el guard lo devuelve, o
    levanta 403. Nunca None ni una excepción de otro tipo.
    """
    guard = _guards_de_rol(metodo)[0]
    usuario = _usuario_con_rol(rol)

    try:
        assert guard(current_user=usuario) is usuario
    except HTTPException as exc:
        assert exc.status_code == 403
