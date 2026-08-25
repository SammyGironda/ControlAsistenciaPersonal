"""
Tests del RBAC de /api/v1/reportes (2026-08-24).

La auditoria encontro 5 de las 10 rutas del modulo COMPLETAMENTE abiertas:
GET /, GET /{id}, GET /{id}/descargar, PUT /{id} y el DELETE soft de /{id}.

Las dos escrituras eran las mas visibles -- un PUT con {"activo": false} sin
token desactivaba un registro de la bitacora -- pero la mas grave era
GET /{id}/descargar, que no devuelve metadatos sino el ARCHIVO FISICO via
FileResponse: el XLSX de planilla trae los salarios individuales de todos los
empleados y el ID es incremental, asi que cualquiera sin token podia recorrerlos.

Reparto que se prueba aca:
- Lectura (los 3 GET) -> require_roles("admin", "rrhh").
- Escritura (PUT y los 2 DELETE) -> require_admin.

La lectura SI discrimina por rol, al reves que en /departamentos: estos GET no
alimentan ningun desplegable de otra pantalla. El unico consumidor es
Frontend/src/api/reportes.js -> hooks/useReportes.js -> pages/reportes/ReportesPage.jsx,
que ya era de facto admin+rrhh porque sus 4 botones de generar exigen ese rol
desde el 2026-08-10.

La escritura es admin-only y no rrhh por la misma frontera que PUT /usuarios/{id}
y POST /parametros-impuesto: desactivar un registro de la bitacora es administrar
la evidencia, no gestionar personal. Como eliminar_reporte es soft delete
(activo = False), rrhh sigue pudiendo leerlo todo; lo que no puede es retirarlo
del listado por defecto.

La tabla CASOS cubre las 10 rutas del modulo, no solo las 5 que este cambio
toco, para que los canarios del final protejan el modulo entero.

Unitarios, sin base de datos ni TestClient. Se enumera `router.routes` y NO
`app.routes` a proposito: importar app.main arrastra DeprecationWarnings y la
suite quedo sin warnings el 2026-08-12.
"""

import inspect
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.features.reports.reporte.router import router as router_reportes


TODOS_LOS_ROLES = ["admin", "rrhh", "supervisor", "empleado", "consulta"]

SOLO_ADMIN = frozenset({"admin"})
ADMIN_Y_RRHH = frozenset({"admin", "rrhh"})

PREFIJO = "/reportes"

# El path del recurso lleva el conversor `:int` tal como lo registra el router.
# Sin el, _ruta() no encuentra nada y todos los tests fallarian por "no hay ruta".
ID = "{reporte_id:int}"


def _usuario(rol: str, id=1, id_empleado=3) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        username="test",
        id_empleado=id_empleado,
        rol=SimpleNamespace(nombre=rol),
    )


# La ruta que el APIRouter registra es prefijo + path del decorador.
#
# Agregar un endpoint nuevo de reportes sin sumarlo aca rompe los canarios del
# final, que es exactamente para lo que existen.
CASOS = [
    # Los 4 generadores: ya tenian guard desde el 2026-08-10.
    ("POST", f"{PREFIJO}/asistencia-mensual", ADMIN_Y_RRHH),
    ("POST", f"{PREFIJO}/planilla", ADMIN_Y_RRHH),
    ("POST", f"{PREFIJO}/vacaciones", ADMIN_Y_RRHH),
    ("POST", f"{PREFIJO}/individual/{{id_empleado:int}}", ADMIN_Y_RRHH),
    # Lectura: abiertas hasta el 2026-08-24.
    ("GET", f"{PREFIJO}/", ADMIN_Y_RRHH),
    ("GET", f"{PREFIJO}/{ID}", ADMIN_Y_RRHH),
    ("GET", f"{PREFIJO}/{ID}/descargar", ADMIN_Y_RRHH),
    # Escritura: PUT y el DELETE soft estaban abiertos; el permanente ya tenia guard.
    ("PUT", f"{PREFIJO}/{ID}", SOLO_ADMIN),
    ("DELETE", f"{PREFIJO}/{ID}", SOLO_ADMIN),
    ("DELETE", f"{PREFIJO}/{ID}/permanente", SOLO_ADMIN),
]

IDS = [f"{metodo} {ruta}" for metodo, ruta, _ in CASOS]


def _ruta(metodo: str, ruta: str):
    """La ruta registrada en el router para ese metodo, o None si no existe."""
    for route in router_reportes.routes:
        if getattr(route, "path", None) == ruta and metodo in getattr(route, "methods", set()):
            return route
    return None


