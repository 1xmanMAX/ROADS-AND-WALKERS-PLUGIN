"""Instala el complemento de Corredor Simple para que Civil 3D 2025 lo cargue solo al iniciar.

    python herramientas/instalar_civil3d.py            instala (o actualiza)
    python herramientas/instalar_civil3d.py --quitar   desinstala

Crea %APPDATA%\\Autodesk\\ApplicationPlugins\\CorredorSimple.bundle (carpeta de complementos que Civil 3D
carga al iniciar, sin NETLOAD) con el .dll y un corredor_simple.json que dice dónde están Python y la
app. Después, en Civil 3D: CS_GENERAR -> carpeta del proyecto.
Compile antes: dotnet build civil3d_verificador -c Release
"""
import json
import os
import shutil
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
BIN = RAIZ / "civil3d_verificador" / "bin" / "Release" / "net8.0-windows"
DESTINO = Path(os.environ.get("APPDATA", "")) / "Autodesk" / "ApplicationPlugins" / "CorredorSimple.bundle"

PAQUETE = """<?xml version="1.0" encoding="utf-8"?>
<ApplicationPackage SchemaVersion="1.0" AppVersion="1.0" Name="Corredor Simple"
    Description="Pistas y veredas: genera en Civil 3D el modelo de Corredor Simple (CS_GENERAR)"
    ProductCode="{6E0C9C1B-5D2A-4C55-9A3E-2B7C1F0D8A11}" UpgradeCode="{0B3F8E62-91C4-4E7B-8B1D-5A6C2E9F4D30}"
    Author="Corredor Simple">
  <CompanyDetails Name="Corredor Simple" />
  <Components>
    <RuntimeRequirements OS="Win64" Platform="AutoCAD*" SeriesMin="R25.0" SeriesMax="R25.0" />
    <ComponentEntry AppName="CorredorSimple" ModuleName="./Contents/C3DVerificador.dll"
        LoadOnAutoCADStartup="True" AppDescription="Corredor Simple para Civil 3D">
      <Commands GroupName="CORREDOR_SIMPLE">
        <Command Global="CS_GENERAR" Local="CS_GENERAR" />
        <Command Global="CS_PRESENTAR" Local="CS_PRESENTAR" />
        <Command Global="CS_VERIFICAR" Local="CS_VERIFICAR" />
        <Command Global="CS_EXTRAER" Local="CS_EXTRAER" />
      </Commands>
    </ComponentEntry>
  </Components>
</ApplicationPackage>
"""


def instalar():
    if not (BIN / "C3DVerificador.dll").exists():
        raise SystemExit(f"Falta {BIN / 'C3DVerificador.dll'}: compile con 'dotnet build civil3d_verificador -c Release'.")
    cont = DESTINO / "Contents"
    if cont.exists():
        shutil.rmtree(cont)          # Civil 3D tiene que estar cerrado para reemplazar el .dll
    cont.mkdir(parents=True)
    for f in BIN.glob("C3DVerificador.*"):
        shutil.copy2(f, cont / f.name)
    py = shutil.which("py") or sys.executable
    (cont / "corredor_simple.json").write_text(json.dumps(
        {"python": sys.executable, "app": str(RAIZ), "nota": f"py encontrado: {py}"}, indent=1), encoding="utf-8")
    (DESTINO / "PackageContents.xml").write_text(PAQUETE, encoding="utf-8")
    print(f"Instalado en {DESTINO}\nAbra Civil 3D y escriba CS_GENERAR.")


def quitar():
    if DESTINO.exists():
        shutil.rmtree(DESTINO)
    print(f"Quitado {DESTINO}")


if __name__ == "__main__":
    quitar() if "--quitar" in sys.argv else instalar()
