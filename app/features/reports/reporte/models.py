"""
Modelo Reporte - Bitacora de reportes generados por el sistema.
Semana 8: reportes XLSX y PDF para asistencia, planilla y vacaciones.
"""

from datetime import date, datetime
from typing import Optional, TYPE_CHECKING
import enum

from sqlalchemy import String, Integer, Date, DateTime, Boolean, ForeignKey, CheckConstraint, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.features.auth.usuario.models import Usuario
    from app.features.employees.departamento.models import Departamento
    from app.features.employees.empleado.models import Empleado


class TipoReporteEnum(str, enum.Enum):
    """Tipos de reporte soportados en el MVP."""

    asistencia_mensual = "asistencia_mensual"
    planilla = "planilla"
    vacaciones = "vacaciones"
    individual = "individual"


class FormatoReporteEnum(str, enum.Enum):
    """Formatos de exportacion de reporte."""

    PDF = "PDF"
    XLSX = "XLSX"
    CSV = "CSV"


class Reporte(Base):
    """
    Tabla: rrhh.reporte

    Registra cada archivo exportado por el modulo de reportes.
    Incluye filtros aplicados, periodo y ruta de almacenamiento.
    """

    __tablename__ = "reporte"
    __table_args__ = (
        CheckConstraint("periodo_fin >= periodo_inicio", name="chk_reporte_periodo"),
        {"schema": "rrhh"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    nombre: Mapped[str] = mapped_column(String(100), nullable=False)

    tipo_reporte: Mapped[TipoReporteEnum] = mapped_column(
        SQLEnum(
            TipoReporteEnum,
            name="tipo_reporte_enum",
            create_constraint=True,
            native_enum=False,
        ),
        nullable=False,
    )

    id_generado_por: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("rrhh.usuario.id", ondelete="SET NULL"),
        nullable=True,
    )

    id_departamento: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("rrhh.departamento.id", ondelete="SET NULL"),
        nullable=True,
    )

    id_empleado: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("rrhh.empleado.id", ondelete="SET NULL"),
        nullable=True,
    )

    periodo_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    periodo_fin: Mapped[date] = mapped_column(Date, nullable=False)

    ruta_archivo: Mapped[str] = mapped_column(String(255), nullable=False)

    formato: Mapped[FormatoReporteEnum] = mapped_column(
        SQLEnum(
            FormatoReporteEnum,
            name="formato_reporte_enum",
            create_constraint=True,
            native_enum=False,
        ),
        nullable=False,
    )

    fecha_generacion: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    generado_por: Mapped[Optional["Usuario"]] = relationship("Usuario", lazy="select")
    departamento: Mapped[Optional["Departamento"]] = relationship("Departamento", lazy="select")
    empleado: Mapped[Optional["Empleado"]] = relationship("Empleado", lazy="select")

    def __repr__(self) -> str:
        return (
            f"<Reporte(id={self.id}, tipo={self.tipo_reporte}, formato={self.formato}, "
            f"fecha_generacion={self.fecha_generacion})>"
        )
