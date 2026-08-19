"""
Tests del RBAC de /api/v1/departamentos y de la validación de ciclos (2026-08-19).

Antes de este cambio las 7 rutas del módulo estaban COMPLETAMENTE abiertas: el
docstring del router decía "sin autenticación hasta Semana 9" y el archivo ni
siquiera importaba app.core.deps. Cualquiera sin token podía crear, renombrar o
desactivar la estructura organizacional entera.

Reparto que se prueba acá:
- Escritura (POST / PUT / DELETE) -> require_admin.
- Lectura (los 4 GET) -> get_current_user, o sea cualquier autenticado. NO es
  admin+rrhh a propósito: GET /departamentos/ alimenta el desplegable
  "Área / Departamento" del formulario de empleados, que un supervisor puede
  abrir. Con un guard de rol ahí, ese desplegable quedaría vacío por un 403.

Esa asimetría obliga a DOS comprobaciones distintas, y es la razón de que este
archivo tenga un helper que test_usuarios_roles_auth.py no necesita:

- `_guards_de_rol` (copiado de test_usuarios_roles_auth.py) detecta el guard por
  su firma, que recibe `current_user`. Sirve para require_admin.
- `_exige_autenticacion` hace falta porque get_current_user NO matchea ese
  criterio: sus parámetros son `credentials` y `db`. Además tiene que bajar
  RECURSIVAMENTE por las sub-dependencias, porque en las rutas de escritura
  get_current_user no cuelga de la ruta sino de require_admin.

La tercera parte cubre `_generaria_ciclo`, la validación nueva de services.py: el
código sólo detectaba el auto-padre (ciclo de largo 1), así que A -> B y después
mover A bajo B pasaba y dejaba una jerarquía sin raíz alcanzable.

Unitarios, sin base de datos ni TestClient. Se enumera `router.routes` y NO
`app.routes` a propósito: importar app.main arrastra DeprecationWarnings y la
suite quedó sin warnings el 2026-08-12.
"""

import inspect
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.features.employees.departamento import services
from app.features.employees.departamento.models import Departamento
from app.features.employees.departamento.router import router as router_departamentos


TODOS_LOS_ROLES = ["admin", "rrhh", "supervisor", "empleado", "consulta"]

SOLO_ADMIN = frozenset({"admin"})
# Marca "esta ruta no discrimina por rol, sólo exige estar autenticado".
CUALQUIER_AUTENTICADO = None


def _usuario(rol: str, id=1, id_empleado=3) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        username="test",
        id_empleado=id_empleado,
        rol=SimpleNamespace(nombre=rol),
    )


# La ruta que el APIRouter registra es prefijo + path del decorador. La barra
# final es parte de la ruta: sin ella FastAPI redirige (307).
#
# Agregar un endpoint nuevo sin sumarlo acá rompe los canarios de más abajo, que
# es exactamente para lo que existen.
CASOS = [
    ("POST", "/departamentos/", SOLO_ADMIN),
    ("GET", "/departamentos/", CUALQUIER_AUTENTICADO),
    ("GET", "/departamentos/raiz", CUALQUIER_AUTENTICADO),
    ("GET", "/departamentos/{departamento_id}", CUALQUIER_AUTENTICADO),
    ("GET", "/departamentos/{departamento_id}/jerarquia", CUALQUIER_AUTENTICADO),
    ("PUT", "/departamentos/{departamento_id}", SOLO_ADMIN),
    ("DELETE", "/departamentos/{departamento_id}", SOLO_ADMIN),
]

IDS = [f"{metodo} {ruta}" for metodo, ruta, _ in CASOS]

ESCRITURAS = [(m, r) for m, r, permitidos in CASOS if permitidos == SOLO_ADMIN]
LECTURAS = [(m, r) for m, r, permitidos in CASOS if permitidos is CUALQUIER_AUTENTICADO]


def _ruta(metodo: str, ruta: str):
    """La ruta registrada en el router para ese método, o None si no existe."""
    for route in router_departamentos.routes:
        if getattr(route, "path", None) == ruta and metodo in getattr(route, "methods", set()):
            return route
    return None


