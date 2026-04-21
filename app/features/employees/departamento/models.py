"""
Modelo Departamento.
Estructura organizacional jerarquica.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING, List
from sqlalchemy import String, Boolean, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.features.employees.cargo.models import Cargo
    from app.features.employees.empleado.models import Empleado


class Departamento(Base):
    """
    Tabla: rrhh.departamento
    Departamentos organizacionales de la empresa (jerárquico).

    Ejemplo de jerarquía:
    - Gerencia General (id_padre=NULL)
      - Gerencia RRHH (id_padre=1)
        - Área Nóminas (id_padre=2)
    """

    __tablename__ = "departamento"

    # --- Columnas ---
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    id_padre: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("departamento.id", ondelete="RESTRICT"),
        nullable=True
    )
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now, nullable=False
    )

    # --- Relaciones jerárquicas (self-referential) ---
    padre: Mapped[Optional["Departamento"]] = relationship(
        "Departamento",
        remote_side=[id],
        back_populates="hijos"
    )
    hijos: Mapped[List["Departamento"]] = relationship(
        "Departamento",
        back_populates="padre"
    )

    # --- Relaciones con otras entidades ---
    cargos: Mapped[List["Cargo"]] = relationship(back_populates="departamento")
    empleados: Mapped[List["Empleado"]] = relationship(back_populates="departamento")

    def __repr__(self) -> str:
        return f"<Departamento(id={self.id}, codigo='{self.codigo}', nombre='{self.nombre}')>"
