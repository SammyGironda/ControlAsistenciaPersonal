"""
Modelo Contrato - Historial contractual del empleado.
Soporta contratos indefinidos y plazo fijo según legislación boliviana.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, TYPE_CHECKING, List
from sqlalchemy import String, Integer, ForeignKey, Numeric, Date, Text, Enum as SQLEnum, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.base import Base

if TYPE_CHECKING:
    from app.features.employees.empleado.models import Empleado
    from app.features.contracts.ajuste_salarial.models import DecretoIncrementoSalarial, AjusteSalarial


# --- ENUMs ---
class TipoContratoEnum(str, enum.Enum):
    """
    Tipo de contrato laboral en Bolivia.
    - indefinido: Sin fecha fin. Incrementos por decreto se registran en ajuste_salarial.
    - plazo_fijo: Con fecha fin. Al renovar se crea NUEVO contrato con salario ya incrementado.
    """
    indefinido = "indefinido"
    plazo_fijo = "plazo_fijo"


class EstadoContratoEnum(str, enum.Enum):
    """Estado del contrato."""
    activo = "activo"
    vencido = "vencido"
    rescindido = "rescindido"


class Contrato(Base):
    """
    Tabla: rrhh.contrato
    Historial contractual completo del empleado.
    
    Lógica de negocio:
    - Contrato indefinido: fecha_fin=NULL. Incrementos salariales anuales se registran en ajuste_salarial.
    - Contrato plazo_fijo: fecha_fin obligatoria. Al renovar se crea NUEVO contrato (no ajuste).
    - Solo un contrato activo por empleado en un momento dado.
    - id_decreto_origen registra si el contrato nació de una renovación por decreto.
    """
    
    __tablename__ = "contrato"
    
    # --- Columnas principales ---
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_empleado: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("empleado.id", ondelete="CASCADE"),
        nullable=False
    )
    tipo_contrato: Mapped[TipoContratoEnum] = mapped_column(
        SQLEnum(TipoContratoEnum, name="tipo_contrato_enum", create_constraint=True, native_enum=False),
        nullable=False
    )
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_fin: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="NULL = contrato indefinido"
    )
    salario_base: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Salario inicial del contrato en Bs."
    )
    estado: Mapped[EstadoContratoEnum] = mapped_column(
        SQLEnum(EstadoContratoEnum, name="estado_contrato_enum", create_constraint=True, native_enum=False),
        default=EstadoContratoEnum.activo,
        nullable=False
    )
    
    # --- Relación con decreto (opcional) ---
    id_decreto_origen: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("decreto_incremento_salarial.id", ondelete="SET NULL"),
        nullable=True,
        comment="Referencia al decreto si el contrato nació de una renovación por decreto"
    )
    
    # --- Observaciones ---
    observacion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # --- Auditoría ---
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now, nullable=False
    )
    
    # --- Constraints ---
    __table_args__ = (
        CheckConstraint(
            "fecha_fin IS NULL OR fecha_fin > fecha_inicio",
            name="chk_contrato_fechas"
        ),
        CheckConstraint(
            "tipo_contrato = 'indefinido' OR fecha_fin IS NOT NULL",
            name="chk_plazo_fijo_fecha_fin"
        ),
        CheckConstraint(
            "salario_base > 0",
            name="chk_contrato_salario"
        ),
    )
    
    # --- Relaciones ---
    empleado: Mapped["Empleado"] = relationship("Empleado", back_populates="contratos")
    decreto_origen: Mapped[Optional["DecretoIncrementoSalarial"]] = relationship(
        "DecretoIncrementoSalarial",
        back_populates="contratos_originados"
    )
    ajustes_salariales: Mapped[List["AjusteSalarial"]] = relationship(
        "AjusteSalarial",
        back_populates="contrato",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<Contrato(id={self.id}, empleado_id={self.id_empleado}, tipo='{self.tipo_contrato}', estado='{self.estado}')>"
    
    @property
    def es_vigente(self) -> bool:
        """Retorna True si el contrato está activo y no ha vencido."""
        if self.estado != EstadoContratoEnum.activo:
            return False
        if self.fecha_fin is None:
            return True
        return date.today() <= self.fecha_fin
