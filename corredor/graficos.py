"""Dibujos de revisión: planta, sección transversal, perfil con guitarra, tierras y 3D.

Convenciones visuales:
  * Materiales con trama propia (concreto punteado, base con rayas, pedraplén con piedras...).
  * Corte en rojo rayado, relleno en verde cuadriculado.
  * Flechas de cota para anchos, flechas de pendiente con %, rótulos con flecha a cada capa.
  * Elementos del levantamiento con el color y símbolo del catálogo de códigos.
  * Interferencias: círculo rojo (ERROR) o naranja (AVISO).
"""
import math

import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch, Polygon, Rectangle
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from .codigos import Catalogo
from .geometria import fmt_prog
from .malla import fachadas_3d, modelo

COLORES = {
    "CALZADA": "#8e8e8e", "CUNETA": "#4a90c2", "SARDINEL": "#d0d3d4", "VEREDA": "#e6d3b3",
    "FACHADA": "#c0392b", "TERRENO": "#8d6e63",
}
COLORES_CAPAS = ["#b3b6b7", "#e9c46a", "#f4a261", "#8d6e63", "#6d4c41"]
COLORES_VEREDA = ["#e5e7e9", "#f6c99a", "#e59866"]
COLOR_CUNETA_CONC = "#c8cdd0"
CORTE, RELLENO = "#e74c3c", "#27ae60"
NIVEL_COLOR = {"ERROR": "#e74c3c", "AVISO": "#f39c12", "INFO": "#27ae60"}


def estilo_material(nombre, k=0, vereda=False):
    """(color, trama) según el nombre del material."""
    n = nombre.lower()
    if "cuneta" in n:
        return COLOR_CUNETA_CONC, "...."
    if any(x in n for x in ("concreto", "losa", "carpeta", "asfalt")):
        return (COLORES_VEREDA[0] if vereda else COLORES_CAPAS[0]), ".."
    if "pedrapl" in n or "piedra" in n:
        return "#a1887f", "oo"
    if "mejoramiento" in n or "afirmado" in n:
        return "#bcaaa4", "xx"
    if "subbase" in n or "sub-base" in n or "sub base" in n:
        return COLORES_CAPAS[2], "\\\\\\"
    if "base" in n:
        return (COLORES_VEREDA[1] if vereda else COLORES_CAPAS[1]), "///"
    return (COLORES_VEREDA if vereda else COLORES_CAPAS)[k % 3], "--"


def color_capa(proy, nombre):
    for k, cp in enumerate(proy.capas_de("calzada")):
        if cp.nombre == nombre:
            return estilo_material(nombre, k)[0]
    for k, cp in enumerate(proy.capas_de("vereda")):
        if cp.nombre == nombre:
            return estilo_material(nombre, k, True)[0]
    return COLOR_CUNETA_CONC


def _estilo_capa(proy, nombre):
    for k, cp in enumerate(proy.capas_de("calzada")):
        if cp.nombre == nombre:
            return estilo_material(nombre, k)
    for k, cp in enumerate(proy.capas_de("vereda")):
        if cp.nombre == nombre:
            return estilo_material(nombre, k, True)
    return estilo_material(nombre)


def _catalogo(proy):
    return proy.catalogo or Catalogo()


def _flecha_cota(ax, x1, x2, y, texto, color="#1a5276", fs=7):
    ax.annotate("", (x1, y), (x2, y), arrowprops=dict(arrowstyle="<->", color=color, lw=0.8, shrinkA=0, shrinkB=0))
    ax.text((x1 + x2) / 2, y, texto, ha="center", va="bottom", fontsize=fs, color=color,
            bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=0.8))


def _flecha_pendiente(ax, x1, z1, x2, z2, texto, dy=0.07, color="#154360"):
    """Flecha paralela a la superficie, apuntando hacia abajo (sentido del agua)."""
    if z2 > z1:
        x1, z1, x2, z2 = x2, z2, x1, z1
    ax.annotate("", (x2, z2 + dy), (x1, z1 + dy), arrowprops=dict(arrowstyle="-|>", color=color, lw=1.0))
    ax.text((x1 + x2) / 2, (z1 + z2) / 2 + dy + 0.015, texto, ha="center", va="bottom", fontsize=7,
            color=color, weight="bold")


