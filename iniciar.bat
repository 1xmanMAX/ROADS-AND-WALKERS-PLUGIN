@echo off
REM Abre Corredor Simple sin crear el ejecutable (requiere Python instalado).
python -m pip install -q -r requirements.txt
python CorredorSimple.py %*
