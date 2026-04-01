"""
Modelo Usuario.
Sistema de autenticación y autorización.

IMPORTANTE:
- En Semana 2-8: Endpoints abiertos (sin JWT)
- En Semana 9: Se activa JWT + middleware de autenticación
"""

from datetime import datetime
from typing import Optional, TYPE_CHECKING
from sqlalchemy import String, Boolean, Integer, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.security import hash_password, verify_password


from app.db.base import Base

if TYPE_CHECKING:
    from app.features.auth.rol.models import Rol
    from app.features.employees.empleado.models import Empleado



class Usuario(Base):
    """
    Tabla: rrhh.usuario
    Representa a un usuario del sistema con credenciales de acceso.

    Campos clave:
    - username: Único, login del usuario
    - password_hash: Contraseña hasheada con bcrypt
    - id_rol: Define los permisos (admin, rrhh, consulta, empleado)
    - id_empleado: Vincula al usuario con su registro de empleado (opcional)

    Nota: JWT se activa en Semana 9. Hasta entonces, los endpoints son abiertos.
    """

    __tablename__ = "usuario"

    # --- Columnas de identificación ---
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Contraseña hasheada con bcrypt"
    )

    # --- Autorización ---
    id_rol: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("rol.id", ondelete="RESTRICT"),
        nullable=False
    )

    # --- Vinculación con empleado (opcional para usuarios externos) ---
    id_empleado: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("empleado.id", ondelete="CASCADE"),
        nullable=True,
        unique=True,
        comment="NULL para usuarios sin registro de empleado (ej: admin externo)"
    )

    # --- Estado del usuario ---
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ultimo_acceso: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # --- Auditoría ---
    created_at: Mapped[datetime] = mapped_column(default=datetime.now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        default=datetime.now, onupdate=datetime.now, nullable=False
    )

    # --- Relaciones ---
    rol: Mapped["Rol"] = relationship(back_populates="usuarios")
    empleado: Mapped[Optional["Empleado"]] = relationship(back_populates="usuario")

    def __repr__(self) -> str:
        return f"<Usuario(id={self.id}, username='{self.username}', rol_id={self.id_rol})>"

    def set_password(self, password: str) -> None:
        """Hashea y guarda la contraseña usando bcrypt centralizado."""
        self.password_hash = hash_password(password)

    def check_password(self, password: str) -> bool:
        """Verifica si la contraseña en texto plano coincide con el hash."""
        return verify_password(password, self.password_hash)
