"""
Modelos Vacacion y DetalleVacacion - Gestión de saldo vacacional en horas según LGT Art. 44.
Sistema basado en horas (no días) para máxima precisión y cumplimiento legal.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, TYPE_CHECKING, List
from sqlalchemy import (
    String, Integer, ForeignKey, Numeric, Date, Text,
    UniqueConstraint, Computed, Enum as SQLEnum
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.base import Base

if TYPE_CHECKING:
    from app.features.employees.empleado.models import Empleado
    from app.features.attendance.justificacion.models import JustificacionAusencia


# --- ENUMs ---
class TipoVacacionEnum(str, enum.Enum):
    """
    Tipo de vacación según goce de haber.

    - goce_de_haber: El empleado recibe su salario normal (descuenta de horas_goce_haber)
    - sin_goce_de_haber: El empleado NO recibe salario (descuenta de horas_sin_goce_haber)
    - licencia_accidente: Licencia médica vinculada con justificacion_ausencia
    """
    goce_de_haber = "goce_de_haber"
    sin_goce_de_haber = "sin_goce_de_haber"
    licencia_accidente = "licencia_accidente"


class EstadoDetalleVacacionEnum(str, enum.Enum):
    """
    Estado del ciclo de vida de una solicitud de vacación.

    - solicitado: Empleado hizo la solicitud, esperando aprobación
    - aprobado: Supervisor/RRHH aprobó, reserva las horas
    - tomado: Vacación ejecutada, horas descontadas definitivamente
    - rechazado: Supervisor/RRHH rechazó, libera reserva
    - cancelado: Empleado canceló antes de la fecha, libera reserva
    """
    solicitado = "solicitado"
    aprobado = "aprobado"
    tomado = "tomado"
    rechazado = "rechazado"
    cancelado = "cancelado"


class Vacacion(Base):
    """
    Tabla: rrhh.vacacion

    Saldo vacacional anual por empleado EN HORAS.

    Reglas de negocio (LGT Art. 44):
    - < 1 año de antigüedad: 0 horas
    - 1-5 años: 120 horas (15 días × 8h)
    - 5-10 años: 160 horas (20 días × 8h)
    - 10+ años: 240 horas (30 días × 8h)

    horas_correspondientes se calcula automáticamente al crear el registro
    usando la función fn_horas_vacacion_lgt(fecha_ingreso, gestion).

    Las horas pueden aumentar por:
    - Feriados trabajados (+ 8h por feriado)
    - Transfers de beneficio_cumpleanos no usado (+ 4h)

    horas_pendientes es una columna GENERATED ALWAYS AS (horas_correspondientes - horas_tomadas) STORED.

    Constraint UNIQUE: (id_empleado, gestion) - un registro por empleado por año.
    """

    __tablename__ = "vacacion"
    __table_args__ = (
        UniqueConstraint('id_empleado', 'gestion', name='uq_vacacion_empleado_gestion'),
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

    horas_correspondientes: Mapped[Decimal] = mapped_column(
        Numeric(6, 1),
        nullable=False,
        default=Decimal("0.0"),
        comment="Horas totales asignadas (LGT + feriados trabajados + cumpleaños transferido)"
    )

    horas_goce_haber: Mapped[Decimal] = mapped_column(
        Numeric(6, 1),
        nullable=False,
        default=Decimal("0.0"),
        comment="Horas disponibles con pago de salario"
    )

    horas_sin_goce_haber: Mapped[Decimal] = mapped_column(
        Numeric(6, 1),
        nullable=False,
        default=Decimal("0.0"),
        comment="Horas disponibles sin pago de salario"
    )

    horas_tomadas: Mapped[Decimal] = mapped_column(
        Numeric(6, 1),
        nullable=False,
        default=Decimal("0.0"),
        comment="Total de horas consumidas"
    )

    horas_pendientes: Mapped[Decimal] = mapped_column(
        Numeric(6, 1),
        Computed("horas_correspondientes - horas_tomadas", persisted=True),
        nullable=False,
        comment="Columna generada: horas_correspondientes - horas_tomadas"
    )

    observacion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Auditoría ---
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now, nullable=False
    )

    # --- Relaciones ---
    empleado: Mapped["Empleado"] = relationship(
        "Empleado",
        foreign_keys=[id_empleado],
        back_populates="vacaciones",
        lazy="select"
    )

    detalles: Mapped[List["DetalleVacacion"]] = relationship(
        "DetalleVacacion",
        back_populates="vacacion",
        cascade="all, delete-orphan",
        lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<Vacacion(id={self.id}, empleado_id={self.id_empleado}, "
            f"gestion={self.gestion}, horas_pendientes={self.horas_pendientes})>"
        )


class DetalleVacacion(Base):
    """
    Tabla: rrhh.detalle_vacacion

    Solicitudes individuales de uso de vacaciones.

    Ciclo de vida:
    1. solicitado: Empleado envía solicitud
    2. aprobado: Supervisor/RRHH aprueba, reserva las horas
    3. tomado: Vacación ejecutada, horas se descuentan definitivamente de vacacion.horas_tomadas

    Estados alternativos:
    - rechazado: Supervisor rechaza, libera reserva
    - cancelado: Empleado cancela antes de la fecha

    Cuando estado cambia a 'tomado', el backend debe:
    1. Sumar horas_habiles a vacacion.horas_tomadas
    2. Restar horas_habiles de vacacion.horas_goce_haber o vacacion.horas_sin_goce_haber
       según tipo_vacacion

    tipo_vacacion='licencia_accidente' vincula una licencia médica (id_justificacion)
    con el saldo vacacional, solo si el empleado y RRHH deciden usar ese saldo.
    """

    __tablename__ = "detalle_vacacion"
    __table_args__ = {"schema": "rrhh"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    id_vacacion: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rrhh.vacacion.id", ondelete="CASCADE"),
        nullable=False
    )

    id_justificacion: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("rrhh.justificacion_ausencia.id", ondelete="SET NULL"),
        nullable=True,
        comment="Solo se usa cuando tipo_vacacion=licencia_accidente"
    )

    fecha_inicio: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Primer día de vacaciones"
    )

    fecha_fin: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Último día de vacaciones"
    )

    horas_habiles: Mapped[Decimal] = mapped_column(
        Numeric(6, 1),
        nullable=False,
        comment="Horas hábiles de vacación (calculadas por backend)"
    )

    tipo_vacacion: Mapped[TipoVacacionEnum] = mapped_column(
        SQLEnum(
            TipoVacacionEnum,
            name="tipo_vacacion_enum",
            create_constraint=True,
            native_enum=True,
            schema="rrhh",
        ),
        nullable=False,
        default=TipoVacacionEnum.goce_de_haber
    )

    estado: Mapped[EstadoDetalleVacacionEnum] = mapped_column(
        SQLEnum(
            EstadoDetalleVacacionEnum,
            name="estado_detalle_vacacion_enum",
            create_constraint=True,
            native_enum=True,
            schema="rrhh",
        ),
        nullable=False,
        default=EstadoDetalleVacacionEnum.solicitado
    )

    id_aprobado_por: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("rrhh.empleado.id", ondelete="SET NULL"),
        nullable=True,
        comment="ID del empleado que aprobó/rechazó"
    )

    observacion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # --- Auditoría ---
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now, nullable=False
    )

    # --- Relaciones ---
    vacacion: Mapped["Vacacion"] = relationship(
        "Vacacion",
        back_populates="detalles",
        lazy="select"
    )

    justificacion: Mapped[Optional["JustificacionAusencia"]] = relationship(
        "JustificacionAusencia",
        back_populates="detalles_vacacion",
        lazy="select"
    )

    aprobador: Mapped[Optional["Empleado"]] = relationship(
        "Empleado",
        foreign_keys=[id_aprobado_por],
        lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<DetalleVacacion(id={self.id}, vacacion_id={self.id_vacacion}, "
            f"fecha_inicio={self.fecha_inicio}, horas={self.horas_habiles}, estado={self.estado})>"
        )
