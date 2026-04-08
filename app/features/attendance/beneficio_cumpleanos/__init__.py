"""
Módulo de Beneficio Cumpleaños - SEMANA 7
Gestión del medio día libre por cumpleaños (4 horas).
"""

from app.features.attendance.beneficio_cumpleanos.models import BeneficioCumpleanos
from app.features.attendance.beneficio_cumpleanos.router import router as beneficio_cumpleanos_router

__all__ = ["BeneficioCumpleanos", "beneficio_cumpleanos_router"]
