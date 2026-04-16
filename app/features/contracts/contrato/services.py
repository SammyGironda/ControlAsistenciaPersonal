"""
Services para gestión de contratos laborales.
Lógica de negocio completa para CRUD y operaciones especiales.
"""

from datetime import date
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from fastapi import HTTPException, status

from app.features.contracts.contrato.models import Contrato, TipoContratoEnum, EstadoContratoEnum
from app.features.contracts.contrato.schemas import (
    ContratoCreate,
    ContratoUpdate,
    ContratoRenovacion,
    ContratoCreateIndefinido,
    ContratoCreatePlazoFijo,
)
from app.features.employees.empleado.models import Empleado, EstadoEmpleadoEnum


# ============================================================
# CRUD BÁSICO
# ============================================================

def create_contrato(db: Session, data: ContratoCreate) -> Contrato:
    """
    Crea un nuevo contrato.
    
    Validaciones:
    - El empleado debe existir y estar activo
    - No debe tener otro contrato activo
    - Si es plazo_fijo, debe tener fecha_fin
    """
    # Validar que el empleado existe y está activo
    empleado = db.query(Empleado).filter(Empleado.id == data.id_empleado).first()
    if not empleado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el empleado con ID {data.id_empleado}"
        )
    
    if empleado.estado == EstadoEmpleadoEnum.baja:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El empleado {empleado.nombre_completo} está dado de baja (estado: {empleado.estado})"
        )
    
    # Validar que no tenga otro contrato activo
    contrato_activo_existente = db.query(Contrato).filter(
        and_(
            Contrato.id_empleado == data.id_empleado,
            Contrato.estado == EstadoContratoEnum.activo,
            or_(
                Contrato.fecha_fin.is_(None),
                Contrato.fecha_fin >= date.today()
            )
        )
    ).first()
    
    if contrato_activo_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El empleado ya tiene un contrato activo (ID: {contrato_activo_existente.id})"
        )
    
    # Crear contrato
    contrato = Contrato(
        id_empleado=data.id_empleado,
        tipo_contrato=TipoContratoEnum(data.tipo_contrato),
        fecha_inicio=data.fecha_inicio,
        fecha_fin=data.fecha_fin,
        salario_base=data.salario_base,
        estado=EstadoContratoEnum.activo,
        documento_contrato_url=data.documento_contrato_url,
        observacion=data.observacion
    )
    
    db.add(contrato)
    db.commit()
    db.refresh(contrato)

    if empleado.estado != EstadoEmpleadoEnum.activo:
        empleado.estado = EstadoEmpleadoEnum.activo
        db.commit()
        db.refresh(empleado)
    
    return contrato


def create_contrato_indefinido(db: Session, data: ContratoCreateIndefinido) -> Contrato:
    contrato_data = ContratoCreate(
        id_empleado=data.id_empleado,
        tipo_contrato="indefinido",
        fecha_inicio=data.fecha_inicio,
        fecha_fin=None,
        salario_base=data.salario_base,
        documento_contrato_url=data.documento_contrato_url,
        observacion=data.observacion
    )
    return create_contrato(db, contrato_data)


def create_contrato_plazo_fijo(db: Session, data: ContratoCreatePlazoFijo) -> Contrato:
    contrato_data = ContratoCreate(
        id_empleado=data.id_empleado,
        tipo_contrato="plazo_fijo",
        fecha_inicio=data.fecha_inicio,
        fecha_fin=data.fecha_fin,
        salario_base=data.salario_base,
        documento_contrato_url=data.documento_contrato_url,
        observacion=data.observacion
    )
    return create_contrato(db, contrato_data)


def get_contrato_by_id(db: Session, contrato_id: int) -> Optional[Contrato]:
    """Obtiene un contrato por ID."""
    return db.query(Contrato).filter(Contrato.id == contrato_id).first()


def get_contratos_by_empleado(
    db: Session,
    empleado_id: int,
    solo_activos: bool = False
) -> List[Contrato]:
    """
    Obtiene todos los contratos de un empleado.
    
    Args:
        empleado_id: ID del empleado
        solo_activos: Si True, solo retorna contratos con estado='activo'
    """
    query = db.query(Contrato).filter(Contrato.id_empleado == empleado_id)
    
    if solo_activos:
        query = query.filter(Contrato.estado == EstadoContratoEnum.activo)
    
    return query.order_by(Contrato.fecha_inicio.desc()).all()


def get_contrato_activo_empleado(db: Session, empleado_id: int) -> Optional[Contrato]:
    """
    Obtiene el contrato activo actual de un empleado.
    
    Retorna el contrato con estado='activo' y que esté vigente (fecha_fin NULL o futura).
    """
    return db.query(Contrato).filter(
        and_(
            Contrato.id_empleado == empleado_id,
            Contrato.estado == EstadoContratoEnum.activo,
            or_(
                Contrato.fecha_fin.is_(None),
                Contrato.fecha_fin >= date.today()
            )
        )
    ).first()


