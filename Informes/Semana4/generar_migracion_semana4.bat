@echo off
REM Script para generar migración de Semana 4
cd /d "%~dp0"
venv\Scripts\python.exe -m alembic revision --autogenerate -m "semana4_modulo_contracts"
pause

