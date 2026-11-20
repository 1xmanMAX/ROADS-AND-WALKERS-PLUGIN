"""Eje en planta (alineamiento) y perfil longitudinal (rasante).

Fórmulas (lenguaje simple):
  Punto del eje:   avanzar 'd' metros desde el inicio del tramo en la dirección del tramo.
                   E = E0 + d·sen(Az)   N = N0 + d·cos(Az)
  Desplazamiento:  correrse 'o' metros a la derecha (o>0) o izquierda (o<0), perpendicular al eje.
                   E += o·cos(Az)       N -= o·sen(Az)
  Rasante:         cota = cota_inicio_tramo + pendiente/100 · (prog − prog_inicio_tramo)
"""
import math


def fmt_prog(p, dec=2):
    """150.5 -> '0+150.50'."""
    p = round(p, dec)
    signo = "-" if p < 0 else ""
    p = abs(p)
    km = int(p // 1000)
    m = p - km * 1000
    ancho = 4 + dec if dec else 3
    return f"{signo}{km}+{m:0{ancho}.{dec}f}"


def fmt_prog_corto(p):
    """Para nombres de puntos: 50 -> '0+050', 124.35 -> '0+124.35'."""
    if abs(p - round(p)) < 0.005:
        return fmt_prog(round(p), 0)
    return fmt_prog(p, 2)


class Alineamiento:
    def __init__(self, vertices, prog_inicial=0.0):
        if len(vertices) < 2:
            raise ValueError("El eje necesita al menos 2 vértices.")
        self.vertices = [(float(e), float(n)) for e, n in vertices]
        self.prog_inicial = float(prog_inicial)
        self.segs = []
        p = self.prog_inicial
        for (e0, n0), (e1, n1) in zip(self.vertices[:-1], self.vertices[1:]):
            L = math.hypot(e1 - e0, n1 - n0)
            if L < 1e-6:
                raise ValueError(f"Hay dos vértices repetidos en ({e0:.3f}, {n0:.3f}).")
            ux, uy = (e1 - e0) / L, (n1 - n0) / L
            self.segs.append({"p0": p, "p1": p + L, "e0": e0, "n0": n0, "ux": ux, "uy": uy, "L": L})
            p += L
        self.prog_final = p

    @property
    def longitud(self):
        return self.prog_final - self.prog_inicial

    def _seg(self, p):
        for s in self.segs:
            if p <= s["p1"] + 1e-9:
                return s
        return self.segs[-1]

    def punto(self, prog, offset=0.0):
        s = self._seg(prog)
        d = prog - s["p0"]
        nx, ny = s["uy"], -s["ux"]          # normal a la derecha
        return (s["e0"] + d * s["ux"] + offset * nx, s["n0"] + d * s["uy"] + offset * ny)

    def direccion(self, prog):
        s = self._seg(prog)
        return s["ux"], s["uy"]

    def normal(self, prog):
        ux, uy = self.direccion(prog)
        return uy, -ux

    def azimut(self, prog):
        ux, uy = self.direccion(prog)
        return math.degrees(math.atan2(ux, uy)) % 360.0

    def progs_vertices(self):
        return [s["p0"] for s in self.segs] + [self.prog_final]

    def proyectar(self, e, n):
        """Devuelve (progresiva, offset, distancia_fuera) del punto respecto al eje."""
        mejor = None
        for s in self.segs:
            de, dn = e - s["e0"], n - s["n0"]
            t = de * s["ux"] + dn * s["uy"]
            tc = min(max(t, 0.0), s["L"])
            pe, pn = s["e0"] + tc * s["ux"], s["n0"] + tc * s["uy"]
            dist = math.hypot(e - pe, n - pn)
            off = de * s["uy"] - dn * s["ux"]
            fuera = abs(t - tc)
            if mejor is None or dist < mejor[0] - 1e-9:
                mejor = (dist, s["p0"] + tc, off, fuera)
        return mejor[1], mejor[2], mejor[3]


class Perfil:
    """Tramos rectos de rasante: (prog_inicio, cota_inicio, pendiente %, prog_fin)."""

    def __init__(self, tramos):
        if not tramos:
            raise ValueError("El perfil no tiene tramos.")
        self.tramos = sorted([tuple(map(float, t)) for t in tramos], key=lambda t: t[0])

    def _tramo(self, p):
        for t in self.tramos:
            if p <= t[3] + 1e-9:
                return t
        return self.tramos[-1]

    def cota(self, p):
        t = self._tramo(p)
        return t[1] + t[2] / 100.0 * (p - t[0])

    def pendiente(self, p):
        return self._tramo(p)[2]

    def quiebres(self):
        """Progresivas donde cambia la pendiente (sin el inicio ni el final)."""
        return [t[0] for t in self.tramos[1:]]

    def pvis(self):
        """Puntos de intersección vertical (progresiva, cota) para Civil 3D."""
        pv = [(self.tramos[0][0], self.tramos[0][1])]
        for t in self.tramos:
            pv.append((t[3], t[1] + t[2] / 100.0 * (t[3] - t[0])))
        return pv

    def validar(self, eje_id, pmax, pmin, alin=None):
        """Devuelve lista de (nivel, prog, mensaje)."""
        av = []
        for k, t in enumerate(self.tramos):
            pend = abs(t[2])
            if pend > pmax + 1e-9:
                av.append(("AVISO", t[0], f"pendiente {t[2]:+.2f}% supera la máxima configurada ({pmax:.2f}%)."))
            if pend < pmin - 1e-9:
                av.append(("AVISO", t[0], f"pendiente {t[2]:+.2f}% es menor que la mínima configurada ({pmin:.2f}%)."))
            if k > 0:
                a = self.tramos[k - 1]
                if abs(a[3] - t[0]) > 0.001:
                    av.append(("ERROR", t[0], f"el tramo anterior termina en {fmt_prog(a[3])} pero este empieza en "
                                              f"{fmt_prog(t[0])} (hueco o traslape)."))
                zfin = a[1] + a[2] / 100.0 * (a[3] - a[0])
                if abs(zfin - t[1]) > 0.001:
                    av.append(("ERROR", t[0], f"escalón en la rasante: el tramo anterior llega a {zfin:.3f} "
                                              f"y este empieza en {t[1]:.3f} (diferencia {t[1]-zfin:+.3f} m)."))
        if alin is not None:
            if self.tramos[0][0] > alin.prog_inicial + 0.001 or self.tramos[-1][3] < alin.prog_final - 0.01:
                av.append(("AVISO", None, f"el perfil ({fmt_prog(self.tramos[0][0])} a {fmt_prog(self.tramos[-1][3])}) "
                                          f"no cubre todo el eje ({fmt_prog(alin.prog_inicial)} a "
                                          f"{fmt_prog(alin.prog_final)}); se extrapola."))
        return av


def interseccion_segmentos(p1, p2, p3, p4):
    """Intersección de los segmentos p1-p2 y p3-p4. Devuelve (t, u) o None."""
    d1 = (p2[0] - p1[0], p2[1] - p1[1])
    d2 = (p4[0] - p3[0], p4[1] - p3[1])
    den = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(den) < 1e-12:
        return None
    w = (p3[0] - p1[0], p3[1] - p1[1])
    t = (w[0] * d2[1] - w[1] * d2[0]) / den
    u = (w[0] * d1[1] - w[1] * d1[0]) / den
    if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
        return t, u
    return None