def get_all_contratos(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    tipo_contrato: Optional[str] = None,
    estado: Optional[str] = None
) -> List[Contrato]:
    """
    Lista todos los contratos con filtros opcionales.
    """
    query = db.query(Contrato)
    
    if tipo_contrato:
        query = query.filter(Contrato.tipo_contrato == TipoContratoEnum(tipo_contrato))
    
    if estado:
        query = query.filter(Contrato.estado == EstadoContratoEnum(estado))
    
    return query.order_by(Contrato.created_at.desc()).offset(skip).limit(limit).all()


# ============================================================
# GESTIÓN DE ESTADOS
# ============================================================

def finalizar_contrato(db: Session, contrato_id: int, observacion: Optional[str] = None) -> Contrato:
    """
    Finaliza un contrato (cambio de estado a 'vencido').
    
    Se usa cuando el contrato termina de forma normal (ej: vencimiento plazo_fijo).
    """
    contrato = get_contrato_by_id(db, contrato_id)
    if not contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el contrato con ID {contrato_id}"
        )
    
    if contrato.estado != EstadoContratoEnum.activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El contrato no está activo (estado actual: {contrato.estado})"
        )
    
    contrato.estado = EstadoContratoEnum.vencido
    if observacion:
        contrato.observacion = f"{contrato.observacion or ''}\n[FINALIZADO] {observacion}".strip()
    
    db.commit()
    db.refresh(contrato)
    
    return contrato


def rescindir_contrato(db: Session, contrato_id: int, observacion: Optional[str] = None) -> Contrato:
    """
    Rescinde un contrato (cambio de estado a 'rescindido').
    
    Se usa cuando el contrato termina de forma anticipada o forzada.
    """
    contrato = get_contrato_by_id(db, contrato_id)
    if not contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el contrato con ID {contrato_id}"
        )
    
    if contrato.estado != EstadoContratoEnum.activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El contrato no está activo (estado actual: {contrato.estado})"
        )
    
    contrato.estado = EstadoContratoEnum.rescindido
    if observacion:
        contrato.observacion = f"{contrato.observacion or ''}\n[RESCINDIDO] {observacion}".strip()
    
    db.commit()
    db.refresh(contrato)
    
    return contrato


def renovar_contrato_plazo_fijo(
    db: Session,
    contrato_id: int,
    data: ContratoRenovacion
) -> Contrato:
    """
    Renueva un contrato plazo_fijo creando un NUEVO contrato con salario incrementado.
    
    Proceso:
    1. Valida que el contrato existe, es plazo_fijo y está activo
    2. Finaliza el contrato anterior
    3. Crea un nuevo contrato con el nuevo salario
    
    NOTA: Para contratos indefinidos, los incrementos se registran en ajuste_salarial,
    NO se crea un nuevo contrato.
    """
    contrato_anterior = get_contrato_by_id(db, contrato_id)
    if not contrato_anterior:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el contrato con ID {contrato_id}"
        )
    
    # Validar que es plazo_fijo
    if contrato_anterior.tipo_contrato != TipoContratoEnum.plazo_fijo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Solo se pueden renovar contratos plazo_fijo. Para contratos indefinidos, usar ajuste_salarial."
        )
    
    # Validar que está activo
    if contrato_anterior.estado != EstadoContratoEnum.activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El contrato no está activo (estado: {contrato_anterior.estado})"
        )
    
    # Validar que el nuevo contrato comienza después del anterior
    if data.fecha_inicio <= contrato_anterior.fecha_inicio:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La fecha_inicio del nuevo contrato debe ser posterior al contrato anterior"
        )
    
    # Finalizar contrato anterior
    contrato_anterior.estado = EstadoContratoEnum.vencido
    contrato_anterior.observacion = f"{contrato_anterior.observacion or ''}\n[RENOVADO] Nuevo contrato creado".strip()
    
    # Crear nuevo contrato
    contrato_nuevo = Contrato(
        id_empleado=contrato_anterior.id_empleado,
        tipo_contrato=TipoContratoEnum.plazo_fijo,
        fecha_inicio=data.fecha_inicio,
        fecha_fin=data.fecha_fin,
        salario_base=data.salario_base,
        estado=EstadoContratoEnum.activo,
        documento_contrato_url=data.documento_contrato_url,
        observacion=f"Renovación de contrato ID {contrato_id}. {data.observacion or ''}".strip()
    )
    
    db.add(contrato_nuevo)
    db.commit()
    db.refresh(contrato_nuevo)
    
    return contrato_nuevo


def update_contrato(db: Session, contrato_id: int, data: ContratoUpdate) -> Contrato:
    """
    Actualiza campos específicos de un contrato.
    
    Solo permite actualizar: estado, observacion
    """
    contrato = get_contrato_by_id(db, contrato_id)
    if not contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el contrato con ID {contrato_id}"
        )
    
    if data.estado is not None:
        contrato.estado = EstadoContratoEnum(data.estado)

    if data.documento_contrato_url is not None:
        contrato.documento_contrato_url = data.documento_contrato_url
    
    if data.observacion is not None:
        contrato.observacion = data.observacion
    
    db.commit()
    db.refresh(contrato)
    
    return contrato
