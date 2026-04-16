@echo off
REM ============================================================
REM SCRIPT DE EJECUCIÓN SEMANA 4 - FINALIZACIÓN
REM Sistema RRHH Bolivia
REM ============================================================

echo.
echo ========================================
echo  FINALIZACION SEMANA 4 - CONTRACTS
echo ========================================
echo.

REM Activar entorno virtual
echo [1/4] Activando entorno virtual...
call venv\Scripts\activate.bat

REM Verificar estado de migraciones
echo.
echo [2/4] Verificando estado de migraciones...
alembic current

echo.
echo [3/4] Ejecutando migración de Semana 4...
alembic upgrade head

echo.
echo [4/4] Verificando que todo se creo correctamente...
echo.
echo NOTA: Conéctate a PostgreSQL y ejecuta estos comandos:
echo.
echo -- Verificar tablas creadas:
echo SELECT table_name FROM information_schema.tables 
echo WHERE table_schema = 'rrhh' 
echo   AND table_name IN ('contrato', 'decreto_incremento_salarial', 'condicion_decreto', 'ajuste_salarial', 'parametro_impuesto');
echo.
echo -- Verificar funciones SQL:
echo SELECT routine_name FROM information_schema.routines 
echo WHERE routine_schema = 'rrhh' 
echo   AND routine_name IN ('fn_horas_vacacion_lgt', 'fn_porcentaje_incremento_decreto', 'fn_sync_salario_empleado');
echo.
echo -- Verificar trigger:
echo SELECT trigger_name FROM information_schema.triggers 
echo WHERE trigger_schema = 'rrhh' 
echo   AND trigger_name = 'trg_sync_salario_empleado';
echo.

echo.
echo ========================================
echo  EJECUCION COMPLETADA
echo ========================================
echo.
echo Ahora puedes:
echo   1. Arrancar el servidor: uvicorn app.main:app --reload --port 8000
echo   2. Abrir Swagger: http://localhost:8000/docs
echo   3. Probar los endpoints según Informes\Semana4\TESTING_MANUAL.md
echo.

pause
