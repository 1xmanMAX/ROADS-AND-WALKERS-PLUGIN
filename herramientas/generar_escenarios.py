"""Genera levantamientos de prueba (ficticios) para someter la app a casos distintos del ejemplo.

Uso:  python herramientas/generar_escenarios.py [carpeta_destino]     (por defecto escenarios/)

Cada carpeta es un proyecto completo (mismos CSV que datos_ejemplo/). Semilla fija: siempre salen
iguales. Escenarios:

  E01_ladera           una calle en ladera: pendiente 9 % (> máx.), terreno con 12 % transversal
                       (corte de un lado y relleno del otro), levantamiento en grilla de 4 m.
  E02_eje_quebrado     eje con 4 vértices (deflexiones de 25°, 40° y 15°), levantamiento por
                       cadenas (eje, bordes, fachadas) cada 10 m, puertas en los quiebres.
  E03_cruce_oblicuo_T  principal + secundaria a 60° (rasantes que no coinciden) + calle en T que
                       empieza en el eje de la principal + calle que empieza en su sardinel.
  E04_llano_relleno    terreno bajo y plano: todo relleno, pendiente 0.3 % (< mín.), calle ancha.
  E05_irregular        puntos dispersos al azar, con ruido, un hueco sin puntos, puntos repetidos y
                       terreno que no llega al final de la calle; CSV de Excel en español
                       (punto y coma, coma decimal) y terreno PENZD sin cabecera.
  E06_malla_3x3        malla de 3 × 3 calles giradas 30°, 9 cruces, progresivas que empiezan en
                       1+000, coordenadas locales pequeñas.
  E07_pasaje_angosto   pasaje de 4.50 m sin vereda (ancho 0), una sola capa, bombeo 3 %,
                       pendiente 12 %, sin cuneta.
  E08_curva_cerrada    curva de radio 25 m dibujada con cuerdas de 2 m (muchos vértices) y terreno
                       en corte asimétrico: prueba el área media en curva contra Civil 3D.
  E09_codificado       levantamiento con códigos de campo (FAC, PTA, COC, POS, ARB, BZD, EMP, BM): sin
                       fachadas.csv ni umbrales.csv; la app los arma desde los códigos.
"""
import csv
import math
import random
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from corredor.datos import guardar_proyecto  # noqa: E402
from corredor.geometria import Alineamiento, Perfil  # noqa: E402
from corredor.modelo import (BM, Calle, Capa, LineaFachada, Proyecto, PuntoTerreno,  # noqa: E402
                             TramoCuneta, Umbral)

CAPAS_STD = [Capa("calzada", 1, "Losa de concreto fc210", 16), Capa("calzada", 2, "Base granular", 15),
             Capa("calzada", 3, "Subbase granular", 15),
             Capa("vereda", 1, "Concreto vereda fc175", 10), Capa("vereda", 2, "Base granular vereda", 10)]


# ------------------------------------------------------------------ utilidades
def polilinea_desplazada(vertices, o):
    """Polilínea paralela a 'o' m (derecha +) con esquinas en inglete (como OFFSET de AutoCAD)."""
    out = []
    n = len(vertices)
    for i in range(n):
        if i == 0 or i == n - 1:
            a, b = (vertices[0], vertices[1]) if i == 0 else (vertices[-2], vertices[-1])
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            nx, ny = (b[1] - a[1]) / L, -(b[0] - a[0]) / L
            p = vertices[i]
            out.append((p[0] + o * nx, p[1] + o * ny))
            continue
        a, p, b = vertices[i - 1], vertices[i], vertices[i + 1]
        L1 = math.hypot(p[0] - a[0], p[1] - a[1])
        L2 = math.hypot(b[0] - p[0], b[1] - p[1])
        n1 = ((p[1] - a[1]) / L1, -(p[0] - a[0]) / L1)
        n2 = ((b[1] - p[1]) / L2, -(b[0] - p[0]) / L2)
        bx, by = n1[0] + n2[0], n1[1] + n2[1]
        lb = math.hypot(bx, by)
        cos_m = (bx * n1[0] + by * n1[1]) / lb
        out.append((p[0] + o * bx / lb / cos_m, p[1] + o * by / lb / cos_m))
    return out


