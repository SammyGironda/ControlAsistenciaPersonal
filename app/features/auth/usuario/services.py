"""
Services para Usuario - Lógica de negocio.
Incluye manejo de contraseñas con bcrypt.

El alta de cuentas es un flujo de PROVISIÓN, no un CRUD: el admin indica a qué
empleado y con qué rol, y el backend deriva el username y genera una contraseña
temporal que el usuario debe reemplazar en su primer login
(requiere_cambio_password). La contraseña se devuelve en texto plano una sola vez
y nunca se persiste legible.
"""

import unicodedata
from typing import TYPE_CHECKING, List, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.features.auth.usuario.models import Usuario
from app.features.auth.usuario import schemas
from app.features.auth.rol.services import get_rol
from app.features.employees.empleado.models import Empleado, EstadoEmpleadoEnum

from app.core.security import generar_password_temporal, verify_password

if TYPE_CHECKING:
    # Sólo para la anotación de cambiar_password_obligatorio. El DTO vive en el
    # módulo del router de /auth, que es donde se expone el endpoint; importarlo
    # en runtime desde acá no haría falta y acoplaría dos capas sin necesidad.
    from app.features.auth.schemas import CambioPasswordObligatorioRequest


# Roles a los que se les puede crear una cuenta hoy. `empleado` y `consulta`
# quedan fuera porque todavía no existen pantallas de autoservicio: una cuenta
# con esos roles entraría al sistema y recibiría 403 en casi todo.
#
# Se declara acá y NO en app/core/deps.py, donde viven ROLES_GESTORES y compañía,
# porque deps.py importa este módulo: la constante allá cerraría un import
# circular.
ROLES_ASIGNABLES = frozenset({"admin", "rrhh", "supervisor"})

# rrhh.usuario.username es String(50) UNIQUE.
LONGITUD_MAXIMA_USERNAME = 50

# Reintentos del INSERT ante colisión de username por carrera entre dos altas.
MAX_INTENTOS_USERNAME = 3


# ============================================================
# CRUD BÁSICO
# ============================================================

def get_usuario(db: Session, usuario_id: int, with_rol: bool = False) -> Usuario:
    if with_rol:
        stmt = select(Usuario).options(joinedload(Usuario.rol)).where(Usuario.id == usuario_id)
        usuario = db.execute(stmt).scalar_one_or_none()
    else:
        usuario = db.get(Usuario, usuario_id)
    
    if not usuario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Usuario con ID {usuario_id} no encontrado"
        )
    return usuario


def get_usuario_by_username(db: Session, username: str) -> Optional[Usuario]:
    stmt = select(Usuario).where(func.lower(Usuario.username) == username.lower())
    return db.execute(stmt).scalar_one_or_none()


def get_usuarios(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    solo_activos: bool = False,
    id_rol: Optional[int] = None
) -> List[Usuario]:
    stmt = select(Usuario).options(joinedload(Usuario.rol)).offset(skip).limit(limit)
    
    if solo_activos:
        stmt = stmt.where(Usuario.activo == True)
    
    if id_rol:
        stmt = stmt.where(Usuario.id_rol == id_rol)
    
    return list(db.execute(stmt).scalars().all())


# ============================================================
# GENERACIÓN DE USERNAME
# ============================================================

def _slug(texto: str) -> str:
    """
    Primera palabra del texto, sin acentos, en minúsculas y sólo [a-z0-9].

    'Pérez' -> 'perez', 'Ñuñez' -> 'nunez', "O'Brien" -> 'obrien'.

    NFKD descompone cada letra acentuada en letra base + marca de combinación;
    el filtro de `unicodedata.combining` descarta las marcas y deja la base. El
    `isascii()` final saca cualquier cosa que la descomposición no haya reducido
    a ASCII, para no meter bytes raros en el username.
    """
    palabras = (texto or "").strip().split()
    if not palabras:
        return ""

    normalizado = unicodedata.normalize("NFKD", palabras[0])
    sin_acentos = "".join(c for c in normalizado if not unicodedata.combining(c))

    return "".join(c for c in sin_acentos.lower() if c.isalnum() and c.isascii())


