"""
Tests del RBAC de /api/v1/ajustes-salariales/parametros-impuesto y del cierre
automático de vigencia (2026-08-19).

Antes de este cambio las 4 rutas del módulo estaban COMPLETAMENTE abiertas,
incluido el POST. Como rrhh.parametro_impuesto alimenta la vista
v_saldo_impuestos_planilla, cualquiera sin token podía insertar RC_IVA al 0% o
al 999% y alterar el salario neto de todos los empleados en el siguiente
reporte — sin rastro de autoría (la tabla no tiene columna de actor) y sin forma
de revertirlo por API (no hay UPDATE ni DELETE).

Reparto que se prueba acá:
- Escritura (POST) -> require_admin.
- Lectura (los 4 GET) -> require_roles("admin", "rrhh").

A diferencia de /departamentos, acá la lectura SÍ discrimina por rol: estos GET
no alimentan ningún desplegable de otra pantalla. El frontend no tenía cliente
de este módulo y el único consumidor de la tabla en el backend es la vista SQL,
que la lee directamente y no por HTTP.

La segunda parte cubre create_parametro_impuesto, que ahora cierra la vigencia
de la tasa anterior del mismo concepto en la misma transacción.

Unitarios, sin base de datos ni TestClient. Se enumera `router.routes` y NO
`app.routes` a propósito: importar app.main arrastra DeprecationWarnings y la
suite quedó sin warnings el 2026-08-12.
"""

import inspect
from datetime import date
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.features.contracts.ajuste_salarial import services
from app.features.contracts.ajuste_salarial.router import router as router_ajustes


TODOS_LOS_ROLES = ["admin", "rrhh", "supervisor", "empleado", "consulta"]

SOLO_ADMIN = frozenset({"admin"})
ADMIN_Y_RRHH = frozenset({"admin", "rrhh"})

PREFIJO = "/ajustes-salariales/parametros-impuesto"


def _usuario(rol: str, id=1, id_empleado=3) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        username="test",
        id_empleado=id_empleado,
        rol=SimpleNamespace(nombre=rol),
    )


