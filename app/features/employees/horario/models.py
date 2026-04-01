"""
Modelos Horario y AsignacionHorario.
Define turnos laborales y su asignación temporal a empleados.
"""

from datetime import datetime, time, date
from typing import Optional, TYPE_CHECKING, List
from sqlalchemy import String, Boolean, Integer, ForeignKey, Numeric, Time, Date, Enum as SQLEnum, JSON, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.base import Base

if TYPE_CHECKING:
    from app.features.employees.empleado.models import Empleado


# --- ENUMs ---
class TipoJornadaEnum(str, enum.Enum):
    """
    Tipo de jornada laboral.
    - continua: Sin pausa formal de almuerzo (entrada-salida directa)
    - discontinua: Con pausa de almuerzo (no se registra biométricamente)
    """
    continua = "continua"
    discontinua = "discontinua"


class Horario(Base):
    """
    Tabla: rrhh.horario
    Define los turnos laborales disponibles en la empresa.

    Campos clave:
    - hora_entrada / hora_salida: Horario oficial del turno
    - tolerancia_minutos: Minutos de gracia antes de considerar retraso
    - jornada_semanal_horas: Total de horas semanales (máx 48h según LGT)
    - dias_laborables: Array JSON con días de la semana [1=Lunes, 7=Domingo]
    - tipo_jornada: continua | discontinua
    """

    __tablename__ = "horario"

    # --- Columnas ---
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Ej: 'Turno Oficina', 'Turno Noche'"
    )
    hora_entrada: Mapped[time] = mapped_column(Time, nullable=False)
    hora_salida: Mapped[time] = mapped_column(Time, nullable=False)
    tolerancia_minutos: Mapped[int] = mapped_column(
        Integer,
        default=5,
        nullable=False,
        comment="Minutos de gracia para considerar retraso"
    )
    jornada_semanal_horas: Mapped[float] = mapped_column(
        Numeric(4, 1),
        default=40.0,
        nullable=False,
        comment="Total horas semanales (máx 48 según LGT Art. 46)"
    )
    dias_laborables: Mapped[dict] = mapped_column(
        JSON,
        default=lambda: [1, 2, 3, 4, 5],  # Lunes a Viernes por defecto
        nullable=False,
        comment="Array de días laborables [1=Lun, 2=Mar, ..., 7=Dom]"
    )
    tipo_jornada: Mapped[TipoJornadaEnum] = mapped_column(
        SQLEnum(TipoJornadaEnum, name="tipo_jornada_enum", create_constraint=True, native_enum=False),
        default=TipoJornadaEnum.continua,
        nullable=False
    )
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now, nullable=False
    )

    # --- Relaciones ---
    asignaciones: Mapped[List["AsignacionHorario"]] = relationship(back_populates="horario")

    def __repr__(self) -> str:
        return f"<Horario(id={self.id}, nombre='{self.nombre}', entrada={self.hora_entrada}, salida={self.hora_salida})>"


class AsignacionHorario(Base):
    """
    Tabla: rrhh.asignacion_horario
    Asigna un horario específico a un empleado con vigencia temporal.

    Lógica de negocio:
    - Un empleado puede tener múltiples asignaciones en el tiempo
    - Solo UNA asignación puede estar activa (es_activo=TRUE) por fecha
    - fecha_fin=NULL indica asignación vigente indefinidamente
    - No puede haber solapamiento de fechas para el mismo empleado
    """

    __tablename__ = "asignacion_horario"

    # --- Columnas ---
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    id_empleado: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("empleado.id", ondelete="CASCADE"),
        nullable=False
    )
    id_horario: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("horario.id", ondelete="RESTRICT"),
        nullable=False
    )
    fecha_inicio: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_fin: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="NULL = asignación vigente indefinidamente"
    )
    es_activo: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        comment="Solo una asignación activa por empleado en una fecha"
    )
    observacion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now, nullable=False
    )

    # --- Relaciones ---
    empleado: Mapped["Empleado"] = relationship(back_populates="asignaciones_horario")
    horario: Mapped["Horario"] = relationship(back_populates="asignaciones")

    def __repr__(self) -> str:
        return f"<AsignacionHorario(id={self.id}, empleado_id={self.id_empleado}, horario_id={self.id_horario}, vigente={self.fecha_inicio} - {self.fecha_fin})>"
