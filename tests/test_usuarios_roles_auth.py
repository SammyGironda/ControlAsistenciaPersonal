"""
Tests del RBAC de /api/v1/usuarios y /api/v1/roles (2026-08-13).

Antes de este cambio, en cada uno de los dos módulos el ÚNICO endpoint con guard
era el DELETE. Eso habilitaba una escalada de privilegios anónima: POST /roles/
para crear un rol, POST /usuarios/ para crear una cuenta con ese rol, y
POST /auth/login devolvía un JWT de admin legítimo. Los dos primeros pasos son
ahora require_admin.

Tres capas cubiertas:
1. Los guards declarativos (require_admin / require_roles en el decorador),
   resueltos ENUMERANDO las rutas registradas, no leyendo el archivo — mismo
   método que test_compensacion_auth.py.
2. El guard de pertenencia de app/core/deps.py que hizo falta agregar
   (es_admin, exigir_gestion_de_usuario), que compara contra usuario.id y no
   contra id_empleado como los de /vacaciones.
3. POST /usuarios/{id}/change-password, donde ese guard vive en el CUERPO del
   endpoint, invocado directamente como función normal — estilo
   test_vacaciones_auth.py.

Unitarios, sin base de datos ni TestClient: el usuario es un SimpleNamespace y
los servicios se reemplazan con monkeypatch. Lo que se prueba es la decisión de
autorización, no la lógica de negocio de usuarios/roles.

Se enumera `router.routes` y NO `app.routes` a propósito: importar app.main
arrastra 4 DeprecationWarning de @app.on_event más uno de reportlab, y la suite
quedó sin warnings el 2026-08-12. Lo único que este archivo no cubre es el
montaje bajo API_PREFIX en main.py — verificado a mano enumerando app.routes.
"""

import inspect
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core import deps
from app.features.auth.rol.router import router as router_roles
from app.features.auth.usuario import router as endpoints_usuarios
from app.features.auth.usuario import services as services_usuarios
from app.features.auth.usuario.router import router as router_usuarios


# El servicio real nunca corre en estos tests, así que la sesión puede ser
# cualquier objeto: sólo viaja de parámetro en parámetro.
DB = object()

ID_PROPIO = 1     # id de la cuenta del usuario autenticado
ID_AJENO = 42     # cualquier otra cuenta

TODOS_LOS_ROLES = ["admin", "rrhh", "supervisor", "empleado", "consulta"]

GESTORES = {"admin", "rrhh"}
SOLO_ADMIN = {"admin"}


def _usuario(rol: str, id=ID_PROPIO, id_empleado=3) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        username="test",
        id_empleado=id_empleado,
        rol=SimpleNamespace(nombre=rol),
    )


# La ruta que el APIRouter registra es prefijo + path del decorador. La barra
# final es parte de la ruta: sin ella FastAPI redirige (307).
#
# Cada entrada es (router, método, ruta, roles que deben pasar). Agregar un
# endpoint nuevo sin sumarlo acá rompe los tests de recuento de más abajo.
CASOS = [
    (router_usuarios, "POST", "/usuarios/", SOLO_ADMIN),
    (router_usuarios, "GET", "/usuarios/", GESTORES),
    (router_usuarios, "GET", "/usuarios/{usuario_id}", GESTORES),
    (router_usuarios, "GET", "/usuarios/{usuario_id}/with-rol", GESTORES),
    (router_usuarios, "PUT", "/usuarios/{usuario_id}", SOLO_ADMIN),
    (router_usuarios, "DELETE", "/usuarios/{usuario_id}", SOLO_ADMIN),
    (router_usuarios, "PATCH", "/usuarios/{usuario_id}/toggle-activo", SOLO_ADMIN),
    (router_roles, "POST", "/roles/", SOLO_ADMIN),
    (router_roles, "GET", "/roles/", GESTORES),
    (router_roles, "GET", "/roles/{rol_id}", GESTORES),
    (router_roles, "PUT", "/roles/{rol_id}", SOLO_ADMIN),
    (router_roles, "DELETE", "/roles/{rol_id}", SOLO_ADMIN),
    (router_roles, "PATCH", "/roles/{rol_id}/toggle-activo", SOLO_ADMIN),
    (router_roles, "GET", "/roles/{rol_id}/usuarios/count", GESTORES),
]

