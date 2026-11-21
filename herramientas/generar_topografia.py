"""Topografía de práctica con pendientes variadas, para modelar una vía en Civil 3D desde cero.

    python herramientas/generar_topografia.py [carpeta]        (por defecto topografia_practica/)

Zona de 420 × 320 m (UTM 19S, como en Puno, cota ~3820):
  * Llanura al oeste          0.5 – 1 %   (cuesta drenar: pendiente mínima)
  * Ladera suave al centro    3 – 4 %
  * Quebrada N-S              cauce de ~3 m de hondo, sinuoso (alcantarilla o relleno)
  * Ladera fuerte al este     12 – 18 %   (pendiente máxima, corte alto)
  * Talud/terraza             escalón de ~1.5 m en la ladera fuerte
  * Lomita                    4 m de alto en la llanura
  * Vía existente asfaltada   al sur, para empalmar el diseño (bordes PEX y eje EJX)

Salida (en la carpeta):
  topografia_PENZD.csv     puntos para Civil 3D (Insert > Points from File, formato "PENZD (comma
                           delimited)") y para Corredor Simple (terreno.csv). Códigos del manual de
                           campo (docs/CODIFICACION_CAMPO.md): TN, ZJ/BOR (quebrada), CAB/PIE (talud),
                           PEX/EJX (vía existente), BM.
  topografia_vista.png     relieve, curvas cada 1 m y mapa de pendientes
  LEEME.md                 qué hay y cómo modelar la vía en Civil 3D (corredor nativo)
  topografia.dwg           (si hay Civil 3D) puntos COGO + superficie TN con curvas de nivel
"""
import math
import random
import sys
from pathlib import Path

import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

E0, N0, Z0 = 324000.0, 8396000.0, 3820.0
ANCHO, ALTO = 420.0, 320.0


def _sig(t):
    return 1.0 / (1.0 + np.exp(-t))


