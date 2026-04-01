"""
Modelo Empleado.
Entidad central del sistema - datos personales y laborales.
"""

from datetime import datetime, date
from decimal import Decimal
from typing import Optional, TYPE_CHECKING, List
from sqlalchemy import String, Boolean, Integer, ForeignKey, Numeric, Date, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.db.base import Base

if TYPE_CHECKING:
    from app.features.employees.departamento.models import Departamento, ComplementoDep
    from app.features.employees.cargo.models import Cargo
    from app.features.auth.usuario.models import Usuario
    from app.features.employees.horario.models import AsignacionHorario
    from app.features.contracts.contrato.models import Contrato
    from app.features.contracts.ajuste_salarial.models import AjusteSalarial


# --- ENUMs ---
class GeneroEnum(str, enum.Enum):
    """Género del empleado."""
    masculino = "masculino"
    femenino = "femenino"
    otro = "otro"


class EstadoEmpleadoEnum(str, enum.Enum):
    """Estado laboral del empleado."""
    activo = "activo"
    baja = "baja"
    suspendido = "suspendido"


class Empleado(Base):
    """
    Tabla: rrhh.empleado
    Información personal y laboral de cada empleado.

    Campos clave:
    - ci_numero + complemento_dep + ci_sufijo: CI completo según SEGIP
    - salario_base: Salario vigente (se sincroniza desde ajuste_salarial)
    - estado: activo | baja | suspendido
    """

    __tablename__ = "empleado"

    # --- Columnas de identificación ---
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ci_numero: Mapped[str] = mapped_column(String(20), nullable=False)
    complemento_dep: Mapped[str] = mapped_column(
        String(2),
        ForeignKey("complemento_dep.codigo", ondelete="RESTRICT"),
        nullable=False
    )
    ci_sufijo_homonimo: Mapped[Optional[str]] = mapped_column(
        String(10),
        nullable=True,
        comment="Sufijo para homónimos SEGIP"
    )

    # --- Datos personales ---
    nombres: Mapped[str] = mapped_column(String(100), nullable=False)
    apellidos: Mapped[str] = mapped_column(String(100), nullable=False)
    fecha_nacimiento: Mapped[date] = mapped_column(Date, nullable=False)
    genero: Mapped[GeneroEnum] = mapped_column(
        SQLEnum(GeneroEnum, name="genero_enum", create_constraint=True, native_enum=False),
        nullable=False
    )

    # --- Datos laborales ---
    fecha_ingreso: Mapped[date] = mapped_column(Date, nullable=False)
    estado: Mapped[EstadoEmpleadoEnum] = mapped_column(
        SQLEnum(EstadoEmpleadoEnum, name="estado_empleado_enum", create_constraint=True, native_enum=False),
        default=EstadoEmpleadoEnum.activo,
        nullable=False
    )
    id_cargo: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("cargo.id", ondelete="RESTRICT"),
        nullable=False
    )
    id_departamento: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("departamento.id", ondelete="RESTRICT"),
        nullable=False
    )
    salario_base: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
        comment="Salario vigente en Bs. - se actualiza desde ajuste_salarial"
    )

    # --- Contacto ---
    email: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    telefono: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    foto_url: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # --- Auditoría ---
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now, nullable=False
    )

    # --- Relaciones ---
    departamento: Mapped["Departamento"] = relationship(back_populates="empleados")
    cargo: Mapped["Cargo"] = relationship(back_populates="empleados")
    # complemento: Mapped["ComplementoDep"] = relationship(back_populates="empleados")

    # --- Relación con Usuario (Semana 2) ---
    usuario: Mapped[Optional["Usuario"]] = relationship(back_populates="empleado")

    # --- Relación con AsignacionHorario (Semana 3) ---
    asignaciones_horario: Mapped[List["AsignacionHorario"]] = relationship(back_populates="empleado")

    # --- Relaciones con Contracts (Semana 4) ---
    contratos: Mapped[List["Contrato"]] = relationship(
        "Contrato",
        back_populates="empleado",
        foreign_keys="[Contrato.id_empleado]",
        cascade="all, delete-orphan"
    )
    ajustes_salariales: Mapped[List["AjusteSalarial"]] = relationship(
        "AjusteSalarial",
        back_populates="empleado",
        foreign_keys="[AjusteSalarial.id_empleado]",
        cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Empleado(id={self.id}, ci='{self.ci_numero}', nombre='{self.nombres} {self.apellidos}')>"

    @property
    def nombre_completo(self) -> str:
        """Retorna el nombre completo del empleado."""
        return f"{self.nombres} {self.apellidos}"

    @property
    def ci_completo(self) -> str:
        """Retorna el CI formateado: 1234567-LP o 1234567-LP-1A"""
        partes = [self.ci_numero, self.complemento_dep]
        if self.ci_sufijo_homonimo:
            partes.append(self.ci_sufijo_homonimo)
        return "-".join(partes)
