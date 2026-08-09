"""
Modelo CompensacionHorasExtra - Registro puntual de horas extra que se
compensan como saldo vacacional (goce de haber) de la gestión correspondiente.

Tabla creada en la migración 122bc6566cae
(semana9_horario_personalizado_compensacion_horas_extra), junto con el
trigger de Neon `trg_compensacion_horas_extra_a_vacacion`: al insertar una
fila aquí, ese trigger suma `horas` a `vacacion.horas_correspondientes` y
`vacacion.horas_goce_haber` de la gestión indicada (creando el registro de
`Vacacion` si todavía no existe para esa gestión). La suma ocurre enteramente
en la base de datos; este modelo solo permite insertar la fila que la dispara.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Integer, ForeignKey, Date, Numeric, Text, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.features.employees.empleado.models import Empleado


class CompensacionHorasExtra(Base):
    """
    Tabla: rrhh.compensacion_horas_extra

    Un registro por empleado por fecha (UNIQUE). Hoy se usa para acreditar
    8h de vacación cuando un empleado trabaja un día que sería descanso o
    feriado (p. ej. un viaje_trabajo aprobado que cae sobre un fin de
    semana) — ver `justificacion/services.py::_aplicar_viaje_trabajo_aprobado`.
    """

    __tablename__ = "compensacion_horas_extra"
    __table_args__ = (
        UniqueConstraint("id_empleado", "fecha", name="uq_compensacion_horas_extra_empleado_fecha"),
        CheckConstraint("horas > 0", name="ck_compensacion_horas_extra_horas_positivas"),
        {"schema": "rrhh"},
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    id_empleado: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rrhh.empleado.id", ondelete="CASCADE"),
        nullable=False,
    )

    fecha: Mapped[date] = mapped_column(Date, nullable=False)

    horas: Mapped[Decimal] = mapped_column(
        Numeric(4, 1),
        nullable=False,
        default=Decimal("8.0"),
        comment="Horas a acreditar en vacacion.horas_goce_haber vía trigger",
    )

    motivo: Mapped[str] = mapped_column(Text, nullable=False)

    gestion: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Gestión (año) de vacacion a la que se acredita la compensación",
    )

    id_registrado_por: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("rrhh.empleado.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(default=datetime.now, nullable=False)

    # --- Relaciones ---
    empleado: Mapped["Empleado"] = relationship(
        "Empleado",
        foreign_keys=[id_empleado],
        lazy="select",
    )

    registrado_por: Mapped[Optional["Empleado"]] = relationship(
        "Empleado",
        foreign_keys=[id_registrado_por],
        lazy="select",
    )

    def __repr__(self) -> str:
        return (
            f"<CompensacionHorasExtra(id={self.id}, empleado_id={self.id_empleado}, "
            f"fecha={self.fecha}, horas={self.horas})>"
        )
