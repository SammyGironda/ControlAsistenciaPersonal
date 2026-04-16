"""add_por_habilitar_estado_empleado

Revision ID: b2c7f4a1d8e3
Revises: 9b1e4c2a7d4f
Create Date: 2026-04-16 16:58:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "b2c7f4a1d8e3"
down_revision: Union[str, None] = "9b1e4c2a7d4f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint(
        op.f("ck_empleado_estado_empleado_enum"),
        "empleado",
        schema="rrhh",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_empleado_estado_empleado_enum"),
        "empleado",
        "estado IN ('activo', 'baja', 'por_habilitar', 'suspendido')",
        schema="rrhh",
    )
    op.alter_column(
        "empleado",
        "estado",
        existing_type=sa.Enum(
            "activo",
            "baja",
            "suspendido",
            name="estado_empleado_enum",
            native_enum=False,
            create_constraint=True,
        ),
        server_default="por_habilitar",
        schema="rrhh",
    )


def downgrade() -> None:
    op.alter_column(
        "empleado",
        "estado",
        existing_type=sa.Enum(
            "activo",
            "baja",
            "suspendido",
            name="estado_empleado_enum",
            native_enum=False,
            create_constraint=True,
        ),
        server_default=None,
        schema="rrhh",
    )
    op.drop_constraint(
        op.f("ck_empleado_estado_empleado_enum"),
        "empleado",
        schema="rrhh",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_empleado_estado_empleado_enum"),
        "empleado",
        "estado IN ('activo', 'baja', 'suspendido')",
        schema="rrhh",
    )
