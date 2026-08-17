"""
Tests del alta de usuarios con contraseña temporal (2026-08-17).

Hasta ahora POST /usuarios/ recibía username y password del cliente y los
guardaba tal cual: el admin inventaba el username, elegía una contraseña, y esa
contraseña quedaba como definitiva sin que su dueño la cambiara nunca. Tampoco
había recuperación — no hay SMTP configurado y change_password exige la
contraseña actual incluso para el admin.

Ahora el admin indica a QUIÉN (id_empleado) y con QUÉ ROL, y el backend deriva el
username del nombre del empleado, genera una contraseña temporal aleatoria y
marca la cuenta con requiere_cambio_password. La contraseña se devuelve en texto
plano una sola vez.

Cinco capas cubiertas:
1. security.generar_password_temporal: aleatoriedad, política y legibilidad.
2. services._slug / generar_username: convención, acentos y desempate.
3. services.create_usuario: flag, hash, validaciones y carrera de username.
4. services.resetear_password / cambiar_password_obligatorio.
5. Los guards de las dos rutas nuevas, enumerando las rutas registradas.

Unitarios, sin base de datos ni TestClient: la sesión es un doble y los servicios
se reemplazan con monkeypatch. Los dobles son SimpleNamespace y no Mock a
propósito: un Mock responde a cualquier atributo y haría pasar tests con el
código roto (la lección de test_actor_autenticado_id.py).

Se enumera `router.routes` y NO `app.routes`, igual que test_usuarios_roles_auth.py:
importar app.main arrastra DeprecationWarnings de @app.on_event y de reportlab, y
la suite quedó sin warnings el 2026-08-12.
"""

import inspect
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core import deps
from app.core.security import (
    LONGITUD_PASSWORD_TEMPORAL,
    generar_password_temporal,
    verify_password,
)
from app.features.auth.router import router as router_auth
from app.features.auth.schemas import (
    CambioPasswordObligatorioRequest,
    UsuarioTokenInfo,
)
from app.features.auth.usuario import services
from app.features.auth.usuario.router import router as router_usuarios
from app.features.auth.usuario.schemas import (
    UsuarioChangePassword,
    UsuarioCreate,
    validar_password_fuerte,
)
from app.features.employees.empleado.models import EstadoEmpleadoEnum


TODOS_LOS_ROLES = ["admin", "rrhh", "supervisor", "empleado", "consulta"]

# Los que NO pueden recibir una cuenta: no hay pantallas de autoservicio todavía.
ROLES_NO_ASIGNABLES = ["empleado", "consulta"]

# Caracteres que se confunden al dictar la contraseña por teléfono.
AMBIGUOS = "0Oo1lI"


# ============================================================
# Dobles
# ============================================================

def _empleado(nombres="Juan", apellidos="Perez", id=5, estado=EstadoEmpleadoEnum.activo):
    return SimpleNamespace(id=id, nombres=nombres, apellidos=apellidos, estado=estado)


class FakeDB:
    """
    Doble de Session con lo mínimo que tocan estos servicios.

    `add` acumula, `commit` puede fallar una cantidad configurable de veces para
    simular la carrera de username, y `refresh` no hace nada porque no hay base
    que releer.
    """

    def __init__(self, empleado=None, usuario_de_empleado=None, fallos_de_commit=0):
        self._empleado = empleado
        self._usuario_de_empleado = usuario_de_empleado
        self.fallos_de_commit = fallos_de_commit
        self.agregados = []
        self.commits = 0
        self.rollbacks = 0

    def get(self, _modelo, _pk):
        return self._empleado

    def execute(self, _stmt):
        # La única query que estos servicios hacen por `execute` es la de
        # "¿este empleado ya tiene usuario?".
        return SimpleNamespace(scalar_one_or_none=lambda: self._usuario_de_empleado)

    def add(self, objeto):
        self.agregados.append(objeto)

    def commit(self):
        if self.fallos_de_commit > 0:
            self.fallos_de_commit -= 1
            from sqlalchemy.exc import IntegrityError
            raise IntegrityError("duplicate key", None, Exception("uq_usuario_username"))
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def refresh(self, _objeto):
        pass


@pytest.fixture
def rol_admin(monkeypatch):
    """get_rol devuelve un rol asignable. Devuelve el doble para poder mutarle el nombre."""
    rol = SimpleNamespace(id=1, nombre="admin")
    monkeypatch.setattr(services, "get_rol", lambda db, id_rol: rol)
    return rol


