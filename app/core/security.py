"""
Módulo de seguridad centralizado.

Tres responsabilidades:
- Contraseñas: bcrypt directo (sin passlib) para evitar incompatibilidades de versiones.
- Contraseñas temporales: generación aleatoria con `secrets` para el alta de cuentas.
- Tokens JWT: emisión y decodificación con PyJWT.

Este módulo es capa de dominio: NO conoce FastAPI ni HTTP. Las excepciones de PyJWT
se propagan tal cual y se traducen a 401 en app/core/deps.py.
"""

import secrets
from datetime import timedelta
from typing import Any, Dict, Optional

import bcrypt
import jwt

from app.core.config import get_settings
from app.core.timezone import get_utc_now


def hash_password(plain_password: str) -> str:
    """Hashea una contraseña con bcrypt. Incluye sal automática."""
    password_bytes = plain_password.encode("utf-8")
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifica si la contraseña coincide con el hash almacenado."""
    password_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)


# ============================================================
# Contraseñas temporales
# ============================================================

# Sin 0/O/o, 1/l/I ni símbolos que se confundan al dictarlos: esta contraseña se
# transmite en voz alta (teléfono, WhatsApp), no se copia y pega. Un carácter
# ambiguo se traduce en un login fallido que parece un bug del sistema.
_MAYUSCULAS = "ABCDEFGHJKLMNPQRSTUVWXYZ"
_MINUSCULAS = "abcdefghijkmnpqrstuvwxyz"
_DIGITOS = "23456789"
_SIMBOLOS = "!@#$%*+-="
_ALFABETO_TEMPORAL = _MAYUSCULAS + _MINUSCULAS + _DIGITOS + _SIMBOLOS

LONGITUD_PASSWORD_TEMPORAL = 12


def generar_password_temporal(longitud: int = LONGITUD_PASSWORD_TEMPORAL) -> str:
    """
    Genera una contraseña temporal aleatoria, apta para dictarse en voz alta.

    Garantiza al menos una mayúscula, una minúscula, un dígito y un símbolo:
    los construye primero y baraja después. Sortear al azar y reintentar hasta
    que cumpla sesgaría la distribución y, en el peor caso, no terminaría nunca.

    Usa `secrets` y no `random`: `random` es un Mersenne Twister cuyo estado se
    reconstruye a partir de unas pocas salidas, y esto es material de
    autenticación.

    La contraseña resultante cumple por construcción la política de
    `validar_password_fuerte` (mín. 8, mayúscula, minúscula y dígito), así que el
    usuario nunca recibe una temporal que el sistema rechazaría.
    """
    if longitud < 8:
        raise ValueError("La contraseña temporal debe tener al menos 8 caracteres")

    obligatorios = [
        secrets.choice(_MAYUSCULAS),
        secrets.choice(_MINUSCULAS),
        secrets.choice(_DIGITOS),
        secrets.choice(_SIMBOLOS),
    ]
    resto = [secrets.choice(_ALFABETO_TEMPORAL) for _ in range(longitud - len(obligatorios))]

    caracteres = obligatorios + resto
    secrets.SystemRandom().shuffle(caracteres)

    return "".join(caracteres)


# ============================================================
# JWT — emisión y validación de access tokens
# ============================================================

def create_access_token(
    id_usuario: int,
    id_rol: int,
    nombre_rol: str,
    id_empleado: Optional[int] = None,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """
    Emite un access token JWT firmado para un usuario ya autenticado.

    Este módulo NO valida credenciales: eso es responsabilidad de
    `features/auth/usuario/services.verify_credentials()`. Aquí sólo se firma.

    Payload:
    - sub: id del usuario como str (RFC 7519 exige que `sub` sea string)
    - id_usuario / id_rol / nombre_rol / id_empleado: datos de conveniencia
      para el frontend. OJO: son una foto del momento de la emisión. Para
      autorizar SIEMPRE releer el usuario de la base (ver deps.get_current_user).
    - iat / exp: emisión y expiración, en UTC.

    `expires_delta` sólo se usa en tests; en producción sale de
    settings.ACCESS_TOKEN_EXPIRE_MINUTES.
    """
    settings = get_settings()

    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    ahora = get_utc_now()

    payload: Dict[str, Any] = {
        "sub": str(id_usuario),
        "id_usuario": id_usuario,
        "id_rol": id_rol,
        "nombre_rol": nombre_rol,
        "id_empleado": id_empleado,
        "iat": ahora,
        "exp": ahora + expires_delta,
    }

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decodifica y valida un access token. Devuelve el payload.

    `algorithms` se pasa como lista explícita a propósito: es lo que impide que
    un token con cabecera `alg: none` (o firmado con otro algoritmo) sea aceptado.

    No captura las excepciones de PyJWT — las propaga para que la capa HTTP
    distinga expirado de inválido:
    - jwt.ExpiredSignatureError: token vencido (subclase de InvalidTokenError)
    - jwt.InvalidTokenError: firma inválida, malformado, etc.
    """
    settings = get_settings()

    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )