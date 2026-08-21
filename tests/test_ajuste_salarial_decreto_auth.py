"""
Tests del RBAC de /api/v1/ajustes-salariales (ajustes individuales + decretos,
sin contar /parametros-impuesto, que ya tiene su propio archivo) y de
`services.actualizar_decreto` (2026-08-20).

Antes de este cambio, de las 10 rutas de este módulo sólo 2 tenían guard
(`POST /` y `POST /decretos/{id}/aplicar`); las otras 8 —incluido
`POST /decretos`, escritura de datos salariales— estaban completamente
abiertas. Reparto que se prueba acá:
- Escritura de decretos (POST, PUT, aplicar) -> require_admin.
- Crear ajuste individual -> require_roles("admin", "rrhh").
- Lectura (historial/vigente de empleado, listar/obtener/buscar por año
  decreto, ajustes generados bajo un decreto) -> require_roles("admin", "rrhh").

La segunda parte cubre `actualizar_decreto`, que bloquea la edición de un
decreto que ya generó ajustes salariales (para no orfanizar en silencio la
auditoría vía el `ondelete="SET NULL"` de `AjusteSalarial.id_condicion_decreto`).

Unitarios, sin base de datos ni TestClient. Se enumera `router.routes` y NO
`app.routes` a propósito, mismo motivo que test_parametro_impuesto_auth.py:
importar app.main arrastra DeprecationWarnings y rompería el baseline sin
warnings de la suite.
"""

import inspect
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.features.contracts.ajuste_salarial import services
from app.features.contracts.ajuste_salarial import router as router_module
from app.features.contracts.ajuste_salarial.router import router as router_ajustes


TODOS_LOS_ROLES = ["admin", "rrhh", "supervisor", "empleado", "consulta"]

SOLO_ADMIN = frozenset({"admin"})
ADMIN_Y_RRHH = frozenset({"admin", "rrhh"})

PREFIJO = "/ajustes-salariales"


def _usuario(rol: str, id=1, id_empleado=3) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        username="test",
        id_empleado=id_empleado,
        rol=SimpleNamespace(nombre=rol),
    )


# La ruta que el APIRouter registra es prefijo + path del decorador.
#
# Agregar un endpoint nuevo de ajustes/decretos sin sumarlo acá rompe los
# canarios del final, que es exactamente para lo que existen.
CASOS = [
    ("POST", f"{PREFIJO}/", ADMIN_Y_RRHH),
    ("GET", f"{PREFIJO}/empleado/{{empleado_id}}/historial", ADMIN_Y_RRHH),
    ("GET", f"{PREFIJO}/empleado/{{empleado_id}}/vigente", ADMIN_Y_RRHH),
    ("POST", f"{PREFIJO}/decretos", SOLO_ADMIN),
    ("PUT", f"{PREFIJO}/decretos/{{decreto_id}}", SOLO_ADMIN),
    ("GET", f"{PREFIJO}/decretos", ADMIN_Y_RRHH),
    ("GET", f"{PREFIJO}/decretos/{{decreto_id}}", ADMIN_Y_RRHH),
    ("GET", f"{PREFIJO}/decretos/anio/{{anio}}", ADMIN_Y_RRHH),
    ("GET", f"{PREFIJO}/decretos/{{decreto_id}}/ajustes", ADMIN_Y_RRHH),
    ("POST", f"{PREFIJO}/decretos/{{decreto_id}}/aplicar", SOLO_ADMIN),
]

IDS = [f"{metodo} {ruta}" for metodo, ruta, _ in CASOS]


def _ruta(metodo: str, ruta: str):
    """La ruta registrada en el router para ese método, o None si no existe."""
    for route in router_ajustes.routes:
        if getattr(route, "path", None) == ruta and metodo in getattr(route, "methods", set()):
            return route
    return None


def _guards_de_rol(metodo: str, ruta: str):
    """
    Las dependencias de la ruta que deciden por rol.

    Se detectan por su firma (reciben `current_user`), no por su nombre: así el
    test sigue valiendo si el guard se renombra, y no confunde a get_db ni a
    get_current_user, cuyos parámetros son `credentials` y `db`.

    Copiado de test_parametro_impuesto_auth.py / test_departamentos_auth.py.
    """
    route = _ruta(metodo, ruta)
    assert route is not None, f"No hay ruta {metodo} {ruta} registrada en el router"

    guards = []
    for dependencia in route.dependant.dependencies:
        parametros = inspect.signature(dependencia.call).parameters
        if "current_user" in parametros:
            guards.append(dependencia.call)
    return guards


