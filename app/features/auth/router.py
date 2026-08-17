"""
Router de autenticación: login y consulta del usuario autenticado.

POST /login emite el access token JWT. La validación de credenciales NO se
reimplementa acá: se delega en usuario_services.verify_credentials(), que ya
resuelve el username case-insensitive, verifica que el usuario esté activo,
compara el hash bcrypt y actualiza ultimo_acceso.

POST /usuarios/verify-credentials fue eliminado el 2026-08-13: estaba abierto,
recibía la contraseña como query param y ya nadie lo llamaba (Frontend/src/api/auth.js
pega contra este /login desde el 2026-08-10). El servicio que compartían,
usuario_services.verify_credentials(), es el que sigue usando el login de acá.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.features.auth import schemas
from app.features.auth.usuario.models import Usuario
from app.features.auth.usuario import services as usuario_services

router = APIRouter(
    prefix="/auth",
    tags=["Auth"],
)


@router.post(
    "/login",
    response_model=schemas.TokenResponse,
    summary="Iniciar sesión y obtener un access token JWT",
)
def login(
    credenciales: schemas.LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Autentica un usuario y devuelve un access token JWT.

    - **username**: nombre de usuario (no distingue mayúsculas)
    - **password**: contraseña en texto plano (viaja en el body, no en la URL)

    Devuelve 401 si las credenciales son incorrectas o el usuario está inactivo.
    Como efecto secundario, actualiza `ultimo_acceso` del usuario.
    """
    usuario = usuario_services.verify_credentials(
        db, credenciales.username, credenciales.password
    )

    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Recarga con joinedload del rol: verify_credentials no lo trae, y acceder a
    # usuario.rol.nombre dispararía un lazy-load implícito.
    usuario = usuario_services.get_usuario(db, usuario.id, with_rol=True)

    settings = get_settings()
    access_token = create_access_token(
        id_usuario=usuario.id,
        id_rol=usuario.id_rol,
        nombre_rol=usuario.rol.nombre,
        id_empleado=usuario.id_empleado,
    )

    return schemas.TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        usuario=schemas.UsuarioTokenInfo(
            id=usuario.id,
            username=usuario.username,
            id_rol=usuario.id_rol,
            nombre_rol=usuario.rol.nombre,
            id_empleado=usuario.id_empleado,
            requiere_cambio_password=usuario.requiere_cambio_password,
        ),
    )


@router.get(
    "/me",
    response_model=schemas.UsuarioTokenInfo,
    summary="Datos del usuario autenticado",
)
def read_current_user(current_user: Usuario = Depends(get_current_user)):
    """
    Devuelve el usuario correspondiente al token enviado en
    `Authorization: Bearer <token>`.

    Sirve para que el frontend valide un token guardado en localStorage al
    arrancar, y para que cualquier rol consulte su propia cuenta sin necesitar
    los endpoints de /usuarios, reservados a admin y rrhh.
    """
    return schemas.UsuarioTokenInfo(
        id=current_user.id,
        username=current_user.username,
        id_rol=current_user.id_rol,
        nombre_rol=current_user.rol.nombre,
        id_empleado=current_user.id_empleado,
        requiere_cambio_password=current_user.requiere_cambio_password,
    )


@router.post(
    "/cambiar-password-obligatorio",
    summary="Cambiar la contraseña temporal propia",
)
def cambiar_password_obligatorio(
    datos: schemas.CambioPasswordObligatorioRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    El usuario autenticado reemplaza su contraseña temporal y baja el flag
    `requiere_cambio_password`.

    Vive en /auth y no en /usuarios porque **no lleva `usuario_id` en el path**:
    opera siempre sobre la cuenta del token. Eso elimina de raíz el guard de
    pertenencia que sí necesita `/usuarios/{id}/change-password`, y hace que
    cualquier rol pueda usarlo sobre lo suyo y sólo sobre lo suyo.

    Requiere:
    - **password_actual**: la contraseña vigente (la temporal que entregó el admin)
    - **password_nueva**: mínimo 8 caracteres, con mayúscula, minúscula y dígito

    Devuelve 400 si la contraseña actual no es correcta o si la nueva es igual a
    la actual, y 422 si la nueva no cumple la política.
    """
    # current_user.id — la PK del modelo. `id_usuario` es sólo un claim del JWT y
    # no existe como atributo del objeto ORM (ver core/deps.py).
    return usuario_services.cambiar_password_obligatorio(db, current_user.id, datos)
