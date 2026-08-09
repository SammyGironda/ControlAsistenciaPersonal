"""Agrega el CHECK chk_vacacion_no_excede a rrhh.vacacion

El constraint está en `codigoPostgresSQL.txt` pero nunca se desplegó en Neon
(punto 12 de las discrepancias de CLAUDE.md, reverificado el 2026-08-09 contra
`pg_constraint`: la tabla no tenía ningún CHECK).

Sin él, nada impide que `horas_tomadas` supere a `horas_correspondientes` desde
cualquier flujo que escriba la tabla — incluido el trigger
`trg_compensacion_horas_extra_a_vacacion`, que hace UPSERT directo sin pasar por
el servicio. La validación equivalente en
`vacaciones/services.py::cambiar_estado_detalle` cubre el camino de la API; este
constraint cubre el resto.

Verificación previa a la aplicación (solo lectura, 2026-08-09): 1 fila en
`rrhh.vacacion`, 0 filas con `horas_tomadas > horas_correspondientes`.

NOTA: `chk_vacacion_horas_positivas` y el trigger de `updated_at` de `vacacion`
también siguen faltando en producción. Quedan fuera del alcance de esta
migración.

Revision ID: 3d9a17c4b8e2
Revises: 122bc6566cae
Create Date: 2026-08-09

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '3d9a17c4b8e2'
down_revision = '122bc6566cae'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE rrhh.vacacion
        ADD CONSTRAINT chk_vacacion_no_excede
        CHECK (horas_tomadas <= horas_correspondientes);
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE rrhh.vacacion
        DROP CONSTRAINT IF EXISTS chk_vacacion_no_excede;
    """)
