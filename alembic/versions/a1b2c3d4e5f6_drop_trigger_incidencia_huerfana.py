"""drop trigger incidencia huerfana (conflicto con codigo Python)

Revision ID: a1b2c3d4e5f6
Revises: 4fe73b669ee1
Create Date: 2026-05-30 21:35:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '4fe73b669ee1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Eliminar trigger que causa conflicto: al hacer UPDATE de es_huerfana=True
    # el trigger inserta en incidencia_marcacion, y luego el codigo Python
    # intenta insertar el mismo registro causando UniqueViolation y ROLLBACK.
    # El codigo Python ya maneja la creacion de incidencias correctamente.
    op.execute("DROP TRIGGER IF EXISTS trg_crear_incidencia_marcacion ON rrhh.marcacion;")
    op.execute("DROP FUNCTION IF EXISTS rrhh.fn_crear_incidencia_marcacion();")


def downgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION rrhh.fn_crear_incidencia_marcacion()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.es_huerfana THEN
                INSERT INTO rrhh.incidencia_marcacion (
                    id_marcacion,
                    tipo_incidencia,
                    estado_resolucion,
                    created_at,
                    updated_at
                )
                VALUES (
                    NEW.id,
                    'huerfana',
                    'pendiente',
                    NOW(),
                    NOW()
                )
                ON CONFLICT (id_marcacion) DO NOTHING;
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_crear_incidencia_marcacion
        AFTER INSERT OR UPDATE OF es_huerfana ON rrhh.marcacion
        FOR EACH ROW
        WHEN (NEW.es_huerfana = TRUE)
        EXECUTE FUNCTION rrhh.fn_crear_incidencia_marcacion();
        """
    )