# ids legibles en la salida de pytest: "POST /usuarios/" en vez de "CASOS3".
IDS = [f"{metodo} {ruta}" for _, metodo, ruta, _ in CASOS]


def _ruta(router, metodo: str, ruta: str):
    """La ruta registrada en el router para ese método, o None si no existe."""
    for route in router.routes:
        if getattr(route, "path", None) == ruta and metodo in getattr(route, "methods", set()):
            return route
    return None


def _guards_de_rol(router, metodo: str, ruta: str):
    """
    Las dependencias de la ruta que deciden por rol.

    Se detectan por su firma (reciben `current_user`), no por su nombre: así el
    test sigue valiendo si el guard se renombra, y no confunde a get_db ni a
    get_current_user, cuyos parámetros son `credentials` y `db`.
    """
    route = _ruta(router, metodo, ruta)
    assert route is not None, f"No hay ruta {metodo} {ruta} registrada en el router"

    guards = []
    for dependencia in route.dependant.dependencies:
        parametros = inspect.signature(dependencia.call).parameters
        if "current_user" in parametros:
            guards.append(dependencia.call)
    return guards


# ============================================================
# Guards declarativos: cada ruta tiene el suyo
# ============================================================

@pytest.mark.parametrize("router, metodo, ruta, permitidos", CASOS, ids=IDS)
def test_la_ruta_tiene_exactamente_un_guard_de_rol(router, metodo, ruta, permitidos):
    assert len(_guards_de_rol(router, metodo, ruta)) == 1


@pytest.mark.parametrize("router, metodo, ruta, permitidos", CASOS, ids=IDS)
def test_el_guard_acepta_los_roles_permitidos(router, metodo, ruta, permitidos):
    guard = _guards_de_rol(router, metodo, ruta)[0]

    for rol in permitidos:
        usuario = _usuario(rol)
        assert guard(current_user=usuario) is usuario


@pytest.mark.parametrize("router, metodo, ruta, permitidos", CASOS, ids=IDS)
def test_el_guard_acepta_los_roles_permitidos_en_mayusculas(router, metodo, ruta, permitidos):
    """El nombre del rol viaja como está en rrhh.rol; la comparación es case-insensitive."""
    guard = _guards_de_rol(router, metodo, ruta)[0]

    for rol in permitidos:
        usuario = _usuario(rol.upper())
        assert guard(current_user=usuario) is usuario


@pytest.mark.parametrize("router, metodo, ruta, permitidos", CASOS, ids=IDS)
def test_el_guard_rechaza_los_roles_no_permitidos(router, metodo, ruta, permitidos):
    guard = _guards_de_rol(router, metodo, ruta)[0]

    for rol in [r for r in TODOS_LOS_ROLES if r not in permitidos]:
        with pytest.raises(HTTPException) as exc:
            guard(current_user=_usuario(rol))

        assert exc.value.status_code == 403


@pytest.mark.parametrize("rol", TODOS_LOS_ROLES)
@pytest.mark.parametrize("router, metodo, ruta, permitidos", CASOS, ids=IDS)
def test_ningun_rol_pasa_sin_decision_explicita(router, metodo, ruta, permitidos, rol):
    """
    Todo rol de la base recibe un veredicto claro: o el guard lo devuelve, o
    levanta 403. Nunca None ni una excepción de otro tipo.
    """
    guard = _guards_de_rol(router, metodo, ruta)[0]
    usuario = _usuario(rol)

    try:
        assert guard(current_user=usuario) is usuario
    except HTTPException as exc:
        assert exc.status_code == 403


