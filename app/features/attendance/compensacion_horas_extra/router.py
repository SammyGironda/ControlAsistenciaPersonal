"""
Router para CompensacionHorasExtra - Registro admin-only de compensación de
horas por trabajo en fin de semana o feriado no planeado.

El REGISTRO (POST) queda detrás de require_admin(); la CONSULTA (GET) admite
además el rol rrhh, que audita lo cargado sin poder cargar nada. Son dos
decisiones distintas y por eso son dos guards distintos: acreditar horas al
saldo vacacional es irreversible desde la API (no hay PUT ni DELETE y el
trigger sólo actúa en INSERT), mientras que leer el historial es la operación
de auditoría para la que existe este listado.

id_registrado_por se deriva del usuario autenticado (get_actor_empleado_id),
ya no se acepta del cliente. El insert es independiente de asistencia_diaria:
funciona tanto si esa fecha ya tiene registro de asistencia_diaria como si aún
no existe (se genera recién al procesar el Excel mensual).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_actor_empleado_id, get_current_user, require_admin, require_roles
from app.features.auth.usuario.models import Usuario
from app.features.attendance.compensacion_horas_extra import services
from app.features.attendance.compensacion_horas_extra.schemas import (
    CompensacionHorasExtraCreate,
    CompensacionHorasExtraResponse,
)

router = APIRouter(prefix="/compensaciones-horas-extra", tags=["Compensación Horas Extra"])


@router.post(
    "/",
    response_model=CompensacionHorasExtraResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar compensación de horas extra",
    dependencies=[Depends(require_admin)],
)
def crear_compensacion(
    data: CompensacionHorasExtraCreate,
    db: Session = Depends(get_db),
    current_user: Usuario = Depends(get_current_user),
):
    """
    Registra que un empleado trabajó un fin de semana o feriado no
    planeado y acredita las horas correspondientes como saldo vacacional.

    **No valida** que la fecha haya sido realmente un fin de semana o
    feriado — se confía en que el admin lo carga correctamente.

    **No depende de asistencia_diaria**: puede registrarse antes de que
    exista el registro de esa fecha (asistencia_diaria se genera recién al
    procesar el Excel mensual) o después, indistintamente.

    **Efecto:** el trigger de Neon `trg_compensacion_horas_extra_a_vacacion`
    suma automáticamente `horas` a `vacacion.horas_correspondientes` y
    `vacacion.horas_goce_haber` de la gestión indicada (creando el registro
    de `vacacion` si todavía no existe para esa gestión). Este endpoint solo
    inserta la fila que dispara ese trigger.

    **Validaciones:**
    - El empleado debe existir (404 si no)
    - Solo puede haber una compensación por empleado+fecha (409 si ya existe)
    """
    services._get_empleado_or_404(db, data.id_empleado)

    compensacion = services.registrar_compensacion(
        db,
        id_empleado=data.id_empleado,
        fecha=data.fecha,
        horas=data.horas,
        motivo=data.motivo,
        gestion=data.gestion,
        id_registrado_por=get_actor_empleado_id(current_user),
    )

    if compensacion is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe una compensación registrada para el empleado {data.id_empleado} en la fecha {data.fecha}"
        )

    return compensacion


@router.get(
    "/",
    response_model=List[CompensacionHorasExtraResponse],
    summary="Listar compensaciones de horas extra",
    dependencies=[Depends(require_roles("admin", "rrhh"))],
)
def listar_compensaciones(
    id_empleado: Optional[int] = Query(None, description="Filtrar por empleado"),
    gestion: Optional[int] = Query(None, description="Filtrar por año"),
    skip: int = Query(0, ge=0, description="Registros a omitir"),
    limit: int = Query(100, ge=1, le=500, description="Límite de registros"),
    db: Session = Depends(get_db)
):
    """
    Lista compensaciones de horas extra con filtros opcionales.

    **Útil para reportes/auditoría de RRHH**, que puede consultarlo pero no
    registrar: el POST sigue siendo exclusivo del rol admin.

    **Filtros disponibles:**
    - `id_empleado`: compensaciones de un empleado específico
    - `gestion`: compensaciones acreditadas a una gestión (año) específica
    """
    return services.listar_compensaciones(
        db,
        id_empleado=id_empleado,
        gestion=gestion,
        skip=skip,
        limit=limit
    )
