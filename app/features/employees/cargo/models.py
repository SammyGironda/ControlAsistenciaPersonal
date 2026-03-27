"""
Modelo Cargo.
Puestos de trabajo dentro de la estructura organizacional.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING, List
from sqlalchemy import String, Boolean, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.features.employees.departamento.models import Departamento
    from app.features.employees.empleado.models import Empleado


class Cargo(Base):
    """
    Tabla: rrhh.cargo
    Define los cargos/puestos de trabajo de la organización.

    Atributos importantes:
    - nivel: Jerarquía numérica (1=Director, 2=Gerente, etc.)
    - es_cargo_confianza: Si es TRUE, el empleado está exento de marcar huella
    """

    __tablename__ = "cargo"

    # --- Columnas ---
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    nivel: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    es_cargo_confianza: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        comment="TRUE = exento de marcar huella biométrica"
    )
    id_departamento: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("departamento.id", ondelete="RESTRICT"),
        nullable=False
    )
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now, nullable=False
    )

    # --- Relaciones ---
    departamento: Mapped["Departamento"] = relationship(back_populates="cargos")
    empleados: Mapped[list["Empleado"]] = relationship(back_populates="cargo")

    def __repr__(self) -> str:
        return f"<Cargo(id={self.id}, codigo='{self.codigo}', nombre='{self.nombre}')>"