@pytest.fixture
def sin_usernames_tomados(monkeypatch):
    """
    Reemplaza get_usuario_by_username por un set en memoria.

    Devuelve el set para que cada test decida qué usernames ya existen. La
    comparación es en minúsculas, igual que el servicio real (func.lower).
    """
    tomados = set()
    monkeypatch.setattr(
        services,
        "get_usuario_by_username",
        lambda db, username: username.lower() in tomados,
    )
    return tomados


# ============================================================
# 1. generar_password_temporal
# ============================================================

def test_la_longitud_por_defecto_es_doce():
    assert len(generar_password_temporal()) == LONGITUD_PASSWORD_TEMPORAL == 12


@pytest.mark.parametrize("longitud", [8, 12, 16, 40])
def test_respeta_la_longitud_pedida(longitud):
    assert len(generar_password_temporal(longitud)) == longitud


@pytest.mark.parametrize("longitud", [0, 1, 7, -3])
def test_rechaza_longitudes_demasiado_cortas(longitud):
    """Por debajo de 8 no entra la política de fortaleza que el sistema exige."""
    with pytest.raises(ValueError):
        generar_password_temporal(longitud)


def test_siempre_trae_mayuscula_minuscula_digito_y_simbolo():
    """No es azar: los cuatro se construyen primero y después se baraja."""
    for _ in range(200):
        password = generar_password_temporal()

        assert any(c.isupper() for c in password)
        assert any(c.islower() for c in password)
        assert any(c.isdigit() for c in password)
        assert any(not c.isalnum() for c in password)


def test_nunca_usa_caracteres_ambiguos():
    """Se dicta por teléfono: un 0 confundido con O es un login fallido."""
    for _ in range(200):
        password = generar_password_temporal()

        assert not set(password) & set(AMBIGUOS), f"'{password}' tiene caracteres ambiguos"


def test_dos_invocaciones_no_repiten_el_valor():
    assert len({generar_password_temporal() for _ in range(200)}) == 200


def test_la_temporal_siempre_cumple_la_politica_del_sistema():
    """
    Si no, el backend entregaría una contraseña que él mismo rechaza al validarla.
    """
    for _ in range(100):
        assert validar_password_fuerte(generar_password_temporal())


# ============================================================
# 2. _slug y generar_username
# ============================================================

@pytest.mark.parametrize(
    "texto, esperado",
    [
        ("Juan", "juan"),
        ("Pérez", "perez"),
        ("Ñuñez", "nunez"),
        ("MARÍA", "maria"),
        ("O'Brien", "obrien"),
        ("De-La-Cruz", "delacruz"),
        ("Juan Carlos", "juan"),        # sólo la primera palabra
        ("  Ana  ", "ana"),             # se ignoran los espacios de borde
        ("Perez2", "perez2"),           # los dígitos sobreviven
        ("", ""),
        ("   ", ""),
    ],
)
def test_slug_normaliza_acentos_y_deja_solo_alfanumericos(texto, esperado):
    assert services._slug(texto) == esperado


def test_slug_de_none_no_revienta():
    assert services._slug(None) == ""


def test_username_sigue_la_convencion_primernombre_punto_apellido(sin_usernames_tomados):
    db = FakeDB()

    assert services.generar_username(db, _empleado("Juan", "Perez")) == "juan.perez"


def test_username_ignora_acentos_y_segundos_nombres(sin_usernames_tomados):
    db = FakeDB()
    empleado = _empleado("José María", "Ñuñez Gómez")

    assert services.generar_username(db, empleado) == "jose.nunez"


def test_username_agrega_sufijo_numerico_ante_colision(sin_usernames_tomados):
    sin_usernames_tomados.add("juan.perez")
    db = FakeDB()

    assert services.generar_username(db, _empleado("Juan", "Perez")) == "juan.perez2"


def test_username_sigue_incrementando_el_sufijo(sin_usernames_tomados):
    sin_usernames_tomados.update({"juan.perez", "juan.perez2", "juan.perez3"})
    db = FakeDB()

    assert services.generar_username(db, _empleado("Juan", "Perez")) == "juan.perez4"


