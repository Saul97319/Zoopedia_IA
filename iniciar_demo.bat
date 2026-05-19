@echo off
echo =========================================
echo   Iniciando Zoopedia - Modo Demo Avanzado
echo =========================================

:: 1. Iniciar el backend en una nueva ventana (MODIFICADO)
echo Actualizando dirección de red...
call venv\Scripts\activate
python actualizar_ip.py

echo Iniciando el servidor FastAPI y el motor de IA...
start "Backend Zoopedia" cmd /k "call venv\Scripts\activate && cd backend && uvicorn main_api:app --host 0.0.0.0 --port 8000 --reload"

:: 2. Escáner dinámico: Esperar a que el puerto 8000 se abra
echo Esperando a que el servidor indique "Application startup complete"...

:esperar_servidor
:: Busca silenciosamente si el puerto 8000 ya esta escuchando (LISTENING)
netstat -ano | find "LISTENING" | find ":8000" >nul

:: Si el resultado es error (aún no existe el puerto), espera 1 segundo y repite
if %ERRORLEVEL% neq 0 (
    timeout /t 1 /nobreak > NUL
    goto esperar_servidor
)

:: 3. Cuando el puerto responde, abrimos el frontend inmediatamente
echo.
echo !Servidor en linea y listo! Abriendo la interfaz...
start "" "frontend\index.html"

exit