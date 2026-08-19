"""
Services para ajustes salariales, decretos e impuestos.
Incluye lógica para aplicación masiva de decretos.
"""

from datetime import date, timedelta
from typing import List, Optional, Dict, Any
from decimal import Decimal
from sqlalchemy.orm import Session
from sqlalchemy import and_, text, or_, func
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

def create_ajuste_salarial(db: Session, data: AjusteSalarialCreate, id_aprobado_por: int) -> AjusteSalarial:
    """
    Crea un nuevo ajuste salarial.

    id_aprobado_por es el id_empleado del usuario autenticado (resuelto en el
    router vía get_actor_empleado_id) — siempre viene no-nulo.

    Validaciones:
    - El empleado debe existir
    - El empleado debe tener un contrato indefinido activo y vigente
    - salario_nuevo debe ser diferente al salario actual del empleado
    - El ajuste salarial manual solo aplica a contratos indefinidos

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
    
    # Validar contrato vigente del empleado
    contrato = db.query(Contrato).filter(
        and_(
            Contrato.id_empleado == data.id_empleado,
            Contrato.estado == EstadoContratoEnum.activo,
            Contrato.tipo_contrato == TipoContratoEnum.indefinido
        )
    ).order_by(Contrato.fecha_inicio.desc()).first()
    if not contrato:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe un contrato indefinido activo para el empleado con ID {data.id_empleado}"
        )

    if data.fecha_vigencia > date.today():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="fecha_vigencia no puede ser posterior a la fecha actual"
        )

    motivo = MotivoAjusteEnum(data.motivo)

    if motivo == MotivoAjusteEnum.decreto_anual and data.id_condicion_decreto is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="id_condicion_decreto es obligatorio cuando el motivo es decreto_anual"
        )

    if motivo != MotivoAjusteEnum.decreto_anual and data.id_condicion_decreto is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="id_condicion_decreto solo puede enviarse cuando el motivo es decreto_anual"
        )

    salario_anterior = empleado.salario_base
    if salario_anterior is None or salario_anterior <= 0:
        salario_anterior = contrato.salario_base

    if salario_anterior == data.salario_nuevo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="salario_nuevo debe ser diferente al salario actual del empleado"
        )
    
    # Validar condición decreto si se proporciona
    if data.id_condicion_decreto is not None:
        condicion = db.query(CondicionDecreto).filter(
            CondicionDecreto.id == data.id_condicion_decreto
        ).first()
        if not condicion:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No existe la condición de decreto con ID {data.id_condicion_decreto}"
            )

    aprobador = db.query(Empleado).filter(Empleado.id == id_aprobado_por).first()
    if not aprobador:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No existe el empleado aprobador con ID {id_aprobado_por}"
        )

    # Crear ajuste solo cuando todas las validaciones ya pasaron.
    ajuste = AjusteSalarial(
        id_empleado=data.id_empleado,
        id_contrato=contrato.id,
        id_condicion_decreto=data.id_condicion_decreto,
        salario_anterior=salario_anterior,
        salario_nuevo=data.salario_nuevo,
        fecha_vigencia=data.fecha_vigencia,
        motivo=motivo,
        id_aprobado_por=id_aprobado_por,
        observacion=data.observacion,
    )

    try:
        db.add(ajuste)
        db.flush()
        db.commit()
        db.refresh(ajuste)
        return ajuste
    except Exception:
        db.rollback()
        raise


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
    
    Retorna el ajuste más reciente cuya fecha_vigencia sea menor o igual a hoy.
    Si no existe uno aplicable todavía, retorna None.
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
            {"decreto_id": decreto_id, "salario": salario_actual}
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

    Cada empleado se confirma con su propio commit, de modo que un fallo aislado
    (por ejemplo, un salario fuera de todos los tramos del decreto) no descarta
    los ajustes de los empleados ya procesados: se registra en `errores` y el
    proceso continúa con el siguiente.

    Retorna:
    - empleados_procesados: Total de empleados evaluados
    - ajustes_creados: Total de ajustes efectivamente confirmados en base de datos
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
    
    # Obtener empleados con contrato indefinido activo.
    # `.distinct()` evita que un empleado con más de un contrato indefinido
    # activo aparezca repetido y reciba ajustes duplicados.
    empleados_con_contrato_indefinido = db.query(Empleado).join(
        Contrato, Contrato.id_empleado == Empleado.id
    ).filter(
        and_(
            Empleado.estado == EstadoEmpleadoEnum.activo,
            Contrato.tipo_contrato == TipoContratoEnum.indefinido,
            Contrato.estado == EstadoContratoEnum.activo
        )
    ).distinct().all()

    empleados_procesados = len(empleados_con_contrato_indefinido)
    ajustes_creados = 0
    errores = []

    for empleado in empleados_con_contrato_indefinido:
        # Se capturan antes del try: tras un rollback los objetos de la sesión
        # quedan expirados y volver a leerlos para armar el mensaje de error
        # dispararía un SELECT sobre una sesión que acaba de fallar.
        empleado_id = empleado.id
        empleado_nombre = empleado.nombre_completo

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
                errores.append(f"Empleado ID {empleado_id}: No se encontró contrato indefinido activo")
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
            
            # Commit por empleado: cada ajuste es independiente. Antes había un
            # único commit al final del loop, así que el rollback del except
            # descartaba TODOS los ajustes acumulados de los empleados
            # anteriores — un fallo en el empleado 500 borraba los 499 previos.
            db.add(ajuste)
            db.commit()
            ajustes_creados += 1

        except Exception as e:
            # Ahora el rollback solo descarta el ajuste del empleado en curso.
            db.rollback()
            errores.append(f"Empleado ID {empleado_id} ({empleado_nombre}): {str(e)}")
            continue

    return {
        "decreto_id": decreto_id,
        "empleados_procesados": empleados_procesados,
        "ajustes_creados": ajustes_creados,
        "errores": errores
    }


# ============================================================
# PARAMETRO IMPUESTO - CRUD
# ============================================================

def get_ultimo_parametro(db: Session, nombre: str) -> Optional[ParametroImpuesto]:
    """
    Última versión registrada de un concepto, vigente o no.

    Desempata por (fecha_vigencia_inicio, id) para ser determinístico incluso si
    dos filas comparten fecha de inicio.
    """
    return db.query(ParametroImpuesto).filter(
        ParametroImpuesto.nombre == nombre
    ).order_by(
        ParametroImpuesto.fecha_vigencia_inicio.desc(),
        ParametroImpuesto.id.desc(),
    ).first()


def create_parametro_impuesto(db: Session, data: ParametroImpuestoCreate) -> ParametroImpuesto:
    """
    Registra una tasa nueva y CIERRA la vigencia de la anterior del mismo
    concepto, en la misma transacción.

    Antes esto no lo hacía nadie: el docstring decía "se debe cerrar
    manualmente", pero como no hay endpoint de UPDATE, "manualmente" significaba
    SQL directo contra la base. El resultado era que dos filas del mismo
    concepto quedaban abiertas a la vez y cada consumidor desempataba distinto.

    El cierre va en la MISMA transacción que el alta a propósito: si la tasa
    nueva se insertara y el cierre de la vieja quedara en otro commit, un fallo
    entre ambos dejaría el concepto con dos tasas vigentes — que es exactamente
    el estado que esta función existe para evitar.
    """
    anterior = get_ultimo_parametro(db, data.nombre)

    # Validar ANTES de mutar nada: si alguna de estas condiciones falla después
    # de tocar `anterior`, la sesión queda con valores inválidos.
    if anterior is not None:
        if anterior.tipo_aporte != data.tipo_aporte:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"El concepto '{data.nombre}' ya está registrado como "
                    f"{anterior.tipo_aporte}, no como {data.tipo_aporte}. "
                    "Un concepto no cambia de tipo de aporte: si es un concepto "
                    "distinto, usá otro nombre."
                ),
            )

        if data.fecha_vigencia_inicio <= anterior.fecha_vigencia_inicio:
            # Sin este chequeo el cierre calcularía fecha_vigencia_fin <=
            # fecha_vigencia_inicio y violaría chk_parametro_fechas: el usuario
            # recibiría un IntegrityError como 500 en vez de un 400 legible.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"La nueva tasa de '{data.nombre}' debe empezar después del "
                    f"{anterior.fecha_vigencia_inicio.isoformat()}, que es cuando "
                    "empieza la tasa que reemplaza."
                ),
            )

        if (
            anterior.fecha_vigencia_fin is not None
            and data.fecha_vigencia_inicio <= anterior.fecha_vigencia_fin
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"La nueva tasa de '{data.nombre}' se solapa con la anterior, "
                    f"que rige hasta el {anterior.fecha_vigencia_fin.isoformat()}."
                ),
            )

    parametro = ParametroImpuesto(
        nombre=data.nombre,
        tipo_aporte=data.tipo_aporte,
        porcentaje=data.porcentaje,
        fecha_vigencia_inicio=data.fecha_vigencia_inicio,
        fecha_vigencia_fin=data.fecha_vigencia_fin,
        descripcion=data.descripcion
    )

    if anterior is not None and anterior.fecha_vigencia_fin is None:
        # Un día antes, no el mismo día: tanto get_parametro_vigente como la
        # vista v_saldo_impuestos_planilla filtran `fecha_vigencia_fin >= fecha`
        # (inclusive), así que cerrar en la misma fecha dejaría un día con las
        # dos tasas vigentes.
        anterior.fecha_vigencia_fin = data.fecha_vigencia_inicio - timedelta(days=1)

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


def get_all_parametros_impuesto(db: Session) -> List[ParametroImpuesto]:
    """
    Todas las tasas registradas, vigentes e históricas.

    La pantalla de impuestos necesita vigentes E historial de todos los
    conceptos en una sola carga. Armarlo con get_all_parametros_vigentes() más
    un get_historial_parametro() por concepto tiene un agujero: un concepto
    cuya vigencia se cerró y nunca se reemplazó no aparece entre los vigentes,
    así que su historial nunca se pediría y el concepto desaparecería.
    """
    return db.query(ParametroImpuesto).order_by(
        ParametroImpuesto.nombre.asc(),
        ParametroImpuesto.fecha_vigencia_inicio.desc(),
    ).all()


def get_all_parametros_vigentes(db: Session) -> List[ParametroImpuesto]:
    """
    Obtiene todos los parámetros vigentes actualmente.

    Retorna el último parámetro vigente de cada concepto.
    """
    hoy = date.today()

    # Desempata por fecha_vigencia_inicio, igual que get_parametro_vigente y que
    # la vista v_saldo_impuestos_planilla. Antes usaba MAX(id): con dos filas
    # vigentes del mismo concepto, este endpoint y la vista podían discrepar
    # sobre cuál tasa está rigiendo.
    subquery = db.query(
        ParametroImpuesto.nombre.label('nombre'),
        func.max(ParametroImpuesto.fecha_vigencia_inicio).label('max_inicio')
    ).filter(
        and_(
            ParametroImpuesto.fecha_vigencia_inicio <= hoy,
            or_(
                ParametroImpuesto.fecha_vigencia_fin.is_(None),
                ParametroImpuesto.fecha_vigencia_fin >= hoy
            )
        )
    ).group_by(ParametroImpuesto.nombre).subquery()

    return db.query(ParametroImpuesto).join(
        subquery,
        and_(
            ParametroImpuesto.nombre == subquery.c.nombre,
            ParametroImpuesto.fecha_vigencia_inicio == subquery.c.max_inicio,
        )
    ).order_by(ParametroImpuesto.nombre.asc()).all()