def tramos_perfil(prog0, cota0, pendientes):
    """[(longitud, pendiente %)] -> tramos de perfil encadenados."""
    t, p, z = [], prog0, cota0
    for L, g in pendientes:
        t.append([p, round(z, 4), g, p + L])
        z += g / 100 * L
        p += L
    return t


def rasante_calle(c):
    return Perfil(c.tramos)


def cota_vereda_en_fachada(c, prog, par=None):
    """Cota de la vereda terminada en el pie de fachada (sección típica sin recorte)."""
    z = rasante_calle(c).cota(prog)
    return z - c.bombeo_pct / 100 * c.ancho_calzada / 2 + 0.15 + 0.02 * c.ancho_vereda


def proyecto_base(nombre, calles):
    proy = Proyecto(nombre=nombre, calles=calles, capas=list(CAPAS_STD))
    return proy


def fachadas_paralelas(proy, c, lado, o, tramos, tipo="FACHADA"):
    """Fachadas a 'o' m del eje por tramos de progresiva [(p1, p2)] (manzanas)."""
    alin = Alineamiento(c.vertices, c.prog_inicial)
    sg = -1 if lado == "IZQ" else 1
    for k, (p1, p2) in enumerate(tramos, start=1):
        # vértices del eje dentro del tramo + extremos, desplazados
        progs = [p1] + [q for q in alin.progs_vertices() if p1 < q < p2] + [p2]
        base = [alin.punto(q) for q in progs]
        pts = polilinea_desplazada(base, sg * o) if len(base) > 2 else [alin.punto(q, sg * o) for q in progs]
        proy.fachadas.append(LineaFachada(f"{c.eje_id}-{lado}-{k}", c.eje_id, lado, tipo,
                                          [(round(e, 3), round(n, 3), tipo) for e, n in pts]))


def puerta(proy, c, id_, lado, prog, dif, tipo="PUERTA", ancho=1.0):
    alin = Alineamiento(c.vertices, c.prog_inicial)
    sg = -1 if lado == "IZQ" else 1
    o = c.ancho_calzada / 2 + 0.40 + 0.15 + c.ancho_vereda
    e, n = alin.punto(prog, sg * o)
    proy.umbrales.append(Umbral(id_, c.eje_id, lado, round(e, 3), round(n, 3),
                                round(cota_vereda_en_fachada(c, prog) + dif, 3), ancho, tipo))


def levantar(proy, z_fun, modo, paso, ruido=0.01, margen=12.0, semilla=1, hueco=None, recorte=None):
    """Puntos del levantamiento.

    modo 'grilla': grilla regular; 'cadenas': cada 'paso' m a lo largo de cada eje en offsets
    típicos; 'azar': puntos uniformes al azar con densidad 1 por paso² m².
    hueco: (e, n, radio) zona sin puntos. recorte: función (e, n) -> bool que deja fuera puntos.
    """
    rnd = random.Random(semilla)
    pts = []
    if modo == "cadenas":
        for c in proy.calles:
            alin = Alineamiento(c.vertices, c.prog_inicial)
            p = alin.prog_inicial - 3
            while p <= alin.prog_final + 3 + 1e-6:
                b = c.ancho_calzada / 2
                for o, cod in ((-(b + 2.05 + c.ancho_vereda), "PF"), (-b, "BC"), (0, "EJ"), (b, "BC"),
                               (b + 2.05 + c.ancho_vereda, "PF"), (-(b + 6), "TN"), (b + 6, "TN")):
                    e, n = alin.punto(p, o) if alin.prog_inicial <= p <= alin.prog_final else _fuera(alin, p, o)
                    pts.append((e, n, cod))
                p += paso
    else:
        es, ns = [], []
        for c in proy.calles:
            for e, n in c.vertices:
                es.append(e)
                ns.append(n)
        e0, e1, n0, n1 = min(es) - margen, max(es) + margen, min(ns) - margen, max(ns) + margen
        if modo == "grilla":
            e = e0
            while e <= e1:
                n = n0
                while n <= n1:
                    pts.append((e + rnd.uniform(-0.3, 0.3), n + rnd.uniform(-0.3, 0.3), "TN"))
                    n += paso
                e += paso
        else:
            for _ in range(int((e1 - e0) * (n1 - n0) / paso ** 2)):
                pts.append((rnd.uniform(e0, e1), rnd.uniform(n0, n1), "TN"))
        # solo cerca de alguna calle (como un levantamiento real de calles)
        alins = [Alineamiento(c.vertices, c.prog_inicial) for c in proy.calles]
        pts = [p for p in pts if any(_cerca(a, p[0], p[1], margen) for a in alins)]
    out = []
    for i, (e, n, cod) in enumerate(pts, start=1):
        if hueco and math.hypot(e - hueco[0], n - hueco[1]) < hueco[2]:
            continue
        if recorte and recorte(e, n):
            continue
        out.append(PuntoTerreno(str(1000 + i), round(e, 3), round(n, 3), round(z_fun(e, n) + rnd.uniform(-ruido, ruido), 3), cod))
    proy.terreno = out


