"""
Dependencias compartidas de FastAPI (autenticación/autorización).

SEMANA 9: JWT sigue comentado en app/core/security.py y ningún router del
backend tiene guard de auth activo todavía ("sin autenticación hasta Semana
9" en los docstrings de cada router). require_admin() es un placeholder
no-op para que los endpoints que YA deben quedar restringidos a admin
(ej. horario_personalizado) lo declaren desde ahora vía Depends() y no haya
que tocar cada router de nuevo cuando se active JWT real.

TODO Semana 9: reemplazar el cuerpo de require_admin() por la verificación
real (decodificar token vía get_current_user, validar current_user.rol
== 'admin', levantar 401/403 si corresponde).
"""


def require_admin() -> None:
    """Placeholder de autorización admin-only. No hace nada todavía."""
    return None
