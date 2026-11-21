"""Vuelca a JSON el contenido de DWG (solo lectura) con Civil 3D sin ventana: alineamientos, perfiles,
superficies y puntos COGO si los hay, y si no (planos explotados) textos, polilíneas, líneas y bloques
por capa. Lo usa importar_nunoa.py.

    python herramientas/extraer_dwg.py <carpeta_o_dwg> <carpeta_json> [patron]

Necesita el complemento compilado (dotnet build civil3d_verificador -c Release): comando CS_EXTRAER.
Los DWG se abren en una base de datos lateral, de solo lectura: no se modifican.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verificar_civil3d import C3D, DLL, PLANTILLA  # noqa: E402


def extraer(dwgs, salida, timeout=3600):
    salida = Path(salida).resolve()
    salida.mkdir(parents=True, exist_ok=True)
    scr = Path(tempfile.mkdtemp()) / "extraer.scr"
    scr.write_text("\n".join([
        '(setvar "SECURELOAD" 0)',
        '(setvar "FILEDIA" 0)',
        f'(command "_.NETLOAD" "{DLL.as_posix()}")',
        "CS_EXTRAER",
        "_.QUIT",
        "_Y",
        "",
    ]), encoding="utf-8")
    env = dict(os.environ, CS_EXT_DWG=";".join(str(Path(d).resolve()) for d in dwgs), CS_EXT_OUT=str(salida))
    cmd = [str(C3D / "accoreconsole.exe"), "/i", str(PLANTILLA), "/s", str(scr),
           "/ld", str(C3D / "AecBase.dbx"), "/p", "<<C3D_Metric>>", "/product", "C3D", "/language", "en-US"]
    r = subprocess.run(cmd, env=env, capture_output=True, timeout=timeout)
    texto = (r.stdout + r.stderr).decode("utf-16-le", errors="ignore")
    (salida / "accoreconsole.log").write_text(texto, encoding="utf-8")
    return sorted(salida.glob("*.json"))


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 1
    origen, salida = Path(argv[0]), argv[1]
    patron = argv[2] if len(argv) > 2 else "*.dwg"
    dwgs = [origen] if origen.is_file() else sorted(origen.glob(patron))
    for f in extraer(dwgs, salida):
        print(f)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
