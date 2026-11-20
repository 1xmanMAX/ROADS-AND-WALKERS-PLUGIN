"""Superficie del terreno existente (TIN) a partir de los puntos del levantamiento.

Se unen los puntos en triángulos (triangulación de Delaunay, como la superficie
de Civil 3D). La cota en un punto cualquiera se interpola en el plano del
triángulo que lo contiene. Se descartan triángulos con lados muy largos
(por ejemplo, a través del interior de una manzana donde no hay puntos).
"""
import numpy as np
from matplotlib.tri import LinearTriInterpolator, Triangulation


class Terreno:
    def __init__(self, puntos, arista_max=25.0):
        self.puntos = puntos
        self.ok = len(puntos) >= 3
        if not self.ok:
            return
        self.e0 = min(p.este for p in puntos)
        self.n0 = min(p.norte for p in puntos)
        # se trabaja con coordenadas relativas para no perder precisión
        x = np.array([p.este - self.e0 for p in puntos])
        y = np.array([p.norte - self.n0 for p in puntos])
        z = np.array([p.cota for p in puntos])
        self.x, self.y, self.z = x, y, z
        tri = Triangulation(x, y)
        t = tri.triangles
        lados = np.max(np.stack([
            np.hypot(x[t[:, 0]] - x[t[:, 1]], y[t[:, 0]] - y[t[:, 1]]),
            np.hypot(x[t[:, 1]] - x[t[:, 2]], y[t[:, 1]] - y[t[:, 2]]),
            np.hypot(x[t[:, 2]] - x[t[:, 0]], y[t[:, 2]] - y[t[:, 0]])]), axis=0)
        tri.set_mask(lados > arista_max)
        self.tri = tri
        self.interp = LinearTriInterpolator(tri, z)

    def cota(self, e, n):
        """Cota del terreno en (e, n); NaN si está fuera de la superficie."""
        if not self.ok:
            return float("nan")
        v = self.interp(np.atleast_1d(np.asarray(e, float) - self.e0),
                        np.atleast_1d(np.asarray(n, float) - self.n0))
        v = np.ma.filled(v, np.nan)
        return v if np.ndim(e) else float(v[0])

    def triangulos(self):
        """Lista de triángulos válidos [(i, j, k), ...]."""
        if not self.ok:
            return []
        m = self.tri.mask
        return [tuple(t) for t, malo in zip(self.tri.triangles, m) if not malo]
