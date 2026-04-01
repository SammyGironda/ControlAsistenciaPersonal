from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool, text
from alembic import context

from app.core.config import get_settings
from app.db.base import Base

# ============================================================
# IMPORTAR TODOS LOS MODELOS AQUÍ
# Esto permite que Alembic detecte todos los modelos
# ============================================================
# --- Semana 1: Modelos base ---
from app.features.auth.rol.models import Rol  # noqa: F401
from app.features.employees.departamento.models import Departamento, ComplementoDep  # noqa: F401
from app.features.employees.cargo.models import Cargo  # noqa: F401
from app.features.employees.empleado.models import Empleado  # noqa: F401

# --- Semana 2: Auth ---
from app.features.auth.usuario.models import Usuario  # noqa: F401

# --- Semana 3: Horarios ---
from app.features.employees.horario.models import Horario, AsignacionHorario  # noqa: F401

# --- Semana 4: Contracts ---
from app.features.contracts.contrato.models import Contrato
from app.features.contracts.ajuste_salarial.models import AjusteSalarial

# --- Semana 5-7: Attendance ---
# from app.features.attendance.marcacion.models import Marcacion
# from app.features.attendance.asistencia_diaria.models import AsistenciaDiaria
# from app.features.attendance.feriados.models import DiaFestivo
# from app.features.attendance.beneficio_cumpleanos.models import BeneficioCumpleanos
# from app.features.attendance.justificacion.models import JustificacionAusencia

# --- Semana 8: Reports ---
# from app.features.reports.reporte.models import Reporte
# ============================================================

settings = get_settings()
config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_schemas=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_schemas=True,
            compare_type=True,
            # ← SIN version_table_schema: alembic_version va en public (siempre funciona)
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()