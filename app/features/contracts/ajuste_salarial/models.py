"""
Modelos para ajustes salariales, decretos e impuestos.
Historial completo de cambios salariales y parámetros tributarios.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, TYPE_CHECKING, List
from sqlalchemy import (
    String, Integer, ForeignKey, Numeric, Date, Text, 
    Enum as SQLEnum, CheckConstraint, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.base import Base

if TYPE_CHECKING:
    from app.features.employees.empleado.models import Empleado
    from app.features.contracts.contrato.models import Contrato


# --- ENUMs ---
class MotivoAjusteEnum(str, enum.Enum):
    """
    Motivo del ajuste salarial.
    - decreto_anual: Incremento por decreto supremo del gobierno (solo para contratos indefinidos).
    - renovacion: Renovación de contrato plazo_fijo con nuevo salario.
    - merito: Incremento por desempeño destacado.
    - promocion: Incremento por cambio de cargo.
    """
    decreto_anual = "decreto_anual"
    renovacion = "renovacion"
    merito = "merito"
    promocion = "promocion"


# ============================================================
# 1. DECRETO INCREMENTO SALARIAL
# ============================================================
class DecretoIncrementoSalarial(Base):
    """
    Tabla: rrhh.decreto_incremento_salarial
    Cabecera de decretos supremos anuales de incremento salarial.
    Los porcentajes por tramo están en CondicionDecreto.
    
    Ejemplo: DS 4984 / 2024 establece SMN 2500 Bs. vigente desde 1/may/2024
    con tramos diferenciados según salario actual del empleado.
    """
    
    __tablename__ = "decreto_incremento_salarial"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    anio: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        unique=True,
        comment="Año del decreto (ej: 2024)"
    )
    nuevo_smn: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Nuevo Salario Mínimo Nacional en Bs."
    )
    fecha_vigencia: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Fecha desde la cual rige el decreto"
    )
    referencia_decreto: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Ej: 'DS 4984' o 'DS 5001' - Referencia oficial del Decreto Supremo"
    )
    
    # --- Auditoría ---
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now, nullable=False
    )
    
    # --- Relaciones ---
    condiciones: Mapped[List["CondicionDecreto"]] = relationship(
        "CondicionDecreto",
        back_populates="decreto",
        cascade="all, delete-orphan",
        order_by="CondicionDecreto.orden"
    )
    contratos_originados: Mapped[List["Contrato"]] = relationship(
        "Contrato",
        back_populates="decreto_origen"
    )
    
    def __repr__(self) -> str:
        return f"<DecretoIncrementoSalarial(id={self.id}, anio={self.anio}, ref='{self.referencia_decreto}')>"


# ============================================================
# 2. CONDICION DECRETO
# ============================================================
class CondicionDecreto(Base):
    """
    Tabla: rrhh.condicion_decreto
    Tramos salariales del decreto con porcentajes diferenciados.
    
    Lógica:
    - NULL en salario_desde/hasta = sin límite
    - ORDER BY orden para resolver solapamientos
    - El backend toma el primer tramo coincidente (fn_porcentaje_incremento_decreto)
    
    Ejemplo DS 4984:
    - Orden 1: salario_desde=NULL, salario_hasta=2500 → 5%
    - Orden 2: salario_desde=2501, salario_hasta=5000 → 3%
    - Orden 3: salario_desde=5001, salario_hasta=NULL → 1%
    """
    
    __tablename__ = "condicion_decreto"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_decreto: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("decreto_incremento_salarial.id", ondelete="CASCADE"),
        nullable=False
    )
    orden: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Prioridad de evaluación (el backend toma el primer tramo coincidente)"
    )
    salario_desde: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="NULL = aplica desde cualquier salario (sin límite inferior)"
    )
    salario_hasta: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="NULL = aplica hasta cualquier salario (sin límite superior)"
    )
    porcentaje_incremento: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        comment="Porcentaje de incremento (ej: 5.00 = 5%)"
    )
    
    # --- Auditoría ---
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now, nullable=False
    )
    
    # --- Constraints ---
    __table_args__ = (
        CheckConstraint(
            "salario_desde IS NULL OR salario_hasta IS NULL OR salario_desde < salario_hasta",
            name="chk_condicion_decreto_salarios"
        ),
        CheckConstraint(
            "porcentaje_incremento >= 0",
            name="chk_condicion_decreto_porcentaje"
        ),
    )
    
    # --- Relaciones ---
    decreto: Mapped["DecretoIncrementoSalarial"] = relationship(
        "DecretoIncrementoSalarial",
        back_populates="condiciones"
    )
    ajustes_salariales: Mapped[List["AjusteSalarial"]] = relationship(
        "AjusteSalarial",
        back_populates="condicion_aplicada"
    )
    
    def __repr__(self) -> str:
        return f"<CondicionDecreto(id={self.id}, decreto_id={self.id_decreto}, orden={self.orden}, %={self.porcentaje_incremento})>"


# ============================================================
# 3. AJUSTE SALARIAL
# ============================================================
class AjusteSalarial(Base):
    """
    Tabla: rrhh.ajuste_salarial
    Trayectoria salarial completa del empleado.
    Cada cambio de salario genera un registro aquí.
    
    Trigger trg_sync_salario_empleado actualiza empleado.salario_base
    automáticamente al insertar si fecha_vigencia <= hoy.
    
    id_condicion_decreto registra exactamente qué tramo del decreto se aplicó (auditoría).
    """
    
    __tablename__ = "ajuste_salarial"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_empleado: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("empleado.id", ondelete="CASCADE"),
        nullable=False
    )
    id_contrato: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("contrato.id", ondelete="CASCADE"),
        nullable=False
    )
    id_condicion_decreto: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("condicion_decreto.id", ondelete="SET NULL"),
        nullable=True,
        comment="Si motivo=decreto_anual, registra qué tramo del decreto se aplicó"
    )
    salario_anterior: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False
    )
    salario_nuevo: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False
    )
    fecha_vigencia: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Fecha desde la cual rige el nuevo salario"
    )
    motivo: Mapped[MotivoAjusteEnum] = mapped_column(
        SQLEnum(MotivoAjusteEnum, name="motivo_ajuste_enum", create_constraint=True, native_enum=False),
        nullable=False
    )
    id_aprobado_por: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("empleado.id", ondelete="SET NULL"),
        nullable=True,
        comment="Empleado que aprobó el ajuste (ej: RRHH o supervisor)"
    )
    observacion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # --- Auditoría ---
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, nullable=False)
    
    # --- Constraints ---
    __table_args__ = (
        CheckConstraint(
            "salario_anterior <> salario_nuevo",
            name="chk_ajuste_salario_distinto"
        ),
        CheckConstraint(
            "salario_anterior > 0 AND salario_nuevo > 0",
            name="chk_ajuste_salarios_positivos"
        ),
    )
    

    # --- Relaciones ---
    empleado: Mapped["Empleado"] = relationship(
        "Empleado",
        foreign_keys=[id_empleado],
        back_populates="ajustes_salariales"
    )
    contrato: Mapped["Contrato"] = relationship(
        "Contrato",
        foreign_keys=[id_contrato],
        back_populates="ajustes_salariales"
    )
    condicion_aplicada: Mapped[Optional["CondicionDecreto"]] = relationship(
        "CondicionDecreto",
        foreign_keys=[id_condicion_decreto],
        back_populates="ajustes_salariales"
    )
    aprobado_por: Mapped[Optional["Empleado"]] = relationship(
        "Empleado",
        foreign_keys=[id_aprobado_por]
    )
    
    def __repr__(self) -> str:
        return f"<AjusteSalarial(id={self.id}, empleado_id={self.id_empleado}, {self.salario_anterior}→{self.salario_nuevo}, motivo='{self.motivo}')>"


# ============================================================
# 4. PARAMETRO IMPUESTO
# ============================================================
class ParametroImpuesto(Base):
    """
    Tabla: rrhh.parametro_impuesto
    Tasas vigentes por período de conceptos tributarios y aportes.
    
    Ejemplos:
    - RC_IVA (Impuesto al Valor Agregado): 13% vigente desde 1/ene/1992
    - AFP_LABORAL (Aporte trabajador): 12.71% (10% jubilación + 1.71% riesgo común + 1% solidario)
    - AFP_PATRONAL (Aporte empleador): 3% (riesgo profesional + vivienda + pro-vivienda)
    
    Historial: Al cambiar una tasa, se cierra el registro anterior (fecha_vigencia_fin)
    y se crea uno nuevo.
    """
    
    __tablename__ = "parametro_impuesto"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Nombre del concepto: RC_IVA, AFP_LABORAL, AFP_PATRONAL, etc."
    )
    porcentaje: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        comment="Porcentaje aplicable (ej: 13.00 = 13%)"
    )
    fecha_vigencia_inicio: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )
    fecha_vigencia_fin: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="NULL = vigente indefinidamente"
    )
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # --- Auditoría ---
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now, nullable=False
    )
    
    # --- Constraints ---
    __table_args__ = (
        CheckConstraint(
            "fecha_vigencia_fin IS NULL OR fecha_vigencia_fin > fecha_vigencia_inicio",
            name="chk_parametro_fechas"
        ),
        CheckConstraint(
            "porcentaje >= 0",
            name="chk_parametro_porcentaje"
        ),
    )
    
    def __repr__(self) -> str:
        return f"<ParametroImpuesto(id={self.id}, nombre='{self.nombre}', %={self.porcentaje}, vigente_desde={self.fecha_vigencia_inicio})>"