def cota(x, y):
    """Cota del terreno en coordenadas locales (x al este, y al norte, en m desde la esquina SO)."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    # pendiente hacia el este: 0.6 % en la llanura, +3 % desde x≈130, +12 % desde x≈280 (integrada)
    def integral(xx, x0, ancho, pend):
        return pend * ancho * np.log1p(np.exp((xx - x0) / ancho))
    z = 0.006 * x + integral(x, 130, 10, 0.030) + integral(x, 280, 12, 0.120)
    # más fuerte hacia el norte en la ladera (hasta 18 %)
    z += 0.06 * _sig((x - 300) / 15) * (y / ALTO) * (x - 280).clip(0) * 0.25
    # caída general al sur (1 %): la vía existente está abajo
    z += 0.010 * y
    # quebrada sinuosa N-S alrededor de x = 205
    eje_q = 205 + 12 * np.sin(y / 45)
    z -= 3.2 * np.exp(-((x - eje_q) / 9.0) ** 2) * (0.6 + 0.4 * y / ALTO)
    # talud / terraza en la ladera fuerte (escalón de 1.5 m)
    z += 1.5 * _sig((y - 190) / 2.0) * _sig((x - 290) / 8)
    # lomita en la llanura
    z += 4.0 * np.exp(-(((x - 70) / 28) ** 2 + ((y - 230) / 24) ** 2))
    # vía existente al sur: plataforma con bombeo 2 % (eje en y = 7) que se funde con el terreno
    # entre y = 12 y y = 22 (cuneta de tierra / berma), sin escalones
    base = 0.006 * x + integral(x, 130, 10, 0.030) + integral(x, 280, 12, 0.120)
    via = base + 0.05 - 0.02 * np.abs(y - 7)
    w = _sig((y - 17) / 2.0)
    z = w * z + (1 - w) * via
    return Z0 + z


def puntos(semilla=7):
    rnd = random.Random(semilla)
    pts = []

    def p(x, y, cod, ruido=0.03):
        pts.append((x, y, float(cota(x, y)) + rnd.uniform(-ruido, ruido), cod))
    # grilla de 6 m (más densa, 3 m, en la quebrada y en la ladera fuerte)
    y = 16.0
    while y <= ALTO:
        x = 0.0
        while x <= ANCHO:
            denso = abs(x - (205 + 12 * math.sin(y / 45))) < 25 or x > 270
            paso = 3.0 if denso else 6.0
            p(x + rnd.uniform(-0.4, 0.4), y + rnd.uniform(-0.4, 0.4), "TN")
            x += paso
        y += 4.0
    # quebrada: fondo y bordes (líneas de quiebre)
    y = 14.0
    while y <= ALTO:
        ex = 205 + 12 * math.sin(y / 45)
        p(ex, y, "ZJ1", 0.02)
        p(ex - 9, y, "BOR1", 0.02)
        p(ex + 9, y, "BOR2", 0.02)
        y += 5.0
    # talud de la terraza: cabeza y pie
    x = 292.0
    while x <= ANCHO:
        p(x, 193.5, "CAB1", 0.01)
        p(x, 186.5, "PIE1", 0.01)
        x += 6.0
    # vía existente: bordes de asfalto y eje cada 10 m
    x = 0.0
    while x <= ANCHO:
        p(x, 3.4, "PEX1", 0.005)
        p(x, 7.0, "EJX1", 0.005)
        p(x, 10.6, "PEX2", 0.005)
        x += 10.0
    # BMs
    for i, (x, y) in enumerate(((20, 20), (400, 20), (210, 300)), start=1):
        pts.append((x, y, float(cota(x, y)) + 0.15, f"BM / BM-{i:02d}"))
    # al revés no: se mantiene el orden de toma (las líneas se unen en ese orden)
    return [(i + 1, E0 + x, N0 + y, z, c) for i, (x, y, z, c) in enumerate(pts)]


def vista(pts, ruta):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import BoundaryNorm, ListedColormap
    xs = np.linspace(0, ANCHO, 421)
    ys = np.linspace(0, ALTO, 321)
    X, Y = np.meshgrid(xs, ys)
    Z = cota(X, Y)
    gy, gx = np.gradient(Z, ys, xs)
    S = np.hypot(gx, gy) * 100
    fig, axs = plt.subplots(1, 2, figsize=(17, 6.8))
    ax = axs[0]
    ls = matplotlib.colors.LightSource(azdeg=315, altdeg=40)
    ax.imshow(ls.shade(Z, cmap=plt.cm.terrain, vert_exag=6, blend_mode="soft"), origin="lower",
              extent=(E0, E0 + ANCHO, N0, N0 + ALTO))
    cs = ax.contour(X + E0, Y + N0, Z, levels=np.arange(math.floor(Z.min()), Z.max() + 1, 1.0), colors="k", linewidths=0.4)
    ax.clabel(cs, cs.levels[::5], fmt="%.0f", fontsize=7)
    ax.set_title("Relieve y curvas de nivel cada 1 m")
    cmap = ListedColormap(["#1a9850", "#91cf60", "#fee08b", "#fc8d59", "#d73027", "#7f0000"])
    lim = [0, 2, 5, 8, 12, 18, 100]
    ax = axs[1]
    im = ax.imshow(S, origin="lower", extent=(E0, E0 + ANCHO, N0, N0 + ALTO), cmap=cmap, norm=BoundaryNorm(lim, cmap.N))
    cb = fig.colorbar(im, ax=ax, ticks=lim[:-1] + [25], fraction=0.035)
    cb.ax.set_yticklabels(["0", "2", "5", "8", "12", "18", ">18 %"])
    for (x, y, t) in ((60, 120, "LLANURA\n0.5–1 %"), (160, 120, "LADERA\nSUAVE 3–4 %"), (215, 260, "QUEBRADA"),
                      (350, 100, "LADERA\nFUERTE 12–18 %"), (345, 205, "TALUD"), (70, 245, "LOMITA"),
                      (200, 4, "VÍA EXISTENTE (empalme)")):
        ax.annotate(t, (E0 + x, N0 + y), ha="center", va="center", fontsize=8, weight="bold")
    ax.set_title("Pendiente del terreno (%)")
    for a in axs:
        a.ticklabel_format(useOffset=False, style="plain")
        a.tick_params(labelsize=7)
    fig.suptitle(f"Topografía de práctica: {len(pts)} puntos, cotas {Z.min():.1f} a {Z.max():.1f} m")
    fig.tight_layout()
    fig.savefig(ruta, dpi=110)
    plt.close(fig)
    return float(Z.min()), float(Z.max())


LEEME = """# Topografía de práctica (pendientes variadas)

Zona de 420 × 320 m, UTM 19S (E {e0:.0f}–{e1:.0f}, N {n0:.0f}–{n1:.0f}), cotas {zmin:.1f} a {zmax:.1f} m.
{n} puntos. Ver `topografia_vista.png`.