def test_la_colision_es_case_insensitive(sin_usernames_tomados):
    """
    En la base el username puede estar guardado con otra capitalización;
    get_usuario_by_username compara con func.lower.
    """
    sin_usernames_tomados.add("juan.perez")
    db = FakeDB()

    # El set guarda minúsculas y el doble compara en minúsculas: si el servicio
    # no consultara así, devolvería 'juan.perez' pisando la cuenta existente.
    assert services.generar_username(db, _empleado("JUAN", "PEREZ")) == "juan.perez2"


def test_username_nunca_supera_los_cincuenta_caracteres(sin_usernames_tomados):
    """`username` es String(50): un valor más largo moriría con DataError."""
    db = FakeDB()
    empleado = _empleado("Maximiliano" * 5, "Wolfeschlegelsteinhausenberger" * 3)

    assert len(services.generar_username(db, empleado)) <= 50


def test_el_sufijo_entra_dentro_del_limite_no_lo_desborda(sin_usernames_tomados):
    """El sufijo recorta la base, no se agrega encima del máximo."""
    db = FakeDB()
    empleado = _empleado("Maximiliano" * 5, "Wolfeschlegelstein" * 3)

    primero = services.generar_username(db, empleado)
    sin_usernames_tomados.add(primero.lower())
    segundo = services.generar_username(db, empleado)

    assert len(segundo) <= 50
    assert segundo != primero
    assert segundo.endswith("2")


def test_empleado_sin_nombres_cae_a_un_username_valido(sin_usernames_tomados):
    """Datos incompletos no deben tumbar el alta con un username vacío."""
    db = FakeDB()

    username = services.generar_username(db, _empleado("", ""))

    assert len(username) >= 3
    assert username == "usuario"


def test_nombre_muy_corto_se_completa_al_minimo(sin_usernames_tomados):
    """El username tiene que tener al menos 3 caracteres."""
    db = FakeDB()

    assert len(services.generar_username(db, _empleado("Li", ""))) >= 3


# ============================================================
# 3. create_usuario
# ============================================================

def test_create_devuelve_la_cuenta_y_la_password_en_texto_plano(rol_admin, sin_usernames_tomados):
    db = FakeDB(empleado=_empleado())

    usuario, password = services.create_usuario(db, UsuarioCreate(id_empleado=5, id_rol=1))

    assert usuario.username == "juan.perez"
    assert isinstance(password, str) and len(password) == 12
    assert db.commits == 1


def test_la_cuenta_nace_exigiendo_cambio_de_password(rol_admin, sin_usernames_tomados):
    db = FakeDB(empleado=_empleado())

    usuario, _ = services.create_usuario(db, UsuarioCreate(id_empleado=5, id_rol=1))

    assert usuario.requiere_cambio_password is True


def test_el_hash_guardado_verifica_contra_la_password_devuelta(rol_admin, sin_usernames_tomados):
    """La contraseña que recibe el admin tiene que servir para loguearse."""
    db = FakeDB(empleado=_empleado())

    usuario, password = services.create_usuario(db, UsuarioCreate(id_empleado=5, id_rol=1))

    assert verify_password(password, usuario.password_hash)


def test_la_password_no_se_persiste_en_texto_plano(rol_admin, sin_usernames_tomados):
    """Sólo se guarda el hash bcrypt: el texto plano existe únicamente en la respuesta."""
    db = FakeDB(empleado=_empleado())

    usuario, password = services.create_usuario(db, UsuarioCreate(id_empleado=5, id_rol=1))

    assert password not in usuario.password_hash
    assert usuario.password_hash.startswith("$2")


@pytest.mark.parametrize("rol", ROLES_NO_ASIGNABLES)
def test_rechaza_los_roles_sin_pantallas_de_autoservicio(rol, rol_admin, sin_usernames_tomados):
    rol_admin.nombre = rol
    db = FakeDB(empleado=_empleado())

    with pytest.raises(HTTPException) as exc:
        services.create_usuario(db, UsuarioCreate(id_empleado=5, id_rol=4))

    assert exc.value.status_code == 400
    assert db.agregados == [], "no debe llegar a construir la cuenta"
    assert db.commits == 0


@pytest.mark.parametrize("rol", ["admin", "rrhh", "supervisor", "ADMIN", "RRHH"])
def test_acepta_los_roles_asignables_en_cualquier_capitalizacion(rol, rol_admin, sin_usernames_tomados):
    """El nombre viaja como esté en rrhh.rol; la comparación es case-insensitive."""
    rol_admin.nombre = rol
    db = FakeDB(empleado=_empleado())

    usuario, _ = services.create_usuario(db, UsuarioCreate(id_empleado=5, id_rol=1))

    assert usuario is not None