def _exige_autenticacion(metodo: str, ruta: str) -> bool:
    """
    ¿La ruta resuelve get_current_user en algún punto de su árbol de dependencias?

    Recursivo: en las rutas con require_admin/require_roles, get_current_user no
    cuelga de la ruta sino del guard.
    """
    route = _ruta(metodo, ruta)
    assert route is not None, f"No hay ruta {metodo} {ruta} registrada en el router"

    pendientes = list(route.dependant.dependencies)
    vistos = set()

    while pendientes:
        dependencia = pendientes.pop()
        if id(dependencia) in vistos:
            continue
        vistos.add(id(dependencia))

        if getattr(dependencia.call, "__name__", None) == "get_current_user":
            return True

        pendientes.extend(dependencia.dependencies)

    return False


# ============================================================
# 1. Toda ruta exige autenticación
# ============================================================

@pytest.mark.parametrize("metodo, ruta, permitidos", CASOS, ids=IDS)
def test_la_ruta_exige_autenticacion(metodo, ruta, permitidos):
    assert _exige_autenticacion(metodo, ruta) is True


# ============================================================
# 2. Cada ruta tiene exactamente un guard de rol, y acepta/rechaza a quien debe
# ============================================================

@pytest.mark.parametrize("metodo, ruta, permitidos", CASOS, ids=IDS)
def test_la_ruta_tiene_exactamente_un_guard_de_rol(metodo, ruta, permitidos):
    assert len(_guards_de_rol(metodo, ruta)) == 1


@pytest.mark.parametrize("metodo, ruta, permitidos", CASOS, ids=IDS)
def test_el_guard_acepta_los_roles_permitidos(metodo, ruta, permitidos):
    guard = _guards_de_rol(metodo, ruta)[0]

    for rol in permitidos:
        usuario = _usuario(rol)
        assert guard(current_user=usuario) is usuario


@pytest.mark.parametrize("metodo, ruta, permitidos", CASOS, ids=IDS)
def test_el_guard_rechaza_los_demas_roles_con_403(metodo, ruta, permitidos):
    guard = _guards_de_rol(metodo, ruta)[0]

    for rol in TODOS_LOS_ROLES:
        if rol in permitidos:
            continue
        with pytest.raises(HTTPException) as excinfo:
            guard(current_user=_usuario(rol))
        assert excinfo.value.status_code == 403


def test_crear_y_editar_decreto_son_admin_only_pero_crear_ajuste_no():
    """
    La asimetría es deliberada: un ajuste individual también lo puede cargar
    rrhh (es su trabajo del día a día), pero decretar un incremento para toda
    la planta o aplicarlo masivamente es admin.
    """
    guard_post_decreto = _guards_de_rol("POST", f"{PREFIJO}/decretos")[0]
    with pytest.raises(HTTPException) as excinfo:
        guard_post_decreto(current_user=_usuario("rrhh"))
    assert excinfo.value.status_code == 403

    guard_post_ajuste = _guards_de_rol("POST", f"{PREFIJO}/")[0]
    usuario_rrhh = _usuario("rrhh")
    assert guard_post_ajuste(current_user=usuario_rrhh) is usuario_rrhh


# ============================================================
# 3. Canarios de recuento
# ============================================================

def _rutas_del_modulo():
    """Rutas de ajustes/decretos, sin las 5 de parametros-impuesto (archivo aparte)."""
    return [
        route for route in router_ajustes.routes
        if "parametros-impuesto" not in getattr(route, "path", "")
    ]


def test_canario_cantidad_de_rutas_de_ajustes_y_decretos():
    """
    Si aparece una ruta nueva, este test falla y obliga a decidir su guard en
    vez de dejarla abierta sin que nadie lo note. Actualizar el número es
    parte del trabajo, no un arreglo del test.
    """
    assert len(_rutas_del_modulo()) == 10


def test_canario_todas_las_rutas_del_modulo_estan_cubiertas():
    """Ninguna ruta de ajustes/decretos quedó fuera de la tabla CASOS."""
    registradas = {
        (metodo, route.path)
        for route in _rutas_del_modulo()
        for metodo in route.methods
    }
    declaradas = {(metodo, ruta) for metodo, ruta, _ in CASOS}

    assert registradas == declaradas


# ============================================================
# 4. actualizar_decreto: bloqueo por ajustes ya generados
# ============================================================

class _QueryFalso:
    """Doble de db.query(...) que devuelve una fila fija en .first()."""

    def __init__(self, resultado):
        self._resultado = resultado

    def filter(self, *args, **kwargs):
        return self

    def first(self):
        return self._resultado