def _fuera(alin, p, o):
    """Prolonga el eje en línea recta antes del inicio / después del final."""
    if p < alin.prog_inicial:
        ux, uy = alin.direccion(alin.prog_inicial)
        e, n = alin.punto(alin.prog_inicial, o)
        d = p - alin.prog_inicial
    else:
        ux, uy = alin.direccion(alin.prog_final)
        e, n = alin.punto(alin.prog_final, o)
        d = p - alin.prog_final
    return e + d * ux, n + d * uy


def _cerca(alin, e, n, dist):
    p, off, fuera = alin.proyectar(e, n)
    return abs(off) <= dist and fuera <= dist


def z_por_calle(proy, prof, extra=lambda e, n, p, o: 0.0):
    """Terreno = rasante de la calle más cercana + 'prof' (tapada) + extra(e, n, prog, offset)."""
    datos = [(Alineamiento(c.vertices, c.prog_inicial), Perfil(c.tramos)) for c in proy.calles]

    def z(e, n):
        mejor = None
        for alin, perf in datos:
            p, o, fuera = alin.proyectar(e, n)
            d = abs(o) + fuera
            if mejor is None or d < mejor[0]:
                mejor = (d, perf.cota(p), p, o)
        _, zr, p, o = mejor
        return zr + prof + extra(e, n, p, o)
    return z


