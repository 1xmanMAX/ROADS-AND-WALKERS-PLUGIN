r"""Sección transversal típica aplicada en una progresiva.

Puntos de la sección (de izquierda a derecha; sufijo I = izquierda, D = derecha):

  PFI  BVI  CSI        BCI           EJE           BCD        CSD  BVD  PFD
   |vereda|sard|        \___ calzada (bombeo) ___/        |sard|vereda|
              PSI\_FCI_/                                   \_FCD_/PSD
                  cuneta                                    cuneta

  EJE  eje (cota de rasante)
  BC   borde de calzada          = rasante − bombeo × semiancho
  FC   fondo de cuneta (V)       = BC − profundidad, a la mitad del ancho de cuneta
  PS   pie de sardinel           = misma cota que BC, al final de la cuneta
  CS   cabeza de sardinel        = BC + altura de sardinel (cara vertical)
  BV   borde interior de vereda  = CS, tras el ancho del sardinel
  PF   pie de fachada (borde exterior de vereda) = BV + pendiente vereda × ancho vereda

Capas de calzada: paralelas a la rasante (siguen el bombeo). La 1.ª capa
(losa/carpeta) ocupa solo la calzada; las capas granulares de debajo se
prolongan bajo la cuneta y el sardinel. Capas de vereda: paralelas a la vereda.
Subrasante (fondo de excavación): fondo de la última capa de calzada y, bajo la
vereda, fondo de la última capa de vereda.
"""
import math
from dataclasses import dataclass, field

ORDEN_LADO = ["PF", "BV", "CS", "PS", "FC", "BC"]   # de afuera hacia el eje


@dataclass
class Seccion:
    eje_id: str
    prog: float
    rasante: float
    pendiente: float
    e: float
    n: float
    nx: float
    ny: float
    lateral: dict = field(default_factory=dict)        # {'I': bool, 'D': bool}
    vereda_ancho: dict = field(default_factory=dict)   # ancho usado por lado
    vereda_disponible: dict = field(default_factory=dict)
    cuneta: dict = field(default_factory=dict)         # {'I': (ancho, prof)}
    omitida: bool = False                              # dentro de una calle principal (intersección)
    tipo: str = "INTERVALO"
    lineas: dict = field(default_factory=dict)         # nombre -> [(codigo, offset, z)] izq->der
    poligonos: dict = field(default_factory=dict)      # capa -> [[(o, z), ...], ...]
    area_corte: float = 0.0
    area_relleno: float = 0.0
    terreno_faltante: float = 0.0
    perfil_terreno: list = field(default_factory=list)  # [(o, z_terreno)]

    def xy(self, offset):
        return self.e + offset * self.nx, self.n + offset * self.ny

    def punto(self, linea, codigo):
        for c, o, z in self.lineas.get(linea, []):
            if c == codigo:
                return o, z
        return None

    @property
    def puntos(self):
        return self.lineas["TERMINADO"]

    def area(self, capa):
        return sum(area_poligono(p) for p in self.poligonos.get(capa, []))


def area_poligono(pts):
    a = 0.0
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def _espejo(lista_derecha):
    """Convierte la lista del lado derecho (del eje hacia afuera) en la del lado izquierdo, afuera->eje."""
    return [(c[:-1] + "I" if c.endswith("D") else c, -o, z) for c, o, z in reversed(lista_derecha)]


