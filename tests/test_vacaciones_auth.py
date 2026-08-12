"""
Tests del RBAC de /api/v1/vacaciones (2026-08-12).

Dos capas cubiertas:
1. Los helpers de pertenencia de app/core/deps.py (es_gestor, puede_leer_todo,
   es_aprobador, exigir_lectura_de_empleado, exigir_gestion_de_empleado,
   alcance_lectura).
2. Las funciones de vacaciones/router.py donde ese guard vive en el cuerpo del
   endpoint, invocadas directamente como funciones normales.

Unitarios, sin base de datos ni TestClient, igual que test_rbac.py y
test_jwt_auth.py: el usuario es un SimpleNamespace y los servicios se
reemplazan con monkeypatch. Lo que se prueba es la decisión de autorización, no
la lógica de negocio (que ya cubre test_vacacion_cambio_estado.py).

Los guards puestos en el decorador (require_roles / require_admin) NO se prueban
acá: son la misma closure ya cubierta por test_rbac.py. La verificación de que
cada ruta la tiene aplicada se hizo enumerando app.routes.
"""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.core import deps
from app.features.attendance.vacaciones import router as vacaciones_router
from app.features.attendance.vacaciones import services
from app.features.attendance.vacaciones.models import EstadoDetalleVacacionEnum
from app.features.attendance.vacaciones.schemas import CambiarEstadoRequest


# El servicio real nunca corre en estos tests, así que la sesión puede ser
# cualquier objeto: sólo viaja de parámetro en parámetro.
DB = object()

DUENIO = 7        # id_empleado dueño del recurso bajo prueba
AJENO = 99        # cualquier otro empleado


def _usuario(rol: str, id_empleado=DUENIO) -> SimpleNamespace:
    return SimpleNamespace(
        id=1,
        id_usuario=1,
        username="test",
        id_empleado=id_empleado,
        rol=SimpleNamespace(nombre=rol),
    )


# ============================================================
# deps: clasificación por rol
# ============================================================

@pytest.mark.parametrize("rol", ["admin", "rrhh", "ADMIN", "RRHH"])
def test_es_gestor_acepta_admin_y_rrhh(rol):
    assert deps.es_gestor(_usuario(rol)) is True


@pytest.mark.parametrize("rol", ["supervisor", "empleado", "consulta"])
def test_es_gestor_rechaza_al_resto(rol):
    assert deps.es_gestor(_usuario(rol)) is False


@pytest.mark.parametrize("rol", ["admin", "rrhh", "supervisor", "Supervisor"])
def test_puede_leer_todo_incluye_supervisor(rol):
    assert deps.puede_leer_todo(_usuario(rol)) is True


@pytest.mark.parametrize("rol", ["empleado", "consulta"])
def test_puede_leer_todo_rechaza_empleado_y_consulta(rol):
    assert deps.puede_leer_todo(_usuario(rol)) is False


@pytest.mark.parametrize("rol", ["admin", "rrhh", "supervisor"])
def test_es_aprobador_acepta_los_tres_roles_de_aprobacion(rol):
    assert deps.es_aprobador(_usuario(rol)) is True


@pytest.mark.parametrize("rol", ["empleado", "consulta"])
def test_es_aprobador_rechaza_al_resto(rol):
    assert deps.es_aprobador(_usuario(rol)) is False


# ============================================================
# deps: exigir_lectura_de_empleado
# ============================================================

@pytest.mark.parametrize("rol", ["admin", "rrhh", "supervisor"])
def test_lectura_de_empleado_ajeno_permitida_a_roles_con_lectura_total(rol):
    """Un supervisor necesita ver el saldo del solicitante para poder evaluarlo."""
    assert deps.exigir_lectura_de_empleado(_usuario(rol), AJENO) is None


def test_lectura_de_lo_propio_permitida_al_empleado():
    assert deps.exigir_lectura_de_empleado(_usuario("empleado"), DUENIO) is None


@pytest.mark.parametrize("rol", ["empleado", "consulta"])
def test_lectura_de_empleado_ajeno_da_403(rol):
    with pytest.raises(HTTPException) as exc:
        deps.exigir_lectura_de_empleado(_usuario(rol), AJENO)

    assert exc.value.status_code == 403


