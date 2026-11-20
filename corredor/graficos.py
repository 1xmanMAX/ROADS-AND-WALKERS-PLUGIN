"""Dibujos para revisar: planta, perfil longitudinal, sección transversal y modelo 3D."""
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection

from .geometria import fmt_prog
from .malla import fachadas_3d, modelo

COLORES = {
    "CALZADA": "#8e8e8e", "CUNETA": "#4a90c2", "SARDINEL": "#d0d3d4", "VEREDA": "#e6d3b3",
    "FACHADA": "#c0392b", "TERRENO": "#8d6e63",
}
COLORES_CAPAS = ["#a6acaf", "#d4ac0d", "#ca6f1e", "#784212", "#5d4037"]
COLORES_VEREDA = ["#d5d8dc", "#f0b27a", "#e59866"]
COLOR_CUNETA_CONC = "#b2babb"


def color_capa(proy, nombre):
    for k, cp in enumerate(proy.capas_de("calzada")):
        if cp.nombre == nombre:
            return COLORES_CAPAS[k % len(COLORES_CAPAS)]
    for k, cp in enumerate(proy.capas_de("vereda")):
        if cp.nombre == nombre:
            return COLORES_VEREDA[k % len(COLORES_VEREDA)]
    return COLOR_CUNETA_CONC


def _color_categoria(cat):
    if cat.startswith("CAPA C"):
        k = int(cat.split()[1][1:]) - 1
        return COLORES_CAPAS[k % len(COLORES_CAPAS)]
    if cat.startswith("CAPA V"):
        k = int(cat.split()[1][1:]) - 1
        return COLORES_VEREDA[k % len(COLORES_VEREDA)]
    return COLORES.get(cat, "#999999")


# ------------------------------------------------------------------ planta
def dibujar_planta(ax, res, eje_sel=None):
    proy = res.proyecto
    if proy.terreno:
        ax.scatter([p.este for p in proy.terreno], [p.norte for p in proy.terreno], s=4, c="#8d6e63",
                   label="Terreno levantado", zorder=1)
    for l in proy.fachadas:
        ax.plot([p[0] for p in l.puntos], [p[1] for p in l.puntos], color="#c0392b", lw=1.2, zorder=2)
    for k, rc in res.calles.items():
        lw = 2.2 if (eje_sel in (None, k)) else 1.0
        tp = [p for p in rc.secciones[0].puntos]
        for codigo in ("BCI", "BCD", "PFI", "PFD"):
            xs, ys = [], []
            for s in rc.secciones:
                pt = s.punto("TERMINADO", codigo)
                if pt is None or s.omitida:
                    xs.append(np.nan); ys.append(np.nan)
                    continue
                e, n = s.xy(pt[0]); xs.append(e); ys.append(n)
            ax.plot(xs, ys, color="#555" if codigo.startswith("BC") else "#b9770e", lw=0.8, zorder=3)
        v = rc.alin.vertices
        ax.plot([p[0] for p in v], [p[1] for p in v], "-", color="#1a5276", lw=lw, zorder=4)
        for s in rc.secciones:
            if abs(s.prog % 50) < 0.01 or s.tipo in ("INICIO", "FIN"):
                ax.annotate(fmt_prog(s.prog, 0), (s.e, s.n), fontsize=7, color="#1a5276",
                            xytext=(3, 3), textcoords="offset points")
        mid = rc.alin.punto(rc.alin.prog_inicial + 0.3 * rc.alin.longitud, -9.0)
        ax.annotate(f"{k}\n{rc.calle.nombre}", mid, fontsize=8, weight="bold", color="#1a5276", ha="center",
                    va="center")
    for u in res.umbrales:
        uu = u["umbral"]
        col = "#c0392b" if u["diferencia"] < 0 else "#1e8449"
        ax.plot(uu.este, uu.norte, "s", color=col, ms=6, zorder=5)
        ax.annotate(f"{uu.id} {u['diferencia']:+.3f}", (uu.este, uu.norte), fontsize=7, color=col,
                    xytext=(4, -10), textcoords="offset points")
    for b in proy.bms:
        ax.plot(b.este, b.norte, "^", color="#7d3c98", ms=7, zorder=5)
        ax.annotate(b.id, (b.este, b.norte), fontsize=7, color="#7d3c98", xytext=(4, 4), textcoords="offset points")
    ax.set_aspect("equal", adjustable="datalim")
    ax.set_xlabel("Este (m)")
    ax.set_ylabel("Norte (m)")
    ax.ticklabel_format(useOffset=False, style="plain")
    ax.grid(alpha=0.3)
    ax.set_title("Planta")


