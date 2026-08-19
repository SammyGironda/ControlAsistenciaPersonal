"""
Router para endpoints de Departamento.

Reparto de roles (aplicado el 2026-08-19; antes las 7 rutas estaban abiertas):

- **Escritura** (crear / actualizar / desactivar) -> `require_admin`. Reorganizar
  la estructura organizacional es administracion del sistema, no gestion de
  personal: mover un departamento cambia a que unidad pertenecen sus empleados.
- **Lectura** (los 4 GET) -> `get_current_user`, o sea cualquier usuario
  autenticado, y NO `require_roles("admin", "rrhh")`.

  El motivo es concreto: `GET /departamentos/` alimenta el desplegable
  "Area / Departamento" del formulario de empleados, y el item "Empleados" del
  Sidebar no esta reservado por rol. Con un guard de admin+rrhh, un supervisor
  abriria ese formulario y veria el desplegable vacio por un 403. El catalogo
  organizacional no es dato sensible; lo que hay que proteger es modificarlo.

Ninguna ruta necesita guard de pertenencia: un departamento no tiene dueño, asi
que los 7 guards son declarativos (`dependencies=[...]` en el decorador) y las
firmas de las funciones no cambian.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user, require_admin
from app.features.employees.departamento import services
from app.features.employees.departamento.schemas import (
    DepartamentoCreate,
    DepartamentoUpdate,
    DepartamentoResponse,
    DepartamentoConHijos
)

router = APIRouter(
    prefix="/departamentos",
    tags=["Departamentos"]
)


@router.post(
    "/",
    response_model=DepartamentoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Crear departamento",
    description="Crea un nuevo departamento organizacional. Puede ser raíz (id_padre=NULL) o hijo.",
    dependencies=[Depends(require_admin)]
)
def create_departamento(
    data: DepartamentoCreate,
    db: Session = Depends(get_db)
):
    """
    Crea un nuevo departamento.
    
    - **nombre**: Nombre del departamento
    - **codigo**: Código único del departamento
    - **id_padre**: ID del departamento padre (NULL = raíz)
    - **activo**: Estado del departamento
    """
    return services.create_departamento(db, data)


@router.get(
    "/",
    response_model=List[DepartamentoResponse],
    summary="Listar departamentos",
    description="Obtiene todos los departamentos con paginación opcional",
    dependencies=[Depends(get_current_user)]
)
def get_all_departamentos(
    skip: int = Query(0, ge=0, description="Offset para paginación"),
    limit: int = Query(100, ge=1, le=500, description="Cantidad máxima de resultados"),
    activo_only: bool = Query(False, description="Solo departamentos activos"),
    db: Session = Depends(get_db)
):
    """Lista todos los departamentos con filtros opcionales."""
    return services.get_all_departamentos(db, skip=skip, limit=limit, activo_only=activo_only)


@router.get(
    "/raiz",
    response_model=List[DepartamentoConHijos],
    summary="Obtener árbol organizacional completo",
    description="Retorna todos los departamentos raíz con su jerarquía completa de hijos",
    dependencies=[Depends(get_current_user)]
)
def get_departamentos_raiz(db: Session = Depends(get_db)):
    """
    Obtiene el árbol organizacional completo.
    
    Retorna solo los departamentos raíz (id_padre=NULL),
    pero cada uno incluye recursivamente todos sus hijos.
    """
    return services.get_departamentos_raiz(db)


@router.get(
    "/{departamento_id}",
    response_model=DepartamentoResponse,
    summary="Obtener departamento por ID",
    description="Retorna un departamento específico por su ID",
    dependencies=[Depends(get_current_user)]
)
def get_departamento(
    departamento_id: int,
    db: Session = Depends(get_db)
):
    """Obtiene un departamento por ID."""
    departamento = services.get_departamento_by_id(db, departamento_id)
    if not departamento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el departamento con id {departamento_id}"
        )
    return departamento


@router.get(
    "/{departamento_id}/jerarquia",
    response_model=DepartamentoConHijos,
    summary="Obtener departamento con jerarquía de hijos",
    description="Retorna un departamento con todos sus subdepartamentos (recursivo)",
    dependencies=[Depends(get_current_user)]
)
def get_jerarquia_departamento(
    departamento_id: int,
    db: Session = Depends(get_db)
):
    """
    Obtiene un departamento con toda su jerarquía de hijos.
    
    Útil para visualizar la estructura organizacional
    debajo de un departamento específico.
    """
    return services.get_jerarquia_departamento(db, departamento_id)


@router.put(
    "/{departamento_id}",
    response_model=DepartamentoResponse,
    summary="Actualizar departamento",
    description="Actualiza los datos de un departamento existente",
    dependencies=[Depends(require_admin)]
)
def update_departamento(
    departamento_id: int,
    data: DepartamentoUpdate,
    db: Session = Depends(get_db)
):
    """Actualiza un departamento existente."""
    return services.update_departamento(db, departamento_id, data)


@router.delete(
    "/{departamento_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar departamento",
    description="Elimina (soft delete) un departamento. No permite eliminar si tiene hijos, cargos o empleados activos.",
    dependencies=[Depends(require_admin)]
)
def delete_departamento(
    departamento_id: int,
    db: Session = Depends(get_db)
):
    """
    Elimina un departamento (soft delete).
    
    Validaciones:
    - No puede tener subdepartamentos activos
    - No puede tener cargos asignados
    - No puede tener empleados activos
    """
    services.delete_departamento(db, departamento_id)
    return None