def test_lectura_con_cuenta_sin_empleado_vinculado_da_400():
    """Se propaga el 400 de get_actor_empleado_id, con su mensaje accionable."""
    with pytest.raises(HTTPException) as exc:
        deps.exigir_lectura_de_empleado(_usuario("empleado", id_empleado=None), DUENIO)

    assert exc.value.status_code == 400
    assert "vinculado a un empleado" in exc.value.detail


def test_lectura_con_cuenta_admin_sin_empleado_vinculado_pasa():
    """El admin del seed no tiene id_empleado y aun así debe poder consultar."""
    assert deps.exigir_lectura_de_empleado(_usuario("admin", id_empleado=None), AJENO) is None


# ============================================================
# deps: exigir_gestion_de_empleado
# ============================================================

@pytest.mark.parametrize("rol", ["admin", "rrhh"])
def test_gestion_de_empleado_ajeno_permitida_a_gestores(rol):
    assert deps.exigir_gestion_de_empleado(_usuario(rol), AJENO) is None


def test_gestion_de_empleado_ajeno_prohibida_al_supervisor():
    """Diferencia clave con la lectura: el supervisor aprueba, no solicita por otro."""
    with pytest.raises(HTTPException) as exc:
        deps.exigir_gestion_de_empleado(_usuario("supervisor"), AJENO)

    assert exc.value.status_code == 403


def test_gestion_de_lo_propio_permitida_al_empleado():
    assert deps.exigir_gestion_de_empleado(_usuario("empleado"), DUENIO) is None


def test_gestion_de_empleado_ajeno_da_403():
    with pytest.raises(HTTPException) as exc:
        deps.exigir_gestion_de_empleado(_usuario("empleado"), AJENO)

    assert exc.value.status_code == 403


# ============================================================
# deps: alcance_lectura
# ============================================================

@pytest.mark.parametrize("rol", ["admin", "rrhh", "supervisor"])
def test_alcance_lectura_sin_restriccion_para_lectura_total(rol):
    assert deps.alcance_lectura(_usuario(rol)) is None


@pytest.mark.parametrize("rol", ["empleado", "consulta"])
def test_alcance_lectura_devuelve_el_propio_id_empleado(rol):
    assert deps.alcance_lectura(_usuario(rol)) == DUENIO


def test_alcance_lectura_sin_empleado_vinculado_da_400():
    with pytest.raises(HTTPException) as exc:
        deps.alcance_lectura(_usuario("empleado", id_empleado=None))

    assert exc.value.status_code == 400


# ============================================================
# router: POST /{id_vacacion}/detalles (el guard pedido explícitamente)
# ============================================================

@pytest.fixture
def crear_detalle_espiado(monkeypatch):
    """Reemplaza crear_detalle_vacacion y registra si llegó a llamarse."""
    llamadas = []

    def _fake(db, id_vacacion, data):
        llamadas.append((id_vacacion, data))
        return "detalle-creado"

    monkeypatch.setattr(services, "crear_detalle_vacacion", _fake)
    return llamadas


def _duenio_de_vacacion(monkeypatch, id_empleado):
    monkeypatch.setattr(
        services, "obtener_empleado_de_vacacion", lambda db, id_vacacion: id_empleado
    )


def test_crear_detalle_propio_permitido_al_empleado(monkeypatch, crear_detalle_espiado):
    _duenio_de_vacacion(monkeypatch, DUENIO)

    resultado = vacaciones_router.crear_detalle_vacacion(
        id_vacacion=3, data="payload", db=DB, current_user=_usuario("empleado")
    )

    assert resultado == "detalle-creado"
    assert crear_detalle_espiado == [(3, "payload")]


def test_crear_detalle_ajeno_da_403_y_no_toca_el_servicio(monkeypatch, crear_detalle_espiado):
    """La validación corre ANTES de mutar: el servicio no debe llegar a ejecutarse."""
    _duenio_de_vacacion(monkeypatch, AJENO)

    with pytest.raises(HTTPException) as exc:
        vacaciones_router.crear_detalle_vacacion(
            id_vacacion=3, data="payload", db=DB, current_user=_usuario("empleado")
        )

    assert exc.value.status_code == 403
    assert crear_detalle_espiado == []