def construir(calle, alin, perfil, prog, par, capas_calz, capas_ver,
              lateral, ancho_vereda, cuneta, tipo="INTERVALO"):
    """Construye la sección completa.

    par: parámetros del proyecto (dict con valores en cm/% tal como en la interfaz).
    lateral / ancho_vereda / cuneta: diccionarios por lado 'I' y 'D'.
    """
    R = perfil.cota(prog)
    e, n = alin.punto(prog)
    nx, ny = alin.normal(prog)
    s = calle.bombeo_pct / 100.0
    b = calle.ancho_calzada / 2.0
    ws = par["sardinel_ancho"] / 100.0
    hs = par["sardinel_altura"] / 100.0
    pv = par["vereda_pendiente"] / 100.0
    zBC = R - s * b

    sec = Seccion(calle.eje_id, prog, R, perfil.pendiente(prog), e, n, nx, ny,
                  lateral=dict(lateral), vereda_ancho={}, cuneta=dict(cuneta), tipo=tipo)

    t_calz = [c.espesor for c in capas_calz]
    t_ver = [c.espesor for c in capas_ver]
    T = sum(t_calz)
    Tv = sum(t_ver)

    lados = {}
    ext = {}       # hasta dónde llegan las capas granulares de calzada
    for lado in ("I", "D"):
        pts = [("BC" + "D", b, zBC)]
        info = {"o_bv": None}
        if lateral[lado]:
            c, hc = cuneta[lado]
            w = max(0.0, ancho_vereda[lado])
            o_ps = b + c
            o_bv = o_ps + ws
            o_pf = o_bv + w
            zCS = zBC + hs
            pts += [("FCD", b + c / 2.0, zBC - hc), ("PSD", o_ps, zBC), ("CSD", o_ps, zCS),
                    ("BVD", o_bv, zCS), ("PFD", o_pf, zCS + pv * w)]
            info.update(o_ps=o_ps, o_bv=o_bv, o_pf=o_pf, zCS=zCS, w=w, c=c, hc=hc)
            ext[lado] = o_bv
            sec.vereda_ancho[lado] = w
        else:
            ext[lado] = b
            sec.vereda_ancho[lado] = 0.0
        lados[lado] = (pts, info)

    # ---- superficie terminada
    der = lados["D"][0]
    izq = _espejo(lados["I"][0])
    sec.lineas["TERMINADO"] = izq + [("EJE", 0.0, R)] + der

    # ---- capas de calzada
    prof = 0.0
    for k, (capa, t) in enumerate(zip(capas_calz, t_calz), start=1):
        eI = b if k == 1 else ext["I"]
        eD = b if k == 1 else ext["D"]
        zt = lambda o, d=prof: R - s * abs(o) - d
        tope = [("LI", -eI, zt(-eI)), ("EJE", 0.0, zt(0.0)), ("LD", eD, zt(eD))]
        if k > 1:   # puntos en el borde de calzada para replanteo de cada capa
            tope = [tope[0], ("BCI", -b, zt(-b)), tope[1], ("BCD", b, zt(b)), tope[2]]
        else:
            tope = [("BCI", -b, zt(-b)), ("EJE", 0.0, zt(0.0)), ("BCD", b, zt(b))]
        fondo = [(c_, o, z - t) for c_, o, z in tope]
        sec.lineas[f"C{k}_TOPE"] = tope
        sec.lineas[f"C{k}_FONDO"] = fondo
        sec.poligonos[capa.nombre] = [[(o, z) for _, o, z in tope] + [(o, z) for _, o, z in reversed(fondo)]]
        prof += t

    # ---- cuneta + sardinel (concreto) y capas de vereda
    t1 = t_calz[0] if t_calz else 0.0
    sec.poligonos["Concreto cuneta y sardinel"] = []
    for lado, sg in (("I", -1), ("D", 1)):
        pts, info = lados[lado]
        if not lateral[lado]:
            continue
        o_bv, o_pf, zCS, w = info["o_bv"], info["o_pf"], info["zCS"], info["w"]
        poly = [(o, z) for _, o, z in pts[:5]] + [(o_bv, R - s * o_bv - t1), (b, R - s * b - t1)]
        sec.poligonos["Concreto cuneta y sardinel"].append([(sg * o, z) for o, z in poly])
        if w <= 0:
            continue
        d = 0.0
        for k, (capa, t) in enumerate(zip(capas_ver, t_ver), start=1):
            tope = [("BV", o_bv, zCS - d), ("PF", o_pf, zCS + pv * w - d)]
            fondo = [(c_, o, z - t) for c_, o, z in tope]
            suf = lado
            sec.lineas[f"V{k}_TOPE_{suf}"] = [(c_ + suf, sg * o, z) for c_, o, z in (tope if sg > 0 else tope[::-1])]
            sec.lineas[f"V{k}_FONDO_{suf}"] = [(c_ + suf, sg * o, z) for c_, o, z in (fondo if sg > 0 else fondo[::-1])]
            sec.poligonos.setdefault(capa.nombre, []).append(
                [(sg * o, z) for _, o, z in tope] + [(sg * o, z) for _, o, z in reversed(fondo)])
            d += t

    # ---- subrasante (fondo de excavación), izquierda -> derecha
    def lado_sub(lado):
        _, info = lados[lado]
        e_ = ext[lado]
        res = [("SBC", e_, R - s * e_ - T)]
        if lateral[lado] and info["w"] > 0:
            res += [("SVI", info["o_bv"], info["zCS"] - Tv), ("SVE", info["o_pf"], info["zCS"] + pv * info["w"] - Tv)]
        return res

    d_sub = [(c_ + "D", o, z) for c_, o, z in lado_sub("D")]
    i_sub = [(c_ + "I", -o, z) for c_, o, z in reversed(lado_sub("I"))]
    sec.lineas["SUBRASANTE"] = i_sub + [("EJE", 0.0, R - T)] + d_sub
    return sec


def calcular_tierras(sec, terreno, paso=0.10):
    """Área de corte y relleno entre el terreno y la subrasante.

    Se recorre la línea de subrasante con un paso pequeño; en cada punto
    diferencia = terreno − subrasante. Positivo = corte, negativo = relleno.
    Área = suma de trapecios: ancho × (dif1 + dif2) / 2, partiendo el trapecio
    donde el terreno cruza la subrasante.
    """
    linea = sec.lineas["SUBRASANTE"]
    corte = relleno = faltante = 0.0
    perfil_t = []
    for (c1, oa, za), (c2, ob, zb) in zip(linea[:-1], linea[1:]):
        if ob - oa < 1e-9:      # tramo vertical: no aporta área
            continue
        m = max(1, math.ceil((ob - oa) / paso))
        os_ = [oa + (ob - oa) * i / m for i in range(m + 1)]
        es = [sec.e + o * sec.nx for o in os_]
        ns = [sec.n + o * sec.ny for o in os_]
        zt = terreno.cota(es, ns) if terreno is not None and terreno.ok else [float("nan")] * len(os_)
        difs = []
        for i, o in enumerate(os_):
            zd = za + (zb - za) * (o - oa) / (ob - oa)
            zti = float(zt[i])
            perfil_t.append((o, zti))
            difs.append(zti - zd)
        for i in range(m):
            h = os_[i + 1] - os_[i]
            d1, d2 = difs[i], difs[i + 1]
            if math.isnan(d1) or math.isnan(d2):
                faltante += h
                continue
            if d1 >= 0 and d2 >= 0:
                corte += h * (d1 + d2) / 2
            elif d1 <= 0 and d2 <= 0:
                relleno += -h * (d1 + d2) / 2
            else:
                x = h * d1 / (d1 - d2)
                if d1 > 0:
                    corte += x * d1 / 2
                    relleno += -(h - x) * d2 / 2
                else:
                    relleno += -x * d1 / 2
                    corte += (h - x) * d2 / 2
    sec.area_corte, sec.area_relleno, sec.terreno_faltante = corte, relleno, faltante
    # perfil del terreno en todo el ancho (para dibujar)
    sec.perfil_terreno = sorted({round(o, 4): z for o, z in perfil_t}.items())
    return corte, relleno
