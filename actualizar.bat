@echo off
rem Actualiza los precios y los publica en GitHub. Correr desde una PC en Argentina.
cd /d "%~dp0"
git pull --quiet
python actualizar_precios.py
if errorlevel 1 exit /b 1
del /q sepa.zip 2>nul
git add data/precios.json
git commit -m "Precios actualizados %date%"
git push
