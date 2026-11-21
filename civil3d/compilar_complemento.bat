@echo off
REM Recompila el complemento (requiere .NET 8 SDK). Las referencias de Autodesk se bajan de NuGet.
dotnet build "%~dp0CorredorSimpleC3D\CorredorSimpleC3D.csproj" -c Release || (pause & exit /b 1)
copy /y "%~dp0CorredorSimpleC3D\bin\Release\net8.0-windows\CorredorSimpleC3D.dll" "%~dp0CorredorSimple.bundle\Contents\" >nul
echo Listo: CorredorSimple.bundle\Contents\CorredorSimpleC3D.dll
pause
