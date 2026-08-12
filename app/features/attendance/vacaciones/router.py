"""
Router para Vacacion y DetalleVacacion - Endpoints REST para gestión de vacaciones.

RBAC (2026-08-12): todos los endpoints exigen un JWT válido. Sobre eso se aplican
dos capas, según lo que haga cada uno:

- **Rol** (`require_roles` / `require_admin` en el decorador) para lo que es
  gestión pura del saldo vacacional — crearlo, editarlo, incrementarlo, borrarlo —
  y para la cola de aprobación.
- **Pertenencia** (`exigir_lectura_de_empleado` / `exigir_gestion_de_empleado` /
  `alcance_lectura`, en el cuerpo) para lo que un empleado hace sobre lo suyo.
  Va en el cuerpo y no en el decorador porque el id_empleado dueño casi nunca
  viene en la request: hay que resolverlo antes contra la base
  (`services.obtener_empleado_de_vacacion` / `_de_detalle`).

Reparto por rol: admin/rrhh gestionan a cualquier empleado · supervisor consulta
a cualquiera y aprueba/rechaza · empleado consulta, crea, edita y cancela lo
suyo. Los listados no devuelven 403 a un empleado: se le fuerza el filtro a su
propio id_empleado (`alcance_lectura`), pisando el que haya mandado.
"""

from datetime import date
from typing import List, Optional
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Query, Body, Response, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import (
    alcance_lectura,
    es_aprobador,
    exigir_gestion_de_empleado,
    exigir_lectura_de_empleado,
    get_current_user,
    require_admin,
    require_roles,
)
from app.features.auth.usuario.models import Usuario
from app.features.attendance.vacaciones import services
from app.features.attendance.vacaciones.schemas import (
    VacacionCreate,
    VacacionUpdate,
    VacacionResponse,
    DetalleVacacionCreate,
    DetalleVacacionUpdate,
    DetalleVacacionResponse,
    CambiarEstadoRequest,
    CalculoHorasHabilesResponse,
    AsegurarGestionRequest,
    TipoVacacionEnum,
    EstadoDetalleVacacionEnum
)

router = APIRouter(prefix="/vacaciones", tags=["Vacaciones"])


# ===== ENDPOINTS DE APOYO AL FORMULARIO DE SOLICITUD =====
#
# Van primero porque sus paths son literales: aunque `/{id:int}` no llegaría a
# capturarlos gracias al converter `:int`, dejarlos arriba evita que un cambio
# futuro del converter los rompa en silencio.

