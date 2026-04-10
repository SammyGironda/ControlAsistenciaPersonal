"""
Modelo BeneficioCumpleanos - Medio día libre por cumpleaños (4 horas).
Gestión anual mediante LGT Bolivia. Se crea automáticamente por worker.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Integer, Boolean, ForeignKey, UniqueConstraint, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.features.employees.empleado.models import Empleado
    from app.features.attendance.justificacion.models import JustificacionAusencia


class BeneficioCumpleanos(Base):
    """
    Tabla: rrhh.beneficio_cumpleanos

    Medio día libre (4 horas) anual por cumpleaños del empleado.

    Reglas de negocio:
    - El worker automático crea el registro el día del cumpleaños del empleado
    - Un beneficio por empleado por gestión (UNIQUE constraint)
    - Si al 31/dic no fue utilizado (fue_utilizado=FALSE):
      * Se transfieren 4h a vacacion.horas_goce_haber
      * Se marca transferido_a_vacacion=TRUE
    - Si el empleado lo usa, se vincula con una justificacion_ausencia

    Constraint UNIQUE garantiza (id_empleado, gestion).
    """

    __tablename__ = "beneficio_cumpleanos"
    __table_args__ = (
        UniqueConstraint('id_empleado', 'gestion', name='uq_beneficio_empleado_gestion'),
        {"schema": "rrhh"}
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    id_empleado: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rrhh.empleado.id", ondelete="CASCADE"),
        nullable=False
    )

    gestion: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Año de la gestión (ej: 2026)"
    )

    fue_utilizado: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="TRUE si el empleado usó el beneficio"
    )

    fecha_uso: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="Fecha/hora en que se usó el beneficio"
    )

    id_justificacion: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("rrhh.justificacion_ausencia.id", ondelete="SET NULL"),
        nullable=True,
        comment="FK a justificacion_ausencia si el empleado solicitó usar el beneficio"
    )

    transferido_a_vacacion: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="TRUE si las 4h ya fueron sumadas al saldo vacacional"
    )

    # --- Auditoría ---
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now, nullable=False
    )

    # --- Relaciones ---
    empleado: Mapped["Empleado"] = relationship(
        "Empleado",
        foreign_keys=[id_empleado],
        back_populates="beneficios_cumpleanos",
        lazy="select"
    )

    justificacion: Mapped[Optional["JustificacionAusencia"]] = relationship(
        "JustificacionAusencia",
        foreign_keys=[id_justificacion],
        back_populates="beneficios_cumpleanos",
        lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<BeneficioCumpleanos(id={self.id}, empleado_id={self.id_empleado}, "
            f"gestion={self.gestion}, fue_utilizado={self.fue_utilizado})>"
        )