def _guards_de_rol(metodo: str, ruta: str):
    """
    Las dependencias de la ruta que deciden por rol.

    Se detectan por su firma (reciben `current_user`), no por su nombre: así el
    test sigue valiendo si el guard se renombra, y no confunde a get_db ni a
    get_current_user, cuyos parámetros son `credentials` y `db`.
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

    Tiene que ser recursivo: en las rutas de escritura get_current_user no cuelga
    de la ruta, sino de require_admin, que es quien lo declara en su firma. Mirar
    sólo el primer nivel daría False para las tres escrituras.

    Acá sí se compara por NOMBRE y no por firma, al revés que _guards_de_rol: lo
    que se afirma es que interviene esa función concreta, la única que convierte
    un header Authorization en un Usuario y responde 401 cuando falta.
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
    El test que impide la regresión de fondo: que una ruta de departamentos
    vuelva a quedar llamable sin token.
    """
    assert _exige_autenticacion(metodo, ruta) is True


# ============================================================
# 2. Escritura: sólo admin
# ============================================================

@pytest.mark.parametrize("metodo, ruta", ESCRITURAS, ids=[f"{m} {r}" for m, r in ESCRITURAS])
def test_la_escritura_tiene_exactamente_un_guard_de_rol(metodo, ruta):
    assert len(_guards_de_rol(metodo, ruta)) == 1


@pytest.mark.parametrize("metodo, ruta", ESCRITURAS, ids=[f"{m} {r}" for m, r in ESCRITURAS])
def test_la_escritura_acepta_admin(metodo, ruta):
    guard = _guards_de_rol(metodo, ruta)[0]
    usuario = _usuario("admin")

    assert guard(current_user=usuario) is usuario


@pytest.mark.parametrize("metodo, ruta", ESCRITURAS, ids=[f"{m} {r}" for m, r in ESCRITURAS])
def test_la_escritura_acepta_admin_en_mayusculas(metodo, ruta):
    """El nombre del rol viaja como está en rrhh.rol; la comparación es case-insensitive."""
    guard = _guards_de_rol(metodo, ruta)[0]
    usuario = _usuario("ADMIN")

    assert guard(current_user=usuario) is usuario


@pytest.mark.parametrize("rol", [r for r in TODOS_LOS_ROLES if r != "admin"])
@pytest.mark.parametrize("metodo, ruta", ESCRITURAS, ids=[f"{m} {r}" for m, r in ESCRITURAS])
def test_la_escritura_rechaza_todo_lo_demas(metodo, ruta, rol):
    """
    Incluye rrhh explícitamente: reorganizar el organigrama es administración del
    sistema, no gestión de personal. Si alguien aflojara un require_admin a
    require_roles("admin","rrhh"), esto lo delata.
    """
    guard = _guards_de_rol(metodo, ruta)[0]

    with pytest.raises(HTTPException) as exc:
        guard(current_user=_usuario(rol))

    assert exc.value.status_code == 403


# ============================================================
# 3. Lectura: autenticación sí, rol no
# ============================================================

@pytest.mark.parametrize("metodo, ruta", LECTURAS, ids=[f"{m} {r}" for m, r in LECTURAS])
def test_la_lectura_no_discrimina_por_rol(metodo, ruta):
    """
    Ningún GET debe llevar guard de rol. Es lo que mantiene vivo el desplegable
    de departamentos del formulario de empleados para un supervisor.
    """
    assert _guards_de_rol(metodo, ruta) == []


# ============================================================
# 4. Canarios de recuento
# ============================================================

def test_el_prefijo_del_router_no_cambio():
    assert router_departamentos.prefix == "/departamentos"


def test_el_router_expone_exactamente_siete_rutas():
    """
    Va a fallar cuando se agregue un endpoint, y eso es el éxito: obliga a
    decidir su guard y sumarlo a CASOS en vez de dejarlo abierto sin que nadie
    lo note. Actualizar el número es parte del trabajo, no un arreglo del test.
    """
    assert len(router_departamentos.routes) == 7


def test_todas_las_rutas_registradas_estan_en_casos():
    """
    Complementa al recuento: una ruta RENOMBRADA no cambia el total, pero rompe
    esta igualdad de conjuntos.
    """
    registradas = {
        (metodo, route.path)
        for route in router_departamentos.routes
        for metodo in route.methods
    }
    cubiertas = {(metodo, ruta) for metodo, ruta, _ in CASOS}

    assert registradas == cubiertas