def _cota(ax, x, z, texto, color="#111", arriba=True, rot=90):
    ax.plot([x], [z], marker="v" if arriba else "^", color=color, ms=4, zorder=6)
    ax.annotate(texto, (x, z), xytext=(0, 7 if arriba else -7), textcoords="offset points", rotation=rot,
                fontsize=6.3, ha="center", va="bottom" if arriba else "top", color=color)


# ------------------------------------------------------------------ planta
def dibujar_planta(ax, res, eje_sel=None, mostrar_puntos=True, mostrar_etiquetas=True, resaltar=None):
    proy = res.proyecto
    cat = _catalogo(proy)
    # superficie del proyecto: calzada, cunetas, veredas
    for k, rc in res.calles.items():
        secs = [s for s in rc.secciones if not s.omitida]
        for c1, c2, color, z in (("BCI", "BCD", COLORES["CALZADA"], 1), ("BCD", "PSD", COLORES["CUNETA"], 1),
                                 ("PSI", "BCI", COLORES["CUNETA"], 1), ("BVD", "PFD", COLORES["VEREDA"], 1),
                                 ("PFI", "BVI", COLORES["VEREDA"], 1), ("PSD", "BVD", COLORES["SARDINEL"], 1),
                                 ("BVI", "PSI", COLORES["SARDINEL"], 1)):
            for s1, s2 in zip(secs[:-1], secs[1:]):
                if any(a <= (s1.prog + s2.prog) / 2 <= b for a, b in rc.zonas_omitidas):
                    continue
                pa = [s1.punto("TERMINADO", c1), s1.punto("TERMINADO", c2)]
                pb = [s2.punto("TERMINADO", c1), s2.punto("TERMINADO", c2)]
                if None in pa or None in pb:
                    continue
                q = [s1.xy(pa[0][0]), s1.xy(pa[1][0]), s2.xy(pb[1][0]), s2.xy(pb[0][0])]
                ax.add_patch(Polygon(q, closed=True, fc=color, ec="none", alpha=0.55 if eje_sel in (None, k) else 0.25,
                                     zorder=z))
    # fachadas
    estilos = {"CA": ("#c0392b", "-", 2.2), "MU": ("#e67e22", "-", 2.2), "LP": ("#d4ac0d", "--", 1.8)}
    for l in proy.fachadas:
        col, ls, lw = estilos.get(l.tipo, ("#c0392b", "-", 1.8))
        ax.plot([p[0] for p in l.puntos], [p[1] for p in l.puntos], color=col, ls=ls, lw=lw, zorder=3)
        if mostrar_etiquetas:
            m = len(l.puntos) // 2
            ax.annotate(l.linea_id, l.puntos[m][:2], fontsize=6.5, color=col, xytext=(3, 3),
                        textcoords="offset points", zorder=8)
    # ejes y progresivas
    for k, rc in res.calles.items():
        v = rc.alin.vertices
        lw = 1.6 if eje_sel in (None, k) else 0.8
        ax.plot([p[0] for p in v], [p[1] for p in v], "-.", color="#1a5276", lw=lw, zorder=4)
        for s in rc.secciones:
            if abs(s.prog % 20) < 0.01 or s.tipo in ("INICIO", "FIN"):
                a, b = s.xy(-1.2), s.xy(1.2)
                ax.plot([a[0], b[0]], [a[1], b[1]], color="#1a5276", lw=0.8, zorder=4)
                if mostrar_etiquetas:
                    ax.annotate(fmt_prog(s.prog, 0), s.xy(-2.0), fontsize=6.5, color="#1a5276", ha="center",
                                va="center", zorder=8)
        mid = rc.alin.punto(rc.alin.prog_inicial + 0.3 * rc.alin.longitud, -9.5)
        ax.annotate(f"{k}\n{rc.calle.nombre}", mid, fontsize=8, weight="bold", color="#1a5276", ha="center",
                    va="center", zorder=9, bbox=dict(boxstyle="round", fc="white", ec="#1a5276", alpha=0.85))
    # puntos del levantamiento
    if mostrar_puntos and proy.levantamiento:
        grupos = {}
        for p in proy.levantamiento:
            c, *_ = cat.interpretar(p.codigo)
            grupos.setdefault(c.codigo if c else "?", (c, []))[1].append(p)
        for cod, (c, pts) in grupos.items():
            if c is not None and c.tipo == "LINEA":
                ms, mk = 3, "s"
            else:
                ms, mk = (7 if c and c.tipo in ("ELEMENTO", "PUERTA", "COCHERA", "BM") else 2.5), (c.simbolo if c else "x")
            ax.plot([p.este for p in pts], [p.norte for p in pts], ls="none", marker=mk, ms=ms,
                    color=c.color if c else "#000", mec="white" if ms > 5 else None, mew=0.5, zorder=6,
                    label=f"{cod} {c.nombre if c else 'desconocido'} ({len(pts)})")
    elif proy.terreno:
        ax.plot([p.este for p in proy.terreno], [p.norte for p in proy.terreno], ".", ms=2.5, color="#8d6e63")
    # cocheras: línea del portón
    for u in proy.umbrales:
        if u.tipo == "COCHERA" and u.extremos:
            (e1, n1, _), (e2, n2, _) = u.extremos
            ax.plot([e1, e2], [n1, n2], color="#2471a3", lw=3.5, solid_capstyle="butt", zorder=7)
    # interferencias
    for f in res.interferencias:
        if f["nivel"] in ("ERROR", "AVISO"):
            ax.plot(f["este"], f["norte"], "o", ms=15, mfc="none", mec=NIVEL_COLOR[f["nivel"]], mew=1.8, zorder=7)
            if mostrar_etiquetas:
                ax.annotate(f["id"], (f["este"], f["norte"]), fontsize=6, color=NIVEL_COLOR[f["nivel"]],
                            xytext=(7, -9), textcoords="offset points", zorder=8, weight="bold")
    # BM
    for b in proy.bms:
        ax.plot(b.este, b.norte, "^", color="#6c3483", ms=11, mec="white", zorder=9)
        ax.annotate(f"{b.id}\n{b.cota:.3f}", (b.este, b.norte), fontsize=7, color="white", weight="bold",
                    xytext=(8, 6), textcoords="offset points", zorder=10,
                    bbox=dict(boxstyle="round,pad=0.2", fc="#6c3483", ec="none"))
    if resaltar is not None:
        ax.plot(*resaltar, "o", ms=26, mfc="none", mec="#00bcd4", mew=2.5, zorder=11)
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xlabel("Este (m)")
    ax.set_ylabel("Norte (m)")
    ax.ticklabel_format(useOffset=False, style="plain")
    ax.grid(alpha=0.25)
    # flecha del norte
    ax.annotate("N", xy=(0.97, 0.97), xytext=(0.97, 0.88), xycoords="axes fraction", ha="center", fontsize=11,
                weight="bold", arrowprops=dict(arrowstyle="-|>", color="#111", lw=1.5))
    extra = [Patch(fc=COLORES["CALZADA"], alpha=0.6, label="Calzada"), Patch(fc=COLORES["VEREDA"], alpha=0.7, label="Vereda"),
             Patch(fc=COLORES["CUNETA"], alpha=0.6, label="Cuneta"),
             Line2D([], [], color="#c0392b", lw=2, label="Casa (CA)"), Line2D([], [], color="#e67e22", lw=2, label="Muro (MU)"),
             Line2D([], [], color="#d4ac0d", lw=2, ls="--", label="Límite (LP)"),
             Line2D([], [], marker="o", ls="none", mfc="none", mec=NIVEL_COLOR["ERROR"], ms=10, mew=1.8, label="Interferencia")]
    h, lab = ax.get_legend_handles_labels()
    ax.legend(handles=extra + h, fontsize=6.3, loc="center left", bbox_to_anchor=(1.01, 0.5), frameon=True)
    ax.set_title("Planta del proyecto y levantamiento", fontsize=10, weight="bold")