def test_rrhh_no_puede_escribir_usuarios_ni_roles():
    """
    Comprobación explícita de la regla que separa lectura de escritura: rrhh
    gestiona personal, pero no crea cuentas ni roles. Si alguien aflojara un
    require_admin a require_roles("admin","rrhh"), esto lo delata.
    """
    escrituras = [
        (router, metodo, ruta)
        for router, metodo, ruta, permitidos in CASOS
        if permitidos == SOLO_ADMIN
    ]
    assert len(escrituras) == 8

    for router, metodo, ruta in escrituras:
        guard = _guards_de_rol(router, metodo, ruta)[0]

        with pytest.raises(HTTPException) as exc:
            guard(current_user=_usuario("rrhh"))

        assert exc.value.status_code == 403


# ============================================================
# Canarios: ninguna ruta nueva sin guard, y verify-credentials eliminada
# ============================================================

def test_los_prefijos_de_los_routers_no_cambiaron():
    assert router_usuarios.prefix == "/usuarios"
    assert router_roles.prefix == "/roles"


def test_el_router_de_usuarios_expone_exactamente_ocho_rutas():
    """
    7 con guard declarativo + change-password, que lo tiene en el cuerpo.

    Si aparece una novena, este test falla y obliga a decidir su guard en vez de
    dejarla abierta sin que nadie lo note. Fija además que verify-credentials
    quedó eliminada (eran 9).
    """
    assert len(router_usuarios.routes) == 8


def test_el_router_de_roles_expone_exactamente_siete_rutas():
    assert len(router_roles.routes) == 7


def test_verify_credentials_ya_no_esta_registrada():
    """
    Se eliminó el 2026-08-13: estaba abierta y recibía la contraseña como query
    param, o sea que quedaba en los logs de acceso. POST /api/v1/auth/login la
    reemplaza.
    """
    rutas = [getattr(route, "path", None) for route in router_usuarios.routes]

    assert "/usuarios/verify-credentials" not in rutas


def test_el_servicio_verify_credentials_sigue_existiendo():
    """Se borró la ruta, no el servicio: es lo que usa POST /auth/login."""
    assert callable(services_usuarios.verify_credentials)


def test_todas_las_rutas_de_los_dos_routers_estan_en_casos():
    """
    Contracara del recuento: además de cuántas hay, que sean exactamente éstas.
    Una ruta renombrada dejaría de estar cubierta sin cambiar el total.
    """
    registradas = {
        (metodo, route.path)
        for router in (router_usuarios, router_roles)
        for route in router.routes
        for metodo in route.methods
    }
    cubiertas = {(metodo, ruta) for _, metodo, ruta, _ in CASOS}
    cubiertas.add(("POST", "/usuarios/{usuario_id}/change-password"))

    assert registradas == cubiertas


# ============================================================
# deps: es_admin
# ============================================================

@pytest.mark.parametrize("rol", ["admin", "Admin", "ADMIN"])
def test_es_admin_acepta_admin_en_cualquier_capitalizacion(rol):
    assert deps.es_admin(_usuario(rol)) is True


@pytest.mark.parametrize("rol", ["rrhh", "supervisor", "empleado", "consulta"])
def test_es_admin_rechaza_al_resto(rol):
    assert deps.es_admin(_usuario(rol)) is False


def test_es_admin_no_confunde_gestor_con_admin():
    """es_gestor incluye a rrhh; es_admin no. Son decisiones distintas."""
    rrhh = _usuario("rrhh")

    assert deps.es_gestor(rrhh) is True
    assert deps.es_admin(rrhh) is False


# ============================================================
# deps: exigir_gestion_de_usuario
# ============================================================

@pytest.mark.parametrize("rol", TODOS_LOS_ROLES)
def test_gestion_de_la_cuenta_propia_permitida_a_cualquier_rol(rol):
    assert deps.exigir_gestion_de_usuario(_usuario(rol), ID_PROPIO) is None


