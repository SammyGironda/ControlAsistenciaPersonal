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


def _column_exists(table_name: str, column_name: str, schema: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name, schema=schema))


def _foreign_key_exists(table_name: str, fk_name: str, schema: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(fk["name"] == fk_name for fk in inspector.get_foreign_keys(table_name, schema=schema))


def upgrade() -> None:
    table_name = "contrato"
    schema = "rrhh"
    fk_name = op.f("fk_contrato_id_decreto_origen_decreto_incremento_salarial")

    if not _column_exists(table_name, "documento_contrato_url", schema):
        op.add_column(
            table_name,
            sa.Column(
                "documento_contrato_url",
                sa.String(length=255),
                nullable=True,
                comment="URL del contrato escaneado o digital",
            ),
            schema=schema,
        )

    if _foreign_key_exists(table_name, fk_name, schema):
        op.drop_constraint(
            fk_name,
            table_name,
            schema=schema,
            type_="foreignkey",
        )

    if _column_exists(table_name, "id_decreto_origen", schema):
        op.drop_column(table_name, "id_decreto_origen", schema=schema)


def downgrade() -> None:
    table_name = "contrato"
    schema = "rrhh"
    fk_name = op.f("fk_contrato_id_decreto_origen_decreto_incremento_salarial")

    if not _column_exists(table_name, "id_decreto_origen", schema):
        op.add_column(
            table_name,
            sa.Column(
                "id_decreto_origen",
                sa.Integer(),
                nullable=True,
                comment="Referencia al decreto si el contrato nació de una renovación por decreto",
            ),
            schema=schema,
        )

    if _column_exists(table_name, "id_decreto_origen", schema) and not _foreign_key_exists(table_name, fk_name, schema):
        op.create_foreign_key(
            fk_name,
            table_name,
            "decreto_incremento_salarial",
            ["id_decreto_origen"],
            ["id"],
            source_schema=schema,
            referent_schema=schema,
            ondelete="SET NULL",
        )

    if _column_exists(table_name, "documento_contrato_url", schema):
        op.drop_column(table_name, "documento_contrato_url", schema=schema)
