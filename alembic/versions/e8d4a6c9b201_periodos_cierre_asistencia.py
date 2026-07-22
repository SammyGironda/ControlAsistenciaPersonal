"""periodos de cierre mensual de asistencia

Revision ID: e8d4a6c9b201
Revises: a1b2c3d4e5f6
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8d4a6c9b201"
down_revision: Union[str, None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "periodo_asistencia",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("anio", sa.Integer(), nullable=False),
        sa.Column("mes", sa.Integer(), nullable=False),
        sa.Column("estado", sa.String(length=20), nullable=False),
        sa.Column("cerrado_en", sa.DateTime(), nullable=True),
        sa.Column("id_cerrado_por", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("mes BETWEEN 1 AND 12", name="ck_periodo_asistencia_mes"),
        sa.ForeignKeyConstraint(["id_cerrado_por"], ["rrhh.empleado.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("anio", "mes", name="uq_periodo_asistencia_anio_mes"),
        schema="rrhh",
    )


def downgrade() -> None:
    op.drop_table("periodo_asistencia", schema="rrhh")
