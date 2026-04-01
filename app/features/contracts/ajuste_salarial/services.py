"""
Services para ajustes salariales, decretos e impuestos.
Incluye lógica para aplicación masiva de decretos.
"""

from datetime import date
from typing import List, Optional, Dict, Any
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, text
from fastapi import HTTPException, status

from app.features.contracts.ajuste_salarial.models import (
    AjusteSalarial, DecretoIncrementoSalarial, CondicionDecreto,
    ParametroImpuesto, MotivoAjusteEnum
)
from app.features.contracts.ajuste_salarial.schemas import (
    AjusteSalarialCreate, DecretoCreate, CondicionDecretoCreate,
    ParametroImpuestoCreate
)
from app.features.contracts.contrato.models import Contrato, TipoContratoEnum, EstadoContratoEnum
from app.features.employees.empleado.models import Empleado, EstadoEmpleadoEnum


# ============================================================
# AJUSTE SALARIAL - CRUD
# ============================================================

def create_ajuste_salarial(db: Session, data: AjusteSalarialCreate) -> AjusteSalarial:
    """
    Crea un nuevo ajuste salarial.
    
    Validaciones:
    - El empleado, contrato y condición_decreto (si aplica) deben existir
    - salario_nuevo debe ser diferente a salario_anterior
    - El contrato debe estar activo
    
    IMPORTANTE: Al insertar, el trigger trg_sync_salario_empleado actualiza
    automáticamente empleado.salario_base si fecha_vigencia <= hoy.
    """
    # Validar empleado
    empleado = db.query(Empleado).filter(Empleado.id == data.id_empleado).first()
    if not empleado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el empleado con ID {data.id_empleado}"
        )
    
    # Validar contrato
    contrato = db.query(Contrato).filter(Contrato.id == data.id_contrato).first()
    if not contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el contrato con ID {data.id_contrato}"
        )
    
    if contrato.estado != EstadoContratoEnum.activo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El contrato no está activo (estado: {contrato.estado})"
        )
    
    # Validar condición decreto si se proporciona
    if data.id_condicion_decreto:
        condicion = db.query(CondicionDecreto).filter(
            CondicionDecreto.id == data.id_condicion_decreto
        ).first()
        if not condicion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No existe la condición de decreto con ID {data.id_condicion_decreto}"
            )
    
    # Crear ajuste
    ajuste = AjusteSalarial(
        id_empleado=data.id_empleado,
        id_contrato=data.id_contrato,
        id_condicion_decreto=data.id_condicion_decreto,
        salario_anterior=data.salario_anterior,
        salario_nuevo=data.salario_nuevo,
        fecha_vigencia=data.fecha_vigencia,
        motivo=MotivoAjusteEnum(data.motivo),
        id_aprobado_por=data.id_aprobado_por,
        observacion=data.observacion
    )
    
    db.add(ajuste)
    db.commit()
    db.refresh(ajuste)
    
    # Nota: El trigger trg_sync_salario_empleado ya actualizó empleado.salario_base
    # si fecha_vigencia <= CURRENT_DATE
    
    return ajuste


def get_ajustes_by_empleado(
    db: Session,
    empleado_id: int,
    skip: int = 0,
    limit: int = 100
) -> List[AjusteSalarial]:
    """Obtiene el historial completo de ajustes salariales de un empleado."""
    return db.query(AjusteSalarial).filter(
        AjusteSalarial.id_empleado == empleado_id
    ).order_by(AjusteSalarial.fecha_vigencia.desc()).offset(skip).limit(limit).all()


def get_ultimo_ajuste_vigente(db: Session, empleado_id: int) -> Optional[AjusteSalarial]:
    """
    Obtiene el último ajuste salarial vigente de un empleado.
    
    Retorna el ajuste con fecha_vigencia <= hoy, ordenado por fecha_vigencia DESC.
    """
    return db.query(AjusteSalarial).filter(
        and_(
            AjusteSalarial.id_empleado == empleado_id,
            AjusteSalarial.fecha_vigencia <= date.today()
        )
    ).order_by(AjusteSalarial.fecha_vigencia.desc()).first()


# ============================================================
# DECRETO - CRUD
# ============================================================

def create_decreto(db: Session, data: DecretoCreate) -> DecretoIncrementoSalarial:
    """
    Crea un decreto con sus condiciones (tramos).
    
    Validaciones:
    - El año debe ser único
    - Debe tener al menos una condición
    - Los órdenes deben ser únicos
    """
    # Validar que no existe otro decreto para el mismo año
    decreto_existente = db.query(DecretoIncrementoSalarial).filter(
        DecretoIncrementoSalarial.anio == data.anio
    ).first()
    
    if decreto_existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un decreto para el año {data.anio} (ID: {decreto_existente.id})"
        )
    
    # Crear decreto
    decreto = DecretoIncrementoSalarial(
        anio=data.anio,
        nuevo_smn=data.nuevo_smn,
        fecha_vigencia=data.fecha_vigencia,
        referencia_decreto=data.referencia_decreto
    )
    
    db.add(decreto)
    db.flush()  # Para obtener el ID del decreto
    
    # Crear condiciones
    for cond_data in data.condiciones:
        condicion = CondicionDecreto(
            id_decreto=decreto.id,
            orden=cond_data.orden,
            salario_desde=cond_data.salario_desde,
            salario_hasta=cond_data.salario_hasta,
            porcentaje_incremento=cond_data.porcentaje_incremento
        )
        db.add(condicion)
    
    db.commit()
    db.refresh(decreto)
    
    return decreto


