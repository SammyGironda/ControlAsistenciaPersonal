"""
Modelo HorarioPersonalizadoEmpleado.
Override 1:1 opcional del horario estándar (asignacion_horario) para un
empleado puntual: tolerancia y hora de entrada propias, y/o salida
flexible sin hora fija. Tabla creada en la migración 122bc6566cae
(semana9_horario_personalizado_compensacion_horas_extra).
"""

from datetime import datetime, time
from typing import Optional, TYPE_CHECKING
from sqlalchemy import Boolean, Integer, ForeignKey, Time, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.features.employees.empleado.models import Empleado


class HorarioPersonalizadoEmpleado(Base):
    """
    Tabla: rrhh.horario_personalizado_empleado

    Un registro por empleado como máximo (UNIQUE en id_empleado). Si
    `activo=TRUE` sus campos reemplazan al horario general asignado
    (rrhh.asignacion_horario -> rrhh.horario) al calcular minutos_retraso
    en asistencia_diaria. Si `activo=FALSE`, el empleado vuelve a regirse
    por el horario general sin perder el historial del override.

    Campos clave:
    - tolerancia_minutos / hora_entrada: reemplazan a los del horario
      general para el cálculo de minutos_retraso (afecta descuento salarial).
    - hora_salida: solo referencial para minutos_trabajados/estadísticas,
      nunca se usa para calcular horas_extra pagables.
    - salida_flexible: si TRUE, no hay hora de salida fija esperada.
    """

    __tablename__ = "horario_personalizado_empleado"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_empleado: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("empleado.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    tolerancia_minutos: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Minutos de gracia propios del empleado (reemplaza al del horario general)",
    )
    hora_entrada: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
        comment="Hora de entrada propia del empleado (reemplaza a la del horario general)",
    )
    hora_salida: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
        comment="Solo referencial para estadísticas; nunca se usa para horas_extra pagables",
    )
    salida_flexible: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    observacion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now, nullable=False
    )

    # --- Relaciones ---
    empleado: Mapped["Empleado"] = relationship(back_populates="horario_personalizado")

    def __repr__(self) -> str:
        return (
            f"<HorarioPersonalizadoEmpleado(id={self.id}, empleado_id={self.id_empleado}, "
            f"activo={self.activo})>"
        )
