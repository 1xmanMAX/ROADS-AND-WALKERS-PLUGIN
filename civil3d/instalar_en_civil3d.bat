@echo off
REM Instala el complemento Corredor Simple para Civil 3D 2025 (autocarga al iniciar Civil 3D).
set DESTINO=%APPDATA%\Autodesk\ApplicationPlugins\CorredorSimple.bundle
if exist "%DESTINO%" rmdir /s /q "%DESTINO%"
xcopy /e /i /y "%~dp0CorredorSimple.bundle" "%DESTINO%" >nul
echo Instalado en %DESTINO%
echo Abra Civil 3D 2025 y escriba CSAYUDA. Para importar: CSIMPORTAR.
echo (Si Civil 3D ya estaba abierto, cierrelo y vuelva a abrirlo, o use NETLOAD con el .dll)
pause
