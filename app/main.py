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

# --- Semana 5-7: Attendance ---
# from app.features.attendance.router import router as attendance_router
# app.include_router(attendance_router, prefix=settings.API_PREFIX)

# --- Semana 8: Reports ---
# from app.features.reports.reporte.router import router as reporte_router
# app.include_router(reporte_router, prefix=settings.API_PREFIX)
