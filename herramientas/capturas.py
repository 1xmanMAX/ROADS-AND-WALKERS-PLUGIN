"""Capturas de pantalla de la app con el proyecto de ejemplo (documentación).

Linux:  xvfb-run -s "-screen 0 1560x960x24" python herramientas/capturas.py docs/capturas
"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from corredor.app import App  # noqa: E402

salida = Path(sys.argv[1] if len(sys.argv) > 1 else "capturas")
salida.mkdir(parents=True, exist_ok=True)
app = App(str(Path(__file__).resolve().parent.parent / "datos_ejemplo"))
app.geometry("1560x960+0+0")


def foto(nombre):
    for _ in range(3):
        app.update()
        app.after(300)
    subprocess.run(["import", "-window", "root", str(salida / f"{nombre}.png")], check=True)
    print("captura", nombre)


def guion():
    app.v_bm.set("BM-01")
    app.v_la.set("1.425")
    app.nb.select(app.tabs["lev"]); foto("01_levantamiento")
    app.nb.select(app.tabs["cal"]); foto("02_calles_ejes")
    app.nb.select(app.tabs["cap"]); foto("03_seccion_capas")
    app.nb.select(app.tabs["rev"])
    app.v_calle.set("EJE-01"); app._llenar_progs(); app.v_ir.set("50"); app._ir_a_prog(); foto("04_seccion_EJE-01_0+050")
    app.v_ir.set("85"); app._ir_a_prog(); foto("05_seccion_puerta_PU_0+085")
    app.v_calle.set("EJE-02"); app._llenar_progs(); app.v_ir.set("180"); app._ir_a_prog(); foto("06_seccion_relleno_EJE-02")
    app.v_vista.set("Perfil"); app.dibujar_vista(); foto("07_perfil_guitarra_EJE-02")
    app.v_vista.set("Planta"); app.dibujar_vista(); foto("08_planta_revision")
    app.v_calle.set("EJE-01"); app._llenar_progs(); app.v_ir.set("150"); app._ir_a_prog()
    app.v_vista.set("3D"); app.dibujar_vista(); foto("09_3d_tramo")
    app.nb.select(app.tabs["int"]); foto("10_interferencias")
    app.nb.select(app.tabs["tie"]); app.v_calle_t.set("EJE-02"); app.refrescar_tierras(); foto("11_tierras_EJE-02")
    app.v_calle_t.set("Resumen total"); app.refrescar_tierras(); foto("12_tierras_resumen")
    app.nb.select(app.tabs["pun"]); foto("13_puntos_bm")
    app.nb.select(app.tabs["exp"]); foto("14_exportar")
    app.destroy()


app.after(800, guion)
app.mainloop()
