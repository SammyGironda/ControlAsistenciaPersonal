"""
RRHH Bolivia MVP - Punto de entrada de la aplicación.
FastAPI + SQLAlchemy 2.0 + PostgreSQL

Para ejecutar:
    uvicorn app.main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings

settings = get_settings()

# --- Crear aplicación FastAPI ---
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Sistema de Recursos Humanos para Bolivia - MVP",
    docs_url="/docs",
    redoc_url="/redoc"
)

# --- Configurar CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# I 

# --- Endpoint de salud ---
@app.get("/", tags=["Health"])
def root():
    """Endpoint raíz - verifica que la API está activa."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health", tags=["Health"])
def health_check():
    """Health check para monitoreo."""
    return {"status": "healthy"}


# ============================================================
# IMPORTAR TODOS LOS MODELOS PRIMERO
# Esto asegura que SQLAlchemy pueda resolver todas las relaciones
# ============================================================
from app.features.employees.departamento.models import Departamento, ComplementoDep  # noqa: F401
from app.features.employees.cargo.models import Cargo  # noqa: F401
from app.features.employees.empleado.models import Empleado  # noqa: F401
from app.features.employees.horario.models import Horario, AsignacionHorario  # noqa: F401
from app.features.auth.rol.models import Rol  # noqa: F401
from app.features.auth.usuario.models import Usuario  # noqa: F401

# --- Semana 4: Contracts ---
from app.features.contracts.contrato.models import Contrato, TipoContratoEnum, EstadoContratoEnum  # noqa: F401
from app.features.contracts.ajuste_salarial.models import (  # noqa: F401
    AjusteSalarial, DecretoIncrementoSalarial, CondicionDecreto,
    ParametroImpuesto, MotivoAjusteEnum
)

# --- Semana 5: Attendance - Marcaciones ---
from app.features.attendance.marcacion.models import (  # noqa: F401
    Marcacion, ArchivoExcel, IncidenciaMarcacion,
    OrigenDatoEnum, TipoMarcacionEnum, EstadoProcesamientoEnum,
    TipoIncidenciaEnum, EstadoResolucionEnum
)

# --- Semana 6: Attendance - Asistencia Diaria ---
from app.features.attendance.asistencia_diaria.models import AsistenciaDiaria, EstadoDiaEnum  # noqa: F401

# --- Semana 7: Attendance - Feriados, Justificaciones y Vacaciones ---
from app.features.attendance.feriados.models import DiaFestivo, AmbitoFestivoEnum  # noqa: F401
from app.features.attendance.beneficio_cumpleanos.models import BeneficioCumpleanos  # noqa: F401
from app.features.attendance.justificacion.models import (  # noqa: F401
    JustificacionAusencia, TipoJustificacionEnum, TipoPermisoEnum, EstadoAprobacionEnum
)
from app.features.attendance.vacaciones.models import (  # noqa: F401
    Vacacion, DetalleVacacion, TipoVacacionEnum, EstadoDetalleVacacionEnum
)


# ============================================================
# ROUTERS - Se agregan por semana
# ============================================================

# --- Semana 2: Auth ---
from app.features.auth.rol.router import router as rol_router
from app.features.auth.usuario.router import router as usuario_router
app.include_router(rol_router, prefix=settings.API_PREFIX)
app.include_router(usuario_router, prefix=settings.API_PREFIX)

# --- Semana 3: Employees ---
from app.features.employees.departamento.router import router as departamento_router
from app.features.employees.cargo.router import router as cargo_router
from app.features.employees.empleado.router import router as empleado_router
from app.features.employees.horario.router import router as horario_router
app.include_router(departamento_router, prefix=settings.API_PREFIX)
app.include_router(cargo_router, prefix=settings.API_PREFIX)
app.include_router(empleado_router, prefix=settings.API_PREFIX)
app.include_router(horario_router, prefix=settings.API_PREFIX)

# --- Semana 4: Contracts ---
from app.features.contracts.contrato.router import router as contrato_router
from app.features.contracts.ajuste_salarial.router import router as ajuste_salarial_router
app.include_router(contrato_router, prefix=settings.API_PREFIX)
app.include_router(ajuste_salarial_router, prefix=settings.API_PREFIX)

# --- Semana 5: Attendance - Marcaciones ---
from app.features.attendance.marcacion.router import router as marcacion_router
app.include_router(marcacion_router, prefix=settings.API_PREFIX)

# --- Semana 6: Attendance - Asistencia Diaria ---
from app.features.attendance.asistencia_diaria.router import router as asistencia_diaria_router
app.include_router(asistencia_diaria_router, prefix=settings.API_PREFIX)

# --- Semana 7: Attendance - Feriados, Justificaciones y Vacaciones ---
from app.features.attendance.router import router as attendance_router
from app.features.attendance.feriados.router import router as feriados_router
from app.features.attendance.beneficio_cumpleanos.router import router as beneficio_cumpleanos_router
from app.features.attendance.justificacion.router import router as justificacion_router
from app.features.attendance.vacaciones.router import router as vacaciones_router
app.include_router(attendance_router, prefix=settings.API_PREFIX)
app.include_router(feriados_router, prefix=settings.API_PREFIX)
app.include_router(beneficio_cumpleanos_router, prefix=settings.API_PREFIX)
app.include_router(justificacion_router, prefix=settings.API_PREFIX)
app.include_router(vacaciones_router, prefix=settings.API_PREFIX)

# --- Semana 8: Reports ---
# from app.features.reports.reporte.router import router as reporte_router
# app.include_router(reporte_router, prefix=settings.API_PREFIX)


# ============================================================
# WORKER AUTOMÁTICO - Semana 6
# ============================================================
from app.features.attendance.worker import start_scheduler, shutdown_scheduler, get_scheduler_status


@app.on_event("startup")
async def startup_event():
    """Iniciar worker de asistencia diaria al arrancar la aplicación."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info("🚀 Iniciando aplicación RRHH Bolivia MVP...")
    
    # Iniciar scheduler de asistencia diaria
    try:
        start_scheduler()
        logger.info("✅ Worker de asistencia diaria iniciado correctamente")
    except Exception as e:
        logger.error(f"❌ Error al iniciar worker: {str(e)}", exc_info=True)


@app.on_event("shutdown")
async def shutdown_event():
    """Detener worker al apagar la aplicación."""
    import logging
    logger = logging.getLogger(__name__)
    logger.info("🛑 Deteniendo aplicación...")
    
    # Detener scheduler
    try:
        shutdown_scheduler()
        logger.info("✅ Worker de asistencia diaria detenido correctamente")
    except Exception as e:
        logger.error(f"❌ Error al detener worker: {str(e)}", exc_info=True)


@app.get("/worker/status", tags=["Worker"])
def worker_status():
    """Endpoint para verificar el estado del worker de asistencia."""
    return get_scheduler_status()