def test_empleado_inexistente_da_404(rol_admin, sin_usernames_tomados):
    db = FakeDB(empleado=None)

    with pytest.raises(HTTPException) as exc:
        services.create_usuario(db, UsuarioCreate(id_empleado=999, id_rol=1))

    assert exc.value.status_code == 404
    assert db.commits == 0


def test_empleado_dado_de_baja_da_400(rol_admin, sin_usernames_tomados):
    db = FakeDB(empleado=_empleado(estado=EstadoEmpleadoEnum.baja))

    with pytest.raises(HTTPException) as exc:
        services.create_usuario(db, UsuarioCreate(id_empleado=5, id_rol=1))

    assert exc.value.status_code == 400
    assert "baja" in exc.value.detail
    assert db.commits == 0


def test_empleado_que_ya_tiene_cuenta_da_400(rol_admin, sin_usernames_tomados):
    db = FakeDB(empleado=_empleado(), usuario_de_empleado=SimpleNamespace(id=1))

    with pytest.raises(HTTPException) as exc:
        services.create_usuario(db, UsuarioCreate(id_empleado=5, id_rol=1))

    assert exc.value.status_code == 400
    assert "ya tiene un usuario" in exc.value.detail
    assert db.commits == 0


def test_una_colision_en_el_insert_hace_rollback_y_reintenta(rol_admin, sin_usernames_tomados):
    """
    Entre generar_username y el INSERT otro admin pudo tomar el username. La
    UNIQUE de la base es la que decide; el rollback es obligatorio o la sesión de
    SQLAlchemy queda rota para todo lo que siga.
    """
    db = FakeDB(empleado=_empleado(), fallos_de_commit=1)

    usuario, password = services.create_usuario(db, UsuarioCreate(id_empleado=5, id_rol=1))

    assert db.rollbacks == 1
    assert db.commits == 1
    assert verify_password(password, usuario.password_hash)


def test_si_todos_los_intentos_colisionan_devuelve_409_y_no_500(rol_admin, sin_usernames_tomados):
    db = FakeDB(empleado=_empleado(), fallos_de_commit=services.MAX_INTENTOS_USERNAME)

    with pytest.raises(HTTPException) as exc:
        services.create_usuario(db, UsuarioCreate(id_empleado=5, id_rol=1))

    assert exc.value.status_code == 409
    assert db.rollbacks == services.MAX_INTENTOS_USERNAME


def test_usuario_create_ya_no_acepta_username_ni_password():
    """
    El contrato se reemplazó a propósito: no debe quedar ninguna vía de alta que
    fije una contraseña definitiva elegida por otra persona.
    """
    campos = set(UsuarioCreate.model_fields)

    assert campos == {"id_empleado", "id_rol", "activo"}


def test_id_empleado_es_obligatorio():
    """Sin empleado no hay nombre del que derivar el username."""
    with pytest.raises(Exception):
        UsuarioCreate(id_rol=1)


# ============================================================
# 4. resetear_password y cambiar_password_obligatorio
# ============================================================

def _usuario_persistido(password="ClaveVieja1", requiere_cambio=False):
    """
    Doble con la superficie real de Usuario, incluidos set_password/check_password.

    El hash es real (bcrypt), no simulado: así los tests comprueban de verdad que
    la contraseña nueva sirve y la vieja deja de servir.
    """
    from app.core.security import hash_password

    usuario = SimpleNamespace(
        id=7,
        username="juan.perez",
        password_hash=hash_password(password),
        requiere_cambio_password=requiere_cambio,
    )
    usuario.set_password = lambda p: setattr(usuario, "password_hash", hash_password(p))
    usuario.check_password = lambda p: verify_password(p, usuario.password_hash)
    return usuario


@pytest.fixture
def usuario_en_base(monkeypatch):
    """get_usuario devuelve un usuario real con hash bcrypt."""
    usuario = _usuario_persistido()
    monkeypatch.setattr(services, "get_usuario", lambda db, usuario_id: usuario)
    return usuario


def test_resetear_vuelve_a_exigir_el_cambio(usuario_en_base):
    db = FakeDB()

    _, password = services.resetear_password(db, 7)

    assert usuario_en_base.requiere_cambio_password is True
    assert verify_password(password, usuario_en_base.password_hash)
    assert db.commits == 1


