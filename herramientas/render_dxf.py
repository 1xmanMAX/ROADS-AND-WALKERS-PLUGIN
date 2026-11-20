"""Dibuja a PNG el DXF exportado (vista en planta y hoja de secciones) para revisarlo sin AutoCAD."""
import sys

import ezdxf
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from ezdxf.addons.drawing import Frontend, RenderContext
from ezdxf.addons.drawing.config import Configuration, BackgroundPolicy
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

dxf, salida = sys.argv[1], sys.argv[2]
doc = ezdxf.readfile(dxf)
msp = doc.modelspace()


def dibujar(nombre, capas, xlim=None, ylim=None, size=(14, 9)):
    fig = plt.figure(figsize=size)
    ax = fig.add_axes([0, 0, 1, 1])
    ctx = RenderContext(doc)
    for l in doc.layers:
        ctx.layers[l.dxf.name.lower()].is_visible = any(l.dxf.name.startswith(c) for c in capas) if hasattr(ctx, "layers") else True
    cfg = Configuration(background_policy=BackgroundPolicy.WHITE)
    ents = [e for e in msp if any(e.dxf.layer.startswith(c) for c in capas)]
    Frontend(ctx, MatplotlibBackend(ax), config=cfg).draw_entities(ents)
    if xlim:
        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)
    fig.savefig(f"{salida}/{nombre}.png", dpi=110)
    plt.close(fig)
    print(nombre)


dibujar("dxf_planta", ["C3D-EJE", "C3D-LF-", "C3D-FACHADA", "C3D-PUERTAS", "C3D-BM", "C3D-NOMBRE", "C3D-TN"])
dibujar("dxf_planta_detalle", ["C3D-EJE", "C3D-LF-", "C3D-FACHADA", "C3D-PUERTAS", "C3D-PUNTOS", "C3D-NOMBRE"],
        (390150, 390200), (8250300, 8250330))
hx = [e for e in msp if e.dxf.layer.startswith("C3D-HOJA")]
xs = [e.dxf.insert.x for e in hx if e.dxftype() == "TEXT"]
ys = [e.dxf.insert.y for e in hx if e.dxftype() == "TEXT"]
x0, y0 = min(xs), max(ys)
dibujar("dxf_hoja_secciones", ["C3D-HOJA"], (x0 - 2, x0 + 98), (y0 - 32, y0 + 2), size=(16, 6))
pp = [e for e in msp if e.dxf.layer.startswith("C3D-PERFIL") and e.dxftype() == "TEXT"]
px = [e.dxf.insert.x for e in pp]; py = [e.dxf.insert.y for e in pp]
dibujar("dxf_perfil", ["C3D-PERFIL"], (min(px) - 6, min(px) + 260), (min(py) - 5, min(py) + 75), size=(16, 6))
