"""fix trigger compensacion horas extra: columnas NOT NULL faltantes

Revision ID: e5f2a8c1d904
Revises: c4d1e9f7a3b2
Create Date: 2026-08-12

`fn_compensacion_horas_extra_a_vacacion()`, creada en la migración
`122bc6566cae`, insertaba en `rrhh.vacacion` sólo cuatro columnas:

    INSERT INTO rrhh.vacacion (id_empleado, gestion,
                               horas_correspondientes, horas_goce_haber)

pero en producción esa tabla tiene otras cuatro columnas NOT NULL **sin
default**: `horas_sin_goce_haber`, `horas_tomadas`, `created_at` y
`updated_at`. Todo INSERT en `rrhh.compensacion_horas_extra` moría con:

    NotNullViolation: null value in column "horas_sin_goce_haber"
    of relation "vacacion" violates not-null constraint

El `ON CONFLICT (id_empleado, gestion) DO UPDATE` no lo evitaba: PostgreSQL
valida los NOT NULL al formar la tupla propuesta, ANTES de detectar el
conflicto. Por eso fallaba incluso cuando la fila de `vacacion` ya existía —
verificado contra el empleado 3, gestión 2026, que sí la tenía.

El fallo era invisible porque `registrar_compensacion` atrapaba cualquier
IntegrityError y devolvía None, y el router traducía ese None a un 409
"Ya existe una compensación registrada...". Los dos llamadores automáticos
(feriado trabajado al procesar el Excel, y viaje_trabajo aprobado que cae en
descanso) ignoraban el retorno, así que nunca acreditaron nada: al momento de
esta migración `rrhh.compensacion_horas_extra` tenía 0 filas.

Esta migración corrige la FUNCIÓN, no la tabla. Se prefiere sobre poner
DEFAULT a las columnas de `rrhh.vacacion` porque el problema es que el trigger
no declara los valores que le corresponden, y tocar los defaults de una tabla
central afecta a todo lo demás que escribe ahí.

No hace falta recrear el TRIGGER: CREATE OR REPLACE FUNCTION conserva el
binding existente de `trg_compensacion_horas_extra_a_vacacion`.

`horas_pendientes` es GENERATED ALWAYS, así que no puede aparecer en el INSERT.
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = 'e5f2a8c1d904'
down_revision = 'c4d1e9f7a3b2'
branch_labels = None
depends_on = None


# Versión corregida: declara las 4 columnas NOT NULL que faltaban y refresca
# updated_at también en la rama del UPDATE (rrhh.vacacion no tiene trigger de
# updated_at — ver discrepancia #11 de CLAUDE.md).
FUNCION_CORREGIDA = """
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

    INSERT INTO rrhh.vacacion (
        id_empleado,
        gestion,
        horas_correspondientes,
        horas_goce_haber,
        horas_sin_goce_haber,
        horas_tomadas,
        created_at,
        updated_at
    )
    VALUES (
        NEW.id_empleado,
        NEW.gestion,
        v_base_horas + NEW.horas,
        NEW.horas,
        0,
        0,
        NOW(),
        NOW()
    )
    ON CONFLICT (id_empleado, gestion) DO UPDATE
        SET horas_correspondientes = rrhh.vacacion.horas_correspondientes + NEW.horas,
            horas_goce_haber       = rrhh.vacacion.horas_goce_haber + NEW.horas,
            updated_at             = NOW();

    RETURN NEW;
END;
$$;
"""

# Versión original tal como quedó en 122bc6566cae. Se restaura tal cual para
# que el downgrade sea exactamente simétrico, aunque esté rota: revertir una
# migración debe devolver el estado anterior, no una variante.
FUNCION_ORIGINAL = """
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
"""


def upgrade() -> None:
    op.execute(FUNCION_CORREGIDA)


def downgrade() -> None:
    op.execute(FUNCION_ORIGINAL)