def test_resetear_invalida_la_password_anterior(usuario_en_base):
    services.resetear_password(FakeDB(), 7)

    assert not usuario_en_base.check_password("ClaveVieja1")


def test_resetear_no_pide_la_password_actual(usuario_en_base):
    """
    Es la vía de recuperación: si la pidiera, un usuario que olvidó su clave no
    tendría salida. Por eso el endpoint está restringido a admin.
    """
    assert "password" not in inspect.signature(services.resetear_password).parameters


def test_cambio_obligatorio_baja_el_flag_y_cambia_el_hash(monkeypatch):
    usuario = _usuario_persistido(password="Temporal1", requiere_cambio=True)
    monkeypatch.setattr(services, "get_usuario", lambda db, usuario_id: usuario)
    db = FakeDB()

    resultado = services.cambiar_password_obligatorio(
        db, 7, CambioPasswordObligatorioRequest(
            password_actual="Temporal1", password_nueva="MiClaveNueva1"
        )
    )

    assert usuario.requiere_cambio_password is False
    assert usuario.check_password("MiClaveNueva1")
    assert not usuario.check_password("Temporal1")
    assert resultado["requiere_cambio_password"] is False
    # El hash y el flag van en una sola transacción: si el flag bajara en un
    # commit aparte, un fallo entre ambos dejaría la cuenta mintiendo.
    assert db.commits == 1


def test_password_actual_incorrecta_da_400_y_no_muta_nada(monkeypatch):
    usuario = _usuario_persistido(password="Temporal1", requiere_cambio=True)
    monkeypatch.setattr(services, "get_usuario", lambda db, usuario_id: usuario)
    hash_original = usuario.password_hash
    db = FakeDB()

    with pytest.raises(HTTPException) as exc:
        services.cambiar_password_obligatorio(
            db, 7, CambioPasswordObligatorioRequest(
                password_actual="LaEquivocada1", password_nueva="MiClaveNueva1"
            )
        )

    assert exc.value.status_code == 400
    assert usuario.password_hash == hash_original
    assert usuario.requiere_cambio_password is True, "el flag no debe bajar"
    assert db.commits == 0


def test_reusar_la_misma_password_da_400(monkeypatch):
    """El punto del flujo es retirar la temporal, no confirmarla."""
    usuario = _usuario_persistido(password="Temporal1", requiere_cambio=True)
    monkeypatch.setattr(services, "get_usuario", lambda db, usuario_id: usuario)
    db = FakeDB()

    with pytest.raises(HTTPException) as exc:
        services.cambiar_password_obligatorio(
            db, 7, CambioPasswordObligatorioRequest(
                password_actual="Temporal1", password_nueva="Temporal1"
            )
        )

    assert exc.value.status_code == 400
    assert "distinta" in exc.value.detail
    assert usuario.requiere_cambio_password is True
    assert db.commits == 0


def test_el_cambio_obligatorio_funciona_con_el_flag_ya_en_false(monkeypatch):
    """
    No exige requiere_cambio_password=True a propósito: verifica la contraseña
    actual de la propia cuenta, así que no hay diferencia de seguridad, y
    rechazar cuando el flag ya bajó volvería frágil el flujo ante un doble submit.
    """
    usuario = _usuario_persistido(password="ClaveVieja1", requiere_cambio=False)
    monkeypatch.setattr(services, "get_usuario", lambda db, usuario_id: usuario)

    services.cambiar_password_obligatorio(
        FakeDB(), 7, CambioPasswordObligatorioRequest(
            password_actual="ClaveVieja1", password_nueva="MiClaveNueva1"
        )
    )

    assert usuario.check_password("MiClaveNueva1")


def test_change_password_tambien_salda_la_temporal(monkeypatch):
    """
    La otra vía de cambio conociendo la anterior. Si no bajara el flag, un usuario
    que usó este endpoint seguiría siendo mandado al cambio obligatorio para
    siempre.
    """
    usuario = _usuario_persistido(password="Temporal1", requiere_cambio=True)
    monkeypatch.setattr(services, "get_usuario", lambda db, usuario_id, **kw: usuario)

    services.change_password(
        FakeDB(), 7, UsuarioChangePassword(
            password_actual="Temporal1", password_nueva="MiClaveNueva1"
        )
    )

    assert usuario.requiere_cambio_password is False


# ============================================================
# 5. Guards de las rutas nuevas
# ============================================================

def _ruta(router, metodo: str, ruta: str):
    for route in router.routes:
        if getattr(route, "path", None) == ruta and metodo in getattr(route, "methods", set()):
            return route
    return None


