"""Superficie del terreno existente (TIN) a partir de los puntos del levantamiento.

Se unen los puntos en triángulos (triangulación de Delaunay, como la superficie
de Civil 3D). La cota en un punto cualquiera se interpola en el plano del
triángulo que lo contiene. Se descartan triángulos con lados muy largos
(por ejemplo, a través del interior de una manzana donde no hay puntos).

Puntos repetidos (misma Este y Norte al milímetro, típico al juntar dos días de campo) se dejan
una sola vez: el primero del archivo. Si las cotas repetidas no coinciden, la app lo avisa. Antes
la triangulación tomaba cualquiera de los dos y el resultado dependía del orden interno.
"""
import numpy as np
from matplotlib.tri import LinearTriInterpolator, Triangulation


class Terreno:
    def __init__(self, puntos, arista_max=25.0):
        self.puntos_originales = puntos
        self.repetidos = []          # [(punto_que_queda, punto_descartado)]
        self.error = ""
        vistos, unicos = {}, []
        for p in puntos:
            k = (round(p.este, 3), round(p.norte, 3))
            if k in vistos:
                self.repetidos.append((vistos[k], p))
                continue
            vistos[k] = p
            unicos.append(p)
        self.puntos = unicos
        self.ok = len(unicos) >= 3
        if not self.ok:
            if puntos:
                self.error = f"solo hay {len(unicos)} punto(s) distintos; se necesitan al menos 3."
            return
        self.e0 = min(p.este for p in unicos)
        self.n0 = min(p.norte for p in unicos)
        # se trabaja con coordenadas relativas para no perder precisión
        x = np.array([p.este - self.e0 for p in unicos])
        y = np.array([p.norte - self.n0 for p in unicos])
        z = np.array([p.cota for p in unicos])
        self.x, self.y, self.z = x, y, z
        try:
            tri = Triangulation(x, y)
        except (RuntimeError, ValueError):
            # todos los puntos en una línea (por ejemplo, solo se levantó el eje): no hay superficie
            self.ok = False
            self.error = "los puntos están todos en una línea; levante también bordes o fachadas."
            return
        t = tri.triangles
        lados = np.max(np.stack([
            np.hypot(x[t[:, 0]] - x[t[:, 1]], y[t[:, 0]] - y[t[:, 1]]),
            np.hypot(x[t[:, 1]] - x[t[:, 2]], y[t[:, 1]] - y[t[:, 2]]),
            np.hypot(x[t[:, 2]] - x[t[:, 0]], y[t[:, 2]] - y[t[:, 0]])]), axis=0)
        malos = lados > arista_max
        if malos.all():
            self.ok = False
            self.error = (f"todos los triángulos tienen lados de más de {arista_max:g} m "
                          f"(puntos muy separados); suba 'arista_max_tin' o densifique el levantamiento.")
            return
        tri.set_mask(malos)
        self.tri = tri
        self.interp = LinearTriInterpolator(tri, z)

    def cota(self, e, n):
        """Cota del terreno en (e, n); NaN si está fuera de la superficie."""
        if not self.ok:
            return np.full(np.shape(e), np.nan) if np.ndim(e) else float("nan")
        v = self.interp(np.atleast_1d(np.asarray(e, float) - self.e0),
                        np.atleast_1d(np.asarray(n, float) - self.n0))
        v = np.ma.filled(v, np.nan)
        return v if np.ndim(e) else float(v[0])

    def triangulos(self):
        """Lista de triángulos válidos [(i, j, k), ...] (índices en self.puntos)."""
        if not self.ok:
            return []
        m = self.tri.mask
        return [tuple(int(i) for i in t) for t, malo in zip(self.tri.triangles, m) if not malo]
