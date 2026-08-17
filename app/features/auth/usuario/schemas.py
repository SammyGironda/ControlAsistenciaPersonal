"""
Schemas Pydantic para Usuario.
Define los DTOs para requests y responses de la API.

IMPORTANTE:
- password_hash NO se expone en ninguna respuesta.
- La ÚNICA respuesta que lleva una contraseña en texto plano es la del alta y la
  del reseteo (UsuarioCreadoResponse / PasswordReseteadaResponse): es la
  contraseña temporal, y ese es el único momento en que existe legible.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator


# ============================================================
# POLÍTICA DE CONTRASEÑAS
# ============================================================

def validar_password_fuerte(valor: str) -> str:
    """
    Exige mínimo 8 caracteres, con mayúscula, minúscula y dígito.

    Se aplica a TODA contraseña elegida por el usuario — el cambio obligatorio y
    también /usuarios/{id}/change-password. Aplicarla sólo al primero dejaría el
    otro endpoint como vía para esquivar la política.

    No se aplica a las contraseñas temporales generadas por el backend porque
    `generar_password_temporal` ya la cumple por construcción.
    """
    faltantes = []

    if len(valor) < 8:
        faltantes.append("al menos 8 caracteres")
    if not any(caracter.isupper() for caracter in valor):
        faltantes.append("una letra mayúscula")
    if not any(caracter.islower() for caracter in valor):
        faltantes.append("una letra minúscula")
    if not any(caracter.isdigit() for caracter in valor):
        faltantes.append("un dígito")

    if faltantes:
        raise ValueError("La contraseña debe tener " + ", ".join(faltantes))

    return valor


# ============================================================
# SCHEMAS DE REQUEST (Input)
# ============================================================

class UsuarioCreate(BaseModel):
    """
    Alta de una cuenta por parte del admin.

    Ya NO recibe username ni password: los genera el backend
    (services.generar_username + security.generar_password_temporal), y la cuenta
    nace con requiere_cambio_password=True. Es la única vía de alta a propósito,
    para que no exista un camino que cree cuentas con contraseña definitiva
    elegida por otra persona.

    `id_empleado` es obligatorio (antes era opcional) porque el username se deriva
    del nombre del empleado. Las cuentas sin empleado vinculado siguen siendo
    válidas en la base — la columna es nullable — pero se crean por seed, no por API.
    """
    id_empleado: int = Field(..., gt=0, description="Empleado al que pertenece la cuenta")
    id_rol: int = Field(..., gt=0, description="Rol asignado: admin, rrhh o supervisor")
    activo: bool = Field(default=True, description="Estado del usuario")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id_empleado": 5,
                "id_rol": 2,
                "activo": True
            }
        }
    )


class UsuarioUpdate(BaseModel):
    """
    Schema para actualizar un usuario existente.
    Todos los campos son opcionales.
    """
    username: Optional[str] = Field(None, min_length=3, max_length=50)
    password: Optional[str] = Field(
        None,
        min_length=8,
        max_length=100,
        description="Nueva contraseña. Al enviarla, la cuenta queda marcada como "
                    "requiere_cambio_password: la eligió el admin, no su dueño."
    )
    id_rol: Optional[int] = Field(None, gt=0)
    id_empleado: Optional[int] = Field(None, gt=0)
    activo: Optional[bool] = None

    @field_validator("password")
    @classmethod
    def _password_fuerte(cls, valor: Optional[str]) -> Optional[str]:
        return valor if valor is None else validar_password_fuerte(valor)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "username": "nuevo.username",
                "activo": False
            }
        }
    )


class UsuarioChangePassword(BaseModel):
    """
    Cambio de contraseña conociendo la anterior.

    `password_actual` no lleva política: es la que ya existe (puede ser una
    temporal generada por el backend). La política se exige sobre la nueva.
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
                "password_actual": "OldPassword123!",
                "password_nueva": "NewPassword456!"
            }
        }
    )


# ============================================================
# SCHEMAS DE RESPONSE (Output)
# ============================================================

class UsuarioRead(BaseModel):
    """
    Schema de respuesta para un usuario.
    NUNCA expone el password_hash por seguridad.
    """
    id: int
    username: str
    id_rol: int
    id_empleado: Optional[int]
    activo: bool
    requiere_cambio_password: bool
    ultimo_acceso: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UsuarioReadWithRol(BaseModel):
    """Schema de respuesta de usuario con información del rol."""
    id: int
    username: str
    id_rol: int
    rol_nombre: str  # Nombre del rol incluido
    id_empleado: Optional[int]
    activo: bool
    requiere_cambio_password: bool
    ultimo_acceso: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UsuarioReadSimple(BaseModel):
    """Schema simplificado de usuario (para uso en otras entidades)."""
    id: int
    username: str
    activo: bool

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# RESPUESTAS CON CONTRASEÑA TEMPORAL
#
# Las únicas dos del sistema que exponen una contraseña en texto plano. Es la
# temporal recién generada: sólo se persiste su hash bcrypt, así que este es el
# único momento en que existe legible. Si el admin la pierde, no se recupera —
# se genera otra con POST /usuarios/{id}/resetear-password.
# ============================================================

class UsuarioCreadoResponse(UsuarioRead):
    """Respuesta de POST /usuarios/: la cuenta creada más su contraseña temporal."""
    password_temporal: str = Field(
        ...,
        description="Contraseña temporal EN TEXTO PLANO. No se vuelve a mostrar: "
                    "comunicarla al usuario antes de cerrar la pantalla."
    )


class PasswordReseteadaResponse(BaseModel):
    """Respuesta de POST /usuarios/{id}/resetear-password."""
    id: int
    username: str
    password_temporal: str = Field(
        ...,
        description="Contraseña temporal EN TEXTO PLANO. No se vuelve a mostrar."
    )
    requiere_cambio_password: bool = True

    model_config = ConfigDict(from_attributes=True)
