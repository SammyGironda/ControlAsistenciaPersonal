"""
Dependencias compartidas de FastAPI (autenticación/autorización).

JWT ya está activo: app/core/security.py emite y valida tokens, y
get_current_user() de este módulo los verifica contra el header
`Authorization: Bearer <token>`.

require_admin() y require_roles() aplican el guard de rol: releen el usuario
autenticado (get_current_user, que ya relee el rol fresco de la base) y
comparan current_user.rol.nombre contra el/los roles permitidos, en
minúsculas. Se usan como dependencies=[Depends(require_admin)] o
dependencies=[Depends(require_roles("admin", "rrhh"))] en el decorador del
endpoint — mismo patrón ya presente en horario_personalizado/router.py y
compensacion_horas_extra/router.py.

get_actor_empleado_id() resuelve el id_empleado del usuario autenticado para poblar
columnas de auditoría con FK a empleado (id_aprobado_por, id_resuelto_por,
id_cerrado_por, id_registrado_por) — ver 2026-08-10, "Reemplazar campos *_por
client-supplied por el actor autenticado". Para columnas con FK a usuario
(id_generado_por, id_subido_por) alcanza con current_user.id_usuario directo.

TODO (sesión siguiente): aplicar estos guards al resto de routers que todavía
quedan completamente abiertos (fuera de los 13 endpoints ya cubiertos por el
cambio de 2026-08-10).

Nota sobre imports: la dirección es siempre deps -> features/auth/usuario/services.
Si algún día usuario/services.py importara este módulo habría un ciclo.
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
import jwt

from app.core.database import get_db
from app.core.security import decode_access_token
from app.features.auth.usuario.models import Usuario
from app.features.auth.usuario import services as usuario_services


# auto_error=False a propósito: con el default (True), HTTPBearer responde 403
# cuando falta el header Authorization, y lo correcto acá es 401. Con False
# devuelve None y el 401 se levanta explícitamente más abajo.
bearer_scheme = HTTPBearer(auto_error=False, description="Access token JWT emitido por POST /api/v1/auth/login")


def _no_autenticado(detail: str) -> HTTPException:
    """401 con el header WWW-Authenticate que exige el esquema Bearer."""
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> Usuario:
    """
    Resuelve el usuario autenticado a partir del header Authorization: Bearer.

    Levanta 401 si no hay token, si es inválido/expirado, si el usuario ya no
    existe o si fue desactivado.

    El usuario se relee de la base en vez de confiar en los claims: el rol o el
    estado activo pueden haber cambiado después de emitir el token.
    """
    if credentials is None or not credentials.credentials:
        raise _no_autenticado("No autenticado")

    try:
        payload = decode_access_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise _no_autenticado("Token expirado")
    except jwt.InvalidTokenError:
        raise _no_autenticado("Token inválido")

    id_usuario = payload.get("id_usuario")
    if id_usuario is None:
        id_usuario = payload.get("sub")

    try:
        id_usuario = int(id_usuario)
    except (TypeError, ValueError):
        raise _no_autenticado("Token inválido")

    # get_usuario levanta 404 si no existe; acá un usuario borrado con token
    # todavía vigente es un problema de autenticación, no un recurso faltante.
    try:
        usuario = usuario_services.get_usuario(db, id_usuario, with_rol=True)
    except HTTPException:
        raise _no_autenticado("Usuario no encontrado")

    if not usuario.activo:
        raise _no_autenticado("Usuario inactivo")

    return usuario


def require_roles(*roles_permitidos: str):
    """
    Factory de dependencia: exige que el usuario autenticado tenga uno de los
    roles indicados (comparación case-insensitive contra current_user.rol.nombre).
    Levanta 403 si el rol no corresponde. get_current_user ya se encarga de
    exigir el 401 si no hay usuario autenticado.
    """
    roles_normalizados = {r.lower() for r in roles_permitidos}

    def _verificar(current_user: Usuario = Depends(get_current_user)) -> Usuario:
        if current_user.rol.nombre.lower() not in roles_normalizados:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Acceso restringido a: {', '.join(sorted(roles_normalizados))}",
            )
        return current_user

    return _verificar


def require_admin(current_user: Usuario = Depends(get_current_user)) -> Usuario:
    """Exige que el usuario autenticado tenga rol admin."""
    if current_user.rol.nombre.lower() != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acceso restringido a: admin")
    return current_user


def get_actor_empleado_id(current_user: Usuario) -> int:
    """
    Resuelve el id_empleado del usuario autenticado, para poblar columnas de
    auditoría que tienen FK a empleado (no a usuario): id_aprobado_por,
    id_resuelto_por, id_cerrado_por, id_registrado_por.

    usuario.id_empleado es nullable (p.ej. el admin del seed no está vinculado
    a un empleado) — 400 en vez de guardar NULL silenciosamente, para que
    siempre haya una persona real detrás de una aprobación/resolución/cierre.
    """
    if current_user.id_empleado is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tu usuario no está vinculado a un empleado; no puede registrar esta acción.",
        )
    return current_user.id_empleado
