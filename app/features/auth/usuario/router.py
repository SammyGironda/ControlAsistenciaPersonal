"""
Router para Usuario - Endpoints REST.

RBAC aplicado el 2026-08-13 (antes sólo el DELETE tenía guard):
- Crear/editar/eliminar cuentas: sólo admin.
- Lectura del padrón de usuarios: admin y rrhh (gestión de personal).
- Cambio de contraseña: el propio usuario sobre su cuenta, o admin.
- Reseteo de contraseña: sólo admin (no pide la contraseña actual).

Alta con contraseña temporal (2026-08-17): POST / ya no recibe username ni
password. El backend deriva el username del nombre del empleado, genera una
contraseña aleatoria y marca la cuenta con requiere_cambio_password. Esa
contraseña viaja en texto plano SÓLO en la respuesta del alta y del reseteo, para
que el admin se la comunique al usuario; el usuario la reemplaza con
POST /api/v1/auth/cambiar-password-obligatorio.

POST /verify-credentials fue eliminado en ese mismo cambio: estaba abierto,
recibía la contraseña como query param (o sea que quedaba en los logs de acceso)
y ningún cliente lo usaba desde el 2026-08-10. POST /api/v1/auth/login lo
reemplaza por completo. services.verify_credentials() sigue existiendo: es lo que
usa ese login.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import (
    exigir_gestion_de_usuario,
    get_current_user,
    require_admin,
    require_roles,
)
from app.features.auth.usuario import schemas, services
from app.features.auth.usuario.models import Usuario

router = APIRouter(
    prefix="/usuarios",
    tags=["Usuarios"],
    responses={404: {"description": "No encontrado"}}
)


@router.post(
    "/",
    response_model=schemas.UsuarioCreadoResponse,
    status_code=201,
    summary="Crear cuenta con contraseña temporal",
    dependencies=[Depends(require_admin)],
)
def create_usuario(
    usuario: schemas.UsuarioCreate,
    db: Session = Depends(get_db)
):
    """
    Crea la cuenta de un empleado. Sólo admin.

    - **id_empleado**: empleado al que pertenece la cuenta (obligatorio: de su
      nombre se deriva el username, con el formato `primernombre.apellido` y un
      sufijo numérico si ya está tomado)
    - **id_rol**: admin, rrhh o supervisor. `empleado` y `consulta` se rechazan
      con 400 mientras no existan pantallas de autoservicio
    - **activo**: estado inicial de la cuenta

    La contraseña la genera el backend y la cuenta nace con
    `requiere_cambio_password`. **La respuesta trae esa contraseña en texto plano
    y es el único lugar donde aparece**: comunicarla al usuario antes de cerrar la
    pantalla. Si se pierde, se genera otra con
    `POST /usuarios/{id}/resetear-password`.
    """
    creado, password_temporal = services.create_usuario(db, usuario)

    return schemas.UsuarioCreadoResponse(
        **schemas.UsuarioRead.model_validate(creado).model_dump(),
        password_temporal=password_temporal,
    )


@router.get(
    "/",
    response_model=List[schemas.UsuarioRead],
    summary="Listar todos los usuarios",
    dependencies=[Depends(require_roles("admin", "rrhh"))],
)
def list_usuarios(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    solo_activos: bool = Query(False),
    id_rol: Optional[int] = Query(None, description="Filtrar por rol"),
    db: Session = Depends(get_db)
):
    """
    Lista todos los usuarios con paginación y filtros. Sólo admin y rrhh.

    Parámetros:
    - **skip**: Offset para paginación
    - **limit**: Límite de resultados
    - **solo_activos**: Solo usuarios activos
    - **id_rol**: Filtrar por rol específico
    """
    return services.get_usuarios(
        db,
        skip=skip,
        limit=limit,
        solo_activos=solo_activos,
        id_rol=id_rol
    )


@router.get(
    "/{usuario_id}",
    response_model=schemas.UsuarioRead,
    summary="Obtener usuario por ID",
    dependencies=[Depends(require_roles("admin", "rrhh"))],
)
def get_usuario(
    usuario_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene un usuario específico por su ID. Sólo admin y rrhh.

    Para consultar la propia cuenta no hace falta este endpoint: GET /api/v1/auth/me
    devuelve el usuario del token.

    Retorna error 404 si no existe.
    """
    return services.get_usuario(db, usuario_id)


