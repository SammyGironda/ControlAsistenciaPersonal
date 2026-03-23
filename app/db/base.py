"""
Base declarativa para todos los modelos SQLAlchemy 2.0.
Todos los modelos heredan de esta clase Base.

IMPORTANTE:
- Cada modelo nuevo debe importarse aquí para que Alembic lo detecte.
- Usar Mapped y mapped_column (SQLAlchemy 2.0 puro).
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime

from app.core.config import get_settings

settings = get_settings()

# --- Convención de nombres para constraints ---
# Esto genera nombres consistentes para PKs, FKs, UNIQUEs, etc.
convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

metadata = MetaData(
    naming_convention=convention,
    schema=settings.DB_SCHEMA  # Todas las tablas en schema 'rrhh'
)


class Base(DeclarativeBase):
    """
    Clase base para todos los modelos.
    Incluye campos comunes: id, created_at, updated_at.
    """
    metadata = metadata


# ============================================================
# REGISTRO DE MODELOS PARA ALEMBIC
# ============================================================
# IMPORTANTE: Los modelos NO se importan aquí para evitar circular imports.
# En su lugar, se importan en alembic/env.py DESPUÉS de importar Base.
# Los scripts que necesiten usar modelos los importan directamente.
# ============================================================
