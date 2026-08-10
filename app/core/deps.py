"""
Dependencias compartidas de FastAPI (autenticación/autorización).

JWT ya está activo: app/core/security.py emite y valida tokens, y
get_current_user() de este módulo los verifica contra el header
`Authorization: Bearer <token>`.

Lo que todavía NO está aplicado es el guard endpoint por endpoint: los routers
del backend siguen abiertos. require_admin() sigue siendo un placeholder no-op
para que los endpoints que YA deben quedar restringidos a admin
(ej. horario_personalizado, compensacion_horas_extra) lo declaren desde ahora
vía Depends() y no haya que tocar cada router de nuevo.

TODO (sesión siguiente): reemplazar el cuerpo de require_admin() por la
verificación real (recibir current_user vía Depends(get_current_user), validar
current_user.rol.nombre == 'admin', levantar 403 si corresponde) y agregar
Depends(get_current_user) a los routers existentes.

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


def require_admin() -> None:
    """Placeholder de autorización admin-only. No hace nada todavía."""
    return None