def generar_username(db: Session, empleado: Empleado) -> str:
    """
    Deriva 'primernombre.apellido' del empleado, único case-insensitive.

    Ante colisión agrega un sufijo numérico: juan.perez, juan.perez2,
    juan.perez3... El sufijo se cuenta CONTRA el límite de 50 caracteres
    recortando la base, no desbordándola: 'username' es String(50) y un valor
    más largo moriría con un DataError de psycopg2.

    La unicidad se consulta con get_usuario_by_username, que ya compara con
    func.lower: 'JUAN.PEREZ' en la base bloquea 'juan.perez'.
    """
    nombre = _slug(empleado.nombres)
    apellido = _slug(empleado.apellidos)

    base = ".".join(parte for parte in (nombre, apellido) if parte) or "usuario"

    # Un empleado con nombre y apellido de una letra daría 'j.p', que ya cumple.
    # El caso a cubrir es el de un solo componente muy corto ('li' -> 'li').
    if len(base) < 3:
        base = f"{base}.usuario"

    candidato = base[:LONGITUD_MAXIMA_USERNAME]
    sufijo = 1

    while get_usuario_by_username(db, candidato):
        sufijo += 1
        marca = str(sufijo)
        candidato = base[:LONGITUD_MAXIMA_USERNAME - len(marca)] + marca

    return candidato


# ============================================================
# ALTA DE CUENTAS (provisión con contraseña temporal)
# ============================================================

def create_usuario(db: Session, usuario_data: schemas.UsuarioCreate) -> Tuple[Usuario, str]:
    """
    Crea la cuenta de un empleado y devuelve (usuario, contraseña temporal).

    La contraseña se devuelve para que el admin se la comunique al usuario; sólo
    se persiste su hash bcrypt. No se loguea en ningún lado.
    """
    rol = get_rol(db, usuario_data.id_rol)  # 404 si el rol no existe

    if rol.nombre.lower() not in ROLES_ASIGNABLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"No se pueden crear cuentas con el rol '{rol.nombre}'. "
                f"Roles permitidos: {', '.join(sorted(ROLES_ASIGNABLES))}."
            )
        )

    empleado = db.get(Empleado, usuario_data.id_empleado)
    if not empleado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el empleado con ID {usuario_data.id_empleado}"
        )

    if empleado.estado == EstadoEmpleadoEnum.baja:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No se puede asociar un usuario a un empleado dado de baja. Primero habilítelo."
        )

    stmt = select(Usuario).where(Usuario.id_empleado == empleado.id)
    if db.execute(stmt).scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El empleado con ID {empleado.id} ya tiene un usuario asociado"
        )

    password_temporal = generar_password_temporal()

    # generar_username consulta y recién después insertamos: entre ambas cosas
    # otro admin puede haber tomado el mismo username. La UNIQUE de la base es la
    # que decide, y reintentar la respeta en vez de devolver un 500 por
    # IntegrityError. El rollback es obligatorio: sin él la sesión de SQLAlchemy
    # queda rota para todo lo que siga.
    for _ in range(MAX_INTENTOS_USERNAME):
        usuario = Usuario(
            username=generar_username(db, empleado),
            id_rol=usuario_data.id_rol,
            id_empleado=empleado.id,
            activo=usuario_data.activo,
            requiere_cambio_password=True,
        )
        usuario.set_password(password_temporal)

        db.add(usuario)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            continue

        db.refresh(usuario)
        return usuario, password_temporal

    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="No se pudo generar un username único para el empleado. Reintente."
    )


def update_usuario(
    db: Session,
    usuario_id: int,
    usuario_data: schemas.UsuarioUpdate
) -> Usuario:
    usuario = get_usuario(db, usuario_id)
    
    if usuario_data.username and usuario_data.username != usuario.username:
        existing = get_usuario_by_username(db, usuario_data.username)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Ya existe un usuario con el username '{usuario_data.username}'"
            )
    
    if usuario_data.id_rol:
        get_rol(db, usuario_data.id_rol)
    
    update_data = usuario_data.model_dump(exclude_unset=True, exclude={"password"})
    for field, value in update_data.items():
        setattr(usuario, field, value)
    
    if usuario_data.password:
        # La fijó el admin, no su dueño: se trata igual que una temporal y el
        # usuario deberá reemplazarla en su próximo login. Si no, este endpoint
        # sería un hueco silencioso por el que una contraseña ajena queda como
        # definitiva.
        usuario.set_password(usuario_data.password)
        usuario.requiere_cambio_password = True

    db.commit()
    db.refresh(usuario)
    return usuario


