"""semana9_horario_personalizado_compensacion_horas_extra

Revision ID: 122bc6566cae
Revises: e8d4a6c9b201
Create Date: 2026-08-08 14:49:25.444183

NOTA sobre 'viaje_trabajo' y estado_dia_enum:
El script original `codigoPostgresSQL.txt` define `estado_dia_enum` como un
tipo ENUM nativo de Postgres, pero en producción (Neon) la columna
`rrhh.asistencia_diaria.tipo_dia` se implementó como VARCHAR(20) sin
CHECK constraint (ver migración 18fbcc39fce1). El tipo `estado_dia_enum` NO
existe como tipo en el schema `rrhh` de producción (verificado contra Neon).
Por lo tanto no hay DDL de enum que alterar para 'viaje_trabajo' en ese campo:
al ser VARCHAR(20) ya acepta el valor 'viaje_trabajo' (13 caracteres) sin
ningún cambio de esquema. Esta migración documenta el hallazgo pero no
ejecuta ninguna alteración sobre asistencia_diaria.

NOTA sobre fn_set_updated_at:
Verificado contra Neon (pg_proc, pg_trigger): esta función NO existe en
producción y ningún trigger de este patrón está desplegado en todo el
schema rrhh (solo existen trg_sync_salario_empleado y
trg_set_total_horas_permiso, sin relación con updated_at). El patrón
documentado en codigoPostgresSQL.txt nunca se aplicó vía Alembic; hoy
updated_at se mantiene únicamente vía SQLAlchemy (onupdate=datetime.now).
Esta migración crea la función porque el trigger de
horario_personalizado_empleado depende de ella.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '122bc6566cae'
down_revision: Union[str, None] = 'e8d4a6c9b201'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------
    # 0. fn_set_updated_at
    # NO existe en producción (verificado: 0 filas en pg_proc para
    # '%updated_at%' y ningún trigger de este tipo en todo el schema
    # rrhh). El patrón de codigoPostgresSQL.txt nunca se desplegó vía
    # Alembic; hoy updated_at solo se mantiene en la capa SQLAlchemy
    # (onupdate=datetime.now). La creamos aquí porque el trigger de
    # horario_personalizado_empleado (más abajo) depende de ella.
    # ------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION rrhh.fn_set_updated_at()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$;
    """)

    # ------------------------------------------------------------
    # 1. horario_personalizado_empleado
    # Override 1:1 opcional del horario estándar para un empleado
    # (tolerancia y horas propias, o salida flexible sin hora fija).
    # ------------------------------------------------------------
    op.create_table(
        'horario_personalizado_empleado',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('id_empleado', sa.Integer(), nullable=False),
        sa.Column('tolerancia_minutos', sa.Integer(), nullable=True),
        sa.Column('hora_entrada', sa.Time(), nullable=True),
        sa.Column('hora_salida', sa.Time(), nullable=True),
        sa.Column('salida_flexible', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('activo', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('observacion', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(
            ['id_empleado'], ['rrhh.empleado.id'],
            name=op.f('fk_horario_personalizado_empleado_id_empleado_empleado'),
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_horario_personalizado_empleado')),
        sa.UniqueConstraint('id_empleado', name=op.f('uq_horario_personalizado_empleado_id_empleado')),
        schema='rrhh',
    )

    op.execute("""
        CREATE TRIGGER trg_horario_personalizado_empleado_updated_at
            BEFORE UPDATE ON rrhh.horario_personalizado_empleado
            FOR EACH ROW EXECUTE FUNCTION rrhh.fn_set_updated_at();
    """)

    # ------------------------------------------------------------
    # 2. compensacion_horas_extra
    # Registro puntual de horas extra que se compensan como saldo
    # vacacional (goce de haber) de la gestión correspondiente.
    # ------------------------------------------------------------
    op.create_table(
        'compensacion_horas_extra',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('id_empleado', sa.Integer(), nullable=False),
        sa.Column('fecha', sa.Date(), nullable=False),
        sa.Column('horas', sa.Numeric(4, 1), nullable=False, server_default='8.0'),
        sa.Column('motivo', sa.Text(), nullable=False),
        sa.Column('gestion', sa.Integer(), nullable=False),
        sa.Column('id_registrado_por', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(
            ['id_empleado'], ['rrhh.empleado.id'],
            name=op.f('fk_compensacion_horas_extra_id_empleado_empleado'),
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['id_registrado_por'], ['rrhh.empleado.id'],
            name=op.f('fk_compensacion_horas_extra_id_registrado_por_empleado'),
            ondelete='SET NULL',
        ),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_compensacion_horas_extra')),
        sa.UniqueConstraint('id_empleado', 'fecha', name='uq_compensacion_horas_extra_empleado_fecha'),
        sa.CheckConstraint('horas > 0', name=op.f('ck_compensacion_horas_extra_horas_positivas')),
        schema='rrhh',
    )

    # Trigger: al insertar una compensación, suma "horas" al saldo
    # vacacional (horas_goce_haber y horas_correspondientes) de la
    # gestión del empleado. Si no existe el registro de vacacion para
    # esa gestión, lo crea usando fn_horas_vacacion_lgt como base y
    # luego suma "horas" sobre esa base.
    op.execute("""
        CREATE OR REPLACE FUNCTION rrhh.fn_compensacion_horas_extra_a_vacacion()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        AS $$
        DECLARE
            v_fecha_ingreso DATE;
            v_base_horas    NUMERIC(6,1);
        BEGIN
            SELECT fecha_ingreso INTO v_fecha_ingreso
            FROM rrhh.empleado
            WHERE id = NEW.id_empleado;

            v_base_horas := rrhh.fn_horas_vacacion_lgt(v_fecha_ingreso, MAKE_DATE(NEW.gestion, 12, 31));

            INSERT INTO rrhh.vacacion (id_empleado, gestion, horas_correspondientes, horas_goce_haber)
            VALUES (NEW.id_empleado, NEW.gestion, v_base_horas + NEW.horas, NEW.horas)
            ON CONFLICT (id_empleado, gestion) DO UPDATE
                SET horas_correspondientes = rrhh.vacacion.horas_correspondientes + NEW.horas,
                    horas_goce_haber       = rrhh.vacacion.horas_goce_haber + NEW.horas;

            RETURN NEW;
        END;
        $$;
    """)

    op.execute("""
        CREATE TRIGGER trg_compensacion_horas_extra_a_vacacion
            AFTER INSERT ON rrhh.compensacion_horas_extra
            FOR EACH ROW EXECUTE FUNCTION rrhh.fn_compensacion_horas_extra_a_vacacion();
    """)

    # ------------------------------------------------------------
    # 3. Enums: agregar 'viaje_trabajo'
    # ------------------------------------------------------------
    # tipo_justificacion_enum SÍ es un tipo nativo en producción.
    op.execute("ALTER TYPE rrhh.tipo_justificacion_enum ADD VALUE IF NOT EXISTS 'viaje_trabajo';")

    # estado_dia_enum NO existe como tipo nativo en producción: ver nota
    # al inicio de este archivo. tipo_dia es VARCHAR(20) y ya admite
    # 'viaje_trabajo' sin cambios de esquema.


def downgrade() -> None:
    # --- Enums ---
    # Postgres no soporta DROP VALUE nativo. Se aborta si ya hay filas
    # usando 'viaje_trabajo' para no perder datos silenciosamente, y si
    # no hay ninguna, se elimina la entrada directamente de pg_enum.
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM rrhh.justificacion_ausencia
                WHERE tipo_justificacion = 'viaje_trabajo'
            ) THEN
                RAISE EXCEPTION 'No se puede revertir: existen justificacion_ausencia con tipo_justificacion = viaje_trabajo';
            END IF;

            DELETE FROM pg_enum
            WHERE enumlabel = 'viaje_trabajo'
              AND enumtypid = 'rrhh.tipo_justificacion_enum'::regtype;
        END;
        $$;
    """)

    # --- compensacion_horas_extra ---
    op.execute("DROP TRIGGER IF EXISTS trg_compensacion_horas_extra_a_vacacion ON rrhh.compensacion_horas_extra;")
    op.execute("DROP FUNCTION IF EXISTS rrhh.fn_compensacion_horas_extra_a_vacacion();")
    op.drop_table('compensacion_horas_extra', schema='rrhh')

    # --- horario_personalizado_empleado ---
    op.execute("DROP TRIGGER IF EXISTS trg_horario_personalizado_empleado_updated_at ON rrhh.horario_personalizado_empleado;")
    op.drop_table('horario_personalizado_empleado', schema='rrhh')

    # --- fn_set_updated_at ---
    # Seguro de eliminar: esta migración es la única que la crea y
    # ningún otro trigger en producción depende de ella (verificado).
    op.execute("DROP FUNCTION IF EXISTS rrhh.fn_set_updated_at();")