def test_crear_detalle_ajeno_prohibido_tambien_al_supervisor(monkeypatch, crear_detalle_espiado):
    _duenio_de_vacacion(monkeypatch, AJENO)

    with pytest.raises(HTTPException) as exc:
        vacaciones_router.crear_detalle_vacacion(
            id_vacacion=3, data="payload", db=DB, current_user=_usuario("supervisor")
        )

    assert exc.value.status_code == 403
    assert crear_detalle_espiado == []


@pytest.mark.parametrize("rol", ["admin", "rrhh"])
def test_crear_detalle_ajeno_permitido_a_gestores(monkeypatch, crear_detalle_espiado, rol):
    _duenio_de_vacacion(monkeypatch, AJENO)

    vacaciones_router.crear_detalle_vacacion(
        id_vacacion=3, data="payload", db=DB, current_user=_usuario(rol)
    )

    assert crear_detalle_espiado == [(3, "payload")]


def test_crear_detalle_sobre_vacacion_inexistente_da_404_no_403(monkeypatch, crear_detalle_espiado):
    """Un ID que no existe debe seguir respondiendo 404 aunque quien pida sea un empleado."""
    def _no_existe(db, id_vacacion):
        raise HTTPException(status_code=404, detail=f"Vacación con ID {id_vacacion} no encontrada")

    monkeypatch.setattr(services, "obtener_empleado_de_vacacion", _no_existe)

    with pytest.raises(HTTPException) as exc:
        vacaciones_router.crear_detalle_vacacion(
            id_vacacion=999, data="payload", db=DB, current_user=_usuario("empleado")
        )

    assert exc.value.status_code == 404
    assert crear_detalle_espiado == []


# ============================================================
# router: POST /detalles/{id}/cambiar-estado
# ============================================================

@pytest.fixture
def cambiar_estado_espiado(monkeypatch):
    llamadas = []

    def _fake(db, id, data, id_aprobado_por=None):
        llamadas.append((id, data.nuevo_estado, id_aprobado_por))
        return "estado-cambiado"

    monkeypatch.setattr(services, "cambiar_estado_detalle", _fake)
    return llamadas


def _duenio_de_detalle(monkeypatch, id_empleado):
    monkeypatch.setattr(
        services, "obtener_empleado_de_detalle", lambda db, id_detalle: id_empleado
    )


def test_empleado_puede_cancelar_su_propia_solicitud(monkeypatch, cambiar_estado_espiado):
    _duenio_de_detalle(monkeypatch, DUENIO)
    data = CambiarEstadoRequest(nuevo_estado=EstadoDetalleVacacionEnum.cancelado)

    resultado = vacaciones_router.cambiar_estado_detalle(
        id=5, data=data, db=DB, current_user=_usuario("empleado")
    )

    assert resultado == "estado-cambiado"
    assert cambiar_estado_espiado == [(5, EstadoDetalleVacacionEnum.cancelado, DUENIO)]


@pytest.mark.parametrize(
    "estado",
    [
        EstadoDetalleVacacionEnum.aprobado,
        EstadoDetalleVacacionEnum.rechazado,
        EstadoDetalleVacacionEnum.tomado,
    ],
)
def test_empleado_no_puede_aprobar_rechazar_ni_tomar_lo_propio(
    monkeypatch, cambiar_estado_espiado, estado
):
    _duenio_de_detalle(monkeypatch, DUENIO)
    data = CambiarEstadoRequest(nuevo_estado=estado)

    with pytest.raises(HTTPException) as exc:
        vacaciones_router.cambiar_estado_detalle(
            id=5, data=data, db=DB, current_user=_usuario("empleado")
        )

    assert exc.value.status_code == 403
    assert "cancelar" in exc.value.detail
    assert cambiar_estado_espiado == []


def test_empleado_no_puede_cancelar_solicitud_ajena(monkeypatch, cambiar_estado_espiado):
    _duenio_de_detalle(monkeypatch, AJENO)
    data = CambiarEstadoRequest(nuevo_estado=EstadoDetalleVacacionEnum.cancelado)

    with pytest.raises(HTTPException) as exc:
        vacaciones_router.cambiar_estado_detalle(
            id=5, data=data, db=DB, current_user=_usuario("empleado")
        )

    assert exc.value.status_code == 403
    assert cambiar_estado_espiado == []


