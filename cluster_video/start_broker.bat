@echo off
REM Script para iniciar el Broker Service (servidor principal)

echo ========================================
echo Iniciando Broker Service en puerto 8001
echo ========================================
echo.

python -m uvicorn broker_service:app --reload --host 0.0.0.0 --port 8001

pause