# ============================================================
# 5. Validación de ciclos en la jerarquía
# ============================================================

class _QueryFalsa:
    """Resuelve `query(Departamento).filter(Departamento.id == N).first()`."""

    def __init__(self, nodos):
        self._nodos = nodos
        self._id = None

    def filter(self, criterio):
        # `Departamento.id == N` es un BinaryExpression cuyo lado derecho es un
        # BindParameter con el valor literal.
        self._id = criterio.right.value
        return self

    def first(self):
        return self._nodos.get(self._id)


class _DbFalsa:
    """
    Doble mínimo de Session. _generaria_ciclo sólo necesita resolver id -> nodo,
    así que no hace falta base de datos ni el modelo real.
    """

    def __init__(self, nodos):
        self._nodos = {nodo.id: nodo for nodo in nodos}
        self.consultas = 0

    def query(self, modelo):
        assert modelo is Departamento
        self.consultas += 1
        return _QueryFalsa(self._nodos)


def _nodo(id: int, id_padre=None) -> SimpleNamespace:
    return SimpleNamespace(id=id, id_padre=id_padre)


def test_mover_un_departamento_bajo_su_propio_hijo_es_ciclo():
    """El caso que el check de auto-padre NO cubría: A -> B, y ahora A bajo B."""
    db = _DbFalsa([_nodo(1), _nodo(2, id_padre=1)])

    assert services._generaria_ciclo(db, departamento_id=1, nuevo_padre_id=2) is True


def test_mover_un_departamento_bajo_un_nieto_tambien_es_ciclo():
    """El ancestro culpable puede estar a cualquier profundidad, no sólo a uno."""
    db = _DbFalsa([_nodo(1), _nodo(2, id_padre=1), _nodo(3, id_padre=2)])

    assert services._generaria_ciclo(db, departamento_id=1, nuevo_padre_id=3) is True


def test_mover_un_departamento_a_otra_rama_no_es_ciclo():
    """El caso legítimo tiene que seguir pasando."""
    db = _DbFalsa([_nodo(1), _nodo(2, id_padre=1), _nodo(3)])

    assert services._generaria_ciclo(db, departamento_id=2, nuevo_padre_id=3) is False


def test_colgar_de_una_raiz_no_es_ciclo():
    db = _DbFalsa([_nodo(1), _nodo(2)])

    assert services._generaria_ciclo(db, departamento_id=2, nuevo_padre_id=1) is False


def test_un_padre_inexistente_no_se_reporta_como_ciclo():
    """
    Ese caso ya lo rechaza update_departamento con 404 antes de llegar acá; lo
    que importa es que la función no explote resolviendo un None.
    """
    db = _DbFalsa([_nodo(1)])

    assert services._generaria_ciclo(db, departamento_id=1, nuevo_padre_id=99) is False


def test_un_ciclo_preexistente_entre_ancestros_no_cuelga():
    """
    Si la base ya quedó con un ciclo por datos cargados antes de esta validación,
    el recorrido tiene que cortar por el set de visitados. Sin ese corte el while
    no termina y el test colgaría la suite entera en vez de fallar.
    """
    db = _DbFalsa([_nodo(1), _nodo(10, id_padre=11), _nodo(11, id_padre=10)])

    assert services._generaria_ciclo(db, departamento_id=1, nuevo_padre_id=10) is False
    # El corte tiene que ser por visitados, no por casualidad: dos nodos en el
    # ciclo => a lo sumo un puñado de consultas, nunca un bucle.
    assert db.consultas <= 3


def test_update_departamento_rechaza_el_ciclo_con_400():
    """
    La integración: que update_departamento realmente consulte la validación y
    traduzca el resultado a un 400 legible, no que quede escrita sin usarse.
    """
    db = _DbFalsa([_nodo(1), _nodo(2, id_padre=1)])

    # get_departamento_by_id y la búsqueda del padre pasan por el mismo doble.
    with pytest.raises(HTTPException) as exc:
        services.update_departamento(
            db,
            departamento_id=1,
            data=SimpleNamespace(
                codigo=None,
                id_padre=2,
                model_dump=lambda **kwargs: {"id_padre": 2},
            ),
        )

    assert exc.value.status_code == 400
    assert "ciclo" in exc.value.detail
