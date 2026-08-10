"""
Tests de emisión y validación de access tokens JWT.

Unitarios, sin base de datos: se usan dobles (SimpleNamespace) y monkeypatch,
igual que el resto de la suite.
"""

from datetime import timedelta
from types import SimpleNamespace

import jwt
import pytest
from fastapi import HTTPException

from app.core import deps
from app.core.config import get_settings
from app.core.security import create_access_token, decode_access_token


# ============================================================
# create_access_token / decode_access_token
# ============================================================

def test_token_round_trip_conserva_los_claims():
    token = create_access_token(
        id_usuario=7,
        id_rol=2,
        nombre_rol="rrhh",
        id_empleado=42,
    )

    payload = decode_access_token(token)

    assert payload["id_usuario"] == 7
    assert payload["id_rol"] == 2
    assert payload["nombre_rol"] == "rrhh"
    assert payload["id_empleado"] == 42
    # sub debe ser string aunque el id sea int (RFC 7519).
    assert payload["sub"] == "7"
    assert payload["exp"] > payload["iat"]


def test_token_admite_id_empleado_nulo():
    """usuario.id_empleado es nullable en producción (admin sin ficha de empleado)."""
    token = create_access_token(
        id_usuario=1,
        id_rol=1,
        nombre_rol="admin",
        id_empleado=None,
    )

    payload = decode_access_token(token)

    assert payload["id_empleado"] is None
    assert payload["sub"] == "1"


def test_expiracion_usa_ACCESS_TOKEN_EXPIRE_MINUTES_de_settings():
    settings = get_settings()

    token = create_access_token(id_usuario=1, id_rol=1, nombre_rol="admin")
    payload = decode_access_token(token)

    vigencia_segundos = payload["exp"] - payload["iat"]
    assert vigencia_segundos == settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60


def test_token_expirado_es_rechazado():
    token = create_access_token(
        id_usuario=1,
        id_rol=1,
        nombre_rol="admin",
        expires_delta=timedelta(minutes=-1),
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_token_firmado_con_otra_clave_es_rechazado():
    settings = get_settings()

    ajeno = jwt.encode(
        {"id_usuario": 1, "sub": "1"},
        "otra-clave-secreta-distinta",
        algorithm=settings.ALGORITHM,
    )

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(ajeno)


def test_token_manipulado_es_rechazado():
    token = create_access_token(id_usuario=1, id_rol=1, nombre_rol="admin")

    # Alterar la firma (último segmento) invalida el token.
    header, payload_b64, firma = token.split(".")
    alterado = f"{header}.{payload_b64}.{firma[:-4]}XXXX"

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(alterado)


# ============================================================
# get_current_user
# ============================================================

def _credenciales(token: str) -> SimpleNamespace:
    """Doble de HTTPAuthorizationCredentials."""
    return SimpleNamespace(scheme="Bearer", credentials=token)


def test_get_current_user_sin_credenciales_devuelve_401():
    with pytest.raises(HTTPException) as exc:
        deps.get_current_user(credentials=None, db=None)

    assert exc.value.status_code == 401
    assert exc.value.detail == "No autenticado"
    assert exc.value.headers["WWW-Authenticate"] == "Bearer"


def test_get_current_user_con_token_expirado_devuelve_401():
    token = create_access_token(
        id_usuario=1,
        id_rol=1,
        nombre_rol="admin",
        expires_delta=timedelta(minutes=-1),
    )

    with pytest.raises(HTTPException) as exc:
        deps.get_current_user(credentials=_credenciales(token), db=None)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Token expirado"


def test_get_current_user_con_token_invalido_devuelve_401():
    with pytest.raises(HTTPException) as exc:
        deps.get_current_user(credentials=_credenciales("esto.no.es-un-jwt"), db=None)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Token inválido"


def test_get_current_user_devuelve_el_usuario_de_la_base(monkeypatch):
    usuario = SimpleNamespace(id=7, username="rrhh.user", id_rol=2, activo=True)
    monkeypatch.setattr(
        deps.usuario_services,
        "get_usuario",
        lambda db, usuario_id, with_rol=False: usuario,
    )

    token = create_access_token(id_usuario=7, id_rol=2, nombre_rol="rrhh")
    resultado = deps.get_current_user(credentials=_credenciales(token), db=None)

    assert resultado is usuario


def test_get_current_user_relee_el_rol_y_no_confia_en_el_claim(monkeypatch):
    """El rol pudo cambiar después de emitir el token: manda la base, no el claim."""
    usuario = SimpleNamespace(id=7, username="rrhh.user", id_rol=4, activo=True)
    monkeypatch.setattr(
        deps.usuario_services,
        "get_usuario",
        lambda db, usuario_id, with_rol=False: usuario,
    )

    # Token emitido cuando el usuario todavía era rol 2.
    token = create_access_token(id_usuario=7, id_rol=2, nombre_rol="rrhh")
    resultado = deps.get_current_user(credentials=_credenciales(token), db=None)

    assert resultado.id_rol == 4


def test_get_current_user_con_usuario_inactivo_devuelve_401(monkeypatch):
    usuario = SimpleNamespace(id=7, username="baja", id_rol=2, activo=False)
    monkeypatch.setattr(
        deps.usuario_services,
        "get_usuario",
        lambda db, usuario_id, with_rol=False: usuario,
    )

    token = create_access_token(id_usuario=7, id_rol=2, nombre_rol="rrhh")

    with pytest.raises(HTTPException) as exc:
        deps.get_current_user(credentials=_credenciales(token), db=None)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Usuario inactivo"


def test_get_current_user_con_usuario_borrado_devuelve_401_no_404(monkeypatch):
    def no_existe(db, usuario_id, with_rol=False):
        raise HTTPException(status_code=404, detail=f"Usuario con ID {usuario_id} no encontrado")

    monkeypatch.setattr(deps.usuario_services, "get_usuario", no_existe)

    token = create_access_token(id_usuario=99, id_rol=2, nombre_rol="rrhh")

    with pytest.raises(HTTPException) as exc:
        deps.get_current_user(credentials=_credenciales(token), db=None)

    assert exc.value.status_code == 401
    assert exc.value.detail == "Usuario no encontrado"
