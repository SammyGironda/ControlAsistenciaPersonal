"""add_documento_contrato_url

Revision ID: 9b1e4c2a7d4f
Revises: d7238264bcd6
Create Date: 2026-04-16 16:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9b1e4c2a7d4f"
down_revision: Union[str, None] = "d7238264bcd6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "contrato",
        sa.Column(
            "documento_contrato_url",
            sa.String(length=255),
            nullable=True,
            comment="URL del contrato escaneado o digital",
        ),
        schema="rrhh",
    )
    op.drop_constraint(
        op.f("fk_contrato_id_decreto_origen_decreto_incremento_salarial"),
        "contrato",
        schema="rrhh",
        type_="foreignkey",
    )
    op.drop_column("contrato", "id_decreto_origen", schema="rrhh")


def downgrade() -> None:
    op.add_column(
        "contrato",
        sa.Column(
            "id_decreto_origen",
            sa.Integer(),
            nullable=True,
            comment="Referencia al decreto si el contrato nació de una renovación por decreto",
        ),
        schema="rrhh",
    )
    op.create_foreign_key(
        op.f("fk_contrato_id_decreto_origen_decreto_incremento_salarial"),
        "contrato",
        "decreto_incremento_salarial",
        ["id_decreto_origen"],
        ["id"],
        source_schema="rrhh",
        referent_schema="rrhh",
        ondelete="SET NULL",
    )
    op.drop_column("contrato", "documento_contrato_url", schema="rrhh")
