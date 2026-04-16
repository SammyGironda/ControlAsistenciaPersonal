@echo off
REM ============================================================
REM Script para corregir error de bcrypt
REM Ejecutar desde: d:\DOCUMENTOS\Desktop\BLUENET\02PROYECTO\v13
REM ============================================================

echo.
echo ========================================
echo CORRIGIENDO ERROR BCRYPT
echo ========================================
echo.

REM Paso 1: Desinstalar bcrypt incompatible
echo [1/6] Desinstalando bcrypt incompatible...
call venv\Scripts\activate.bat
python -m pip uninstall bcrypt -y
if errorlevel 1 (
    echo ERROR: No se pudo desinstalar bcrypt
    pause
    exit /b 1
)
echo OK - bcrypt desinstalado
echo.

REM Paso 2: Instalar bcrypt compatible
echo [2/6] Instalando bcrypt 4.0.1...
python -m pip install bcrypt==4.0.1
if errorlevel 1 (
    echo ERROR: No se pudo instalar bcrypt 4.0.1
    pause
    exit /b 1
)
echo OK - bcrypt 4.0.1 instalado
echo.

REM Paso 3: Verificar versión
echo [3/6] Verificando versión instalada...
python -m pip list | findstr bcrypt
echo.

REM Paso 4: Generar migración
echo [4/6] Generando migracion para quitar email de usuario...
alembic revision --autogenerate -m "semana2_fix_quitar_email_usuario"
if errorlevel 1 (
    echo ERROR: No se pudo generar migracion
    pause
    exit /b 1
)
echo OK - Migracion generada
echo.

REM Paso 5: Aplicar migración
echo [5/6] Aplicando migracion...
alembic upgrade head
if errorlevel 1 (
    echo ERROR: No se pudo aplicar migracion
    pause
    exit /b 1
)
echo OK - Migracion aplicada
echo.

REM Paso 6: Mostrar estado
echo [6/6] Verificando estado de alembic...
alembic current
echo.

echo ========================================
echo CORRECCION COMPLETADA
echo ========================================
echo.
echo Ahora puedes iniciar el servidor con:
echo uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
echo.
pause
