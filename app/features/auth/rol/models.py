"""
Modelo Rol - Roles del sistema.
Define los permisos de usuario: admin, rrhh, consulta, etc.
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.features.auth.usuario.models import Usuario


class Rol(Base):
    """
    Tabla: rrhh.rol
    Define los roles disponibles en el sistema.

    Roles típicos:
    - admin: Acceso total
    - rrhh: Gestión de empleados y asistencia
    - consulta: Solo lectura de reportes
    """

    __tablename__ = "rol"

    # --- Columnas ---
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    nombre: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    descripcion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now, nullable=False
    )

    # --- Relaciones ---
    usuarios: Mapped[list["Usuario"]] = relationship(back_populates="rol")

    def __repr__(self) -> str:
        return f"<Rol(id={self.id}, nombre='{self.nombre}')>"
