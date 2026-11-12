@echo off
cd /d "%~dp0"
echo Koolitee kaaslane - kaivitan veebirakenduse ja test-e-posti...
docker compose up --build
pause
