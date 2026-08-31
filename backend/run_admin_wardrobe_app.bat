@echo off
cd /d "%~dp0"

set "PYTHON_EXE=python"
if exist "%~dp0venv\Scripts\python.exe" set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
if exist "%~dp0venv\Scripts\pythonw.exe" set "PYTHON_W_EXE=%~dp0venv\Scripts\pythonw.exe"
if not defined PYTHON_W_EXE set "PYTHON_W_EXE=%PYTHON_EXE%"

echo Verificando dependencias de la app local...
"%PYTHON_EXE%" -c "import PIL, dotenv" >nul 2>&1
if errorlevel 1 (
    echo Instalando dependencias necesarias...
    "%PYTHON_EXE%" -m pip install -r requirements.txt
    if errorlevel 1 (
        echo No se pudieron instalar las dependencias.
        echo Intentando instalar la variante CPU de rembg...
        "%PYTHON_EXE%" -m pip install "rembg[cpu]"
        if errorlevel 1 (
            echo.
            echo No se pudo instalar todo lo necesario.
            echo Revisá que Python esté instalado y que tengas acceso a internet.
            pause
            exit /b 1
        )
    )
)

echo Lanzando AI Stylist Admin...
start "" "%PYTHON_W_EXE%" admin_seed_wardrobe_app.py
exit /b 0