@router.get(
    "/{usuario_id}/with-rol",
    response_model=schemas.UsuarioReadWithRol,
    summary="Obtener usuario con info del rol",
    dependencies=[Depends(require_roles("admin", "rrhh"))],
)
def get_usuario_with_rol(
    usuario_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene un usuario con información expandida del rol. Sólo admin y rrhh.

    Incluye el nombre del rol además del id_rol.
    """
    return services.get_usuario_with_rol_info(db, usuario_id)


@router.put(
    "/{usuario_id}",
    response_model=schemas.UsuarioRead,
    summary="Actualizar usuario",
    dependencies=[Depends(require_admin)],
)
def update_usuario(
    usuario_id: int,
    usuario: schemas.UsuarioUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualiza un usuario existente. Sólo admin.

    Es admin y no rrhh porque el body admite `id_rol` y `password`: con este
    endpoint se promueve una cuenta a cualquier rol y se le reemplaza la
    contraseña sin conocer la anterior.

    Solo se actualizan los campos enviados.
    Si se envía password, se hashea automáticamente.
    """
    return services.update_usuario(db, usuario_id, usuario)


@router.delete(
    "/{usuario_id}",
    summary="Eliminar usuario (hard delete)",
    dependencies=[Depends(require_admin)],
)
def delete_usuario(
    usuario_id: int,
    db: Session = Depends(get_db)
):
    """
    Elimina un usuario permanentemente de la base de datos.
    """
    return services.delete_usuario(db, usuario_id)


@router.patch(
    "/{usuario_id}/toggle-activo",
    response_model=schemas.UsuarioRead,
    summary="Activar/desactivar usuario",
    dependencies=[Depends(require_admin)],
)
def toggle_activo_usuario(
    usuario_id: int,
    db: Session = Depends(get_db)
):
    """
    Alterna el estado activo/inactivo de un usuario (soft delete). Sólo admin.

    Alternativa más segura al hard delete.
    """
    return services.toggle_activo(db, usuario_id)


@router.post(
    "/{usuario_id}/resetear-password",
    response_model=schemas.PasswordReseteadaResponse,
    summary="Resetear contraseña (genera una temporal nueva)",
    dependencies=[Depends(require_admin)],
)
def resetear_password(
    usuario_id: int,
    db: Session = Depends(get_db)
):
    """
    Asigna una contraseña temporal nueva y vuelve a exigir el cambio en el
    próximo login. Sólo admin.

    Es la vía de recuperación del sistema — no hay envío por correo — y por eso,
    a diferencia de `change-password`, **no pide la contraseña actual**. Ese
    poder es justamente lo que la restringe a admin.

    **La respuesta trae la contraseña en texto plano y no se vuelve a mostrar.**
    """
    usuario, password_temporal = services.resetear_password(db, usuario_id)

    return schemas.PasswordReseteadaResponse(
        id=usuario.id,
        username=usuario.username,
        password_temporal=password_temporal,
        requiere_cambio_password=usuario.requiere_cambio_password,
    )


@router.post(
    "/{usuario_id}/change-password",
    summary="Cambiar contraseña"
)
def change_password(
    usuario_id: int,
    password_data: schemas.UsuarioChangePassword,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Cambia la contraseña de un usuario: la propia, o cualquiera si es admin.

    Requiere:
    - **password_actual**: Contraseña actual (para verificación)
    - **password_nueva**: Nueva contraseña

    Retorna error 400 si la contraseña actual no es correcta, y 403 si se intenta
    cambiar la contraseña de otra cuenta sin ser admin.
    """
    # El guard no puede ir en dependencies=[...]: depende de a quién apunta el
    # path comparado con quién es el actor. Va antes de llamar al servicio.
    exigir_gestion_de_usuario(current_user, usuario_id)

    return services.change_password(db, usuario_id, password_data)
