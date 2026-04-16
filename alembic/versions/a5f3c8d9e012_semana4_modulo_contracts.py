"""semana4_modulo_contracts

Revision ID: a5f3c8d9e012
Revises: 2df89d16a050
Create Date: 2026-04-01 17:04:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a5f3c8d9e012'
down_revision: Union[str, None] = '2df89d16a050'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ============================================================
    # PASO 1: Crear ENUMs
    # ============================================================
    op.execute("""
        CREATE TYPE tipo_contrato_enum AS ENUM ('indefinido', 'plazo_fijo');
    """)
    op.execute("""
        CREATE TYPE estado_contrato_enum AS ENUM ('activo', 'finalizado', 'rescindido');
    """)
    op.execute("""
        CREATE TYPE motivo_ajuste_enum AS ENUM ('decreto_anual', 'renovacion', 'merito', 'promocion');
    """)
    
    # ============================================================
    # PASO 2: Crear tablas
    # ============================================================
    
    # --- Tabla: decreto_incremento_salarial ---
    op.create_table('decreto_incremento_salarial',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('anio', sa.Integer(), nullable=False, comment='Año del decreto (ej: 2024)'),
        sa.Column('nuevo_smn', sa.Numeric(precision=10, scale=2), nullable=False, comment='Nuevo Salario Mínimo Nacional en Bs.'),
        sa.Column('fecha_vigencia', sa.Date(), nullable=False, comment='Fecha desde la cual rige el decreto'),
        sa.Column('referencia_decreto', sa.String(length=100), nullable=False, comment="Ej: 'DS 4984' o 'DS 5001' - Referencia oficial del Decreto Supremo"),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_decreto_incremento_salarial')),
        sa.UniqueConstraint('anio', name=op.f('uq_decreto_incremento_salarial_anio')),
        schema='rrhh'
    )
    
    # --- Tabla: condicion_decreto ---
    op.create_table('condicion_decreto',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('id_decreto', sa.Integer(), nullable=False),
        sa.Column('orden', sa.Integer(), nullable=False, comment='Prioridad de evaluación (el backend toma el primer tramo coincidente)'),
        sa.Column('salario_desde', sa.Numeric(precision=10, scale=2), nullable=True, comment='NULL = aplica desde cualquier salario (sin límite inferior)'),
        sa.Column('salario_hasta', sa.Numeric(precision=10, scale=2), nullable=True, comment='NULL = aplica hasta cualquier salario (sin límite superior)'),
        sa.Column('porcentaje_incremento', sa.Numeric(precision=5, scale=2), nullable=False, comment='Porcentaje de incremento (ej: 5.00 = 5%)'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('salario_desde IS NULL OR salario_hasta IS NULL OR salario_desde < salario_hasta', name=op.f('chk_condicion_decreto_salarios')),
        sa.CheckConstraint('porcentaje_incremento >= 0', name=op.f('chk_condicion_decreto_porcentaje')),
        sa.ForeignKeyConstraint(['id_decreto'], ['rrhh.decreto_incremento_salarial.id'], name=op.f('fk_condicion_decreto_id_decreto_decreto_incremento_salarial'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_condicion_decreto')),
        schema='rrhh'
    )
    
    # --- Tabla: contrato ---
    op.create_table('contrato',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('id_empleado', sa.Integer(), nullable=False),
        sa.Column('tipo_contrato', sa.Enum('indefinido', 'plazo_fijo', name='tipo_contrato_enum', native_enum=False, create_constraint=True), nullable=False),
        sa.Column('fecha_inicio', sa.Date(), nullable=False),
        sa.Column('fecha_fin', sa.Date(), nullable=True, comment='NULL = contrato indefinido'),
        sa.Column('salario_base', sa.Numeric(precision=10, scale=2), nullable=False, comment='Salario inicial del contrato en Bs.'),
        sa.Column('estado', sa.Enum('activo', 'finalizado', 'rescindido', name='estado_contrato_enum', native_enum=False, create_constraint=True), nullable=False),
        sa.Column('documento_contrato_url', sa.String(length=255), nullable=True, comment='URL del contrato escaneado o digital'),
        sa.Column('observacion', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('fecha_fin IS NULL OR fecha_fin > fecha_inicio', name=op.f('chk_contrato_fechas')),
        sa.CheckConstraint("tipo_contrato = 'indefinido' OR fecha_fin IS NOT NULL", name=op.f('chk_plazo_fijo_fecha_fin')),
        sa.CheckConstraint('salario_base > 0', name=op.f('chk_contrato_salario')),
        sa.ForeignKeyConstraint(['id_empleado'], ['rrhh.empleado.id'], name=op.f('fk_contrato_id_empleado_empleado'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_contrato')),
        schema='rrhh'
    )
    
    # --- Tabla: parametro_impuesto ---
    op.create_table('parametro_impuesto',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('nombre', sa.String(length=50), nullable=False, comment='Nombre del concepto: RC_IVA, AFP_LABORAL, AFP_PATRONAL, etc.'),
        sa.Column('porcentaje', sa.Numeric(precision=5, scale=2), nullable=False, comment='Porcentaje aplicable (ej: 13.00 = 13%)'),
        sa.Column('fecha_vigencia_inicio', sa.Date(), nullable=False),
        sa.Column('fecha_vigencia_fin', sa.Date(), nullable=True, comment='NULL = vigente indefinidamente'),
        sa.Column('descripcion', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('fecha_vigencia_fin IS NULL OR fecha_vigencia_fin > fecha_vigencia_inicio', name=op.f('chk_parametro_fechas')),
        sa.CheckConstraint('porcentaje >= 0', name=op.f('chk_parametro_porcentaje')),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_parametro_impuesto')),
        schema='rrhh'
    )
    
    # --- Tabla: ajuste_salarial ---
    op.create_table('ajuste_salarial',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('id_empleado', sa.Integer(), nullable=False),
        sa.Column('id_contrato', sa.Integer(), nullable=False),
        sa.Column('id_condicion_decreto', sa.Integer(), nullable=True, comment='Si motivo=decreto_anual, registra qué tramo del decreto se aplicó'),
        sa.Column('salario_anterior', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('salario_nuevo', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('fecha_vigencia', sa.Date(), nullable=False, comment='Fecha desde la cual rige el nuevo salario'),
        sa.Column('motivo', sa.Enum('decreto_anual', 'renovacion', 'merito', 'promocion', name='motivo_ajuste_enum', native_enum=False, create_constraint=True), nullable=False),
        sa.Column('id_aprobado_por', sa.Integer(), nullable=True, comment='Empleado que aprobó el ajuste (ej: RRHH o supervisor)'),
        sa.Column('observacion', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.CheckConstraint('salario_anterior <> salario_nuevo', name=op.f('chk_ajuste_salario_distinto')),
        sa.CheckConstraint('salario_anterior > 0 AND salario_nuevo > 0', name=op.f('chk_ajuste_salarios_positivos')),
        sa.ForeignKeyConstraint(['id_aprobado_por'], ['rrhh.empleado.id'], name=op.f('fk_ajuste_salarial_id_aprobado_por_empleado'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['id_condicion_decreto'], ['rrhh.condicion_decreto.id'], name=op.f('fk_ajuste_salarial_id_condicion_decreto_condicion_decreto'), ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['id_contrato'], ['rrhh.contrato.id'], name=op.f('fk_ajuste_salarial_id_contrato_contrato'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['id_empleado'], ['rrhh.empleado.id'], name=op.f('fk_ajuste_salarial_id_empleado_empleado'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_ajuste_salarial')),
        schema='rrhh'
    )
    
    # ============================================================
    # PASO 3: Crear funciones PL/pgSQL
    # ============================================================
    
    # --- Función: fn_horas_vacacion_lgt ---
    op.execute("""
        CREATE OR REPLACE FUNCTION rrhh.fn_horas_vacacion_lgt(
            p_fecha_ingreso  DATE,
            p_fecha_calculo  DATE DEFAULT CURRENT_DATE
        )
        RETURNS NUMERIC(6,1)
        LANGUAGE plpgsql
        IMMUTABLE
        AS $$
        DECLARE
            v_anios NUMERIC;
        BEGIN
            v_anios := EXTRACT(YEAR FROM AGE(p_fecha_calculo, p_fecha_ingreso))
                     + EXTRACT(MONTH FROM AGE(p_fecha_calculo, p_fecha_ingreso)) / 12.0;

            RETURN CASE
                WHEN v_anios < 1.0  THEN 0.0
                WHEN v_anios < 5.0  THEN 120.0
                WHEN v_anios < 10.0 THEN 160.0
                ELSE                     240.0
            END;
        END;
        $$;
    """)
    
    op.execute("""
        COMMENT ON FUNCTION rrhh.fn_horas_vacacion_lgt(DATE, DATE) IS
        'LGT Art.44: calcula horas de vacación según antigüedad. <1yr=0h, 1-5yr=120h(15días), 5-10yr=160h(20días), 10+yr=240h(30días). Base: 8h/día. Usar al crear el registro de vacacion para cada gestión.';
    """)
    
    # --- Función: fn_porcentaje_incremento_decreto ---
    op.execute("""
        CREATE OR REPLACE FUNCTION rrhh.fn_porcentaje_incremento_decreto(
            p_id_decreto   INTEGER,
            p_salario      NUMERIC(10,2)
        )
        RETURNS NUMERIC(5,2)
        LANGUAGE plpgsql
        STABLE
        AS $$
        DECLARE
            v_porcentaje NUMERIC(5,2);
        BEGIN
            SELECT porcentaje_incremento
            INTO   v_porcentaje
            FROM   rrhh.condicion_decreto
            WHERE  id_decreto = p_id_decreto
              AND  (salario_desde IS NULL OR p_salario >= salario_desde)
              AND  (salario_hasta IS NULL OR p_salario <= salario_hasta)
            ORDER BY orden
            LIMIT 1;

            IF NOT FOUND THEN
                RAISE EXCEPTION 'No se encontró tramo aplicable en decreto % para salario %',
                    p_id_decreto, p_salario;
            END IF;

            RETURN v_porcentaje;
        END;
        $$;
    """)
    
    op.execute("""
        COMMENT ON FUNCTION rrhh.fn_porcentaje_incremento_decreto(INTEGER, NUMERIC) IS
        'Retorna el porcentaje del primer tramo (ORDER BY orden) del decreto que aplica al salario dado. Lanza excepción si no hay tramo. Usar al registrar ajuste_salarial por decreto_anual.';
    """)
    
    # ============================================================
    # PASO 4: Crear trigger sync_salario_empleado
    # ============================================================
    
    # --- Función del trigger ---
    op.execute("""
        CREATE OR REPLACE FUNCTION rrhh.fn_sync_salario_empleado()
        RETURNS TRIGGER
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.fecha_vigencia <= CURRENT_DATE THEN
                UPDATE rrhh.empleado
                SET    salario_base = NEW.salario_nuevo,
                       updated_at   = NOW()
                WHERE  id = NEW.id_empleado;
            END IF;
            RETURN NEW;
        END;
        $$;
    """)
    
    op.execute("""
        COMMENT ON FUNCTION rrhh.fn_sync_salario_empleado() IS
        'Sincroniza empleado.salario_base al insertar en ajuste_salarial, solo si fecha_vigencia <= hoy. Para ajustes futuros (ej: decreto publicado antes del 1/may), el worker diario debe ejecutar la actualización en la fecha_vigencia.';
    """)
    
    # --- Crear trigger ---
    op.execute("""
        CREATE TRIGGER trg_sync_salario_empleado
            AFTER INSERT ON rrhh.ajuste_salarial
            FOR EACH ROW EXECUTE FUNCTION rrhh.fn_sync_salario_empleado();
    """)


def downgrade() -> None:
    # ============================================================
    # PASO 1: Eliminar trigger y funciones
    # ============================================================
    op.execute("DROP TRIGGER IF EXISTS trg_sync_salario_empleado ON rrhh.ajuste_salarial;")
    op.execute("DROP FUNCTION IF EXISTS rrhh.fn_sync_salario_empleado();")
    op.execute("DROP FUNCTION IF EXISTS rrhh.fn_porcentaje_incremento_decreto(INTEGER, NUMERIC);")
    op.execute("DROP FUNCTION IF EXISTS rrhh.fn_horas_vacacion_lgt(DATE, DATE);")
    
    # ============================================================
    # PASO 2: Eliminar tablas (en orden inverso por dependencias)
    # ============================================================
    op.drop_table('ajuste_salarial', schema='rrhh')
    op.drop_table('parametro_impuesto', schema='rrhh')
    op.drop_table('contrato', schema='rrhh')
    op.drop_table('condicion_decreto', schema='rrhh')
    op.drop_table('decreto_incremento_salarial', schema='rrhh')
    
    # ============================================================
    # PASO 3: Eliminar ENUMs (DESPUÉS de drop tables)
    # ============================================================
    op.execute("DROP TYPE IF EXISTS motivo_ajuste_enum;")
    op.execute("DROP TYPE IF EXISTS estado_contrato_enum;")
    op.execute("DROP TYPE IF EXISTS tipo_contrato_enum;")
