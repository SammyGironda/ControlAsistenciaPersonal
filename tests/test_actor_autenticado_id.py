"""
Tests del actor autenticado en columnas con FK a usuario (2026-08-13).

Los 5 endpoints que pueblan una columna con FK a `usuario.id` — los 4 generadores
de /reportes (reporte.id_generado_por) y POST /marcaciones/upload-excel
(archivo_excel.id_subido_por) — leían `current_user.id_usuario`, que NO EXISTE:

  - `get_current_user` devuelve el objeto ORM Usuario releído de la base.
  - El modelo declara su PK como `id` (auth/usuario/models.py).
  - `id_usuario` es sólo un CLAIM del JWT (core/security.py), no un atributo.

O sea que los 5 atravesaban el guard de rol y morían con AttributeError -> 500:
no se podía generar ningún reporte ni subir el Excel mensual de marcaciones.
Se introdujo el 2026-08-10 al reemplazar los campos *_por client-supplied por el
actor autenticado, y lo propagó el docstring de core/deps.py.

Unitarios, sin base de datos ni TestClient: los servicios se reemplazan con
monkeypatch y se comprueba QUÉ id recibieron. Lo que se prueba es la derivación
del actor, no la generación real del XLSX/PDF ni el parseo del Excel.

CLAVE DEL DISEÑO: el doble de usuario NO tiene el atributo `id_usuario`, igual
que el Usuario real. Un doble que tuviera los dos nombres pasaría el test con el
código roto y no detectaría nada.
"""

import ast
import asyncio
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.features.attendance.marcacion import router as endpoints_marcaciones
from app.features.attendance.marcacion import services as services_marcaciones
from app.features.auth.usuario.models import Usuario
from app.features.reports.reporte import router as endpoints_reportes
from app.features.reports.reporte import services as services_reportes
from app.features.reports.reporte.schemas import (
    ReporteAsistenciaMensualRequest,
    ReporteIndividualRequest,
    ReportePlanillaRequest,
    ReporteVacacionesRequest,
)


# El servicio real nunca corre en estos tests, así que la sesión puede ser
# cualquier objeto: sólo viaja de parámetro en parámetro.
DB = object()

ID_USUARIO_AUTENTICADO = 7   # PK de rrhh.usuario: lo que DEBE llegar al servicio
ID_EMPLEADO_VINCULADO = 3    # FK a rrhh.empleado: NO es lo que va en estas columnas
ID_EMPLEADO_REPORTADO = 12   # el empleado sobre el que se pide el reporte individual


def _usuario() -> SimpleNamespace:
    """
    Doble de Usuario con la misma superficie que el modelo real: `id` e
    `id_empleado`, y deliberadamente SIN `id_usuario`. Si alguien vuelve a
    escribir current_user.id_usuario, el endpoint revienta acá igual que en
    producción, en vez de pasar el test silenciosamente.
    """
    return SimpleNamespace(
        id=ID_USUARIO_AUTENTICADO,
        username="test",
        id_empleado=ID_EMPLEADO_VINCULADO,
        rol=SimpleNamespace(nombre="admin"),
    )


# ============================================================
# 1. La causa raíz, pinneada contra el modelo real
# ============================================================

def test_usuario_declara_su_pk_como_id():
    """La PK del modelo es `id`: es el atributo que hay que usar."""
    assert hasattr(Usuario, "id")


def test_usuario_no_tiene_atributo_id_usuario():
    """
    `id_usuario` es un claim del JWT, no una columna. Si este test empieza a
    fallar porque el modelo ganó ese atributo, revisar los 5 endpoints: la
    confusión volvería a ser silenciosa.
    """
    assert not hasattr(Usuario, "id_usuario")

    with pytest.raises(AttributeError):
        Usuario().id_usuario


# ============================================================
# 2. Los 4 generadores de /reportes
# ============================================================

# Cada caso es (nombre del servicio espiado, invocación del endpoint). El
# id_generado_por viaja SIEMPRE como último posicional, incluso en el
# individual, que además recibe id_empleado.
CASOS_REPORTE = [
    (
        "generar_reporte_asistencia_mensual",
        lambda user: endpoints_reportes.generar_asistencia_mensual(
            data=ReporteAsistenciaMensualRequest(anio=2026, mes=8),
            db=DB,
            current_user=user,
        ),
    ),
    (
        "generar_reporte_planilla",
        lambda user: endpoints_reportes.generar_planilla(
            data=ReportePlanillaRequest(anio=2026, mes=8),
            db=DB,
            current_user=user,
        ),
    ),
    (
        "generar_reporte_vacaciones",
        lambda user: endpoints_reportes.generar_vacaciones(
            data=ReporteVacacionesRequest(gestion=2026),
            db=DB,
            current_user=user,
        ),
    ),
    (
        "generar_reporte_individual_pdf",
        lambda user: endpoints_reportes.generar_individual(
            id_empleado=ID_EMPLEADO_REPORTADO,
            data=ReporteIndividualRequest(
                fecha_inicio=date(2026, 8, 1),
                fecha_fin=date(2026, 8, 31),
            ),
            db=DB,
            current_user=user,
        ),
    ),
]