| Zona | Pendiente | Qué obliga a resolver |
|---|---|---|
| Llanura (oeste) | 0.5 – 1 % | pendiente mínima de drenaje, rasante casi plana |
| Ladera suave (centro) | 3 – 4 % | la zona cómoda |
| Quebrada (x ≈ 205 m, N-S) | cauce de ~3 m | relleno y alcantarilla, o puente |
| Ladera fuerte (este) | 12 – 18 % | pendiente máxima, cortes altos, curvas |
| Talud / terraza (este, N ≈ {nt:.0f}) | escalón 1.5 m | corte adicional |
| Lomita (oeste) | 4 m de alto | rodear o cortar |
| Vía existente (sur) | plataforma con bombeo 2 % | **empalme** del diseño (bordes PEX1/PEX2, eje EJX1) |

Códigos (docs/CODIFICACION_CAMPO.md): `TN` terreno · `ZJ1` fondo de quebrada · `BOR1`/`BOR2` bordes ·
`CAB1`/`PIE1` talud · `PEX1`/`PEX2` bordes de asfalto existente · `EJX1` eje existente · `BM`.

## Modelar la vía en Civil 3D (flujo nativo)

1. **Puntos**: `Insert > Points from File` → `topografia_PENZD.csv`, formato **PENZD (comma delimited)**.
   (O abra `topografia.dwg`: ya tiene los puntos COGO y la superficie.)
2. **Superficie**: `Create Surface` → TIN "TN"; Definition → Point Groups (_All Points). Agregue como
   **breaklines** las polilíneas 3D de ZJ1, BOR1, BOR2, CAB1, PIE1 (Description Keys / Linework con
   el mismo código). Estilo de curvas 1 m / 5 m.
3. **Eje**: dibuje una polilínea (por ejemplo desde la vía existente al sur, cruzando la quebrada y
   subiendo la ladera fuerte) → `Alignment > Create Alignment from Objects`, con curvas (radio mínimo).
4. **Perfil**: `Profile > Create Surface Profile` + `Profile View`; luego `Profile Creation Tools` para
   la rasante: empalme a la cota del eje existente, pendiente máx. (8–10 %) en la ladera, mínima 0.5 %
   en la llanura, curvas verticales.
5. **Ensamblaje**: `Assembly` + subensamblajes de la sección típica (`LaneSuperelevationAOR` o
   `BasicLane` 3.60 m × 2, `UrbanCurbGutterGeneral` para cuneta + sardinel, `UrbanSidewalk` para
   vereda, `LinkSlopeToSurface` / `BasicSideSlopeCutDitch` para los taludes en la ladera).
6. **Corredor**: `Corridor` con eje + perfil + ensamblaje, frecuencia 10 m (5 m en curvas); objetivo de
   superficie = TN para los taludes. `Corridor Surface` (Top y Datum).
7. **Volúmenes**: `Sample Lines` cada 10 m → `Compute Materials` (TN vs Datum) → tabla de volúmenes y
   `Section Views`; o `Volumes Dashboard` con superficie TN vs Datum.

Para comparar: el mismo levantamiento se puede abrir en Corredor Simple (`terreno.csv` = este CSV) y
el verificador de la app compara sus volúmenes con los de Civil 3D.
"""


def main(destino=None):
    destino = Path(destino or RAIZ / "topografia_practica")
    destino.mkdir(parents=True, exist_ok=True)
    pts = puntos()
    with open(destino / "topografia_PENZD.csv", "w", encoding="utf-8") as f:
        for n, e, nn, z, c in pts:
            f.write(f"{n},{e:.3f},{nn:.3f},{z:.3f},{c}\n")
    zmin, zmax = vista(pts, destino / "topografia_vista.png")
    (destino / "LEEME.md").write_text(LEEME.format(e0=E0, e1=E0 + ANCHO, n0=N0, n1=N0 + ALTO, zmin=zmin, zmax=zmax,
                                                    n=len(pts), nt=N0 + 190), encoding="utf-8")
    print(f"{len(pts)} puntos, cotas {zmin:.1f} a {zmax:.1f} -> {destino}")
    try:
        from corredor.civil3d import ErrorCivil3D, topografia_dwg
        dwg, msgs = topografia_dwg(destino / "topografia_PENZD.csv", destino / "topografia.dwg")
        print("\n".join(msgs), "\n->", dwg)
    except ErrorCivil3D as e:
        print("Sin DWG (Civil 3D no disponible):", e)
    return destino


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