# ------------------------------------------------------------------ sección
def dibujar_seccion(ax, sec, proy, res=None, etiquetas=True, elementos=True):
    """Sección transversal con tramas, corte/relleno, flechas de cotas y pendientes, y rótulos de capas."""
    # corte y relleno
    t = [(o, z) for o, z in sec.perfil_terreno if z == z]
    sub = sec.lineas["SUBRASANTE"]
    if t:
        os_ = np.array([o for o, _ in t])
        zt = np.array([z for _, z in t])
        so = [o for _, o, _ in sub]
        sz = [z for _, _, z in sub]
        # subrasante interpolada (en saltos verticales toma el valor del tramo)
        zs = np.interp(os_, so, sz)
        ax.fill_between(os_, zt, zs, where=zt >= zs, interpolate=True, fc=CORTE, alpha=0.18, hatch="///",
                        ec=CORTE, lw=0, label=f"Corte {sec.area_corte:.2f} m²")
        ax.fill_between(os_, zt, zs, where=zt < zs, interpolate=True, fc=RELLENO, alpha=0.25, hatch="xx",
                        ec=RELLENO, lw=0, label=f"Relleno {sec.area_relleno:.2f} m²")
    # capas
    for nombre, polys in sec.poligonos.items():
        col, trama = _estilo_capa(proy, nombre)
        for i, poly in enumerate(polys):
            ax.add_patch(Polygon(poly, closed=True, fc=col, ec="#333", lw=0.5, hatch=trama, zorder=3,
                                 label=nombre if i == 0 else None))
    pts = sec.puntos
    ax.plot([p[1] for p in pts], [p[2] for p in pts], color="#111", lw=1.4, zorder=4)
    ax.plot([p[1] for p in sub], [p[2] for p in sub], color="#922b21", lw=1.1, ls="--", zorder=4, label="Subrasante")
    if t:
        ax.plot([o for o, _ in t], [z for _, z in t], color="#6d4c41", lw=1.5, zorder=5, label="Terreno existente")
    ax.axvline(0, color="#1a5276", lw=0.8, ls="-.", zorder=2)

    d = {c: (o, z) for c, o, z in pts}
    zmax = max(z for _, _, z in pts)
    zmin = min(z for _, _, z in sub)
    if t:
        zmax = max(zmax, max(z for _, z in t))
        zmin = min(zmin, min(z for _, z in t))
    alto = zmax - zmin

    # fachadas (muro con trama)
    for l in ("I", "D"):
        disp = sec.vereda_disponible.get(l)
        bv = d.get("BV" + l)
        if disp is not None and bv is not None:
            sg = 1 if l == "D" else -1
            of = sg * (abs(bv[0]) + disp)
            ax.add_patch(Rectangle((of if sg > 0 else of - 0.25, bv[1] - 0.1), 0.25, 0.9, fc="#f5b7b1", ec="#c0392b",
                                   hatch="////", lw=0.8, zorder=5))
            tipo = getattr(sec, "tipo_fachada", {}).get(l) or "CA"
            ax.text(of + sg * 0.15, bv[1] + 0.85, {"CA": "Casa", "MU": "Muro", "LP": "Lím. propiedad"}.get(tipo, tipo),
                    fontsize=6.5, color="#922b21", ha="left" if sg > 0 else "right", va="bottom")

    if etiquetas:
        # anchos con flechas (arriba)
        yv = zmax + 0.30 * max(alto, 0.5)
        for l, sg in (("I", -1), ("D", 1)):
            bc, ps, bv, pf = (d.get(c + l) for c in ("BC", "PS", "BV", "PF"))
            if bc is None:
                continue
            _flecha_cota(ax, 0, bc[0], yv, f"{abs(bc[0]):.2f}")
            if ps is not None:
                _flecha_cota(ax, bc[0], ps[0], yv + 0.12 * max(alto, 0.5), f"{abs(ps[0] - bc[0]):.2f}", fs=6)
                _flecha_cota(ax, ps[0], bv[0], yv, f"{abs(bv[0] - ps[0]):.2f}", fs=6)
                if abs(pf[0] - bv[0]) > 0.05:
                    _flecha_cota(ax, bv[0], pf[0], yv, f"vereda {abs(pf[0] - bv[0]):.2f}")
            # pendientes
            _flecha_pendiente(ax, 0, d["EJE"][1], bc[0] * 0.75, d["EJE"][1] - abs(d["EJE"][1] - bc[1]) * 0.75,
                              f"{abs(d['EJE'][1] - bc[1]) / max(abs(bc[0]), 1e-6) * 100:.1f}%")
            if bv is not None and pf is not None and abs(pf[0] - bv[0]) > 0.3:
                _flecha_pendiente(ax, bv[0], bv[1], pf[0], pf[1],
                                  f"{abs(pf[1] - bv[1]) / abs(pf[0] - bv[0]) * 100:.1f}%", dy=0.05)
        # cotas de puntos
        for c, o, z in pts:
            if c.startswith(("PS", "CS")):
                continue
            _cota(ax, o, z, f"{z:.3f} {c}")
        # rótulos de capas con flecha: a la derecha, en el mismo orden que las capas (de arriba hacia abajo)
        capas = proy.capas_de("calzada")
        x_txt = (d.get("PFD") or d.get("BCD"))[0] + 0.7
        ys = []
        for k, cp in enumerate(capas, start=1):
            tope = next(z for c, o, z in sec.lineas[f"C{k}_TOPE"] if c == "EJE")
            xo = 2.2
            zc = tope - cp.espesor / 2 - (sec.rasante - d["BCD"][1]) / max(d["BCD"][0], 1e-6) * xo
            y = zc if not ys else min(zc, ys[-1] - 0.06 * max(alto, 0.5))
            ys.append(y)
            ax.annotate(f"{cp.nombre}   e = {cp.espesor:.2f} m", (xo, zc), xytext=(x_txt, y),
                        fontsize=7, va="center", ha="left", color="#212f3d",
                        arrowprops=dict(arrowstyle="-|>", color="#212f3d", lw=0.7), zorder=7,
                        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="#aab7b8"))
        if "Concreto cuneta y sardinel" in sec.poligonos and sec.poligonos["Concreto cuneta y sardinel"]:
            ps = d.get("PSD")
            if ps:
                ax.annotate("Cuneta y sardinel\nde concreto", (ps[0] - 0.1, ps[1] - 0.08), xytext=(x_txt, ys[-1] - 0.09 * max(alto, 0.5)),
                            fontsize=6.5, va="center", color="#212f3d",
                            arrowprops=dict(arrowstyle="-|>", color="#212f3d", lw=0.7), zorder=7,
                            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="#aab7b8"))
        yv = []
        for k, cp in enumerate(proy.capas_de("vereda"), start=1):
            ln = sec.lineas.get(f"V{k}_TOPE_I")
            if not ln:
                continue
            (c1, o1, z1), (c2, o2, z2) = ln
            xo, zo = (o1 + o2) / 2, (z1 + z2) / 2 - cp.espesor / 2
            y = zo - 0.12 * max(alto, 0.5) * k
            ax.annotate(f"{cp.nombre}  e = {cp.espesor:.2f} m", (xo, zo), xytext=(min(o1, o2) - 0.3, y),
                        fontsize=6.5, ha="right", va="center", color="#212f3d",
                        arrowprops=dict(arrowstyle="-|>", color="#212f3d", lw=0.7), zorder=7,
                        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="#aab7b8"))

    # elementos cercanos a la sección (±3 m)
    if elementos and res is not None:
        for f in res.interferencias:
            if f["eje"] != sec.eje_id or f["prog"] is None or abs(f["prog"] - sec.prog) > 3.0 or f["offset"] is None:
                continue
            col = NIVEL_COLOR[f["nivel"]]
            mk = {"PUERTA": "D", "COCHERA": "s"}.get(f["tipo"], "o")
            ax.plot(f["offset"], f["cota_campo"], marker=mk, ms=8, color=col, mec="black", zorder=8)
            ax.annotate(f"{f['id']}\n{f['cota_campo']:.3f}", (f["offset"], f["cota_campo"]), fontsize=6.3, color=col,
                        xytext=(6, -14), textcoords="offset points", weight="bold", zorder=8)

    ax.set_title(f"SECCIÓN {sec.eje_id}  {fmt_prog(sec.prog)}   ·   rasante {sec.rasante:.3f}   ·   "
                 f"corte {sec.area_corte:.2f} m²   ·   relleno {sec.area_relleno:.2f} m²", fontsize=9.5, weight="bold")
    ax.set_xlabel("Distancia al eje (m)    ← izquierda | derecha →")
    ax.set_ylabel("Cota (m)")
    ax.ticklabel_format(useOffset=False, style="plain", axis="y")
    ax.grid(alpha=0.25)
    xr = max(abs(pts[0][1]), abs(pts[-1][1])) + 0.8
    ax.set_xlim(-xr - 2.2, xr + 4.2)
    techo = zmax + 0.65 * max(alto, 0.5)
    for l in ("I", "D"):
        if d.get("BV" + l) is not None and sec.vereda_disponible.get(l) is not None:
            techo = max(techo, d["BV" + l][1] + 1.05)
    ax.set_ylim(zmin - 0.15 * max(alto, 0.5), techo)
    ax.legend(fontsize=6.3, loc="lower left", ncol=3, framealpha=0.9)


