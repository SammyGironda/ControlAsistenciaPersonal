"""add_requiere_cambio_password

Agrega rrhh.usuario.requiere_cambio_password para el flujo de contraseña temporal:
el admin crea la cuenta (o resetea la clave), el backend genera una contraseña
aleatoria y la marca como temporal; el usuario la reemplaza en su primer login y
recién entonces el flag baja.

Revision ID: a7f4c2e8b310
Revises: e5f2a8c1d904
Create Date: 2026-08-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7f4c2e8b310"
down_revision: Union[str, None] = "e5f2a8c1d904"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLA = "usuario"
COLUMNA = "requiere_cambio_password"
SCHEMA = "rrhh"


def _column_exists(table_name: str, column_name: str, schema: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return any(column["name"] == column_name for column in inspector.get_columns(table_name, schema=schema))


def upgrade() -> None:
    # server_default es imprescindible, no cosmético: la tabla ya tiene filas y la
    # columna es NOT NULL, así que sin default el ALTER falla. Se DEJA puesto
    # después del backfill para que cualquier INSERT que no mencione la columna
    # (seeds, SQL crudo) siga siendo válido.
    #
    # Las cuentas preexistentes quedan en FALSE a propósito: sus contraseñas las
    # eligió su dueño, no son temporales.
    if not _column_exists(TABLA, COLUMNA, SCHEMA):
        op.add_column(
            TABLA,
            sa.Column(
                COLUMNA,
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
                comment="TRUE mientras la cuenta tenga una contraseña temporal fijada por el admin",
            ),
            schema=SCHEMA,
        )


def downgrade() -> None:
    if _column_exists(TABLA, COLUMNA, SCHEMA):
        op.drop_column(TABLA, COLUMNA, schema=SCHEMA)
