@echo off
cd /d "%~dp0"

echo Verificando dependencias de la app local...
python -c "import PIL, dotenv" >nul 2>&1
if errorlevel 1 (
    echo Instalando dependencias necesarias...
    python -m pip install -r requirements.txt
    if errorlevel 1 (
        echo.
        echo No se pudieron instalar las dependencias.
        echo Intentando instalar la variante CPU de rembg...
        python -m pip install "rembg[cpu]"
        if errorlevel 1 (
            echo.
            echo No se pudieron instalar ni rembg ni las dependencias.
            echo Revisá que Python esté instalado y que tengas acceso a internet.
            pause
            exit /b 1
        )
    )
)

echo Lanzando AI Stylist Admin...
python admin_seed_wardrobe_app.py
if errorlevel 1 (
    echo.
    echo La app falló al abrirse.
    echo Revisá que el archivo .env y la base de datos estén disponibles.
    echo.
    pause
)