# ------------------------------------------------------------------ perfil con guitarra
def dibujar_perfil(fig, rc, res, paso_guitarra=20.0):
    """Perfil longitudinal arriba y guitarra (tabla de cotas) abajo."""
    proy = res.proyecto
    gs = fig.add_gridspec(2, 1, height_ratios=[3.2, 1.0], hspace=0.04)
    ax = fig.add_subplot(gs[0])
    axg = fig.add_subplot(gs[1], sharex=ax)
    T = sum(c.espesor for c in proy.capas_de("calzada"))
    p = np.linspace(rc.alin.prog_inicial, rc.alin.prog_final, max(2, int(rc.alin.longitud * 2) + 1))
    zr = np.array([rc.perfil.cota(x) for x in p])
    zt = None
    if res.terreno.ok:
        xy = [rc.alin.punto(x) for x in p]
        zt = res.terreno.cota([a for a, _ in xy], [b for _, b in xy])
    prof = 0.0
    capas = proy.capas_de("calzada")
    for k, cp in enumerate(capas):
        col, trama = estilo_material(cp.nombre, k)
        ax.fill_between(p, zr - prof, zr - prof - cp.espesor, fc=col, ec="#555", lw=0.3, hatch=trama,
                        label=cp.nombre, zorder=2)
        prof += cp.espesor
    if zt is not None:
        ax.fill_between(p, zt, zr - T, where=zt > zr - T, interpolate=True, fc=CORTE, alpha=0.18, hatch="///",
                        ec=CORTE, lw=0, label="Corte")
        ax.fill_between(p, zt, zr - T, where=zt < zr - T, interpolate=True, fc=RELLENO, alpha=0.25, hatch="xx",
                        ec=RELLENO, lw=0, label="Relleno")
        ax.plot(p, zt, color="#6d4c41", lw=1.6, label="Terreno en el eje", zorder=4)
    ax.plot(p, zr, color="#154360", lw=2.2, label="Rasante", zorder=5)
    # vereda por lado (borde de fachada) para ver puertas
    vI = [(s.prog, s.punto("TERMINADO", "PFI")[1]) for s in rc.secciones if s.punto("TERMINADO", "PFI") and not s.omitida]
    if vI:
        ax.plot(*zip(*vI), color="#b9770e", lw=0.9, ls=":", label="Vereda en fachada (izq.)")
    vD = [(s.prog, s.punto("TERMINADO", "PFD")[1]) for s in rc.secciones if s.punto("TERMINADO", "PFD") and not s.omitida]
    if vD:
        ax.plot(*zip(*vD), color="#7e5109", lw=0.9, ls="--", label="Vereda en fachada (der.)")
    # pendientes y quiebres
    for t in rc.perfil.tramos:
        pm = (t[0] + t[3]) / 2
        z = rc.perfil.cota(pm)
        dx = (t[3] - t[0]) * 0.18
        z1, z2 = rc.perfil.cota(pm - dx), rc.perfil.cota(pm + dx)
        a, b = ((pm - dx, z1), (pm + dx, z2)) if z1 > z2 else ((pm + dx, z2), (pm - dx, z1))
        ax.annotate("", b, a, arrowprops=dict(arrowstyle="-|>", color="#154360", lw=1.4))
        ax.text(pm, z + 0.25, f"{t[2]:+.2f} %   L = {t[3] - t[0]:.2f} m", ha="center", fontsize=8, weight="bold",
                color="#154360", bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#154360"))
    for q in [rc.perfil.tramos[0][0]] + rc.perfil.quiebres() + [rc.perfil.tramos[-1][3]]:
        z = rc.perfil.cota(q)
        ax.plot([q, q], [z, z + 0.55], color="#154360", lw=0.8)
        ax.plot(q, z, "o", color="#154360", ms=5)
        ax.text(q, z + 0.58, f"PI {fmt_prog(q)}\n{z:.3f}", fontsize=6.5, ha="center", va="bottom", color="#154360")
    for a, b in rc.zonas_sin_lateral:
        ax.axvspan(a, b, color="#f9e79f", alpha=0.5, zorder=0)
        ax.text((a + b) / 2, ax.get_ylim()[0], "CRUCE", rotation=90, fontsize=7, ha="center", va="bottom",
                color="#7d6608")
    # elementos de la calle
    for f in res.interferencias:
        if f["eje"] != rc.calle.eje_id or f["prog"] is None or f["cota_campo"] is None:
            continue
        mk = {"PUERTA": "D", "COCHERA": "s"}.get(f["tipo"], "o")
        ax.plot(f["prog"], f["cota_campo"], marker=mk, ms=6, color=NIVEL_COLOR[f["nivel"]], mec="black", zorder=6)
        if f["nivel"] != "INFO":
            ax.annotate(f["id"], (f["prog"], f["cota_campo"]), fontsize=6, xytext=(3, 5), textcoords="offset points",
                        color=NIVEL_COLOR[f["nivel"]], weight="bold")
    for b in res.bm_ubicacion:
        if b["eje"] == rc.calle.eje_id and b["prog"] is not None:
            ax.plot(b["prog"], b["bm"].cota, "^", color="#6c3483", ms=9, mec="white", zorder=7)
            ax.annotate(b["bm"].id, (b["prog"], b["bm"].cota), fontsize=7, color="#6c3483", xytext=(4, 6),
                        textcoords="offset points", weight="bold")
    ax.set_ylabel("Cota (m)")
    ax.ticklabel_format(useOffset=False, style="plain", axis="y")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=6.5, loc="upper left", ncol=3, framealpha=0.9)
    ax.set_title(f"PERFIL LONGITUDINAL  {rc.calle.eje_id}  {rc.calle.nombre}", fontsize=10, weight="bold")
    ax.tick_params(labelbottom=False)

    # guitarra
    axg.set_ylim(0, 4)
    axg.set_yticks([0.5, 1.5, 2.5, 3.5])
    axg.set_yticklabels(["Progresiva", "Corte(+)/Relleno(−)", "Cota rasante", "Cota terreno"], fontsize=7)
    for y in (1, 2, 3):
        axg.axhline(y, color="#555", lw=0.5)
    secs = [s for s in rc.secciones if not s.omitida and (abs(s.prog % paso_guitarra) < 0.01 or
                                                           s.tipo in ("INICIO", "FIN", "QUIEBRE"))]
    for s in secs:
        e, n = s.e, s.n
        ztt = res.terreno.cota(e, n) if res.terreno.ok else float("nan")
        h = ztt - s.rasante if ztt == ztt else float("nan")
        axg.axvline(s.prog, color="#aaa", lw=0.4)
        axg.text(s.prog, 0.5, fmt_prog(s.prog, 0), fontsize=6.3, ha="center", va="center", weight="bold")
        axg.text(s.prog, 1.5, "" if h != h else f"{h:+.2f}", fontsize=6.3, ha="center", va="center",
                 color=CORTE if h > 0 else RELLENO, weight="bold")
        axg.text(s.prog, 2.5, f"{s.rasante:.3f}", fontsize=6.3, ha="center", va="center", color="#154360")
        axg.text(s.prog, 3.5, "" if ztt != ztt else f"{ztt:.3f}", fontsize=6.3, ha="center",
                 va="center", color="#6d4c41")
    axg.set_xlabel("Progresiva (m)")
    axg.set_xlim(rc.alin.prog_inicial - 3, rc.alin.prog_final + 3)
    return ax, axg