def bms(proy, n=2):
    for i, pt in enumerate(proy.terreno[:: max(1, len(proy.terreno) // n)][:n], start=1):
        proy.bms.append(BM(f"BM-{i:02d}", pt.este, pt.norte, pt.cota, "Hito de concreto (ficticio)"))


# ------------------------------------------------------------------ escenarios
def e01_ladera():
    az = math.radians(30)
    v0 = (512300.0, 8456100.0)
    L = 180
    c = Calle("EJE-01", "Av. La Ladera", 2.0, 7.20, 1.50,
              [v0, (v0[0] + L * math.sin(az), v0[1] + L * math.cos(az))], 0.0,
              tramos_perfil(0, 2650.0, [(90, 9.0), (90, 6.0)]))
    proy = proyecto_base("E01 ladera", [c])
    # 12 % de pendiente transversal: el lado izquierdo es alto (corte), el derecho bajo (relleno)
    z = z_por_calle(proy, 0.40, lambda e, n, p, o: -0.12 * o + 0.25 * math.sin(p / 17))
    levantar(proy, z, "grilla", 4.0, ruido=0.02, margen=10, semilla=11)
    fachadas_paralelas(proy, c, "IZQ", 5.65, [(0, 55), (65, 180)])
    fachadas_paralelas(proy, c, "DER", 5.65, [(0, 80), (95, 180)], "MURO")
    puerta(proy, c, "PU-01", "IZQ", 40, 0.12)
    puerta(proy, c, "PU-02", "DER", 120, -0.05)
    bms(proy)
    return proy


def e02_eje_quebrado():
    v = [(305000.0, 8650000.0)]
    for L, az in ((70, 95), (60, 120), (80, 80), (50, 95)):     # deflexiones +25, -40, +15
        e, n = v[-1]
        v.append((e + L * math.sin(math.radians(az)), n + L * math.cos(math.radians(az))))
    c = Calle("EJE-01", "Jr. Quebrado", 2.0, 6.60, 1.20, v, 0.0,
              tramos_perfil(0, 152.30, [(100, 2.5), (60, -1.5), (100, 0.8)]))
    proy = proyecto_base("E02 eje quebrado", [c])
    proy.parametros["intervalo_secciones"] = 10.0
    z = z_por_calle(proy, 0.70, lambda e, n, p, o: 0.3 * math.sin(p / 25) - 0.01 * abs(o))
    levantar(proy, z, "cadenas", 10.0, ruido=0.015, semilla=22)
    fachadas_paralelas(proy, c, "IZQ", 5.25, [(0, 260)])
    fachadas_paralelas(proy, c, "DER", 5.25, [(0, 128), (132, 260)])
    for i, (lado, p, d) in enumerate((("IZQ", 70, 0.08), ("DER", 70, 0.05), ("DER", 130, -0.04),
                                      ("IZQ", 210, 0.10)), start=1):
        puerta(proy, c, f"PU-{i:02d}", lado, p, d)
    bms(proy)
    return proy


def e03_cruce_oblicuo_T():
    O = (420000.0, 8700000.0)
    az1 = math.radians(90)
    p1 = Calle("EJE-01", "Av. Principal", 2.0, 10.80, 2.40,
               [O, (O[0] + 240 * math.sin(az1), O[1] + 240 * math.cos(az1))], 0.0,
               tramos_perfil(0, 3400.0, [(240, 1.0)]))
    # secundaria a 60° que cruza en la 0+080 de la principal
    X = (O[0] + 80, O[1])
    az2 = math.radians(30)
    s0 = (X[0] - 60 * math.sin(az2), X[1] - 60 * math.cos(az2))
    s = Calle("EJE-02", "Jr. Oblicuo", 2.0, 7.20, 1.50,
              [s0, (s0[0] + 140 * math.sin(az2), s0[1] + 140 * math.cos(az2))], 0.0,
              tramos_perfil(0, 3400.80 - 0.6 * 0.020 * 60 - 0.02, [(140, 0.6)]))   # 2 cm de descuadre
    # calle en T que empieza justo en el eje de la principal (0+160), hacia el sur
    T0 = (O[0] + 160, O[1])
    t = Calle("EJE-03", "Psje. En T", 2.0, 6.00, 1.20, [T0, (T0[0], T0[1] - 90)], 0.0,
              tramos_perfil(0, 3401.60, [(90, -1.2)]))
    # calle que empieza en la cara del sardinel de la principal (no toca su eje), hacia el norte
    b = 10.80 / 2 + 0.40 + 0.15
    U0 = (O[0] + 210, O[1] + b)
    u = Calle("EJE-04", "Psje. Al Sardinel", 2.0, 6.00, 1.20, [U0, (U0[0], U0[1] + 70)], 0.0,
              tramos_perfil(0, 3402.10 - 0.02 * 5.4 + 0.15, [(70, 2.0)]))
    proy = proyecto_base("E03 cruce oblicuo y T", [p1, s, t, u])
    z = z_por_calle(proy, 0.80, lambda e, n, p, o: 0.2 * math.cos(e / 30) * math.sin(n / 25))
    levantar(proy, z, "grilla", 5.0, ruido=0.015, margen=12, semilla=33)
    fachadas_paralelas(proy, p1, "IZQ", 5.4 + 0.55 + 2.4, [(0, 70), (92, 205), (215, 240)])
    fachadas_paralelas(proy, p1, "DER", 5.4 + 0.55 + 2.4, [(0, 150), (170, 240)])
    puerta(proy, p1, "PU-01", "DER", 100, 0.06)
    puerta(proy, t, "PU-02", "IZQ", 40, -0.02)
    bms(proy)
    return proy


def e04_llano_relleno():
    v0 = (600000.0, 9100000.0)
    c = Calle("EJE-01", "Av. Del Llano", 2.5, 10.80, 2.40, [v0, (v0[0] + 200, v0[1] + 15)], 0.0,
              tramos_perfil(0, 25.40, [(200, 0.3)]))
    proy = proyecto_base("E04 llano en relleno", [c])
    proy.capas.append(Capa("calzada", 4, "Mejoramiento / pedraplen", 30))
    z = lambda e, n: 24.10 + 0.002 * (e - v0[0]) + 0.05 * math.sin((n - v0[1]) / 7)
    levantar(proy, z, "grilla", 6.0, ruido=0.02, margen=14, semilla=44)
    bms(proy)
    return proy


def e05_irregular():
    v0 = (330500.0, 8540200.0)
    az = math.radians(140)
    L = 220
    c = Calle("EJE-01", "Calle Irregular", 2.0, 7.20, 1.50,
              [v0, (v0[0] + L * math.sin(az), v0[1] + L * math.cos(az))], 0.0,
              tramos_perfil(0, 812.40, [(110, -2.0), (110, 1.0)]))
    proy = proyecto_base("E05 levantamiento irregular", [c])
    alin = Alineamiento(c.vertices)
    z = z_por_calle(proy, 0.55, lambda e, n, p, o: 0.4 * math.sin(p / 13) * math.cos(o / 4))
    hx, hy = alin.punto(90, 2.0)
    fin = alin.punto(200)
    levantar(proy, z, "azar", 3.5, ruido=0.03, margen=11, semilla=55, hueco=(hx, hy, 9.0),
             recorte=lambda e, n: alin.proyectar(e, n)[0] > 200)
    # puntos repetidos (misma XY, otro código y cota casi igual), como pasa al juntar dos días de campo
    rep = []
    for p in proy.terreno[::25]:
        rep.append(PuntoTerreno(p.numero + "R", p.este, p.norte, round(p.cota + 0.004, 3), "TN2"))
    proy.terreno += rep
    fachadas_paralelas(proy, c, "IZQ", 5.65, [(0, 220)])
    fachadas_paralelas(proy, c, "DER", 5.40, [(0, 100), (110, 220)])
    puerta(proy, c, "PU-01", "IZQ", 30, 0.03)
    bms(proy)
    return proy


def e06_malla_3x3():
    rot = math.radians(30)
    O = (1000.0, 2000.0)

    def P(x, y):
        return (round(O[0] + x * math.cos(rot) + y * math.sin(rot), 3),
                round(O[1] - x * math.sin(rot) + y * math.cos(rot), 3))
    calles = []
    for i, y in enumerate((0, 90, 180), start=1):
        calles.append(Calle(f"EJE-{i:02d}", f"Calle {i}", 2.0, 7.20, 1.50, [P(-20, y), P(200, y)], 1000.0,
                            tramos_perfil(1000.0, 100.0 + 0.012 * y * 100 / 100, [(220, 1.2)])))
    for j, x in enumerate((0, 90, 180), start=4):
        # rasante de las transversales: pasa por las de las longitudinales en cada cruce (aprox.)
        z0 = 100.0 + 0.012 * (x + 20) - 0.012 * 20 * 0
        calles.append(Calle(f"EJE-{j:02d}", f"Jiron {j}", 2.0, 6.60, 1.20, [P(x, -20), P(x, 200)], 1000.0,
                            tramos_perfil(1000.0, round(z0, 4), [(220, 1.08)])))
    proy = proyecto_base("E06 malla 3x3", calles)
    z = z_por_calle(proy, 0.6, lambda e, n, p, o: 0.15 * math.sin(e / 20))
    levantar(proy, z, "grilla", 6.0, ruido=0.015, margen=10, semilla=66)
    bms(proy, 3)
    return proy


def e07_pasaje_angosto():
    v0 = (288000.0, 8770000.0)
    c = Calle("EJE-01", "Psje. Angosto", 3.0, 4.50, 0.0, [v0, (v0[0] - 30, v0[1] + 110)], 0.0,
              tramos_perfil(0, 3105.0, [(60, 12.0), (54.0161, 10.0)]))
    proy = proyecto_base("E07 pasaje angosto", [c])
    proy.capas = [Capa("calzada", 1, "Adoquin sobre cama de arena", 14)]
    proy.parametros.update({"cuneta_ancho": 0.0, "cuneta_profundidad": 0.0, "intervalo_secciones": 5.0,
                            "paso_terreno": 0.05})
    z = z_por_calle(proy, 0.30, lambda e, n, p, o: 0.04 * abs(o) ** 1.5)
    levantar(proy, z, "cadenas", 5.0, ruido=0.01, semilla=77)
    fachadas_paralelas(proy, c, "IZQ", 2.25 + 0.15 + 0.10, [(0, 114)], "MURO")
    fachadas_paralelas(proy, c, "DER", 2.25 + 0.15 + 0.10, [(0, 114)], "MURO")
    bms(proy)
    return proy


def e08_curva_cerrada():
    R = 25.0
    C = (450000.0, 8800000.0)
    v = [(C[0] - 60, C[1] + R)]
    v.append((C[0], C[1] + R))
    n = 40                                    # 90° en cuerdas de ~1 m... (2 m aprox.)
    for k in range(1, n + 1):
        a = math.radians(90 - 90 * k / n)
        v.append((C[0] + R * math.cos(a), C[1] + R * math.sin(a)))
    v.append((C[0] + R, C[1] - 60))
    c = Calle("EJE-01", "Curva Cerrada", 2.0, 7.20, 1.50, [(round(e, 3), round(n_, 3)) for e, n_ in v], 0.0,
              [])
    L = Alineamiento(c.vertices).longitud
    c.tramos = tramos_perfil(0, 50.0, [(L, 1.0)])
    proy = proyecto_base("E08 curva cerrada", [c])
    # corte mucho mayor en el lado exterior de la curva (izquierda) que en el interior (derecha)
    z = z_por_calle(proy, 0.9, lambda e, n_, p, o: -0.25 * o)
    levantar(proy, z, "grilla", 3.0, ruido=0.01, margen=10, semilla=88)
    bms(proy)
    return proy


def e09_codificado():
    """Levantamiento con la codificación de campo (docs/CODIFICACION_CAMPO.md): la app arma sola las
    fachadas (FAC), las puertas (PTA/COC) y los BMs, y revisa postes, tapas y empalmes.
    Dos calles en X en ladera con pendientes variadas (6 %, 1.5 %, 3.5 % y -2 %, 4 %)."""
    O = (300000.0, 8500000.0)
    c1 = Calle("EJE-01", "Av. Codificada", 2.0, 7.20, 1.80, [O, (O[0] + 240, O[1])], 0.0,
               tramos_perfil(0, 3000.0, [(80, 6.0), (80, 1.5), (80, 3.5)]))
    c2 = Calle("EJE-02", "Jr. Codificado", 2.0, 6.00, 1.50, [(O[0] + 120, O[1] - 80), (O[0] + 120, O[1] + 80)], 0.0,
               tramos_perfil(0, 3007.0, [(80, -2.0), (80, 4.0)]))
    proy = proyecto_base("E09 levantamiento codificado", [c1, c2])
    z = z_por_calle(proy, 0.35, lambda e, n, p, o: 0.03 * abs(o))
    levantar(proy, z, "grilla", 4.0, ruido=0.01, margen=11, semilla=99)
    pts = proy.terreno
    num = [5000]

    def pt(e, n, cota, cod):
        num[0] += 1
        pts.append(PuntoTerreno(str(num[0]), round(e, 3), round(n, 3), round(cota, 3), cod))

    def vereda(c, prog, lado):
        al = Alineamiento(c.vertices, c.prog_inicial)
        sg = -1 if lado == "IZQ" else 1
        o = c.ancho_calzada / 2 + 0.40 + 0.15 + c.ancho_vereda
        return al, sg, o
    # fachadas: una línea por cuadra y lado, numeradas, puntos cada 10 m al pie del muro
    linea = 0
    for c, cuadras in ((c1, [(0, 112), (128, 240)]), (c2, [(0, 72), (88, 160)])):
        for lado in ("IZQ", "DER"):
            for p1, p2 in cuadras:
                linea += 1
                al, sg, o = vereda(c, 0, lado)
                q = p1
                while q <= p2 + 1e-6:
                    e, n = al.punto(q, sg * (o + 0.05))
                    pt(e, n, z(e, n), f"FAC{linea}")
                    q += 10 if q + 10 <= p2 or q == p2 else p2 - q
    # puertas (umbral = vereda de diseño + diferencia) y una cochera; la de 0+050 queda enterrada
    for c, prog, lado, dif, cod in ((c1, 50, "DER", -0.04, "PTA 0.90"), (c1, 180, "IZQ", 0.12, "PTA 1.00"),
                                    (c2, 40, "DER", 0.08, "COC 3.00"), (c2, 130, "IZQ", 0.05, "PTA 0.90")):
        al, sg, o = vereda(c, prog, lado)
        e, n = al.punto(prog, sg * o)
        pt(e, n, cota_vereda_en_fachada(c, prog) + dif, cod)
    # postes: en la vereda, en la calzada (error) y uno junto a la fachada; un árbol
    al1 = Alineamiento(c1.vertices)
    e, n = al1.punto(70, 3.60 + 0.40 + 0.15 + 0.50)
    pt(e, n, z(e, n), "POS 0.25 / alumbrado")
    e, n = al1.punto(200, -(3.60 - 0.30))
    pt(e, n, z(e, n), "POS 0.30 / poste en la pista")
    e, n = al1.punto(30, -(3.60 + 0.40 + 0.15 + 1.60))
    pt(e, n, z(e, n), "POS 0.20")
    e, n = al1.punto(150, 3.60 + 0.40 + 0.15 + 0.30)
    pt(e, n, z(e, n), "ARB 0.45")
    # tapas de buzón en el eje (a la cota del terreno actual: hay que nivelarlas)
    for prog in (40, 160, 220):
        e, n = al1.punto(prog)
        pt(e, n, z(e, n) - 0.05, "BZD")
    # empalmes con el pavimento existente en los extremos de EJE-01 (el del final no calza: +4 cm)
    for prog, dz in ((0.0, 0.0), (240.0, 0.04)):
        for o in (-3.0, 0.0, 3.0):
            e, n = al1.punto(prog, o)
            zr = Perfil(c1.tramos).cota(prog) - 0.02 * abs(o)
            pt(e, n, zr + dz, "EMP")
    # BMs
    pt(O[0] - 8, O[1] + 9, z(O[0] - 8, O[1] + 9) + 0.12, "BM / BM-01")
    pt(O[0] + 248, O[1] - 9, z(O[0] + 248, O[1] - 9) + 0.12, "BM / BM-02")
    return proy


ESCENARIOS = {
    "E01_ladera": e01_ladera, "E02_eje_quebrado": e02_eje_quebrado, "E03_cruce_oblicuo_T": e03_cruce_oblicuo_T,
    "E04_llano_relleno": e04_llano_relleno, "E05_irregular": e05_irregular, "E06_malla_3x3": e06_malla_3x3,
    "E07_pasaje_angosto": e07_pasaje_angosto, "E08_curva_cerrada": e08_curva_cerrada,
    "E09_codificado": e09_codificado,
}


def _a_excel_es(carpeta):
    """Reescribe los CSV como los guarda Excel en español: punto y coma y coma decimal."""
    for f in carpeta.glob("*.csv"):
        filas = list(csv.reader(f.read_text(encoding="utf-8").splitlines()))
        with open(f, "w", newline="", encoding="cp1252", errors="replace") as h:
            w = csv.writer(h, delimiter=";")
            for fila in filas:
                # Excel agrega ';' al final de algunas filas: se imita en la de encabezado del terreno
                w.writerow([c.replace(".", ",") if _es_num(c) else c for c in fila])


def _es_num(c):
    try:
        float(c)
        return "." in c
    except ValueError:
        return False


def main(destino):
    destino = Path(destino)
    for nombre, fun in ESCENARIOS.items():
        proy = fun()
        car = destino / nombre
        guardar_proyecto(proy, car)
        if nombre == "E05_irregular":
            _a_excel_es(car)
            # Excel suele dejar columnas vacías de más al final de las filas
            fa = car / "fachadas.csv"
            fa.write_text("\n".join(l + ";;" for l in fa.read_text(encoding="cp1252").splitlines()[1:])
                          and fa.read_text(encoding="cp1252").splitlines()[0] + "\n" +
                          "\n".join(l + ";;" for l in fa.read_text(encoding="cp1252").splitlines()[1:]) + "\n",
                          encoding="cp1252")
            # terreno en PENZD sin cabecera (como lo baja la estación total)
            (car / "terreno.csv").write_text(
                "\n".join(f"{p.numero},{p.este:.3f},{p.norte:.3f},{p.cota:.3f},{p.codigo}" for p in proy.terreno) + "\n",
                encoding="utf-8")
        print(f"{nombre}: {len(proy.calles)} calles, {len(proy.terreno)} puntos, "
              f"{len(proy.fachadas)} fachadas, {len(proy.umbrales)} umbrales")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else RAIZ / "escenarios")