def get_decreto_by_id(db: Session, decreto_id: int) -> Optional[DecretoIncrementoSalarial]:
    """Obtiene un decreto por ID con sus condiciones."""
    return db.query(DecretoIncrementoSalarial).filter(
        DecretoIncrementoSalarial.id == decreto_id
    ).first()


def get_decreto_by_anio(db: Session, anio: int) -> Optional[DecretoIncrementoSalarial]:
    """Obtiene el decreto de un año específico."""
    return db.query(DecretoIncrementoSalarial).filter(
        DecretoIncrementoSalarial.anio == anio
    ).first()


def get_all_decretos(db: Session, skip: int = 0, limit: int = 100) -> List[DecretoIncrementoSalarial]:
    """Lista todos los decretos ordenados por año descendente."""
    return db.query(DecretoIncrementoSalarial).order_by(
        DecretoIncrementoSalarial.anio.desc()
    ).offset(skip).limit(limit).all()


def calcular_porcentaje_incremento(
    db: Session,
    decreto_id: int,
    salario_actual: Decimal
) -> Decimal:
    """
    Calcula el porcentaje de incremento que aplica a un salario dado.
    
    Usa la función PL/pgSQL fn_porcentaje_incremento_decreto.
    Retorna el porcentaje del primer tramo coincidente (ORDER BY orden).
    
    Lanza excepción si no hay tramo aplicable.
    """
    try:
        result = db.execute(
            text("SELECT rrhh.fn_porcentaje_incremento_decreto(:decreto_id, :salario)"),
            {"decreto_id": decreto_id, "salario": float(salario_actual)}
        ).scalar()
        
        return Decimal(str(result))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Error al calcular porcentaje: {str(e)}"
        )


# ============================================================
# DECRETO - APLICACIÓN MASIVA
# ============================================================

def aplicar_decreto_anual(
    db: Session,
    decreto_id: int,
    id_aprobado_por: int
) -> Dict[str, Any]:
    """
    Aplica un decreto anual a TODOS los empleados activos con contrato indefinido.
    
    Proceso:
    1. Obtiene todos los empleados con contrato indefinido activo
    2. Para cada uno:
       - Calcula el porcentaje de incremento según su salario actual
       - Calcula el nuevo salario
       - Crea un ajuste_salarial con motivo='decreto_anual'
    3. El trigger trg_sync_salario_empleado actualiza empleado.salario_base automáticamente
    
    Retorna:
    - empleados_procesados: Total de empleados evaluados
    - ajustes_creados: Total de ajustes creados exitosamente
    - errores: Lista de errores por empleado
    """
    # Validar que el decreto existe
    decreto = get_decreto_by_id(db, decreto_id)
    if not decreto:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el decreto con ID {decreto_id}"
        )
    
    # Validar que el aprobador existe
    aprobador = db.query(Empleado).filter(Empleado.id == id_aprobado_por).first()
    if not aprobador:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el empleado aprobador con ID {id_aprobado_por}"
        )
    
    # Obtener empleados con contrato indefinido activo
    empleados_con_contrato_indefinido = db.query(Empleado).join(
        Contrato, Contrato.id_empleado == Empleado.id
    ).filter(
        and_(
            Empleado.estado == EstadoEmpleadoEnum.activo,
            Contrato.tipo_contrato == TipoContratoEnum.indefinido,
            Contrato.estado == EstadoContratoEnum.activo
        )
    ).all()
    
    empleados_procesados = len(empleados_con_contrato_indefinido)
    ajustes_creados = 0
    errores = []
    
    for empleado in empleados_con_contrato_indefinido:
        try:
            # Obtener contrato activo
            contrato = db.query(Contrato).filter(
                and_(
                    Contrato.id_empleado == empleado.id,
                    Contrato.tipo_contrato == TipoContratoEnum.indefinido,
                    Contrato.estado == EstadoContratoEnum.activo
                )
            ).first()
            
            if not contrato:
                errores.append(f"Empleado ID {empleado.id}: No se encontró contrato indefinido activo")
                continue
            
            # Calcular porcentaje de incremento
            porcentaje = calcular_porcentaje_incremento(db, decreto_id, empleado.salario_base)
            
            # Calcular nuevo salario
            salario_anterior = empleado.salario_base
            incremento = salario_anterior * (porcentaje / Decimal('100'))
            salario_nuevo = salario_anterior + incremento
            
            # Redondear a 2 decimales
            salario_nuevo = salario_nuevo.quantize(Decimal('0.01'))
            
            # Buscar la condición aplicada para auditoría
            condicion_aplicada = db.query(CondicionDecreto).filter(
                and_(
                    CondicionDecreto.id_decreto == decreto_id,
                    or_(
                        CondicionDecreto.salario_desde.is_(None),
                        salario_anterior >= CondicionDecreto.salario_desde
                    ),
                    or_(
                        CondicionDecreto.salario_hasta.is_(None),
                        salario_anterior <= CondicionDecreto.salario_hasta
                    )
                )
            ).order_by(CondicionDecreto.orden).first()
            
            # Crear ajuste salarial
            ajuste = AjusteSalarial(
                id_empleado=empleado.id,
                id_contrato=contrato.id,
                id_condicion_decreto=condicion_aplicada.id if condicion_aplicada else None,
                salario_anterior=salario_anterior,
                salario_nuevo=salario_nuevo,
                fecha_vigencia=decreto.fecha_vigencia,
                motivo=MotivoAjusteEnum.decreto_anual,
                id_aprobado_por=id_aprobado_por,
                observacion=f"Aplicación {decreto.referencia_decreto} - Incremento {porcentaje}%"
            )
            
            db.add(ajuste)
            ajustes_creados += 1
            
        except Exception as e:
            errores.append(f"Empleado ID {empleado.id} ({empleado.nombre_completo}): {str(e)}")
            db.rollback()
            continue
    
    db.commit()
    
    return {
        "decreto_id": decreto_id,
        "empleados_procesados": empleados_procesados,
        "ajustes_creados": ajustes_creados,
        "errores": errores
    }


