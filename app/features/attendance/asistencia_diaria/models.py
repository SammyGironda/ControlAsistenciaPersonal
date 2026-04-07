"""
Modelo de Asistencia Diaria - Un registro por empleado por día.
Calcula automáticamente retrasos, minutos trabajados y tipo de día.
Worker diario ejecuta a las 23:59 para procesar el día completo.
"""

from datetime import date, datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Integer, BigInteger, ForeignKey, Boolean, Text, Date, Numeric, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.base import Base

if TYPE_CHECKING:
    from app.features.employees.empleado.models import Empleado
    from app.features.attendance.marcacion.models import Marcacion
    # Semana 7: from app.features.attendance.justificacion.models import JustificacionAusencia


# --- ENUM ---
class EstadoDiaEnum(str, enum.Enum):
    """
    Estados posibles de un día de asistencia.
    
    - presente: Empleado regular marcó correctamente ENTRADA + SALIDA
    - ausente: Falta injustificada, genera descuento en planilla
    - feriado: Día libre por feriado nacional o departamental
    - permiso_parcial: Trabajó parte del día con permiso por horas
    - presente_exento: Cargo de confianza (sin marcación requerida)
    - licencia_medica: Licencia por accidente/enfermedad (no descuenta salario)
    - descanso: Fin de semana o día no laborable según horario asignado
    """
    presente = "presente"
    ausente = "ausente"
    feriado = "feriado"
    permiso_parcial = "permiso_parcial"
    presente_exento = "presente_exento"
    licencia_medica = "licencia_medica"
    descanso = "descanso"


class AsistenciaDiaria(Base):
    """
    Registro diario de asistencia por empleado.
    
    Un registro por día por empleado. UNIQUE constraint garantiza unicidad.
    Relación ternaria explícita: empleado + marcacion_entrada + marcacion_salida.
    
    Proceso:
    - Worker diario ejecuta a las 23:59
    - Calcula tipo_dia según: horario, cargo, marcaciones, feriados, justificaciones
    - Calcula minutos_retraso respecto a horario.hora_entrada + tolerancia
    - Calcula minutos_trabajados = marcacion_salida - marcacion_entrada
    
    Para cargos de confianza:
    - tipo_dia = 'presente_exento'
    - minutos_retraso = 0 (no se penaliza)
    - minutos_trabajados = 0 (no se registra)
    """
    __tablename__ = "asistencia_diaria"
    __table_args__ = (
        UniqueConstraint('id_empleado', 'fecha', name='uq_asistencia_dia'),
        Index('idx_asistencia_empleado_fecha', 'id_empleado', 'fecha'),
        {"schema": "rrhh"}
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # --- Relaciones ---
    id_empleado: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rrhh.empleado.id", ondelete="CASCADE"),
        nullable=False
    )
    
    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    
    id_marcacion_entrada: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("rrhh.marcacion.id", ondelete="SET NULL"),
        nullable=True
    )
    
    id_marcacion_salida: Mapped[Optional[int]] = mapped_column(
        BigInteger,
        ForeignKey("rrhh.marcacion.id", ondelete="SET NULL"),
        nullable=True
    )
    
    # Semana 7: JustificacionAusencia (nullable hasta que se cree la tabla)
    id_justificacion: Mapped[Optional[int]] = mapped_column(
        Integer,
        # ForeignKey("rrhh.justificacion_ausencia.id", ondelete="SET NULL"),  # Activar en Semana 7
        nullable=True
    )
    
    # --- Datos del día ---
    tipo_dia: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Estado del día: presente, ausente, feriado, descanso, presente_exento, etc."
    )
    
    minutos_retraso: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Minutos de retraso respecto al horario asignado (considerando tolerancia)"
    )
    
    minutos_trabajados: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Minutos netos trabajados (SALIDA - ENTRADA), sin descuento de almuerzo"
    )
    
    horas_extra: Mapped[float] = mapped_column(
        Numeric(4, 1),
        nullable=False,
        default=0.0,
        comment="Horas extra trabajadas (calculadas si excede horario normal)"
    )
    
    horas_permiso_usadas: Mapped[float] = mapped_column(
        Numeric(4, 1),
        nullable=False,
        default=0.0,
        comment="Horas de permiso consumidas (desnormalizado de justificacion_ausencia)"
    )
    
    trabajo_en_feriado: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="TRUE si el empleado marcó en un día feriado. Si !es_cargo_confianza, suma 8h a vacación"
    )
    
    observacion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # --- Auditoría ---
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now
    )
    
    # --- Relationships (lazy para evitar circular imports) ---
    empleado: Mapped["Empleado"] = relationship(
        "Empleado",
        foreign_keys=[id_empleado],
        back_populates="asistencias",
        lazy="select"
    )
    
    marcacion_entrada: Mapped[Optional["Marcacion"]] = relationship(
        "Marcacion",
        foreign_keys=[id_marcacion_entrada],
        lazy="select"
    )
    
    marcacion_salida: Mapped[Optional["Marcacion"]] = relationship(
        "Marcacion",
        foreign_keys=[id_marcacion_salida],
        lazy="select"
    )
    
    # Semana 7: descomentar cuando exista JustificacionAusencia
    # justificacion: Mapped[Optional["JustificacionAusencia"]] = relationship(
    #     "JustificacionAusencia",
    #     foreign_keys=[id_justificacion],
    #     lazy="select"
    # )
    
    def __repr__(self) -> str:
        return (
            f"<AsistenciaDiaria(id={self.id}, empleado_id={self.id_empleado}, "
            f"fecha={self.fecha}, tipo_dia={self.tipo_dia})>"
        )