# La ruta que el APIRouter registra es prefijo + path del decorador.
#
# Agregar un endpoint nuevo de parametros-impuesto sin sumarlo acá rompe los
# canarios del final, que es exactamente para lo que existen.
CASOS = [
    ("POST", PREFIJO, SOLO_ADMIN),
    ("GET", PREFIJO, ADMIN_Y_RRHH),
    ("GET", f"{PREFIJO}/vigentes", ADMIN_Y_RRHH),
    ("GET", f"{PREFIJO}/vigente/{{nombre}}", ADMIN_Y_RRHH),
    ("GET", f"{PREFIJO}/historial/{{nombre}}", ADMIN_Y_RRHH),
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

    Copiado de test_departamentos_auth.py / test_usuarios_roles_auth.py.
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

    Tiene que ser recursivo: get_current_user no cuelga de la ruta, sino de
    require_admin / require_roles, que son quienes lo declaran en su firma.
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
    """
    El test que impide la regresión de fondo: que una tasa de impuesto vuelva a
    ser escribible o legible sin token.
    """
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


def test_solo_el_post_es_admin_only():
    """
    La asimetría es deliberada y vale la pena afirmarla: escribir una tasa es
    admin, leerla la necesita también rrhh para gestión de personal.
    """
    guard_post = _guards_de_rol("POST", PREFIJO)[0]

    with pytest.raises(HTTPException) as excinfo:
        guard_post(current_user=_usuario("rrhh"))
    assert excinfo.value.status_code == 403

    guard_get = _guards_de_rol("GET", PREFIJO)[0]
    usuario_rrhh = _usuario("rrhh")
    assert guard_get(current_user=usuario_rrhh) is usuario_rrhh


# ============================================================
# 3. Canarios de recuento
# ============================================================

def test_canario_cantidad_de_rutas_de_parametros_impuesto():
    """
    Si aparece una ruta nueva de parametros-impuesto, este test falla y obliga a
    decidir su guard en vez de dejarla abierta sin que nadie lo note.
    Actualizar el número es parte del trabajo, no un arreglo del test.
    """
    rutas = [
        route for route in router_ajustes.routes
        if "parametros-impuesto" in getattr(route, "path", "")
    ]
    assert len(rutas) == 5


def test_canario_todas_las_rutas_de_parametros_impuesto_estan_cubiertas():
    """Ninguna ruta de parametros-impuesto quedó fuera de la tabla CASOS."""
    registradas = {
        (metodo, route.path)
        for route in router_ajustes.routes
        if "parametros-impuesto" in getattr(route, "path", "")
        for metodo in route.methods
    }
    declaradas = {(metodo, ruta) for metodo, ruta, _ in CASOS}

    assert registradas == declaradas


# ============================================================
# 4. Cierre automático de la vigencia anterior
# ============================================================

class _QueryFalso:
    """Doble de db.query(...) que devuelve una fila fija en .first()."""

    def __init__(self, resultado):
        self._resultado = resultado

    def filter(self, *args, **kwargs):
        return self

    def order_by(self, *args, **kwargs):
        return self

    def first(self):
        return self._resultado


class _SesionFalsa:
    """Doble mínimo de Session que registra si hubo commit."""

    def __init__(self, anterior=None):
        self._anterior = anterior
        self.agregados = []
        self.commits = 0
        self.refrescados = []

    def query(self, *args, **kwargs):
        return _QueryFalso(self._anterior)

    def add(self, obj):
        self.agregados.append(obj)

    def commit(self):
        self.commits += 1

    def refresh(self, obj):
        self.refrescados.append(obj)


def _tasa(nombre="RC_IVA", tipo="LABORAL", porcentaje="13.00",
          inicio=date(1992, 1, 1), fin=None):
    return SimpleNamespace(
        nombre=nombre,
        tipo_aporte=tipo,
        porcentaje=porcentaje,
        fecha_vigencia_inicio=inicio,
        fecha_vigencia_fin=fin,
    )


def _datos(nombre="RC_IVA", tipo="LABORAL", porcentaje="15.00",
           inicio=date(2026, 1, 1), fin=None, descripcion=None):
    return SimpleNamespace(
        nombre=nombre,
        tipo_aporte=tipo,
        porcentaje=porcentaje,
        fecha_vigencia_inicio=inicio,
        fecha_vigencia_fin=fin,
        descripcion=descripcion,
    )


def test_cierra_la_vigencia_anterior_un_dia_antes():
    """
    Un día antes y no el mismo día: get_parametro_vigente y la vista SQL filtran
    `fecha_vigencia_fin >= fecha` (inclusive), así que cerrar en la misma fecha
    dejaría un día con las dos tasas vigentes.
    """
    anterior = _tasa()
    db = _SesionFalsa(anterior)

    services.create_parametro_impuesto(db, _datos(inicio=date(2026, 1, 1)))

    assert anterior.fecha_vigencia_fin == date(2025, 12, 31)
    assert db.commits == 1


def test_el_alta_y_el_cierre_van_en_el_mismo_commit():
    """El efecto y su marca de control no pueden ir en commits separados."""
    anterior = _tasa()
    db = _SesionFalsa(anterior)

    services.create_parametro_impuesto(db, _datos())

    assert db.commits == 1
    assert len(db.agregados) == 1


def test_sin_tasa_anterior_solo_inserta():
    db = _SesionFalsa(anterior=None)

    services.create_parametro_impuesto(db, _datos(nombre="CONCEPTO_NUEVO"))

    assert db.commits == 1
    assert len(db.agregados) == 1


def test_no_reabre_una_tasa_anterior_ya_cerrada():
    """Si la anterior ya tenía fecha de fin, se respeta la que estaba."""
    anterior = _tasa(inicio=date(2010, 1, 1), fin=date(2024, 9, 30))
    db = _SesionFalsa(anterior)

    services.create_parametro_impuesto(db, _datos(inicio=date(2024, 10, 1)))

    assert anterior.fecha_vigencia_fin == date(2024, 9, 30)
    assert db.commits == 1


def test_rechaza_cambiar_el_tipo_de_aporte_de_un_concepto():
    anterior = _tasa(tipo="LABORAL")
    db = _SesionFalsa(anterior)

    with pytest.raises(HTTPException) as excinfo:
        services.create_parametro_impuesto(db, _datos(tipo="PATRONAL"))

    assert excinfo.value.status_code == 400
    assert db.commits == 0


def test_rechaza_una_fecha_de_inicio_anterior_o_igual_a_la_de_la_tasa_previa():
    """
    Sin este 400 el cierre calcularía fecha_vigencia_fin <= fecha_vigencia_inicio
    y violaría chk_parametro_fechas: el usuario recibiría un IntegrityError como
    500 en vez de un mensaje legible.
    """
    anterior = _tasa(inicio=date(2020, 1, 1))

    for inicio in (date(2020, 1, 1), date(2019, 6, 30)):
        db = _SesionFalsa(_tasa(inicio=date(2020, 1, 1)))
        with pytest.raises(HTTPException) as excinfo:
            services.create_parametro_impuesto(db, _datos(inicio=inicio))
        assert excinfo.value.status_code == 400
        assert db.commits == 0

    assert anterior.fecha_vigencia_fin is None


def test_rechaza_el_solapamiento_con_una_tasa_ya_cerrada():
    anterior = _tasa(inicio=date(2010, 1, 1), fin=date(2024, 9, 30))
    db = _SesionFalsa(anterior)

    with pytest.raises(HTTPException) as excinfo:
        services.create_parametro_impuesto(db, _datos(inicio=date(2024, 9, 15)))

    assert excinfo.value.status_code == 400
    assert db.commits == 0


def test_ante_un_rechazo_no_muta_la_tasa_anterior():
    """
    Validar ANTES de mutar: si el chequeo corriera después del setattr, la sesión
    quedaría con la tasa anterior cerrada aunque el alta se rechace.
    """
    anterior = _tasa(tipo="LABORAL")
    db = _SesionFalsa(anterior)

    with pytest.raises(HTTPException):
        services.create_parametro_impuesto(db, _datos(tipo="PATRONAL"))

    assert anterior.fecha_vigencia_fin is None
    assert db.agregados == []
