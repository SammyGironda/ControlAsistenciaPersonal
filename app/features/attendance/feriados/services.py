"""
Servicios de negocio para DiaFestivo.
CRUD completo con lógica de validación y consultas especializadas.
"""

from datetime import date
from typing import List, Optional
from sqlalchemy import and_, extract, or_
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.features.attendance.feriados.models import DiaFestivo, AmbitoFestivoEnum
from app.features.attendance.feriados.schemas import DiaFestivoCreate, DiaFestivoUpdate


def crear_dia_festivo(db: Session, data: DiaFestivoCreate) -> DiaFestivo:
    """
    Crea un nuevo feriado.
    Valida que no exista un feriado con la misma (fecha, ambito, codigo_departamento).
    """
    existente = db.query(DiaFestivo).filter(
        DiaFestivo.fecha == data.fecha,
        DiaFestivo.ambito == data.ambito,
        DiaFestivo.codigo_departamento == data.codigo_departamento,
    ).first()

    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Ya existe un feriado {data.ambito} en la fecha {data.fecha}"
        )

    # Crear el feriado
    nuevo_feriado = DiaFestivo(
        fecha=data.fecha,
        descripcion=data.descripcion,
        ambito=data.ambito,
        codigo_departamento=data.codigo_departamento,
        activo=data.activo
    )

    db.add(nuevo_feriado)
    db.commit()
    db.refresh(nuevo_feriado)

    return nuevo_feriado


def obtener_dia_festivo(db: Session, id: int) -> DiaFestivo:
    """Obtiene un feriado por ID."""
    feriado = db.query(DiaFestivo).filter(DiaFestivo.id == id).first()

    if not feriado:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Feriado con ID {id} no encontrado"
        )

    return feriado


def listar_dias_festivos(
    db: Session,
    activo: Optional[bool] = None,
    ambito: Optional[AmbitoFestivoEnum] = None,
    anio: Optional[int] = None,
    codigo_departamento: Optional[str] = None,
    skip: int = 0,
    limit: int = 100
) -> List[DiaFestivo]:
    """
    Lista feriados con filtros opcionales.

    Args:
        activo: Filtrar por estado activo/inactivo
        ambito: Filtrar por NACIONAL o DEPARTAMENTAL
        anio: Filtrar por año
        codigo_departamento: Filtrar por código de departamento
    """
    query = db.query(DiaFestivo)

    # Aplicar filtros
    if activo is not None:
        query = query.filter(DiaFestivo.activo == activo)

    if ambito:
        query = query.filter(DiaFestivo.ambito == ambito)

    if anio:
        query = query.filter(extract("year", DiaFestivo.fecha) == anio)

    if codigo_departamento:
        query = query.filter(DiaFestivo.codigo_departamento == codigo_departamento)

    return query.order_by(DiaFestivo.fecha.desc()).offset(skip).limit(limit).all()


def obtener_feriados_aplicables(
    db: Session,
    fecha: date,
    codigo_departamento: str
) -> List[DiaFestivo]:
    """
    Obtiene feriados aplicables a una fecha y departamento específico.

    Retorna feriados NACIONALES o DEPARTAMENTALES que aplican al departamento dado.
    Esta función es usada por el worker de asistencia_diaria.
    """
    return db.query(DiaFestivo).filter(
        DiaFestivo.fecha == fecha,
        DiaFestivo.activo.is_(True),
        or_(
            DiaFestivo.ambito == AmbitoFestivoEnum.NACIONAL,
            and_(
                DiaFestivo.ambito == AmbitoFestivoEnum.DEPARTAMENTAL,
                DiaFestivo.codigo_departamento == codigo_departamento,
            ),
        ),
    ).all()


def actualizar_dia_festivo(
    db: Session,
    id: int,
    data: DiaFestivoUpdate
) -> DiaFestivo:
    """Actualiza un feriado existente."""
    feriado = obtener_dia_festivo(db, id)

    # Aplicar cambios
    if data.fecha is not None:
        feriado.fecha = data.fecha
    if data.descripcion is not None:
        feriado.descripcion = data.descripcion
    if data.ambito is not None:
        feriado.ambito = data.ambito
    if data.codigo_departamento is not None:
        feriado.codigo_departamento = data.codigo_departamento
    if data.activo is not None:
        feriado.activo = data.activo

    db.commit()
    db.refresh(feriado)

    return feriado


def eliminar_dia_festivo(db: Session, id: int) -> DiaFestivo:
    """
    Soft delete: marca el feriado como inactivo.
    Los feriados históricos deben conservarse para auditoría.
    """
    feriado = obtener_dia_festivo(db, id)
    feriado.activo = False

    db.commit()
    db.refresh(feriado)

    return feriado


def eliminar_permanente(db: Session, id: int) -> None:
    """
    Hard delete: Elimina permanentemente el feriado.
    Solo usar si el feriado fue creado por error y no hay datos relacionados.
    """
    feriado = obtener_dia_festivo(db, id)

    db.delete(feriado)
    db.commit()
