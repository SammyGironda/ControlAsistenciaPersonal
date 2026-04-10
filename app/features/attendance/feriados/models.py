"""
Modelo DiaFestivo - Feriados nacionales y departamentales de Bolivia.
Permite registrar feriados que aplican a todos o solo a un departamento.
"""

from datetime import date, datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, Date, ForeignKey, UniqueConstraint, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.base import Base

if TYPE_CHECKING:
    from app.features.employees.departamento.models import ComplementoDep


# --- ENUM ---
class AmbitoFestivoEnum(str, enum.Enum):
    """
    Ámbito de aplicación del feriado.

    - NACIONAL: Aplica a todos los empleados del país
    - DEPARTAMENTAL: Aplica solo a empleados del departamento especificado
    """
    NACIONAL = "NACIONAL"
    DEPARTAMENTAL = "DEPARTAMENTAL"


class DiaFestivo(Base):
    """
    Tabla: rrhh.dia_festivo

    Registro de feriados bolivianos (nacionales o departamentales).

    Reglas de negocio:
    - NACIONAL: codigo_departamento debe ser NULL
    - DEPARTAMENTAL: codigo_departamento es obligatorio
    - Si un empleado regular trabaja en feriado, suma 8h a vacacion.horas_goce_haber
    - No aplica a cargos de confianza (es_cargo_confianza=TRUE)

    Constraint UNIQUE garantiza que no se repita (fecha, ambito, codigo_departamento).
    """

    __tablename__ = "dia_festivo"
    __table_args__ = (
        UniqueConstraint('fecha', 'ambito', 'codigo_departamento', name='uq_dia_festivo'),
        {"schema": "rrhh"}
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    fecha: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    descripcion: Mapped[str] = mapped_column(
        String(150),
        nullable=False,
        comment="Descripción del feriado (ej: 'Día del Trabajo', 'Aniversario de La Paz')"
    )

    ambito: Mapped[AmbitoFestivoEnum] = mapped_column(
        SQLEnum(
            AmbitoFestivoEnum,
            name="ambito_festivo_enum",
            create_constraint=True,
            native_enum=True,
            schema="rrhh",
        ),
        nullable=False,
        comment="NACIONAL aplica a todos, DEPARTAMENTAL solo al departamento indicado"
    )

    codigo_departamento: Mapped[Optional[str]] = mapped_column(
        String(2),
        ForeignKey("rrhh.complemento_dep.codigo", ondelete="RESTRICT"),
        nullable=True,
        comment="NULL solo para NACIONAL. DEPARTAMENTAL requiere el código (LP, CB, SC, etc.)"
    )

    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # --- Auditoría ---
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now, nullable=False
    )

    # --- Relaciones ---
    complemento: Mapped[Optional["ComplementoDep"]] = relationship(
        "ComplementoDep",
        back_populates="feriados",
        foreign_keys=[codigo_departamento],
        lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<DiaFestivo(id={self.id}, fecha={self.fecha}, "
            f"descripcion='{self.descripcion}', ambito={self.ambito})>"
        )