# ------------------------------------------------------------------ tierras
def dibujar_tierras(fig, rc):
    """Áreas por sección (barras) y curva de masa (volumen acumulado)."""
    ax = fig.add_subplot(211)
    secs = [s for s in rc.secciones if not s.omitida]
    x = [s.prog for s in secs]
    ancho = max(1.0, (rc.alin.longitud / max(len(secs), 1)) * 0.6)
    ax.bar(x, [s.area_corte for s in secs], width=ancho, color=CORTE, alpha=0.75, label="Área de corte (m²)")
    ax.bar(x, [-s.area_relleno for s in secs], width=ancho, color=RELLENO, alpha=0.85, label="Área de relleno (m²)")
    ax.axhline(0, color="#333", lw=0.8)
    ax.set_ylabel("m² por sección")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=7)
    ax.set_title(f"Movimiento de tierras {rc.calle.eje_id} {rc.calle.nombre}", fontsize=10, weight="bold")
    ax2 = fig.add_subplot(212, sharex=ax)
    if rc.curva_masa:
        px, vy = zip(*rc.curva_masa)
        ax2.plot(px, vy, color="#6c3483", lw=2, marker=".", label="Curva de masa (corte − relleno compactado)")
        ax2.fill_between(px, vy, 0, color="#6c3483", alpha=0.08)
    ax2.axhline(0, color="#333", lw=0.8)
    ax2.set_xlabel("Progresiva (m)")
    ax2.set_ylabel("m³ acumulados")
    ax2.grid(alpha=0.25)
    ax2.legend(fontsize=7, loc="upper left")
    b = rc.balance
    ax2.text(0.99, 0.04, f"Corte {b.get('corte', 0):.1f} m³ · Relleno {b.get('relleno', 0):.1f} m³\n"
                         f"Eliminación (esponjado) {b.get('eliminacion', 0):.1f} m³ · Préstamo {b.get('prestamo', 0):.1f} m³",
             transform=ax2.transAxes, ha="right", va="bottom", fontsize=8,
             bbox=dict(boxstyle="round", fc="white", ec="#6c3483"))


