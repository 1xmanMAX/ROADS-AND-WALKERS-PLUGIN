"""Toma capturas de pantalla de la app con los datos de ejemplo (para documentación).

Uso (Linux con Xvfb):  xvfb-run -s "-screen 0 1500x930x24" python herramientas/capturas.py <carpeta_salida>
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from corredor.app import App  # noqa: E402

salida = Path(sys.argv[1] if len(sys.argv) > 1 else "capturas")
salida.mkdir(parents=True, exist_ok=True)
app = App(str(Path(__file__).resolve().parent.parent / "datos_ejemplo"))
app.geometry("1500x930+0+0")
pasos = []


def foto(nombre):
    app.update()
    app.after(400)
    app.update()
    subprocess.run(["import", "-window", "root", str(salida / f"{nombre}.png")], check=True)
    print("captura", nombre)


def guion():
    app.calcular()
    app.v_bm.set("BM-01")
    app.v_la.set("1.425")
    for i, nombre in enumerate(["01_levantamiento", "02_calles", "03_capas"]):
        app.nb.select(i)
        foto(nombre)
    app.nb.select(3)
    app.v_vista.set("3D"); app.dibujar_vista(); foto("04_modelo3d")
    app.v_calle3d.set("EJE-01"); app._llenar_progs(); app.v_prog.set("0+050.00"); app.v_tramo.set(True)
    app.v_exag.set("3"); app.v_vista.set("3D"); app.dibujar_vista(); foto("04b_modelo3d_tramo_EJE-01")
    app.v_tramo.set(False); app.v_exag.set("5")
    app.v_calle3d.set("EJE-02"); app._llenar_progs()
    app.v_vista.set("Perfil"); app.dibujar_vista(); foto("05_perfil_EJE-02")
    app.v_calle3d.set("EJE-01"); app._llenar_progs()
    app.v_prog.set("0+050.00"); app.v_vista.set("Sección"); app.dibujar_vista(); foto("06_seccion_EJE-01_0+050")
    app.v_calle3d.set("EJE-02"); app._llenar_progs()
    app.v_prog.set("0+180.00"); app.v_vista.set("Sección"); app.dibujar_vista(); foto("07_seccion_EJE-02_0+180_relleno")
    app.nb.select(4)
    app.v_calle_t.set("EJE-01"); app.refrescar_tierras(); foto("08_tierras_EJE-01")
    app.v_calle_t.set("Resumen total"); app.refrescar_tierras(); foto("09_tierras_total")
    app.nb.select(5)
    foto("10_exportar_avisos")
    app.destroy()


app.after(500, guion)
app.mainloop()
