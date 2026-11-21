"""Generar el modelo en Civil 3D desde la app (sin pasos a mano).

    generar_dwg(proyecto, dwg)   Civil 3D sin ventana (accoreconsole) + comando CS_GENERAR del
                                 complemento: calcula con la app y arma alineamientos y perfiles nativos,
                                 superficies, modelo 3D (con esquinas, badenes, rampas) y códigos de campo.
    abrir(dwg)                   abre el DWG en el Civil 3D que esté abierto (o lo inicia) con la vista 3D.
    generar_y_abrir(proyecto)    las dos cosas: es lo que hace el botón "Generar en Civil 3D".

No cambia nada de la configuración del Civil 3D abierto: el cálculo y el armado se hacen en un proceso
aparte; en la sesión del usuario solo se abre el archivo resultante.
"""
import os
import subprocess
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
C3D = Path(os.environ.get("C3D_DIR", r"C:\Program Files\Autodesk\AutoCAD 2025"))
DLL = Path(os.environ.get("CS_DLL", RAIZ / "civil3d_verificador" / "bin" / "Release" / "net8.0-windows" / "C3DVerificador.dll"))
PLANTILLA = Path(os.environ.get("LOCALAPPDATA", "")) / "Autodesk" / "C3D 2025" / "enu" / "Template" / \
    "_Autodesk Civil 3D (Metric) NCS.dwt"


class ErrorCivil3D(RuntimeError):
    pass


def disponible():
    """(True, '') si se puede generar; si no (False, motivo)."""
    if not (C3D / "accoreconsole.exe").exists():
        return False, f"No se encontró Civil 3D en {C3D} (variable C3D_DIR)."
    if not DLL.exists():
        return False, f"Falta el complemento {DLL}: compile con 'dotnet build civil3d_verificador -c Release'."
    if not PLANTILLA.exists():
        return False, f"No se encontró la plantilla {PLANTILLA}."
    return True, ""


def _consola(script, env_extra, timeout):
    env = dict(os.environ, **env_extra)
    cmd = [str(C3D / "accoreconsole.exe"), "/i", str(PLANTILLA), "/s", str(script),
           "/ld", str(C3D / "AecBase.dbx"), "/p", "<<C3D_Metric>>", "/product", "C3D", "/language", "en-US"]
    r = subprocess.run(cmd, env=env, capture_output=True, timeout=timeout)
    return (r.stdout + r.stderr).decode("utf-16-le", errors="ignore")


def generar_dwg(proyecto, dwg=None, timeout=1800):
    """Arma el DWG del proyecto con CS_GENERAR. Devuelve (ruta_dwg, mensajes [CS])."""
    ok, motivo = disponible()
    if not ok:
        raise ErrorCivil3D(motivo)
    proyecto = Path(proyecto).resolve()
    dwg = Path(dwg).resolve() if dwg else proyecto / "salida_civil3d" / f"{proyecto.name}_corredor.dwg"
    dwg.parent.mkdir(parents=True, exist_ok=True)
    if dwg.exists():
        try:
            dwg.unlink()                    # SAVEAS no pregunta: se reemplaza
        except PermissionError:             # abierto en Civil 3D: se guarda con otro nombre
            import datetime as dt
            dwg = dwg.with_name(f"{dwg.stem}_{dt.datetime.now():%H%M%S}.dwg")
    tmp = Path(tempfile.mkdtemp(prefix="corredor_"))
    scr = tmp / "generar.scr"
    # SECURELOAD 0 solo en este proceso sin ventana (no toca la configuración del Civil 3D del usuario)
    scr.write_text("\n".join([
        '(setvar "SECURELOAD" 0)', '(setvar "FILEDIA" 0)',
        f'(command "_.NETLOAD" "{DLL.as_posix()}")',
        "CS_GENERAR",
        f'(command "_.SAVEAS" "2018" "{dwg.as_posix()}")',
        "_.QUIT", "_Y", ""]), encoding="utf-8")
    log = _consola(scr, {"CS_GEN_DIR": str(proyecto), "CS_APP_DIR": str(RAIZ)}, timeout)
    (dwg.parent / "civil3d_generar.log").write_text(log, encoding="utf-8")
    mensajes = [l.strip() for l in log.splitlines() if "[CS]" in l]
    if not dwg.exists():
        raise ErrorCivil3D("Civil 3D no generó el dibujo:\n" + "\n".join(mensajes[-10:]))
    return dwg, mensajes


_PS_ABRIR = r"""
$ErrorActionPreference = "Stop"
$dwg = $args[0]
function Reintentar($b) { for ($i = 0; $i -lt 240; $i++) { try { return & $b } catch { Start-Sleep -Milliseconds 500 } }; throw "Civil 3D no responde" }
try { $acad = [Runtime.InteropServices.Marshal]::GetActiveObject("AutoCAD.Application") } catch { $acad = $null }
if ($acad -eq $null) { "SIN_CIVIL3D"; exit 0 }
$doc = Reintentar { $acad.Documents.Open($dwg) }
Start-Sleep 2
$doc = Reintentar { $acad.ActiveDocument }
Reintentar { $doc.SendCommand('(command "_.-VIEW" "_SWISO" "_.VSCURRENT" "_R" "_.ZOOM" "_O" (ssget "X" (list (cons 8 "C3D-3D-*"))) "") ') } | Out-Null
"ABIERTO"
"""


def abrir(dwg):
    """Abre el DWG en el Civil 3D abierto; si no hay ninguno, inicia Civil 3D con el archivo."""
    dwg = str(Path(dwg).resolve())
    ps = Path(tempfile.mkdtemp(prefix="corredor_")) / "abrir.ps1"
    ps.write_text(_PS_ABRIR, encoding="utf-8")
    r = subprocess.run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ps), dwg],
                       capture_output=True, text=True, timeout=300)
    if "ABIERTO" in r.stdout:
        return "abierto en el Civil 3D activo"
    subprocess.Popen([str(C3D / "acad.exe"), "/ld", str(C3D / "AecBase.dbx"), "/p", "<<C3D_Metric>>",
                      "/product", "C3D", "/language", "en-US", dwg])
    return "iniciando Civil 3D con el dibujo"


def topografia_dwg(csv, dwg, timeout=1800):
    """DWG con los puntos COGO del levantamiento (PENZD) y la superficie TN con curvas (CS_TOPOGRAFIA)."""
    ok, motivo = disponible()
    if not ok:
        raise ErrorCivil3D(motivo)
    csv, dwg = Path(csv).resolve(), Path(dwg).resolve()
    if dwg.exists():
        dwg.unlink()
    scr = Path(tempfile.mkdtemp(prefix="corredor_")) / "topo.scr"
    scr.write_text("\n".join([
        '(setvar "SECURELOAD" 0)', '(setvar "FILEDIA" 0)',
        f'(command "_.NETLOAD" "{DLL.as_posix()}")',
        "CS_TOPOGRAFIA",
        f'(command "_.SAVEAS" "2018" "{dwg.as_posix()}")',
        "_.QUIT", "_Y", ""]), encoding="utf-8")
    log = _consola(scr, {"CS_TOPO_CSV": str(csv)}, timeout)
    mensajes = [l.strip() for l in log.splitlines() if "[CS]" in l]
    if not dwg.exists():
        raise ErrorCivil3D("Civil 3D no generó el dibujo:\n" + "\n".join(mensajes[-10:]))
    return dwg, mensajes


def generar_y_abrir(proyecto, dwg=None):
    dwg, mensajes = generar_dwg(proyecto, dwg)
    return dwg, mensajes, abrir(dwg)
