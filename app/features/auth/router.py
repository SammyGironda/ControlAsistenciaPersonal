"""
Router de autenticación: login y consulta del usuario autenticado.

POST /login emite el access token JWT. La validación de credenciales NO se
reimplementa acá: se delega en usuario_services.verify_credentials(), que ya
resuelve el username case-insensitive, verifica que el usuario esté activo,
compara el hash bcrypt y actualiza ultimo_acceso.

POST /usuarios/verify-credentials se mantiene: el frontend actual todavía lo
usa para el login (Frontend/src/api/auth.js).
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

    Es el único endpoint protegido por ahora; el resto del backend sigue abierto
    hasta que se apliquen los guards. Sirve además para que el frontend valide
    un token guardado en localStorage al arrancar.
    """
    return schemas.UsuarioTokenInfo(
        id=current_user.id,
        username=current_user.username,
        id_rol=current_user.id_rol,
        nombre_rol=current_user.rol.nombre,
        id_empleado=current_user.id_empleado,
    )
