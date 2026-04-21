"""
Modelo ComplementoDep.
Catalogo SEGIP de departamentos de Bolivia.
"""

from typing import TYPE_CHECKING, List
from sqlalchemy import String, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.features.employees.empleado.models import Empleado
    from app.features.attendance.feriados.models import DiaFestivo


class ComplementoDep(Base):
    """
    Tabla: rrhh.complemento_dep
    Codigos de departamento de Bolivia para emision de CI (SEGIP).

    Codigos:
    - LP: La Paz
    - CB: Cochabamba
    - SC: Santa Cruz
    - OR: Oruro
    - PT: Potosi
    - TJ: Tarija
    - CH: Chuquisaca
    - BE: Beni
    - PD: Pando
    """

    __tablename__ = "complemento_dep"

    codigo: Mapped[str] = mapped_column(String(2), primary_key=True)
    nombre_departamento: Mapped[str] = mapped_column(String(50), nullable=False)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    empleados: Mapped[List["Empleado"]] = relationship(back_populates="complemento")
    feriados: Mapped[List["DiaFestivo"]] = relationship(
        back_populates="complemento",
        lazy="select",
    )

    def __repr__(self) -> str:
        return f"<ComplementoDep(codigo='{self.codigo}', nombre='{self.nombre_departamento}')>"