def _guards_de_rol(metodo: str, ruta: str):
    """
    Las dependencias de la ruta que deciden por rol.

    Se detectan por su firma (reciben `current_user`), no por su nombre: asi el
    test sigue valiendo si el guard se renombra, y no confunde a get_db ni a
    get_current_user, cuyos parametros son `credentials` y `db`.

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
    La ruta resuelve get_current_user en algun punto de su arbol de dependencias?

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
# 1. Toda ruta exige autenticacion
# ============================================================

@pytest.mark.parametrize("metodo, ruta, permitidos", CASOS, ids=IDS)
def test_la_ruta_exige_autenticacion(metodo, ruta, permitidos):
    """
    El test que impide la regresion de fondo: que la bitacora de reportes -- o el
    archivo con los salarios -- vuelva a ser legible o mutable sin token.
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


# ============================================================
# 3. La asimetria lectura/escritura, afirmada explicitamente
# ============================================================

def test_rrhh_lee_pero_no_desactiva():
    """
    rrhh necesita la bitacora para gestion de personal, pero dar de baja un
    registro con valor probatorio es administrar la evidencia: admin-only.

    Vale la pena afirmarlo aparte de la tabla porque es la decision de diseno del
    modulo, y un cambio que unifique los dos guards la borraria sin ruido.
    """
    for metodo, ruta in [
        ("GET", f"{PREFIJO}/"),
        ("GET", f"{PREFIJO}/{ID}"),
        ("GET", f"{PREFIJO}/{ID}/descargar"),
    ]:
        guard = _guards_de_rol(metodo, ruta)[0]
        usuario_rrhh = _usuario("rrhh")
        assert guard(current_user=usuario_rrhh) is usuario_rrhh

    for metodo, ruta in [
        ("PUT", f"{PREFIJO}/{ID}"),
        ("DELETE", f"{PREFIJO}/{ID}"),
        ("DELETE", f"{PREFIJO}/{ID}/permanente"),
    ]:
        guard = _guards_de_rol(metodo, ruta)[0]
        with pytest.raises(HTTPException) as excinfo:
            guard(current_user=_usuario("rrhh"))
        assert excinfo.value.status_code == 403


def _acepta(guard, rol: str) -> bool:
    """True si el guard deja pasar a ese rol, False si responde 403."""
    try:
        guard(current_user=_usuario(rol))
    except HTTPException as excinfo:
        assert excinfo.status_code == 403
        return False
    return True


def test_descargar_decide_igual_que_la_lectura_de_metadatos():
    """
    GET /{id} devuelve la fila de bitacora; GET /{id}/descargar devuelve el XLSX
    con los salarios individuales. Se comparan los dos guards rol por rol en las
    DOS direcciones a proposito:

    - la descarga no puede aceptar a alguien que los metadatos rechazan (seria
      un agujero: el contenido mas sensible con el guard mas laxo);
    - ni rechazar a alguien que los metadatos aceptan (romperia el boton de
      descargar de ReportesPage.jsx para rrhh, con un 403 sin causa visible).

    Afirmar una sola direccion dejaria pasar la otra sin ruido.
    """
    guard_metadatos = _guards_de_rol("GET", f"{PREFIJO}/{ID}")[0]
    guard_descarga = _guards_de_rol("GET", f"{PREFIJO}/{ID}/descargar")[0]

    for rol in TODOS_LOS_ROLES:
        assert _acepta(guard_descarga, rol) == _acepta(guard_metadatos, rol), (
            f"El rol {rol} recibe distinta respuesta en descargar que en metadatos"
        )


def test_ningun_guard_de_escritura_acepta_a_un_no_admin():
    """El PUT y los dos DELETE rechazan a los 4 roles que no son admin."""
    escrituras = [
        ("PUT", f"{PREFIJO}/{ID}"),
        ("DELETE", f"{PREFIJO}/{ID}"),
        ("DELETE", f"{PREFIJO}/{ID}/permanente"),
    ]

    for metodo, ruta in escrituras:
        guard = _guards_de_rol(metodo, ruta)[0]
        for rol in TODOS_LOS_ROLES:
            if rol == "admin":
                continue
            with pytest.raises(HTTPException) as excinfo:
                guard(current_user=_usuario(rol))
            assert excinfo.value.status_code == 403


# ============================================================
# 4. Canarios de recuento
# ============================================================

def test_canario_cantidad_de_rutas_de_reportes():
    """
    Si aparece una ruta nueva de reportes, este test falla y obliga a decidir su
    guard en vez de dejarla abierta sin que nadie lo note. Actualizar el numero
    es parte del trabajo, no un arreglo del test.
    """
    assert len(router_reportes.routes) == 10


def test_canario_todas_las_rutas_de_reportes_estan_cubiertas():
    """Ninguna ruta del router quedo fuera de la tabla CASOS."""
    registradas = {
        (metodo, route.path)
        for route in router_reportes.routes
        for metodo in route.methods
    }
    declaradas = {(metodo, ruta) for metodo, ruta, _ in CASOS}

    assert registradas == declaradas