@router.get(
    "/calcular-horas-habiles",
    response_model=CalculoHorasHabilesResponse,
    summary="Calcular las horas hábiles que consume un rango de fechas"
)
def calcular_horas_habiles(
    id_empleado: int = Query(..., gt=0, description="Empleado sobre cuyo horario se calcula"),
    fecha_inicio: date = Query(..., description="Primer día del rango, inclusive"),
    fecha_fin: date = Query(..., description="Último día del rango, inclusive"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Devuelve cuántas horas hábiles consumiría una solicitud de vacaciones sobre
    ese rango, con el desglose de los días que NO cuentan y por qué.

    Sirve para que el frontend muestre el costo real antes de crear la solicitud:
    `detalle_vacacion.horas_habiles` es un dato que envía el cliente.

    Un día aporta horas solo si tiene horario vigente, cae en un día laborable de
    ese horario y no es feriado. Igual que en el cálculo de asistencia diaria,
    **descanso tiene precedencia sobre feriado**.

    Sin guard de rol a propósito: un empleado debe poder previsualizar lo suyo.
    Sí hay guard de pertenencia — sólo admin/rrhh/supervisor pueden calcular el de
    otro empleado.
    """
    exigir_lectura_de_empleado(current_user, id_empleado)

    return services.calcular_horas_habiles_rango(db, id_empleado, fecha_inicio, fecha_fin)


@router.post(
    "/asegurar-gestion",
    response_model=VacacionResponse,
    summary="Obtener el saldo vacacional de una gestión, creándolo si falta"
)
def asegurar_gestion(
    data: AsegurarGestionRequest,
    response: Response,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Devuelve el registro de vacación del empleado para esa gestión. Si no existe
    lo crea con la base que corresponde por antigüedad
    (`rrhh.fn_horas_vacacion_lgt`, LGT Art. 44).

    **Idempotente**: si el saldo ya existe lo devuelve intacto, sin sumar nada.
    Responde 201 cuando lo creó y 200 cuando ya estaba.

    Existe porque crear un `detalle_vacacion` exige un `id_vacacion` y casi ningún
    empleado tiene todavía su registro de vacación.

    Un empleado sólo puede asegurar su propia gestión; admin/rrhh, la de cualquiera.
    """
    exigir_gestion_de_empleado(current_user, data.id_empleado)

    vacacion, fue_creada = services.asegurar_vacacion_gestion(
        db, data.id_empleado, data.gestion
    )

    if fue_creada:
        response.status_code = status.HTTP_201_CREATED

    return vacacion


# ===== ENDPOINTS PARA VACACION =====

@router.post(
    "/",
    response_model=VacacionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear registro de vacación",
    dependencies=[Depends(require_roles("admin", "rrhh"))],
)
def crear_vacacion(
    data: VacacionCreate,
    db: Session = Depends(get_db)
):
    """
    Crea un nuevo registro de vacación para un empleado y gestión.

    **Solo admin/rrhh:** fija el saldo anual con las horas que se le acreditan al
    empleado, así que no puede quedar en manos del propio empleado. El alta normal
    la hace `POST /asegurar-gestion`, que deriva las horas de la LGT.

    Validaciones:
    - No puede haber duplicados (id_empleado, gestion)
    - horas_correspondientes debe calcularse con fn_horas_vacacion_lgt
    """
    return services.crear_vacacion(db, data)


@router.get(
    "/{id:int}",
    response_model=VacacionResponse,
    summary="Obtener vacación por ID"
)
def obtener_vacacion(
    id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Obtiene un registro de vacación específico por su ID.

    Un empleado sólo puede ver el suyo; admin/rrhh/supervisor, el de cualquiera.
    Un ID inexistente devuelve 404 (no 403), venga de quien venga.
    """
    vacacion = services.obtener_vacacion(db, id)
    exigir_lectura_de_empleado(current_user, vacacion.id_empleado)

    return vacacion


@router.get(
    "/empleado/{id_empleado}/gestion/{gestion}",
    response_model=Optional[VacacionResponse],
    summary="Obtener vacación de empleado por gestión"
)
def obtener_vacacion_empleado_gestion(
    id_empleado: int,
    gestion: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Obtiene el registro de vacación de un empleado para una gestión específica.

    Retorna None si no existe el registro para esa combinación.

    Un empleado sólo puede consultar el suyo. El guard corre ANTES de la consulta:
    pedir el de otro empleado da 403 aunque no exista el registro, para no filtrar
    por diferencia de respuesta quién tiene saldo cargado y quién no.
    """
    exigir_lectura_de_empleado(current_user, id_empleado)

    return services.obtener_vacacion_por_empleado_gestion(db, id_empleado, gestion)


@router.get(
    "/",
    response_model=List[VacacionResponse],
    summary="Listar vacaciones con filtros"
)
def listar_vacaciones(
    id_empleado: Optional[int] = Query(None, description="Filtrar por empleado"),
    gestion: Optional[int] = Query(None, description="Filtrar por año"),
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: int = Query(100, ge=1, le=500, description="Límite de registros"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Lista registros de vacaciones con filtros opcionales.

    **Filtros disponibles:**
    - `id_empleado`: filtrar por empleado específico
    - `gestion`: filtrar por año

    A un rol sin lectura total (`empleado`, `consulta`) se le fuerza `id_empleado`
    al suyo, pisando el que haya enviado: si no, omitir el filtro devolvería el
    padrón completo.
    """
    alcance = alcance_lectura(current_user)
    if alcance is not None:
        id_empleado = alcance

    return services.listar_vacaciones(
        db,
        id_empleado=id_empleado,
        gestion=gestion,
        skip=skip,
        limit=limit
    )


@router.put(
    "/{id:int}",
    response_model=VacacionResponse,
    summary="Actualizar registro de vacación",
    dependencies=[Depends(require_roles("admin", "rrhh"))],
)
def actualizar_vacacion(
    id: int,
    data: VacacionUpdate,
    db: Session = Depends(get_db)
):
    """
    Actualiza los datos de un registro de vacación existente.

    Permite modificar las horas de goce/sin goce de haber y observaciones.

    **Solo admin/rrhh:** son las bolsas contra las que se valida al pasar una
    solicitud a 'tomado'.
    """
    return services.actualizar_vacacion(db, id, data)


@router.delete(
    "/{id:int}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar vacación (CASCADE)",
    dependencies=[Depends(require_admin)],
)
def eliminar_vacacion(
    id: int,
    db: Session = Depends(get_db)
):
    """
    Elimina un registro de vacación y todos sus detalles asociados (CASCADE).

    **ADVERTENCIA:** Esta acción elimina también todos los DetalleVacacion asociados.
    Solo usar en caso de error o para pruebas.
    """
    services.eliminar_vacacion(db, id)
    return None


@router.post(
    "/{id:int}/incrementar-horas",
    response_model=VacacionResponse,
    summary="Incrementar horas de vacación",
    dependencies=[Depends(require_roles("admin", "rrhh"))],
)
def incrementar_horas(
    id: int,
    horas: Decimal = Body(..., embed=True, gt=0, description="Horas a incrementar"),
    tipo: str = Body("goce_haber", embed=True, description="Tipo: 'goce_haber' o 'sin_goce_haber'"),
    db: Session = Depends(get_db)
):
    """
    Incrementa las horas de vacación de un registro.

    **Casos de uso:**
    - Transferencia de beneficio de cumpleaños (+4h goce de haber)
    - Compensación por trabajo en feriado (horas variables)

    **Parámetros:**
    - `horas`: cantidad de horas a sumar
    - `tipo`: 'goce_haber' (default) o 'sin_goce_haber'

    **Solo admin/rrhh:** acredita saldo vacacional, nunca lo hace el propio empleado.
    """
    return services.incrementar_horas(db, id, horas, tipo)


# ===== ENDPOINTS PARA DETALLE_VACACION =====

@router.post(
    "/{id_vacacion}/detalles",
    response_model=DetalleVacacionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear solicitud de vacación"
)
def crear_detalle_vacacion(
    id_vacacion: int,
    data: DetalleVacacionCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Crea una nueva solicitud de vacación para un registro de vacación.

    **Validaciones:**
    - fecha_fin debe ser >= fecha_inicio
    - horas_habiles debe ser > 0
    - El empleado debe tener suficientes horas disponibles
    - El registro de vacación debe existir

    **Estado inicial:** solicitado (requiere aprobación)

    **Pertenencia:** admin/rrhh pueden dar de alta la solicitud de cualquier
    empleado; cualquier otro rol (incluido supervisor) sólo sobre su propia
    vacación, o 403. El dueño se resuelve desde `vacacion.id_empleado` — el body
    no trae `id_empleado`, así que no hay nada que el cliente pueda falsear.
    """
    exigir_gestion_de_empleado(
        current_user, services.obtener_empleado_de_vacacion(db, id_vacacion)
    )

    return services.crear_detalle_vacacion(db, id_vacacion, data)


@router.get(
    "/detalles/{id:int}",
    response_model=DetalleVacacionResponse,
    summary="Obtener detalle de vacación por ID"
)
def obtener_detalle_vacacion(
    id: int,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Obtiene un detalle de vacación específico por su ID.

    Un empleado sólo puede ver los suyos; admin/rrhh/supervisor, los de cualquiera.
    """
    detalle = services.obtener_detalle_vacacion(db, id)
    exigir_lectura_de_empleado(current_user, services.obtener_empleado_de_detalle(db, id))

    return detalle


@router.get(
    "/{id_vacacion}/detalles",
    response_model=List[DetalleVacacionResponse],
    summary="Listar detalles de una vacación"
)
def listar_detalles_vacacion(
    id_vacacion: int,
    estado: Optional[EstadoDetalleVacacionEnum] = Query(None, description="Filtrar por estado"),
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: int = Query(100, ge=1, le=500, description="Límite de registros"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Lista todos los detalles de vacación asociados a un registro de vacación.

    **Filtros disponibles:**
    - `estado`: solicitado, aprobado, tomado, rechazado, cancelado

    Un empleado sólo puede listar los detalles de su propia vacación.
    """
    exigir_lectura_de_empleado(
        current_user, services.obtener_empleado_de_vacacion(db, id_vacacion)
    )

    return services.listar_detalles_por_vacacion(
        db,
        id_vacacion=id_vacacion,
        estado=estado,
        skip=skip,
        limit=limit
    )


@router.get(
    "/detalles/",
    response_model=List[DetalleVacacionResponse],
    summary="Listar todos los detalles con filtros"
)
def listar_todos_detalles(
    id_empleado: Optional[int] = Query(None, description="Filtrar por empleado"),
    estado: Optional[EstadoDetalleVacacionEnum] = Query(None, description="Filtrar por estado"),
    tipo_vacacion: Optional[TipoVacacionEnum] = Query(None, description="Filtrar por tipo"),
    fecha_desde: Optional[date] = Query(None, description="Filtrar desde fecha"),
    fecha_hasta: Optional[date] = Query(None, description="Filtrar hasta fecha"),
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: int = Query(100, ge=1, le=500, description="Límite de registros"),
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Lista todos los detalles de vacación con filtros opcionales.

    **Filtros disponibles:**
    - `id_empleado`: filtrar por empleado específico
    - `estado`: solicitado, aprobado, tomado, rechazado, cancelado
    - `tipo_vacacion`: goce_de_haber, sin_goce_de_haber, licencia_accidente
    - `fecha_desde` y `fecha_hasta`: rango de fechas de inicio

    A un rol sin lectura total se le fuerza `id_empleado` al suyo, igual que en
    `GET /vacaciones/`.
    """
    alcance = alcance_lectura(current_user)
    if alcance is not None:
        id_empleado = alcance

    return services.listar_todos_detalles(
        db,
        id_empleado=id_empleado,
        estado=estado,
        tipo_vacacion=tipo_vacacion,
        fecha_desde=fecha_desde,
        fecha_hasta=fecha_hasta,
        skip=skip,
        limit=limit
    )


@router.get(
    "/detalles/pendientes",
    response_model=List[DetalleVacacionResponse],
    summary="Listar solicitudes pendientes de aprobación",
    dependencies=[Depends(require_roles("admin", "rrhh", "supervisor"))],
)
def listar_detalles_pendientes(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """
    Lista todas las solicitudes de vacación pendientes de aprobación.

    **Útil para supervisores y RRHH** para revisar solicitudes.

    Es la cola de aprobación de toda la empresa, sin filtro por empleado, así que
    queda restringida por rol: un empleado ve sus propias solicitudes pendientes
    por `GET /vacaciones/detalles/?estado=solicitado`.
    """
    return services.listar_detalles_pendientes(db, skip, limit)


@router.put(
    "/detalles/{id:int}",
    response_model=DetalleVacacionResponse,
    summary="Actualizar detalle de vacación"
)
def actualizar_detalle_vacacion(
    id: int,
    data: DetalleVacacionUpdate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Actualiza un detalle de vacación existente.

    **Restricción:** Solo se puede actualizar si está en estado 'solicitado'.
    Solicitudes aprobadas o tomadas no se pueden modificar.

    **Pertenencia:** admin/rrhh sobre cualquier solicitud; el resto sólo sobre la
    propia. El límite temporal (sólo mientras siga en 'solicitado') ya lo aplica
    el servicio, para todos por igual.
    """
    exigir_gestion_de_empleado(current_user, services.obtener_empleado_de_detalle(db, id))

    return services.actualizar_detalle_vacacion(db, id, data)


@router.post(
    "/detalles/{id:int}/cambiar-estado",
    response_model=DetalleVacacionResponse,
    summary="Cambiar estado de solicitud de vacación",
)
def cambiar_estado_detalle(
    id: int,
    data: CambiarEstadoRequest,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Cambia el estado de una solicitud de vacación.

    **Transiciones válidas:**
    - solicitado → aprobado (requiere que el usuario autenticado tenga empleado vinculado)
    - solicitado → rechazado (ídem)
    - aprobado → tomado (cuando el empleado efectivamente toma la vacación)
    - solicitado/aprobado → cancelado (cancelación voluntaria)

    **Validaciones:**
    - Para aprobar/rechazar, el usuario autenticado debe tener empleado vinculado
      (id_aprobado_por se deriva de la sesión, no se acepta del cliente)
    - Al aprobar se valida que haya horas disponibles
    - Al tomar se descuentan las horas del saldo
    - Al cancelar se recalcula el saldo si estaba aprobado

    **Licencia por accidente:** un detalle con `tipo_vacacion='licencia_accidente'`
    NO descuenta saldo vacacional al pasar a 'tomado'. Para que lo descuente hay
    que enviar `cubrir_con_saldo_vacacional=true`, confirmando que RRHH y el
    empleado acordaron cubrir la licencia con el saldo de vacaciones.

    **Quién puede llamarlo:** admin/rrhh/supervisor sobre cualquier solicitud. El
    dueño de la solicitud puede además cancelar la suya — y sólo cancelar: si pide
    cualquier otro estado recibe 403. El guard va acá y no en el decorador porque
    depende del `nuevo_estado`, que sólo se conoce leyendo el body.
    """
    if not es_aprobador(current_user):
        exigir_gestion_de_empleado(current_user, services.obtener_empleado_de_detalle(db, id))

        if data.nuevo_estado != EstadoDetalleVacacionEnum.cancelado:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Solo puedes cancelar tu propia solicitud; aprobarla, rechazarla o "
                    "marcarla como tomada corresponde a RRHH o a tu supervisor."
                ),
            )

    return services.cambiar_estado_detalle(db, id, data, id_aprobado_por=current_user.id_empleado)


@router.delete(
    "/detalles/{id:int}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar detalle de vacación",
    dependencies=[Depends(require_admin)],
)
def eliminar_detalle_vacacion(
    id: int,
    db: Session = Depends(get_db)
):
    """
    Elimina un detalle de vacación.

    **Restricción:** Solo se puede eliminar si está en estado 'solicitado' o 'rechazado'.
    No se pueden eliminar solicitudes aprobadas o tomadas.
    """
    services.eliminar_detalle_vacacion(db, id)
    return None
