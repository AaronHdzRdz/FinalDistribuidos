@echo off
REM Script para iniciar un Worker
REM Edita ADMIN_HOST con la IP del servidor principal si estás en otra computadora

echo ========================================
echo Iniciando Worker Service
echo ========================================
echo.

REM Si estás en otra computadora, descomenta y edita la siguiente línea:
REM set ADMIN_HOST=192.168.1.100

echo ADMIN_HOST=%ADMIN_HOST%
echo WORKER_PORT=8002
echo.

python -m uvicorn worker_service:app --reload --host 0.0.0.0 --port 8002

pause