class _SesionFalsa:
    """Doble mínimo de Session: .query(...).filter(...).first() + commit/refresh."""

    def __init__(self, resultado_query=None):
        self._resultado_query = resultado_query
        self.commits = 0
        self.refrescados = []

    def query(self, *args, **kwargs):
        return _QueryFalso(self._resultado_query)

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        self.refrescados.append(obj)


def _decreto(id=1, anio=2024, referencia="DS 4984"):
    return SimpleNamespace(
        id=id,
        anio=anio,
        nuevo_smn=Decimal("2500.00"),
        fecha_vigencia=date(2024, 5, 1),
        referencia_decreto=referencia,
        condiciones=[],
    )


def _datos_update(anio=2024, tramos=None):
    if tramos is None:
        tramos = [SimpleNamespace(orden=1, salario_desde=None, salario_hasta=None,
                                   porcentaje_incremento=Decimal("5.00"))]
    return SimpleNamespace(
        anio=anio,
        nuevo_smn=Decimal("2600.00"),
        fecha_vigencia=date(2024, 6, 1),
        referencia_decreto="DS 4984 (corregido)",
        condiciones=tramos,
    )


def test_bloquea_edicion_si_el_decreto_ya_tiene_ajustes(monkeypatch):
    decreto = _decreto()
    monkeypatch.setattr(services, "get_decreto_by_id", lambda db, decreto_id: decreto)
    monkeypatch.setattr(services, "contar_ajustes_de_decreto", lambda db, decreto_id: 3)

    db = _SesionFalsa()
    with pytest.raises(HTTPException) as excinfo:
        services.actualizar_decreto(db, 1, _datos_update())

    assert excinfo.value.status_code == 400
    assert "3" in excinfo.value.detail
    assert db.commits == 0
    # No debe haber mutado el decreto tras el rechazo.
    assert decreto.referencia_decreto == "DS 4984"


def test_rechaza_decreto_inexistente(monkeypatch):
    monkeypatch.setattr(services, "get_decreto_by_id", lambda db, decreto_id: None)

    with pytest.raises(HTTPException) as excinfo:
        services.actualizar_decreto(_SesionFalsa(), 999, _datos_update())

    assert excinfo.value.status_code == 404


def test_rechaza_anio_duplicado_de_otro_decreto(monkeypatch):
    decreto = _decreto(id=1, anio=2024)
    otro_decreto = SimpleNamespace(id=2, anio=2025)

    monkeypatch.setattr(services, "get_decreto_by_id", lambda db, decreto_id: decreto)
    monkeypatch.setattr(services, "contar_ajustes_de_decreto", lambda db, decreto_id: 0)

    db = _SesionFalsa(resultado_query=otro_decreto)
    with pytest.raises(HTTPException) as excinfo:
        services.actualizar_decreto(db, 1, _datos_update(anio=2025))

    assert excinfo.value.status_code == 400
    assert "2025" in excinfo.value.detail
    assert db.commits == 0


def test_edita_cabecera_y_reemplaza_tramos_cuando_no_tiene_ajustes(monkeypatch):
    decreto = _decreto()
    monkeypatch.setattr(services, "get_decreto_by_id", lambda db, decreto_id: decreto)
    monkeypatch.setattr(services, "contar_ajustes_de_decreto", lambda db, decreto_id: 0)

    db = _SesionFalsa(resultado_query=None)  # nadie más tiene ese año
    datos = _datos_update(
        anio=2024,
        tramos=[
            SimpleNamespace(orden=1, salario_desde=None, salario_hasta=Decimal("2500.00"),
                             porcentaje_incremento=Decimal("6.00")),
            SimpleNamespace(orden=2, salario_desde=Decimal("2500.01"), salario_hasta=None,
                             porcentaje_incremento=Decimal("2.00")),
        ],
    )

    resultado = services.actualizar_decreto(db, 1, datos)

    assert resultado is decreto
    assert decreto.referencia_decreto == "DS 4984 (corregido)"
    assert decreto.nuevo_smn == Decimal("2600.00")
    assert len(decreto.condiciones) == 2
    assert [c.orden for c in decreto.condiciones] == [1, 2]
    assert db.commits == 1
    assert db.refrescados == [decreto]


# ============================================================
# 5. GET /decretos/{id}/ajustes: 404 si el decreto no existe
# ============================================================

def test_get_ajustes_de_decreto_404_si_no_existe(monkeypatch):
    monkeypatch.setattr(services, "get_decreto_by_id", lambda db, decreto_id: None)

    with pytest.raises(HTTPException) as excinfo:
        router_module.get_ajustes_de_decreto(decreto_id=999, db=None)

    assert excinfo.value.status_code == 404
