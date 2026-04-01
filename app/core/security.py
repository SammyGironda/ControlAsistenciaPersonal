"""
Módulo de seguridad centralizado.
Usa bcrypt directamente (sin passlib) para evitar incompatibilidades de versiones.
"""

import bcrypt


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


# ─────────────────────────────────────────────
# SEMANA 9: descomenta esto cuando actives JWT
# ─────────────────────────────────────────────
# from datetime import datetime, timedelta
# from jose import JWTError, jwt
# from app.core.config import settings
#
# ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = 30
#
# def create_access_token(data: dict) -> str:
#     to_encode = data.copy()
#     expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
#     to_encode.update({"exp": expire})
#     return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)