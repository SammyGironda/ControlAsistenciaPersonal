"""semana4_refuerzo_ajuste_salarial

Revision ID: 1ec7e965e7ea
Revises: b2c7f4a1d8e3
Create Date: 2026-05-23 18:38:21.791139

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1ec7e965e7ea'
down_revision: Union[str, None] = 'b2c7f4a1d8e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_check_constraint(
        op.f("chk_ajuste_salarial_decreto_coherente"),
        "ajuste_salarial",
        "(motivo = 'decreto_anual' AND id_condicion_decreto IS NOT NULL) OR (motivo <> 'decreto_anual' AND id_condicion_decreto IS NULL)",
        schema="rrhh",
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("chk_ajuste_salarial_decreto_coherente"),
        "ajuste_salarial",
        schema="rrhh",
        type_="check",
    )
