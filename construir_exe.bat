@echo off
REM Crea dist\CorredorSimple\CorredorSimple.exe en Windows.
REM Requisitos: Python 3.11 o 3.12 de python.org (con "tcl/tk" marcado al instalar).
python -m pip install -r requirements.txt
python -m pytest -q || (echo Las pruebas fallaron & pause & exit /b 1)
python -m PyInstaller --noconfirm --windowed --name CorredorSimple ^
  --add-data "datos_ejemplo;datos_ejemplo" ^
  --hidden-import matplotlib.backends.backend_tkagg ^
  CorredorSimple.py
echo.
echo Listo: dist\CorredorSimple\CorredorSimple.exe
pause
