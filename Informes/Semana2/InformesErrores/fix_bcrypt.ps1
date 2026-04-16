# ============================================================
# Script PowerShell para corregir error de bcrypt
# Ejecutar desde: d:\DOCUMENTOS\Desktop\BLUENET\02PROYECTO\v13
# ============================================================

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "CORRIGIENDO ERROR BCRYPT" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Cambiar al directorio del proyecto
Set-Location "d:\DOCUMENTOS\Desktop\BLUENET\02PROYECTO\v13"

# Paso 1: Desinstalar bcrypt incompatible
Write-Host "[1/6] Desinstalando bcrypt incompatible..." -ForegroundColor Yellow
& ".\venv\Scripts\python.exe" -m pip uninstall bcrypt -y
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: No se pudo desinstalar bcrypt" -ForegroundColor Red
    exit 1
}
Write-Host "OK - bcrypt desinstalado" -ForegroundColor Green
Write-Host ""

# Paso 2: Instalar bcrypt compatible
Write-Host "[2/6] Instalando bcrypt 4.0.1..." -ForegroundColor Yellow
& ".\venv\Scripts\python.exe" -m pip install bcrypt==4.0.1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: No se pudo instalar bcrypt 4.0.1" -ForegroundColor Red
    exit 1
}
Write-Host "OK - bcrypt 4.0.1 instalado" -ForegroundColor Green
Write-Host ""

# Paso 3: Verificar versión
Write-Host "[3/6] Verificando version instalada..." -ForegroundColor Yellow
& ".\venv\Scripts\python.exe" -m pip list | Select-String "bcrypt"
Write-Host ""

# Paso 4: Generar migración
Write-Host "[4/6] Generando migracion para quitar email de usuario..." -ForegroundColor Yellow
& ".\venv\Scripts\alembic.exe" revision --autogenerate -m "semana2_fix_quitar_email_usuario"
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: No se pudo generar migracion" -ForegroundColor Red
    exit 1
}
Write-Host "OK - Migracion generada" -ForegroundColor Green
Write-Host ""

# Paso 5: Aplicar migración
Write-Host "[5/6] Aplicando migracion..." -ForegroundColor Yellow
& ".\venv\Scripts\alembic.exe" upgrade head
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: No se pudo aplicar migracion" -ForegroundColor Red
    exit 1
}
Write-Host "OK - Migracion aplicada" -ForegroundColor Green
Write-Host ""

# Paso 6: Mostrar estado
Write-Host "[6/6] Verificando estado de alembic..." -ForegroundColor Yellow
& ".\venv\Scripts\alembic.exe" current
Write-Host ""

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "CORRECCION COMPLETADA" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Ahora puedes iniciar el servidor con:" -ForegroundColor Yellow
Write-Host ".\venv\Scripts\uvicorn.exe app.main:app --reload --host 0.0.0.0 --port 8000" -ForegroundColor White
Write-Host ""
