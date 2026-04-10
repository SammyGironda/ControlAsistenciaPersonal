"""semana8_fix_relaciones_y_reglas_contexto

Revision ID: d7238264bcd6
Revises: cfc064401f07
Create Date: 2026-04-10 16:24:48.026599

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d7238264bcd6"
down_revision: Union[str, None] = "cfc064401f07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # FK faltante beneficio_cumpleanos -> justificacion_ausencia
    op.create_foreign_key(
        op.f("fk_beneficio_cumpleanos_id_justificacion_justificacion_ausencia"),
        "beneficio_cumpleanos",
        "justificacion_ausencia",
        ["id_justificacion"],
        ["id"],
        source_schema="rrhh",
        referent_schema="rrhh",
        ondelete="SET NULL",
    )

    # Unicidad de identidad SEGIP del empleado
    op.create_unique_constraint(
        op.f("uq_empleado_ci"),
        "empleado",
        ["ci_numero", "complemento_dep", "ci_sufijo_homonimo"],
        schema="rrhh",
    )

    # Ajuste de resolución de incidencias por empleado (no por usuario)
    op.drop_constraint(
        op.f("fk_incidencia_marcacion_id_resuelto_por_usuario"),
        "incidencia_marcacion",
        schema="rrhh",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_incidencia_marcacion_id_resuelto_por_empleado"),
        "incidencia_marcacion",
        "empleado",
        ["id_resuelto_por"],
        ["id"],
        source_schema="rrhh",
        referent_schema="rrhh",
        ondelete="SET NULL",
    )

    # Parametro legal de tipo de aporte
    op.add_column(
        "parametro_impuesto",
        sa.Column(
            "tipo_aporte",
            sa.String(length=20),
            nullable=False,
            server_default="LABORAL",
            comment="LABORAL o PATRONAL",
        ),
        schema="rrhh",
    )
    op.alter_column("parametro_impuesto", "tipo_aporte", server_default=None, schema="rrhh")
    op.create_check_constraint(
        op.f("chk_parametro_tipo_aporte"),
        "parametro_impuesto",
        "tipo_aporte IN ('LABORAL', 'PATRONAL')",
        schema="rrhh",
    )

    # Columna generada de horas pendientes en vacacion
    op.add_column(
        "vacacion",
        sa.Column(
            "horas_pendientes",
            sa.Numeric(precision=6, scale=1),
            sa.Computed("horas_correspondientes - horas_tomadas", persisted=True),
            nullable=False,
            comment="Columna generada: horas_correspondientes - horas_tomadas",
        ),
        schema="rrhh",
    )

    # Reglas de coherencia para justificaciones
    op.create_check_constraint(
        op.f("chk_justificacion_fechas"),
        "justificacion_ausencia",
        "fecha_fin >= fecha_inicio",
        schema="rrhh",
    )
    op.create_check_constraint(
        op.f("chk_permiso_horas"),
        "justificacion_ausencia",
        "(es_por_horas = FALSE AND hora_inicio_permiso IS NULL AND hora_fin_permiso IS NULL AND total_horas_permiso IS NULL) OR "
        "(es_por_horas = TRUE AND hora_inicio_permiso IS NOT NULL AND hora_fin_permiso IS NOT NULL AND hora_fin_permiso > hora_inicio_permiso AND total_horas_permiso IS NOT NULL AND total_horas_permiso > 0)",
        schema="rrhh",
    )

    # Alineación de checks (columnas VARCHAR + CHECK, no ENUM nativo)
    op.drop_constraint(op.f("ck_contrato_estado_contrato_enum"), "contrato", schema="rrhh", type_="check")
    op.create_check_constraint(
        op.f("ck_contrato_estado_contrato_enum"),
        "contrato",
        "estado IN ('activo', 'vencido', 'rescindido')",
        schema="rrhh",
    )

    op.drop_constraint(op.f("ck_ajuste_salarial_motivo_ajuste_enum"), "ajuste_salarial", schema="rrhh", type_="check")
    op.create_check_constraint(
        op.f("ck_ajuste_salarial_motivo_ajuste_enum"),
        "ajuste_salarial",
        "motivo IN ('decreto_anual', 'renovacion', 'ascenso', 'renegociacion')",
        schema="rrhh",
    )

    op.drop_constraint(
        op.f("ck_incidencia_marcacion_tipo_incidencia_enum"),
        "incidencia_marcacion",
        schema="rrhh",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_incidencia_marcacion_tipo_incidencia_enum"),
        "incidencia_marcacion",
        "tipo_incidencia IN ('huerfana', 'duplicada', 'inconsistente')",
        schema="rrhh",
    )

    op.drop_constraint(
        op.f("ck_incidencia_marcacion_estado_resolucion_enum"),
        "incidencia_marcacion",
        schema="rrhh",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_incidencia_marcacion_estado_resolucion_enum"),
        "incidencia_marcacion",
        "estado_resolucion IN ('pendiente', 'resuelto', 'ignorado')",
        schema="rrhh",
    )

    # Trigger de cálculo automático para permisos por horas
    op.execute(
        """
        CREATE OR REPLACE FUNCTION rrhh.fn_set_total_horas_permiso()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.es_por_horas THEN
                IF NEW.hora_inicio_permiso IS NULL OR NEW.hora_fin_permiso IS NULL THEN
                    RAISE EXCEPTION 'hora_inicio_permiso y hora_fin_permiso son obligatorios cuando es_por_horas=TRUE';
                END IF;
                IF NEW.hora_fin_permiso <= NEW.hora_inicio_permiso THEN
                    RAISE EXCEPTION 'hora_fin_permiso debe ser mayor que hora_inicio_permiso';
                END IF;

                NEW.total_horas_permiso := ROUND(
                    (EXTRACT(EPOCH FROM (NEW.hora_fin_permiso - NEW.hora_inicio_permiso)) / 3600.0)::numeric,
                    1
                );
            ELSE
                NEW.total_horas_permiso := NULL;
            END IF;

            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_set_total_horas_permiso
        BEFORE INSERT OR UPDATE ON rrhh.justificacion_ausencia
        FOR EACH ROW
        EXECUTE FUNCTION rrhh.fn_set_total_horas_permiso();
        """
    )

    # Trigger de creación automática de incidencia por marcación huérfana
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


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_crear_incidencia_marcacion ON rrhh.marcacion;")
    op.execute("DROP FUNCTION IF EXISTS rrhh.fn_crear_incidencia_marcacion();")

    op.execute("DROP TRIGGER IF EXISTS trg_set_total_horas_permiso ON rrhh.justificacion_ausencia;")
    op.execute("DROP FUNCTION IF EXISTS rrhh.fn_set_total_horas_permiso();")

    op.drop_constraint(
        op.f("ck_incidencia_marcacion_estado_resolucion_enum"),
        "incidencia_marcacion",
        schema="rrhh",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_incidencia_marcacion_estado_resolucion_enum"),
        "incidencia_marcacion",
        "estado_resolucion IN ('pendiente', 'revisado', 'resuelto', 'descartado')",
        schema="rrhh",
    )

    op.drop_constraint(
        op.f("ck_incidencia_marcacion_tipo_incidencia_enum"),
        "incidencia_marcacion",
        schema="rrhh",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_incidencia_marcacion_tipo_incidencia_enum"),
        "incidencia_marcacion",
        "tipo_incidencia IN ('marcacion_huerfana', 'marcacion_duplicada', 'horario_irregular')",
        schema="rrhh",
    )

    op.drop_constraint(
        op.f("ck_ajuste_salarial_motivo_ajuste_enum"),
        "ajuste_salarial",
        schema="rrhh",
        type_="check",
    )
    op.create_check_constraint(
        op.f("ck_ajuste_salarial_motivo_ajuste_enum"),
        "ajuste_salarial",
        "motivo IN ('decreto_anual', 'renovacion', 'merito', 'promocion')",
        schema="rrhh",
    )

    op.drop_constraint(op.f("ck_contrato_estado_contrato_enum"), "contrato", schema="rrhh", type_="check")
    op.create_check_constraint(
        op.f("ck_contrato_estado_contrato_enum"),
        "contrato",
        "estado IN ('activo', 'finalizado', 'rescindido')",
        schema="rrhh",
    )

    op.drop_constraint(op.f("chk_permiso_horas"), "justificacion_ausencia", schema="rrhh", type_="check")
    op.drop_constraint(op.f("chk_justificacion_fechas"), "justificacion_ausencia", schema="rrhh", type_="check")

    op.drop_column("vacacion", "horas_pendientes", schema="rrhh")

    op.drop_constraint(op.f("chk_parametro_tipo_aporte"), "parametro_impuesto", schema="rrhh", type_="check")
    op.drop_column("parametro_impuesto", "tipo_aporte", schema="rrhh")

    op.drop_constraint(
        op.f("fk_incidencia_marcacion_id_resuelto_por_empleado"),
        "incidencia_marcacion",
        schema="rrhh",
        type_="foreignkey",
    )
    op.create_foreign_key(
        op.f("fk_incidencia_marcacion_id_resuelto_por_usuario"),
        "incidencia_marcacion",
        "usuario",
        ["id_resuelto_por"],
        ["id"],
        source_schema="rrhh",
        referent_schema="rrhh",
        ondelete="SET NULL",
    )

    op.drop_constraint(op.f("uq_empleado_ci"), "empleado", schema="rrhh", type_="unique")

    op.drop_constraint(
        op.f("fk_beneficio_cumpleanos_id_justificacion_justificacion_ausencia"),
        "beneficio_cumpleanos",
        schema="rrhh",
        type_="foreignkey",
    )