# ------------------------------------------------------------------ perfil
def dibujar_perfil(ax, rc, res):
    proy = res.proyecto
    T = sum(c.espesor for c in proy.capas_de("calzada"))
    p = np.linspace(rc.alin.prog_inicial, rc.alin.prog_final, max(2, int(rc.alin.longitud) + 1))
    zr = np.array([rc.perfil.cota(x) for x in p])
    ax.plot(p, zr, color="#1a5276", lw=2, label="Rasante")
    prof = 0.0
    for k, cp in enumerate(proy.capas_de("calzada")):
        prof += cp.espesor
        ax.plot(p, zr - prof, color=COLORES_CAPAS[k % len(COLORES_CAPAS)], lw=0.8,
                label=f"Fondo {cp.nombre}")
    if res.terreno.ok:
        e = [rc.alin.punto(x)[0] for x in p]
        n = [rc.alin.punto(x)[1] for x in p]
        zt = res.terreno.cota(e, n)
        ax.plot(p, zt, color="#6d4c41", lw=1.3, ls="--", label="Terreno en el eje")
        ax.fill_between(p, zt, zr - T, where=zt > zr - T, color="#e74c3c", alpha=0.15, label="Corte")
        ax.fill_between(p, zt, zr - T, where=zt < zr - T, color="#27ae60", alpha=0.25, label="Relleno")
    for t in rc.perfil.tramos:
        pm = (t[0] + t[3]) / 2
        ax.annotate(f"{t[2]:+.2f} %", (pm, rc.perfil.cota(pm)), xytext=(0, 10), textcoords="offset points",
                    ha="center", fontsize=8, color="#1a5276", weight="bold")
    for q in rc.perfil.quiebres():
        z = rc.perfil.cota(q)
        ax.axvline(q, color="#1a5276", lw=0.6, ls=":")
        ax.annotate(f"Quiebre {fmt_prog(q)}\n{z:.3f}", (q, z), xytext=(4, -28), textcoords="offset points", fontsize=7)
    for a, b in rc.zonas_sin_lateral:
        ax.axvspan(a, b, color="#f4d03f", alpha=0.25)
    ax.set_xlabel("Progresiva (m)")
    ax.set_ylabel("Cota (m)")
    ax.ticklabel_format(useOffset=False, style="plain", axis="y")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7, loc="best")
    ax.set_title(f"Perfil longitudinal {rc.calle.eje_id} {rc.calle.nombre}")


# ------------------------------------------------------------------ sección
def dibujar_seccion(ax, sec, proy, etiquetas=True):
    for nombre, polys in sec.poligonos.items():
        for poly in polys:
            xs = [p[0] for p in poly]
            ys = [p[1] for p in poly]
            ax.fill(xs, ys, color=color_capa(proy, nombre), ec="#333", lw=0.4,
                    label=nombre if poly is polys[0] else None)
    t = sec.puntos
    ax.plot([p[1] for p in t], [p[2] for p in t], color="#111", lw=1.2)
    sr = sec.lineas["SUBRASANTE"]
    ax.plot([p[1] for p in sr], [p[2] for p in sr], color="#c0392b", lw=1, ls="--", label="Subrasante")
    if sec.perfil_terreno:
        ax.plot([p[0] for p in sec.perfil_terreno], [p[1] for p in sec.perfil_terreno], color="#6d4c41",
                lw=1.3, label="Terreno")
    for l in ("I", "D"):
        d = sec.vereda_disponible.get(l)
        pf = sec.punto("TERMINADO", "PF" + l)
        if d is not None and pf is not None:
            o_f = (abs(pf[0]) - sec.vereda_ancho[l] + d) * (1 if l == "D" else -1)
            ax.plot([o_f, o_f], [pf[1], pf[1] + 0.6], color="#c0392b", lw=3)
    if etiquetas:
        for c, o, z in t:
            if c.startswith(("PS",)):
                continue
            ax.annotate(f"{c} {z:.3f}", (o, z), rotation=90, fontsize=6, xytext=(0, 6),
                        textcoords="offset points", ha="center", va="bottom")
    ax.set_title(f"{sec.eje_id}  {fmt_prog(sec.prog)}   rasante {sec.rasante:.3f}   "
                 f"corte {sec.area_corte:.2f} m²  relleno {sec.area_relleno:.2f} m²", fontsize=9)
    ax.set_xlabel("Distancia al eje (m)  — izquierda (−) / derecha (+)")
    ax.set_ylabel("Cota (m)")
    ax.ticklabel_format(useOffset=False, style="plain", axis="y")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=6, loc="lower center", ncol=4)


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
            colores.append(_color_categoria(cat))
    radio = (tramo[2] + 8.0) if tramo is not None else None

    def cerca(q):
        if centro is None:
            return True
        return min(np.hypot(p[0] - centro[0], p[1] - centro[1]) for p in q) <= radio

    if con_fachadas:
        for cat, q in fachadas_3d(proy, res.terreno, res):
            if cerca(q):
                caras.append(q)
                colores.append((0.75, 0.22, 0.17, 0.18))
    if not caras:
        return
    todos = np.array([p for q in caras for p in q])
    e0, n0, z0 = todos[:, 0].min(), todos[:, 1].min(), np.nanmin(todos[:, 2])

    def tr(q):
        return [(p[0] - e0, p[1] - n0, (p[2] - z0) * exag) for p in q]

    ax.add_collection3d(Poly3DCollection([tr(q) for q in caras], facecolors=colores, edgecolors=(0, 0, 0, 0.15),
                                         linewidths=0.15))
    if con_terreno and res.terreno.ok:
        t = res.terreno
        tp = []
        for tri in t.triangulos():
            q = [(t.x[i] + t.e0, t.y[i] + t.n0, t.z[i]) for i in tri]
            if cerca(q):
                tp.append(tr(q))
        ax.add_collection3d(Poly3DCollection(tp, facecolors=(0.55, 0.43, 0.39, 0.15),
                                             edgecolors=(0.4, 0.3, 0.25, 0.35), linewidths=0.2))
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
    ax.set_title(tit)
