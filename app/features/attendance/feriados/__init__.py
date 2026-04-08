"""
Módulo de Feriados - SEMANA 7
Gestión de feriados nacionales y departamentales de Bolivia.
"""

from app.features.attendance.feriados.models import DiaFestivo, AmbitoFestivoEnum
from app.features.attendance.feriados.router import router as feriados_router

__all__ = ["DiaFestivo", "AmbitoFestivoEnum", "feriados_router"]