def delete_usuario(db: Session, usuario_id: int) -> dict:
    usuario = get_usuario(db, usuario_id)
    db.delete(usuario)
    db.commit()
    return {"message": f"Usuario '{usuario.username}' eliminado exitosamente"}


def toggle_activo(db: Session, usuario_id: int) -> Usuario:
    usuario = get_usuario(db, usuario_id)
    usuario.activo = not usuario.activo
    db.commit()
    db.refresh(usuario)
    return usuario


def change_password(
    db: Session,
    usuario_id: int,
    password_data: schemas.UsuarioChangePassword
) -> dict:
    usuario = get_usuario(db, usuario_id)
    
    if not usuario.check_password(password_data.password_actual):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual no es correcta"
        )
    
    usuario.set_password(password_data.password_nueva)
    # Cambió una contraseña conociendo la anterior: si venía de una temporal,
    # queda saldada igual que por el cambio obligatorio.
    usuario.requiere_cambio_password = False
    db.commit()

    return {"message": "Contraseña actualizada exitosamente"}


def resetear_password(db: Session, usuario_id: int) -> Tuple[Usuario, str]:
    """
    Asigna una contraseña temporal nueva a una cuenta existente.

    Es la única recuperación del sistema: no hay SMTP configurado, y
    change_password exige la contraseña actual incluso para el admin (a
    propósito), así que un usuario que olvidó la suya no tendría salida.

    Por eso NO pide la contraseña actual — y por eso el endpoint que la expone
    está restringido a admin.
    """
    usuario = get_usuario(db, usuario_id)

    password_temporal = generar_password_temporal()
    usuario.set_password(password_temporal)
    usuario.requiere_cambio_password = True

    db.commit()
    db.refresh(usuario)

    return usuario, password_temporal


def cambiar_password_obligatorio(
    db: Session,
    usuario_id: int,
    password_data: "CambioPasswordObligatorioRequest"
) -> dict:
    """
    El propio usuario retira su contraseña temporal y baja el flag.

    NO exige que requiere_cambio_password esté en True: verifica la contraseña
    actual de la propia cuenta, así que no hay diferencia de seguridad, y
    rechazar cuando el flag ya bajó volvería frágil el flujo ante un doble submit
    del formulario.

    El hash nuevo y el flag se escriben en UNA sola transacción: si el flag
    bajara en un commit aparte, un fallo entre ambos dejaría la cuenta afirmando
    que ya cambió la contraseña cuando sigue con la temporal.
    """
    usuario = get_usuario(db, usuario_id)

    if not usuario.check_password(password_data.password_actual):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La contraseña actual no es correcta"
        )

    if usuario.check_password(password_data.password_nueva):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La nueva contraseña debe ser distinta de la actual"
        )

    usuario.set_password(password_data.password_nueva)
    usuario.requiere_cambio_password = False
    db.commit()

    return {
        "message": "Contraseña actualizada exitosamente",
        "requiere_cambio_password": False
    }


def verify_credentials(db: Session, username: str, password: str) -> Optional[Usuario]:
    usuario = get_usuario_by_username(db, username)
    
    if not usuario or not usuario.activo:
        return None
    
    if not usuario.check_password(password):
        return None
    
    usuario.ultimo_acceso = datetime.now()
    db.commit()
    
    return usuario


def get_usuario_with_rol_info(db: Session, usuario_id: int) -> dict:
    usuario = get_usuario(db, usuario_id, with_rol=True)
    
    return {
        "id": usuario.id,
        "username": usuario.username,
        "id_rol": usuario.id_rol,
        "rol_nombre": usuario.rol.nombre,
        "id_empleado": usuario.id_empleado,
        "activo": usuario.activo,
        "ultimo_acceso": usuario.ultimo_acceso,
        "created_at": usuario.created_at,
        "updated_at": usuario.updated_at
    }