# ============================================================
# PARAMETRO IMPUESTO - CRUD
# ============================================================

def create_parametro_impuesto(db: Session, data: ParametroImpuestoCreate) -> ParametroImpuesto:
    """
    Crea un nuevo parámetro de impuesto.
    
    Si ya existe un parámetro con el mismo nombre vigente, se debe cerrar
    manualmente (establecer fecha_vigencia_fin) antes de crear el nuevo.
    """
    parametro = ParametroImpuesto(
        nombre=data.nombre,
        porcentaje=data.porcentaje,
        fecha_vigencia_inicio=data.fecha_vigencia_inicio,
        fecha_vigencia_fin=data.fecha_vigencia_fin,
        descripcion=data.descripcion
    )
    
    db.add(parametro)
    db.commit()
    db.refresh(parametro)
    
    return parametro


def get_parametro_vigente(
    db: Session,
    nombre: str,
    fecha: Optional[date] = None
) -> Optional[ParametroImpuesto]:
    """
    Obtiene el parámetro vigente de un concepto en una fecha dada.
    
    Si no se proporciona fecha, usa la fecha actual.
    """
    if fecha is None:
        fecha = date.today()
    
    return db.query(ParametroImpuesto).filter(
        and_(
            ParametroImpuesto.nombre == nombre,
            ParametroImpuesto.fecha_vigencia_inicio <= fecha,
            or_(
                ParametroImpuesto.fecha_vigencia_fin.is_(None),
                ParametroImpuesto.fecha_vigencia_fin >= fecha
            )
        )
    ).order_by(ParametroImpuesto.fecha_vigencia_inicio.desc()).first()


def get_historial_parametro(
    db: Session,
    nombre: str,
    skip: int = 0,
    limit: int = 100
) -> List[ParametroImpuesto]:
    """Obtiene el historial completo de un parámetro."""
    return db.query(ParametroImpuesto).filter(
        ParametroImpuesto.nombre == nombre
    ).order_by(ParametroImpuesto.fecha_vigencia_inicio.desc()).offset(skip).limit(limit).all()


def get_all_parametros_vigentes(db: Session) -> List[ParametroImpuesto]:
    """
    Obtiene todos los parámetros vigentes actualmente.
    
    Retorna el último parámetro vigente de cada concepto.
    """
    # Subconsulta para obtener el máximo id por nombre (el más reciente vigente)
    subquery = db.query(
        ParametroImpuesto.nombre,
        db.func.max(ParametroImpuesto.id).label('max_id')
    ).filter(
        and_(
            ParametroImpuesto.fecha_vigencia_inicio <= date.today(),
            or_(
                ParametroImpuesto.fecha_vigencia_fin.is_(None),
                ParametroImpuesto.fecha_vigencia_fin >= date.today()
            )
        )
    ).group_by(ParametroImpuesto.nombre).subquery()
    
    return db.query(ParametroImpuesto).join(
        subquery,
        ParametroImpuesto.id == subquery.c.max_id
    ).all()
