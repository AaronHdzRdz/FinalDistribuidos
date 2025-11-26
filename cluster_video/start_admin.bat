@echo off
REM Script para iniciar el Admin Service (servidor principal)

echo ========================================
echo Iniciando Admin Service en puerto 8000
echo ========================================
echo.

python -m uvicorn admin_service:app --reload --host 0.0.0.0 --port 8000

pause