def _guards_de_rol(router, metodo: str, ruta: str):
    """
    Las dependencias de la ruta que deciden por rol.

    Se detectan por su firma (reciben `current_user`) y no por su nombre, igual
    que en test_usuarios_roles_auth.py: así el test sigue valiendo si el guard se
    renombra, y no confunde a get_db ni a get_current_user.
    """
    route = _ruta(router, metodo, ruta)
    assert route is not None, f"No hay ruta {metodo} {ruta} registrada en el router"

    return [
        dependencia.call
        for dependencia in route.dependant.dependencies
        if "current_user" in inspect.signature(dependencia.call).parameters
    ]


def test_resetear_password_tiene_exactamente_un_guard_de_rol():
    guards = _guards_de_rol(router_usuarios, "POST", "/usuarios/{usuario_id}/resetear-password")

    assert len(guards) == 1


def test_solo_admin_puede_resetear_una_password():
    """
    No pide la contraseña actual, así que quien llegue acá puede tomar cualquier
    cuenta. Ni siquiera rrhh entra.
    """
    guard = _guards_de_rol(router_usuarios, "POST", "/usuarios/{usuario_id}/resetear-password")[0]

    admin = SimpleNamespace(id=1, rol=SimpleNamespace(nombre="admin"))
    assert guard(current_user=admin) is admin

    for rol in [r for r in TODOS_LOS_ROLES if r != "admin"]:
        with pytest.raises(HTTPException) as exc:
            guard(current_user=SimpleNamespace(id=1, rol=SimpleNamespace(nombre=rol)))

        assert exc.value.status_code == 403


def test_cambiar_password_obligatorio_no_tiene_guard_de_rol():
    """
    Deliberado: opera siempre sobre la cuenta del token, así que cualquier rol
    debe poder retirar su propia contraseña temporal.
    """
    assert _guards_de_rol(router_auth, "POST", "/auth/cambiar-password-obligatorio") == []


def test_cambiar_password_obligatorio_exige_autenticacion():
    """Sin guard de rol, pero nunca abierto: no hay usuario_id en el path que suplantar."""
    route = _ruta(router_auth, "POST", "/auth/cambiar-password-obligatorio")
    llamadas = [dependencia.call for dependencia in route.dependant.dependencies]

    assert deps.get_current_user in llamadas


def test_el_router_de_auth_expone_exactamente_tres_rutas():
    """
    /login (abierta a propósito), /me y /cambiar-password-obligatorio. Una cuarta
    obliga a decidir su guard en vez de dejarla abierta sin que nadie lo note.
    """
    assert len(router_auth.routes) == 3


# ============================================================
# 6. Contrato hacia el frontend
# ============================================================

def test_el_login_informa_si_hay_que_cambiar_la_password():
    """
    Es lo que el frontend necesita para mandar al cambio obligatorio antes de
    dejar entrar al resto del sistema.
    """
    assert "requiere_cambio_password" in UsuarioTokenInfo.model_fields


def test_el_flag_tiene_default_false():
    """Las cuentas que no lo declaran no deben quedar bloqueadas por omisión."""
    info = UsuarioTokenInfo(id=1, username="admin", id_rol=1, nombre_rol="admin")

    assert info.requiere_cambio_password is False


@pytest.mark.parametrize(
    "password",
    ["corta1A", "todominusculas1", "TODOMAYUSCULAS1", "SinDigitosAca", "1234567", ""],
)
def test_la_politica_rechaza_passwords_debiles(password):
    with pytest.raises(ValueError):
        validar_password_fuerte(password)


@pytest.mark.parametrize("password", ["Password123", "MiClaveNueva1", "aB3defgh"])
def test_la_politica_acepta_passwords_validas(password):
    assert validar_password_fuerte(password) == password


def test_el_cambio_obligatorio_valida_la_politica_en_el_schema():
    """Llega como 422 antes de tocar el servicio, no como 400 desde adentro."""
    with pytest.raises(Exception):
        CambioPasswordObligatorioRequest(password_actual="Temporal1", password_nueva="debil")


def test_la_password_actual_no_lleva_politica():
    """Es la temporal ya existente, no una que el usuario esté eligiendo."""
    datos = CambioPasswordObligatorioRequest(
        password_actual="x", password_nueva="MiClaveNueva1"
    )

    assert datos.password_actual == "x"
