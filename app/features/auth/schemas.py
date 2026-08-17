"""
Schemas Pydantic del flujo de autenticación (login + token).

Los schemas de la entidad Usuario viven en features/auth/usuario/schemas.py.
Acá sólo están los DTOs propios del login, que no mapean a ninguna tabla.
"""

from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator

from app.features.auth.usuario.schemas import validar_password_fuerte


# ============================================================
# REQUEST
# ============================================================

class LoginRequest(BaseModel):
    """
    Credenciales de login.

    Van en el body como JSON, a diferencia de /usuarios/verify-credentials, que
    las recibe como query params (y por lo tanto las deja escritas en los logs
    de acceso de cualquier proxy).
    """
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=100)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "admin",
                "password": "Password123!"
            }
        }
    )


class CambioPasswordObligatorioRequest(BaseModel):
    """
    Cambio de la contraseña temporal por parte de su propio dueño.

    `password_actual` no lleva política de fortaleza: es la contraseña que ya
    existe (normalmente una temporal generada por el backend), no una que el
    usuario esté eligiendo. La política se exige sobre `password_nueva`.
    """
    password_actual: str = Field(..., min_length=1, max_length=100)
    password_nueva: str = Field(..., min_length=8, max_length=100)

    @field_validator("password_nueva")
    @classmethod
    def _password_fuerte(cls, valor: str) -> str:
        return validar_password_fuerte(valor)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "password_actual": "Temp4X-9kRmz",
                "password_nueva": "MiClaveNueva1"
            }
        }
    )


# ============================================================
# RESPONSE
# ============================================================

class UsuarioTokenInfo(BaseModel):
    """
    Datos básicos del usuario autenticado.

    Se devuelve junto al token en el login (para que el frontend no tenga que
    decodificar el JWT) y como respuesta de GET /auth/me.
    Nunca incluye password_hash.
    """
    id: int
    username: str
    id_rol: int
    nombre_rol: str
    id_empleado: Optional[int] = None
    # Lo consume el frontend para mandar al cambio obligatorio antes de dejar
    # entrar al resto del sistema. NO es un claim del JWT a propósito: los claims
    # son una foto del momento de la emisión y este valor cambia durante la
    # sesión. Viaja en la respuesta de /login y de /me, que releen la base.
    requiere_cambio_password: bool = False

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """Respuesta de POST /auth/login."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(..., description="Vigencia del token en segundos")
    usuario: UsuarioTokenInfo

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer",
                "expires_in": 1800,
                "usuario": {
                    "id": 1,
                    "username": "admin",
                    "id_rol": 1,
                    "nombre_rol": "admin",
                    "id_empleado": 1,
                    "requiere_cambio_password": False
                }
            }
        }
    )
