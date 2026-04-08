"""
Modelo JustificacionAusencia - Solicitudes de permisos, licencias y vacaciones por horas.
Incluye flujo de aprobación y cálculo automático de horas.
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, ForeignKey, Boolean, Date, Time, Numeric, Text, DateTime, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.base import Base

if TYPE_CHECKING:
    from app.features.employees.empleado.models import Empleado
    from app.features.attendance.asistencia_diaria.models import AsistenciaDiaria
    from app.features.attendance.beneficio_cumpleanos.models import BeneficioCumpleanos
    # from app.features.attendance.vacaciones.models import DetalleVacacion  # Se activará después


# --- ENUMs ---
class TipoJustificacionEnum(str, enum.Enum):
    """
    Tipos de justificación de ausencia según normativa boliviana.

    - permiso_personal: Permiso común (descontable o no según política)
    - licencia_medica_accidente: Licencia por enfermedad o accidente (LGT Art. 32)
    - cumpleanos: Beneficio de medio día por cumpleaños (4h)
    - vacacion_por_horas: Consumo fraccionado de vacaciones (deducible del saldo)
    """
    permiso_personal = "permiso_personal"
    licencia_medica_accidente = "licencia_medica_accidente"
    cumpleanos = "cumpleanos"
    vacacion_por_horas = "vacacion_por_horas"


class TipoPermisoEnum(str, enum.Enum):
    """
    Duración del permiso.

    - dia_completo: Ausencia de jornada completa (8h)
    - por_horas: Ausencia por fracción de jornada
    """
    dia_completo = "dia_completo"
    por_horas = "por_horas"


class EstadoAprobacionEnum(str, enum.Enum):
    """
    Estado del flujo de aprobación.

    - pendiente: Solicitud enviada, esperando revisión
    - aprobado: Aprobado por supervisor/RRHH
    - rechazado: Rechazado por supervisor/RRHH
    """
    pendiente = "pendiente"
    aprobado = "aprobado"
    rechazado = "rechazado"


class JustificacionAusencia(Base):
    """
    Tabla: rrhh.justificacion_ausencia

    Solicitudes de permisos, licencias y uso de vacaciones por horas.

    Reglas de negocio:
    - Si es_por_horas=TRUE:
      * hora_inicio_permiso, hora_fin_permiso y total_horas_permiso son obligatorios
      * total_horas_permiso se calcula automáticamente en el backend
    - Si es_por_horas=FALSE:
      * Todas las columnas de hora deben ser NULL
    - tipo_justificacion='vacacion_por_horas' descuenta de vacacion.horas_goce_haber
    - tipo_justificacion='cumpleanos' vincula con beneficio_cumpleanos
    - Requiere aprobación de supervisor o RRHH

    Constraint CHECK valida coherencia de campos según es_por_horas.
    """

    __tablename__ = "justificacion_ausencia"
    __table_args__ = {"schema": "rrhh"}

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    id_empleado: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rrhh.empleado.id", ondelete="CASCADE"),
        nullable=False
    )

    fecha_inicio: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Primer día de la ausencia o permiso"
    )

    fecha_fin: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        comment="Último día de la ausencia o permiso (puede ser igual a fecha_inicio)"
    )

    tipo_justificacion: Mapped[TipoJustificacionEnum] = mapped_column(
        SQLEnum(TipoJustificacionEnum, name="tipo_justificacion_enum", create_constraint=True, native_enum=False),
        nullable=False
    )

    tipo_permiso: Mapped[TipoPermisoEnum] = mapped_column(
        SQLEnum(TipoPermisoEnum, name="tipo_permiso_enum", create_constraint=True, native_enum=False),
        nullable=False,
        default=TipoPermisoEnum.dia_completo
    )

    es_por_horas: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="TRUE si el permiso es por fracción de jornada (por_horas)"
    )

    # --- Campos para permisos por horas ---
    hora_inicio_permiso: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
        comment="Hora de inicio del permiso (solo si es_por_horas=TRUE)"
    )

    hora_fin_permiso: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
        comment="Hora de fin del permiso (solo si es_por_horas=TRUE)"
    )

    total_horas_permiso: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(4, 1),
        nullable=True,
        comment="Total de horas del permiso. Calculado automáticamente por backend"
    )

    # --- Documentación y aprobación ---
    descripcion: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Descripción o motivo del permiso"
    )

    documento_url: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="URL al documento de respaldo (certificado médico, etc.)"
    )

    estado_aprobacion: Mapped[EstadoAprobacionEnum] = mapped_column(
        SQLEnum(EstadoAprobacionEnum, name="estado_aprobacion_enum", create_constraint=True, native_enum=False),
        nullable=False,
        default=EstadoAprobacionEnum.pendiente
    )

    id_aprobado_por: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("rrhh.empleado.id", ondelete="SET NULL"),
        nullable=True,
        comment="ID del empleado (supervisor o RRHH) que aprobó/rechazó"
    )

    fecha_aprobacion: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
        comment="Fecha/hora en que se aprobó o rechazó"
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
        back_populates="justificaciones",
        lazy="select"
    )

    aprobador: Mapped[Optional["Empleado"]] = relationship(
        "Empleado",
        foreign_keys=[id_aprobado_por],
        lazy="select"
    )

    # Relación con AsistenciaDiaria
    asistencias: Mapped[list["AsistenciaDiaria"]] = relationship(
        "AsistenciaDiaria",
        back_populates="justificacion",
        lazy="select"
    )

    # Relación con BeneficioCumpleanos (opcional)
    # beneficio_cumpleanos: Mapped[Optional["BeneficioCumpleanos"]] = relationship(
    #     "BeneficioCumpleanos",
    #     back_populates="justificacion",
    #     lazy="select"
    # )

    # Relación con DetalleVacacion (se activará después)
    # detalles_vacacion: Mapped[list["DetalleVacacion"]] = relationship(
    #     "DetalleVacacion",
    #     back_populates="justificacion",
    #     lazy="select"
    # )

    def __repr__(self) -> str:
        return (
            f"<JustificacionAusencia(id={self.id}, empleado_id={self.id_empleado}, "
            f"tipo={self.tipo_justificacion}, fecha_inicio={self.fecha_inicio}, "
            f"estado={self.estado_aprobacion})>"
        )
