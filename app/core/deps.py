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

exigir_lectura_de_empleado() / exigir_gestion_de_empleado() / alcance_lectura()
son el guard de PERTENENCIA, no de rol: contestan "¿este recurso es de este
usuario?" para los endpoints donde un empleado accede a lo suyo (ver 2026-08-12,
RBAC de /vacaciones). Son funciones normales, no dependencias de FastAPI: el
id_empleado dueño casi nunca está en la request — hay que leerlo de la base
primero (p.ej. vacacion.id_empleado a partir del id_vacacion del path), así que
la comprobación va en el cuerpo del endpoint, después de resolver el dueño y
ANTES de mutar nada.

exigir_gestion_de_usuario() es el mismo guard de pertenencia pero sobre la CUENTA
en vez del legajo: compara contra usuario.id, no contra id_empleado (ver
2026-08-13, RBAC de /usuarios y /roles). Lo usa POST /usuarios/{id}/change-password.

TODO (sesión siguiente): aplicar estos guards al resto de routers que todavía
quedan completamente abiertos (fuera de los 13 endpoints ya cubiertos por el
cambio de 2026-08-10, los 17 de /vacaciones cubiertos el 2026-08-12 y los 15 de
/usuarios + /roles cubiertos el 2026-08-13).

Nota sobre imports: la dirección es siempre deps -> features/auth/usuario/services.
Si algún día usuario/services.py importara este módulo habría un ciclo.
"""

from typing import Optional

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


# ============================================================
# Pertenencia: "¿este recurso es de este usuario?"
# ============================================================
#
# Los dos alcances son distintos a propósito y por eso son dos helpers:
# un supervisor necesita LEER los datos de cualquier empleado para poder evaluar
# una solicitud (sin ver el saldo no puede aprobar con criterio), pero no debe
# poder CREAR ni editar solicitudes en nombre de otro.

ROLES_GESTORES = frozenset({"admin", "rrhh"})
ROLES_LECTURA_TOTAL = frozenset({"admin", "rrhh", "supervisor"})
ROLES_APROBADORES = frozenset({"admin", "rrhh", "supervisor"})


def _nombre_rol(current_user: Usuario) -> str:
    return current_user.rol.nombre.lower()


def es_admin(current_user: Usuario) -> bool:
    """
    True si el usuario tiene rol admin.

    Gemelo de es_gestor para usar dentro del cuerpo de un endpoint: require_admin
    es una dependencia de FastAPI y expresa la misma regla, pero como guard
    declarativo del decorador.
    """
    return _nombre_rol(current_user) == "admin"


def es_gestor(current_user: Usuario) -> bool:
    """True si el usuario puede gestionar registros de cualquier empleado (admin/rrhh)."""
    return _nombre_rol(current_user) in ROLES_GESTORES


def puede_leer_todo(current_user: Usuario) -> bool:
    """True si el usuario puede consultar registros de cualquier empleado (admin/rrhh/supervisor)."""
    return _nombre_rol(current_user) in ROLES_LECTURA_TOTAL


def es_aprobador(current_user: Usuario) -> bool:
    """
    True si el usuario puede aprobar/rechazar solicitudes ajenas (admin/rrhh/supervisor).

    Hoy coincide en valor con ROLES_LECTURA_TOTAL, pero se declara aparte a
    propósito: son decisiones distintas (leer vs. resolver) y usar el helper de
    lectura para autorizar una escritura haría silencioso el día que diverjan.
    """
    return _nombre_rol(current_user) in ROLES_APROBADORES


def exigir_lectura_de_empleado(current_user: Usuario, id_empleado: int) -> None:
    """
    Permite la consulta si el usuario lee de todos (admin/rrhh/supervisor) o si el
    recurso es del propio empleado vinculado a su cuenta. Si no, 403.

    El 400 de get_actor_empleado_id (cuenta sin empleado vinculado) se propaga tal
    cual: es el mismo diagnóstico y ya tiene un mensaje accionable.
    """
    if puede_leer_todo(current_user):
        return

    if get_actor_empleado_id(current_user) != id_empleado:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo puedes consultar tus propios registros de vacaciones.",
        )


def exigir_gestion_de_empleado(current_user: Usuario, id_empleado: int) -> None:
    """
    Permite crear/modificar si el usuario es gestor (admin/rrhh) o si el recurso es
    del propio empleado vinculado a su cuenta. Si no, 403.

    Nota: un supervisor NO pasa este guard sobre registros ajenos. Aprueba
    solicitudes (require_roles en cambiar-estado), no las crea por otros.
    """
    if es_gestor(current_user):
        return

    if get_actor_empleado_id(current_user) != id_empleado:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo puedes gestionar tus propias solicitudes de vacación.",
        )


def exigir_gestion_de_usuario(current_user: Usuario, id_usuario: int) -> None:
    """
    Permite operar sobre una CUENTA si el actor es admin o si es su propia cuenta.
    Si no, 403.

    Compara contra usuario.id (la PK de rrhh.usuario), NO contra id_empleado: acá
    el recurso es la cuenta de acceso, no el legajo. Por eso no pasa por
    get_actor_empleado_id y una cuenta admin sin empleado vinculado no recibe el
    400 de ese helper — puede cambiar su propia contraseña igual.
    """
    if es_admin(current_user):
        return

    if current_user.id != id_usuario:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo puedes gestionar tu propia cuenta de usuario.",
        )


def alcance_lectura(current_user: Usuario) -> Optional[int]:
    """
    Filtro de empleado que un listado debe aplicar para este usuario.

    None = sin restricción (admin/rrhh/supervisor). Cualquier otro rol recibe su
    propio id_empleado, que el endpoint debe usar PISANDO el filtro que haya
    mandado el cliente — si no, bastaría con omitirlo para ver todo.
    """
    if puede_leer_todo(current_user):
        return None

    return get_actor_empleado_id(current_user)