@pytest.mark.parametrize("rol", ["admin", "ADMIN"])
def test_admin_gestiona_cuentas_ajenas(rol):
    assert deps.exigir_gestion_de_usuario(_usuario(rol), ID_AJENO) is None


@pytest.mark.parametrize("rol", ["rrhh", "supervisor", "empleado", "consulta"])
def test_gestion_de_cuenta_ajena_prohibida_al_resto(rol):
    """Ni siquiera rrhh: para eso está PUT /usuarios/{id}, que es admin."""
    with pytest.raises(HTTPException) as exc:
        deps.exigir_gestion_de_usuario(_usuario(rol), ID_AJENO)

    assert exc.value.status_code == 403
    assert "tu propia cuenta" in exc.value.detail


def test_cuenta_sin_empleado_vinculado_gestiona_lo_propio():
    """
    Compara contra usuario.id, no contra id_empleado: una cuenta admin-only (el
    id_empleado es nullable) debe poder cambiar su propia contraseña sin recibir
    el 400 de get_actor_empleado_id.
    """
    sin_empleado = _usuario("admin", id_empleado=None)

    assert deps.exigir_gestion_de_usuario(sin_empleado, ID_PROPIO) is None


def test_empleado_sin_cuenta_vinculada_tambien_gestiona_lo_propio():
    sin_empleado = _usuario("empleado", id_empleado=None)

    assert deps.exigir_gestion_de_usuario(sin_empleado, ID_PROPIO) is None


# ============================================================
# router: POST /usuarios/{id}/change-password
# ============================================================

@pytest.fixture
def change_password_espiado(monkeypatch):
    """Reemplaza services.change_password y registra si llegó a llamarse."""
    llamadas = []

    def _fake(db, usuario_id, password_data):
        llamadas.append((usuario_id, password_data))
        return {"message": "Contraseña actualizada exitosamente"}

    monkeypatch.setattr(services_usuarios, "change_password", _fake)
    return llamadas


def test_change_password_no_tiene_guard_de_rol():
    """
    Es deliberado: la decisión depende de a quién apunta el path comparado con
    quién es el actor, así que vive en el cuerpo y no en dependencies=[...].
    """
    assert _guards_de_rol(router_usuarios, "POST", "/usuarios/{usuario_id}/change-password") == []


def test_change_password_exige_autenticacion():
    """Sin guard de rol, pero nunca abierto: get_current_user está en la firma."""
    route = _ruta(router_usuarios, "POST", "/usuarios/{usuario_id}/change-password")
    llamadas = [dependencia.call for dependencia in route.dependant.dependencies]

    assert deps.get_current_user in llamadas


@pytest.mark.parametrize("rol", TODOS_LOS_ROLES)
def test_cualquier_rol_cambia_su_propia_contrasenia(change_password_espiado, rol):
    resultado = endpoints_usuarios.change_password(
        usuario_id=ID_PROPIO,
        password_data="payload",
        db=DB,
        current_user=_usuario(rol),
    )

    assert resultado == {"message": "Contraseña actualizada exitosamente"}
    assert change_password_espiado == [(ID_PROPIO, "payload")]


def test_admin_cambia_la_contrasenia_de_otra_cuenta(change_password_espiado):
    endpoints_usuarios.change_password(
        usuario_id=ID_AJENO,
        password_data="payload",
        db=DB,
        current_user=_usuario("admin"),
    )

    assert change_password_espiado == [(ID_AJENO, "payload")]


@pytest.mark.parametrize("rol", ["rrhh", "supervisor", "empleado", "consulta"])
def test_cambiar_contrasenia_ajena_da_403_y_no_toca_el_servicio(change_password_espiado, rol):
    """La validación corre ANTES de mutar: el servicio no debe llegar a ejecutarse."""
    with pytest.raises(HTTPException) as exc:
        endpoints_usuarios.change_password(
            usuario_id=ID_AJENO,
            password_data="payload",
            db=DB,
            current_user=_usuario(rol),
        )

    assert exc.value.status_code == 403
    assert change_password_espiado == []