@pytest.mark.parametrize("rol", ["admin", "rrhh", "supervisor"])
def test_aprobadores_cambian_estado_de_solicitudes_ajenas(monkeypatch, cambiar_estado_espiado, rol):
    # Ni siquiera debería consultarse el dueño: si lo hiciera, este doble lo delataría
    # devolviendo un empleado ajeno.
    _duenio_de_detalle(monkeypatch, AJENO)
    data = CambiarEstadoRequest(nuevo_estado=EstadoDetalleVacacionEnum.aprobado)

    vacaciones_router.cambiar_estado_detalle(
        id=5, data=data, db=DB, current_user=_usuario(rol)
    )

    assert cambiar_estado_espiado == [(5, EstadoDetalleVacacionEnum.aprobado, DUENIO)]


# ============================================================
# router: listados con filtro forzado
# ============================================================

@pytest.fixture
def listar_vacaciones_espiado(monkeypatch):
    llamadas = []
    monkeypatch.setattr(
        services,
        "listar_vacaciones",
        lambda db, **kwargs: llamadas.append(kwargs) or [],
    )
    return llamadas


@pytest.fixture
def listar_detalles_espiado(monkeypatch):
    llamadas = []
    monkeypatch.setattr(
        services,
        "listar_todos_detalles",
        lambda db, **kwargs: llamadas.append(kwargs) or [],
    )
    return llamadas


def test_listar_vacaciones_fuerza_el_filtro_del_empleado(listar_vacaciones_espiado):
    """Pedir explícitamente otro empleado no sirve: se pisa con el propio."""
    vacaciones_router.listar_vacaciones(
        id_empleado=AJENO, gestion=2026, skip=0, limit=100,
        db=DB, current_user=_usuario("empleado"),
    )

    assert listar_vacaciones_espiado[0]["id_empleado"] == DUENIO


def test_listar_vacaciones_sin_filtro_no_devuelve_el_padron_al_empleado(listar_vacaciones_espiado):
    """Omitir el filtro tampoco: es la vía obvia para intentar ver todo."""
    vacaciones_router.listar_vacaciones(
        id_empleado=None, gestion=None, skip=0, limit=100,
        db=DB, current_user=_usuario("empleado"),
    )

    assert listar_vacaciones_espiado[0]["id_empleado"] == DUENIO


@pytest.mark.parametrize("rol", ["admin", "rrhh", "supervisor"])
def test_listar_vacaciones_respeta_el_filtro_pedido_por_un_rol_con_lectura_total(
    listar_vacaciones_espiado, rol
):
    vacaciones_router.listar_vacaciones(
        id_empleado=AJENO, gestion=None, skip=0, limit=100,
        db=DB, current_user=_usuario(rol),
    )

    assert listar_vacaciones_espiado[0]["id_empleado"] == AJENO


def test_listar_vacaciones_sin_filtro_devuelve_todo_al_gestor(listar_vacaciones_espiado):
    vacaciones_router.listar_vacaciones(
        id_empleado=None, gestion=None, skip=0, limit=100,
        db=DB, current_user=_usuario("admin"),
    )

    assert listar_vacaciones_espiado[0]["id_empleado"] is None


def test_listar_detalles_fuerza_el_filtro_del_empleado(listar_detalles_espiado):
    vacaciones_router.listar_todos_detalles(
        id_empleado=AJENO, estado=None, tipo_vacacion=None,
        fecha_desde=None, fecha_hasta=None, skip=0, limit=100,
        db=DB, current_user=_usuario("empleado"),
    )

    assert listar_detalles_espiado[0]["id_empleado"] == DUENIO


def test_listar_detalles_respeta_el_filtro_del_gestor(listar_detalles_espiado):
    vacaciones_router.listar_todos_detalles(
        id_empleado=AJENO, estado=None, tipo_vacacion=None,
        fecha_desde=None, fecha_hasta=None, skip=0, limit=100,
        db=DB, current_user=_usuario("rrhh"),
    )

    assert listar_detalles_espiado[0]["id_empleado"] == AJENO