# ------------------------------------------------------------------ 3D
def dibujar_3d(ax, res, ejes=None, exag=5.0, con_terreno=True, con_fachadas=True, tramo=None):
    """tramo = (eje_id, progresiva_centro, medio_largo): muestra solo ese pedazo, de cerca."""
    import dataclasses
    proy = res.proyecto
    caras, colores = [], []
    centro = None
    for k, rc in res.calles.items():
        if ejes and k not in ejes:
            continue
        if tramo is not None:
            if k != tramo[0]:
                continue
            p0, p1 = tramo[1] - tramo[2], tramo[1] + tramo[2]
            rc = dataclasses.replace(rc, secciones=[s for s in rc.secciones if p0 - 1e-6 <= s.prog <= p1 + 1e-6])
            centro = rc.alin.punto(tramo[1])
        for cat, q in modelo(rc, proy):
            caras.append(q)
            colores.append(_color_categoria(cat, proy))
    radio = (tramo[2] + 8.0) if tramo is not None else None

    def cerca(q):
        if centro is None:
            return True
        return min(np.hypot(p[0] - centro[0], p[1] - centro[1]) for p in q) <= radio

    if con_fachadas:
        for cat, q in fachadas_3d(proy, res.terreno, res):
            if cerca(q):
                caras.append(q)
                colores.append((0.75, 0.22, 0.17, 0.25))
    if not caras:
        return
    todos = np.array([p for q in caras for p in q])
    e0, n0, z0 = todos[:, 0].min(), todos[:, 1].min(), np.nanmin(todos[:, 2])

    def tr(q):
        return [(p[0] - e0, p[1] - n0, (p[2] - z0) * exag) for p in q]

    ax.add_collection3d(Poly3DCollection([tr(q) for q in caras], facecolors=colores, edgecolors=(0, 0, 0, 0.12),
                                         linewidths=0.15))
    if con_terreno and res.terreno.ok:
        t = res.terreno
        tp = []
        for tri in t.triangulos():
            q = [(t.x[i] + t.e0, t.y[i] + t.n0, t.z[i]) for i in tri]
            if cerca(q):
                tp.append(tr(q))
        ax.add_collection3d(Poly3DCollection(tp, facecolors=(0.55, 0.43, 0.39, 0.15),
                                             edgecolors=(0.4, 0.3, 0.25, 0.3), linewidths=0.2))
    # elementos con interferencia
    for f in res.interferencias:
        if f["cota_campo"] is None:
            continue
        q = [(f["este"], f["norte"], f["cota_campo"])]
        if not cerca(q * 3) or (ejes and f["eje"] not in ejes):
            continue
        x, y, z = tr(q)[0]
        ax.scatter([x], [y], [z + 0.2], color=NIVEL_COLOR[f["nivel"]], s=30, depthshade=False, edgecolors="black")
    xs, ys, zs = todos[:, 0] - e0, todos[:, 1] - n0, (todos[:, 2] - z0) * exag
    ax.set_xlim(xs.min(), xs.max())
    ax.set_ylim(ys.min(), ys.max())
    ax.set_zlim(np.nanmin(zs) - 0.5, np.nanmax(zs) + 0.5)
    rx, ry, rz = xs.max() - xs.min(), ys.max() - ys.min(), np.nanmax(zs) - np.nanmin(zs) + 1
    ax.set_box_aspect((rx, ry, max(rz, 0.12 * max(rx, ry))))
    ax.set_xlabel(f"E − {e0:.0f}")
    ax.set_ylabel(f"N − {n0:.0f}")
    ax.set_zlabel(f"(Z − {z0:.1f}) × {exag:g}")
    tit = f"Modelo 3D (exageración vertical × {exag:g})"
    if tramo is not None:
        tit += f" — {tramo[0]} de {fmt_prog(tramo[1] - tramo[2])} a {fmt_prog(tramo[1] + tramo[2])}"
    ax.set_title(tit, fontsize=10, weight="bold")


def _color_categoria(cat, proy):
    if cat.startswith("CAPA C") or cat.startswith("CAPA V"):
        nombre = cat.split(" ", 2)[2]
        return color_capa(proy, nombre)
    return COLORES.get(cat, "#999999")
