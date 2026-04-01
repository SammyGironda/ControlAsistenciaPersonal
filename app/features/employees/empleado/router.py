"""
Router para endpoints de Empleado.
Todos los endpoints están abiertos (sin autenticación hasta Semana 9).
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.features.employees.empleado import services
from app.features.employees.empleado.schemas import (
    EmpleadoCreate,
    EmpleadoUpdate,
    EmpleadoResponse,
    EmpleadoCambioEstado
)
from app.features.employees.horario.schemas import AsignacionHorarioConDetalle

router = APIRouter(
    prefix="/empleados",
    tags=["Empleados"]
)


@router.post(
    "/",
    response_model=EmpleadoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear empleado",
    description="Registra un nuevo empleado en el sistema"
)
def create_empleado(
    data: EmpleadoCreate,
    db: Session = Depends(get_db)
):
    """
    Crea un nuevo empleado.
    
    Validaciones:
    - CI único
    - Edad mínima 18 años
    - Departamento y cargo deben existir y estar activos
    """
    return services.create_empleado(db, data)


@router.get(
    "/",
    response_model=List[EmpleadoResponse],
    summary="Listar empleados",
    description="Obtiene todos los empleados con paginación y filtros opcionales"
)
def get_all_empleados(
    skip: int = Query(0, ge=0, description="Offset para paginación"),
    limit: int = Query(100, ge=1, le=500, description="Cantidad máxima de resultados"),
    estado: Optional[str] = Query(None, pattern="^(activo|baja|suspendido)$", description="Filtrar por estado"),
    id_departamento: Optional[int] = Query(None, description="Filtrar por departamento"),
    id_cargo: Optional[int] = Query(None, description="Filtrar por cargo"),
    db: Session = Depends(get_db)
):
    """Lista todos los empleados con filtros opcionales."""
    return services.get_all_empleados(
        db,
        skip=skip,
        limit=limit,
        estado=estado,
        id_departamento=id_departamento,
        id_cargo=id_cargo
    )


@router.get(
    "/buscar-ci/{ci_completo}",
    response_model=EmpleadoResponse,
    summary="Buscar empleado por CI",
    description="Busca un empleado por su CI completo en formato: 1234567-LP o 1234567-LP-1A"
)
def buscar_por_ci(
    ci_completo: str = Path(..., description="CI en formato: numero-complemento o numero-complemento-sufijo"),
    db: Session = Depends(get_db)
):
    """
    Busca un empleado por su CI completo.
    
    Formatos aceptados:
    - 1234567-LP (sin sufijo homónimo)
    - 1234567-LP-1A (con sufijo homónimo)
    """
    partes = ci_completo.split("-")
    
    if len(partes) < 2 or len(partes) > 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Formato de CI inválido. Use: numero-complemento o numero-complemento-sufijo"
        )
    
    ci_numero = partes[0]
    complemento_dep = partes[1]
    ci_sufijo = partes[2] if len(partes) == 3 else None
    
    empleado = services.buscar_empleado_por_ci(db, ci_numero, complemento_dep, ci_sufijo)
    
    if not empleado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró ningún empleado con CI {ci_completo}"
        )
    
    return empleado


@router.get(
    "/{empleado_id}",
    response_model=EmpleadoResponse,
    summary="Obtener empleado por ID",
    description="Retorna un empleado específico por su ID"
)
def get_empleado(
    empleado_id: int,
    db: Session = Depends(get_db)
):
    """Obtiene un empleado por ID."""
    empleado = services.get_empleado_by_id(db, empleado_id)
    if not empleado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el empleado con id {empleado_id}"
        )
    return empleado


@router.get(
    "/{empleado_id}/horario-actual",
    response_model=Optional[AsignacionHorarioConDetalle],
    summary="Obtener horario actual del empleado",
    description="Retorna el horario vigente del empleado en la fecha actual"
)
def get_horario_actual(
    empleado_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene el horario vigente del empleado.
    
    Retorna None si el empleado no tiene horario asignado actualmente.
    """
    from app.features.employees.horario import services as horario_services
    return horario_services.get_horario_actual_empleado(db, empleado_id)


@router.put(
    "/{empleado_id}",
    response_model=EmpleadoResponse,
    summary="Actualizar empleado",
    description="Actualiza los datos de un empleado existente"
)
def update_empleado(
    empleado_id: int,
    data: EmpleadoUpdate,
    db: Session = Depends(get_db)
):
    """Actualiza un empleado existente."""
    return services.update_empleado(db, empleado_id, data)


@router.put(
    "/{empleado_id}/dar-baja",
    response_model=EmpleadoResponse,
    summary="Dar de baja a un empleado",
    description="Cambia el estado del empleado a 'baja' (soft delete)"
)
def dar_baja_empleado(
    empleado_id: int,
    data: EmpleadoCambioEstado,
    db: Session = Depends(get_db)
):
    """
    Da de baja a un empleado.
    
    El empleado permanece en la BD pero con estado='baja'.
    No se puede reactivar - debe reingresarse como nuevo.
    """
    return services.dar_baja_empleado(db, empleado_id, data)


@router.put(
    "/{empleado_id}/suspender",
    response_model=EmpleadoResponse,
    summary="Suspender empleado",
    description="Cambia el estado del empleado a 'suspendido'"
)
def suspender_empleado(
    empleado_id: int,
    data: EmpleadoCambioEstado,
    db: Session = Depends(get_db)
):
    """
    Suspende temporalmente a un empleado.
    
    Puede ser reactivado posteriormente.
    """
    return services.suspender_empleado(db, empleado_id, data)


@router.put(
    "/{empleado_id}/reactivar",
    response_model=EmpleadoResponse,
    summary="Reactivar empleado",
    description="Cambia el estado del empleado a 'activo' (solo para suspendidos)"
)
def reactivar_empleado(
    empleado_id: int,
    db: Session = Depends(get_db)
):
    """
    Reactiva un empleado suspendido.
    
    No permite reactivar empleados dados de baja.
    """
    return services.reactivar_empleado(db, empleado_id)