IDS_REPORTE = [nombre for nombre, _ in CASOS_REPORTE]


@pytest.mark.parametrize("nombre_servicio, invocar", CASOS_REPORTE, ids=IDS_REPORTE)
def test_generador_de_reporte_deriva_id_generado_por_del_actor(
    nombre_servicio, invocar, monkeypatch
):
    """
    El endpoint debe pasarle al servicio la PK del usuario autenticado. Antes de
    la corrección ni siquiera llegaba a llamarlo: moría en AttributeError.
    """
    recibido = {}

    def espia(*args, **kwargs):
        recibido["args"] = args
        return "reporte-generado"

    monkeypatch.setattr(services_reportes, nombre_servicio, espia)

    resultado = invocar(_usuario())

    assert resultado == "reporte-generado", "el endpoint no llegó a llamar al servicio"
    assert recibido["args"][-1] == ID_USUARIO_AUTENTICADO
    assert recibido["args"][-1] != ID_EMPLEADO_VINCULADO, (
        "id_generado_por tiene FK a usuario.id, no a empleado.id"
    )


# ============================================================
# 3. POST /marcaciones/upload-excel
# ============================================================

# El endpoint es async y el venv no tiene pytest-asyncio: se corre con
# asyncio.run(), que es stdlib y no agrega dependencias a la suite.

# Respuesta mínima que satisface UploadExcelResponse: el endpoint construye el
# schema con **resultado, así que un dict incompleto fallaría por validación y
# enmascararía lo que se quiere probar.
RESULTADO_UPLOAD = {
    "archivo_id": 1,
    "nombre_archivo": "marcaciones.xlsx",
    "estado": "completado",
    "mensaje": "Archivo procesado exitosamente",
}


def test_upload_excel_deriva_id_subido_por_del_actor(monkeypatch):
    """
    archivo_excel.id_subido_por también tiene FK a usuario.id. El .xlsx del
    nombre importa: con otra extensión el endpoint corta con 400 antes de
    llamar al servicio y el test no probaría nada.
    """
    recibido = {}

    def espia(db, file, id_subido_por, *args, **kwargs):
        recibido["id_subido_por"] = id_subido_por
        return dict(RESULTADO_UPLOAD)

    monkeypatch.setattr(services_marcaciones, "procesar_archivo_excel", espia)

    respuesta = asyncio.run(
        endpoints_marcaciones.upload_excel_marcaciones(
            file=SimpleNamespace(filename="marcaciones.xlsx"),
            db=DB,
            current_user=_usuario(),
        )
    )

    assert respuesta.archivo_id == 1, "el endpoint no llegó a llamar al servicio"
    assert recibido["id_subido_por"] == ID_USUARIO_AUTENTICADO
    assert recibido["id_subido_por"] != ID_EMPLEADO_VINCULADO


# ============================================================
# 4. Guardia anti-recurrencia sobre todo app/
# ============================================================

DIRECTORIO_APP = Path(__file__).resolve().parent.parent / "app"


def _accesos_a_id_usuario_sobre_current_user(archivo: Path):
    """
    Devuelve las líneas donde se lee `current_user.id_usuario`.

    Se usa el AST y no un grep de texto a propósito: el docstring de
    core/deps.py menciona el nombre incorrecto para advertir sobre este mismo
    bug, y un grep lo marcaría como violación. El AST sólo ve accesos reales a
    atributo, no strings ni comentarios.
    """
    arbol = ast.parse(archivo.read_text(encoding="utf-8"))

    return [
        nodo.lineno
        for nodo in ast.walk(arbol)
        if isinstance(nodo, ast.Attribute)
        and nodo.attr == "id_usuario"
        and isinstance(nodo.value, ast.Name)
        and nodo.value.id == "current_user"
    ]


def test_ningun_endpoint_lee_current_user_id_usuario():
    """
    Lo que evita que el error vuelva en un endpoint futuro: cualquier
    `current_user.id_usuario` nuevo en app/ rompe la suite en vez de esperar a
    dar 500 en producción.
    """
    violaciones = [
        f"{archivo.relative_to(DIRECTORIO_APP.parent)}:{linea}"
        for archivo in sorted(DIRECTORIO_APP.rglob("*.py"))
        for linea in _accesos_a_id_usuario_sobre_current_user(archivo)
    ]

    assert violaciones == [], (
        "current_user es el objeto ORM Usuario y su PK se llama `id`; "
        "`id_usuario` es sólo un claim del JWT y levanta AttributeError -> 500. "
        f"Usar current_user.id en: {', '.join(violaciones)}"
    )
