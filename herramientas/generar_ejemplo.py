"""
Genera el proyecto de ejemplo en datos_ejemplo/ (reproducible, semilla fija).

    python herramientas/generar_ejemplo.py

Escenario: 4 cuadras de una malla en el altiplano.
  - EJE-01 "Jr. Los Andes": recto, 250 m, azimut 80°, quiebre de pendiente en 0+120 (+1.5 % / -0.8 %).
  - EJE-02 "Jr. Las Flores": recto, 200 m, azimut 350°, +1.2 %, cruza al EJE-01 en su 0+130 (EJE-02 0+100).

El levantamiento sale en UN solo archivo con códigos de campo (ver docs/CODIGOS.md):
TN/EJ/BC terreno, CA casas, MU muros, LP lotes, PU puertas, COI/COF cocheras, BZ buzones,
PO postes, AR árboles, GR grifos, CAG/CLZ cajas, SEN señales, BM1..BM3.
"""
import csv
import math
import random
import sys
from pathlib import Path

random.seed(2026)
RAIZ = Path(__file__).resolve().parent.parent
OUT = RAIZ / "datos_ejemplo"
OUT.mkdir(exist_ok=True)
sys.path.insert(0, str(RAIZ))

A0 = (390100.000, 8250300.000)
AZ_A, AZ_B = math.radians(80.0), math.radians(350.0)
LEN_A, LEN_B = 250.0, 200.0
CRUCE_A, CRUCE_B = 130.0, 100.0
uA = (math.sin(AZ_A), math.cos(AZ_A))
uB = (math.sin(AZ_B), math.cos(AZ_B))
X = (A0[0] + CRUCE_A * uA[0], A0[1] + CRUCE_A * uA[1])
B0 = (X[0] - CRUCE_B * uB[0], X[1] - CRUCE_B * uB[1])


def punto(origen, u, prog, offset):
    nx, ny = u[1], -u[0]
    return (origen[0] + prog * u[0] + offset * nx, origen[1] + prog * u[1] + offset * ny)


def pA(p, o):
    return punto(A0, uA, p, o)


def pB(p, o):
    return punto(B0, uB, p, o)


def ras_A(p):
    p = max(0.0, min(LEN_A, p))
    return 3820.500 + 0.015 * p if p <= 120 else 3822.300 - 0.008 * (p - 120)


def ras_B(p):
    return ras_A(CRUCE_A) + 0.012 * (p - CRUCE_B)


SEMI, BOMBEO, CUN, SAR_A, SAR_H, VER, PV = 3.60, 0.02, 0.40, 0.15, 0.15, 1.50, 0.02
OFF_F = SEMI + CUN + SAR_A + VER   # 5.65


def vereda_en(ras, off_fachada=OFF_F, cun=CUN):
    w = off_fachada - (SEMI + cun + SAR_A)
    return ras - BOMBEO * SEMI + SAR_H + PV * min(w, VER)


def coords_locales(e, n):
    s = (e - A0[0]) * uA[0] + (n - A0[1]) * uA[1]
    t = (e - X[0]) * uB[0] + (n - X[1]) * uB[1]
    return s, t


def z_terreno(e, n, ruido=True):
    s, t = coords_locales(e, n)
    z = ras_A(s) + 0.012 * t + 0.30
    z += 0.12 * math.sin(s / 23.0) * math.cos(t / 31.0)
    z -= 1.60 * math.exp(-(((s - CRUCE_A) / 14.0) ** 2 + ((t - 75.0) / 12.0) ** 2))
    z -= 0.010 * min(min(abs(t), abs(s - CRUCE_A)), 6.0)
    if ruido:
        z += random.uniform(-0.015, 0.015)
    return z


def w(nombre, cab, filas):
    with open(OUT / nombre, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(cab)
        wr.writerows(filas)
    print(f"  {nombre}: {len(filas)} filas")


f3 = lambda v: f"{v:.3f}"

# ================================================================ diseño
w("calles.csv", ["eje_id", "nombre", "bombeo_pct", "ancho_calzada_m", "ancho_vereda_m"],
  [["EJE-01", "Jr. Los Andes", "2.0", "7.20", "1.50"], ["EJE-02", "Jr. Las Flores", "2.0", "7.20", "1.50"]])
w("ejes.csv", ["eje_id", "nombre", "vertice", "este", "norte", "prog_inicial"],
  [["EJE-01", "Jr. Los Andes", 1, f3(A0[0]), f3(A0[1]), "0.000"],
   ["EJE-01", "Jr. Los Andes", 2, *map(f3, pA(LEN_A, 0)), ""],
   ["EJE-02", "Jr. Las Flores", 1, f3(B0[0]), f3(B0[1]), "0.000"],
   ["EJE-02", "Jr. Las Flores", 2, *map(f3, pB(LEN_B, 0)), ""]])
w("perfil.csv", ["eje_id", "prog_inicio", "cota_inicio", "pendiente_pct", "prog_fin"],
  [["EJE-01", "0.000", "3820.500", "1.500", "120.000"], ["EJE-01", "120.000", "3822.300", "-0.800", "250.000"],
   ["EJE-02", "0.000", f3(ras_B(0)), "1.200", "200.000"]])
w("seccion_tipica.csv", ["parametro", "valor", "unidad", "descripcion"], [
    ["cuneta_ancho", "40", "cm", ""], ["cuneta_profundidad", "10", "cm", ""], ["sardinel_ancho", "15", "cm", ""],
    ["sardinel_altura", "15", "cm", ""], ["vereda_pendiente", "2.0", "%", ""], ["intervalo_secciones", "10", "m", ""],
    ["pendiente_long_max", "8.0", "%", "A CONFIRMAR"], ["pendiente_long_min", "0.5", "%", "A CONFIRMAR"],
    ["vereda_ancho_min", "120", "cm", "A CONFIRMAR"]])
w("capas.csv", ["ambito", "orden_desde_arriba", "nombre", "espesor_cm"], [
    ["calzada", 1, "Losa de concreto f'c=210", "16"], ["calzada", 2, "Base granular", "15"],
    ["calzada", 3, "Subbase granular", "15"], ["calzada", 4, "Pedraplén / mejoramiento", "20"],
    ["vereda", 1, "Concreto vereda f'c=175", "10"], ["vereda", 2, "Base granular vereda", "10"]])
w("cunetas_por_tramo.csv", ["eje_id", "lado", "prog_ini", "prog_fin", "ancho_cm", "profundidad_cm", "nota"],
  [["EJE-02", "DER", "150.000", "200.000", "50", "15", "Tramo de hondonada: cuneta mayor"]])

# ================================================================ levantamiento codificado
pts = []
num = {"v": 1000}


def agregar(e, n, z, cod, numero=None):
    if numero is None:
        num["v"] += 1
        numero = num["v"]
    pts.append([numero, f3(e), f3(n), f3(z), cod])


# --- BM (puntos 1, 2, 3) sobre hitos junto a fachadas
for i, (fn, p, o, nota) in enumerate(((pA, 5.0, -5.75, "BM1 hito en esquina de casa"),
                                      (pA, 145.0, 5.75, "BM2 hito junto a cochera"),
                                      (pB, 192.0, -5.75, "BM3 hito en muro")), start=1):
    e, n = fn(p, o)
    agregar(e, n, z_terreno(e, n, False) + 0.10, nota, numero=i)

# --- terreno por secciones cada 15 m (eje, bordes del camino actual)
num["v"] = 1000
for nombre, fn, L, cruce in (("A", pA, LEN_A, CRUCE_A), ("B", pB, LEN_B, CRUCE_B)):
    progs = [-3.0] + list(range(0, int(L) + 1, 15)) + ([L] if L % 15 else []) + [L + 3.0]
    for p in progs:
        if nombre == "B" and abs(p - cruce) < 8:
            continue
        for o, cod in ((-3.5, "BC"), (0.0, "EJ"), (3.5, "BC")):
            pj = p if p in (-3.0, 0, L, L + 3.0) else p + random.uniform(-0.8, 0.8)
            e, n = fn(pj, o + random.uniform(-0.2, 0.2))
            agregar(e, n, z_terreno(e, n), cod)
        if p in (-3.0, L + 3.0):
            for o in (-6.0, 6.0):
                e, n = fn(p, o)
                agregar(e, n, z_terreno(e, n), "TN")
for di in (-8, -4, 4, 8):
    for dj in (-8, -4, 4, 8):
        if abs(di) == 8 and abs(dj) == 8:
            continue
        e = X[0] + di * uA[0] + dj * uB[0]
        n = X[1] + di * uA[1] + dj * uB[1]
        agregar(e, n, z_terreno(e, n), "TN")

# --- manzanas: fachadas (CA), muro (MU), lote vacío (LP), puertas y cocheras en el recorrido
num["v"] = 2000
FA = CRUCE_A - OFF_F          # 124.35: esquina sobre EJE-01
FA2 = CRUCE_A + OFF_F         # 135.65
FB = CRUCE_B - OFF_F          # 94.35
FB2 = CRUCE_B + OFF_F         # 105.65


def off_fach(calle, lado, p):
    j = random.uniform(-0.03, 0.03)
    if calle == "A" and lado == "D" and 200 <= p <= 215:
        return 5.45
    if calle == "B" and lado == "D" and 20 <= p <= 32:
        return 5.05
    return OFF_F + j


eventos = {   # (calle, lado) -> lista de (prog, tipo, datos)
    ("A", "D"): [(35.0, "PU", 0.06), (100.0, "PU", 0.15), (168.5, "COI", 0.02), (171.5, "COF", 0.03)],
    ("A", "I"): [(85.0, "PU", -0.08)],
    ("B", "I"): [(50.0, "PU", 0.12), (120.0, "COI", -0.04), (123.0, "COF", -0.05)],
    ("B", "D"): [(140.0, "PU", -0.03)],
}


def recorrido(calle, lado, p_ini, p_fin, codigo):
    """Puntos de fachada de p_ini a p_fin (cada 10 m + quiebres), con puertas y cocheras intercaladas."""
    fn, ras = (pA, ras_A) if calle == "A" else (pB, ras_B)
    sg = -1 if lado == "I" else 1
    paso = 10 if p_fin > p_ini else -10
    progs = {round(p_ini, 2), round(p_fin, 2)}
    q = math.ceil(min(p_ini, p_fin) / 10) * 10
    while q < max(p_ini, p_fin):
        progs.add(q)
        q += 10
    for qq in (20, 32, 200, 215):
        if min(p_ini, p_fin) < qq < max(p_ini, p_fin):
            progs |= {qq - 0.05, qq + 0.05}
    bordes = {"A": {"I": (39.9, 60.1)}, "B": {"I": (149.9, 190.1)}}.get(calle, {}).get(lado, ())
    progs |= {q for q in bordes if min(p_ini, p_fin) < q < max(p_ini, p_fin)}
    ev = {p: (t, d) for p, t, d in eventos.get((calle, lado), []) if min(p_ini, p_fin) <= p <= max(p_ini, p_fin)}
    progs |= set(ev)
    for p in sorted(progs, reverse=paso < 0):
        if calle == "A" and lado == "I" and 40 <= p <= 60:
            continue              # ahí hay un muro (se levanta aparte con MU1)
        if calle == "B" and lado == "I" and 150 <= p <= 190:
            continue              # lote vacío (LP1)
        o = off_fach(calle, lado, p)
        e, n = fn(p, sg * o)
        if p in ev:
            t, dz = ev[p]
            if t != "COF":     # punto de terreno al pie del muro junto a la puerta
                e2, n2 = fn(p - 0.3 * (1 if paso > 0 else -1), sg * o)
                agregar(e2, n2, z_terreno(e2, n2), codigo)
            agregar(e, n, vereda_en(ras(p), o) + dz, t)
            if t != "COI":
                e2, n2 = fn(p + 0.3 * (1 if paso > 0 else -1), sg * o)
                agregar(e2, n2, z_terreno(e2, n2), codigo)
        else:
            agregar(e, n, z_terreno(e, n), codigo)


# manzana NO (izq EJE-01 hasta la esquina, luego izq EJE-02 hacia el norte)
recorrido("A", "I", 0.0, FA, "CA1")
recorrido("B", "I", FB2, LEN_B, "CA1")
# manzana NE (izq EJE-01 desde la esquina, der EJE-02)
recorrido("B", "D", LEN_B, FB2, "CA2")
recorrido("A", "I", FA2, LEN_A, "CA2")
# manzana SE
recorrido("A", "D", LEN_A, FA2, "CA3")
recorrido("B", "D", FB, 0.0, "CA3")
# manzana SO
recorrido("B", "I", 0.0, FB, "CA4")
recorrido("A", "D", FA, 0.0, "CA4")
# muro adelantado y lote vacío
for p in (40.0, 45.0, 50.0, 55.0, 60.0):
    e, n = pA(p, -5.30)
    agregar(e, n, z_terreno(e, n), "MU1")
for p in (150.0, 160.0, 170.0, 180.0, 190.0):
    e, n = pB(p, -5.65)
    agregar(e, n, z_terreno(e, n), "LP1")

# --- elementos sueltos
num["v"] = 3000
for fn, ras, p, o, cod, dz in (
        (pA, ras_A, 60.0, 0.0, "BZ", None), (pA, ras_A, 190.0, 0.0, "BZ", None),
        (pB, ras_B, 50.0, 0.0, "BZ", None), (pB, ras_B, 175.0, 0.0, "BZ", None),
        (pA, ras_A, 100.0, -5.20, "PO", None), (pA, ras_A, 150.0, 3.95, "PO", None),
        (pB, ras_B, 70.0, 5.30, "PO", None), (pB, ras_B, 180.0, -4.50, "PO", None),
        (pA, ras_A, 230.0, 4.80, "AR", None), (pB, ras_B, 80.0, -4.60, "GR", None),
        (pA, ras_A, 36.5, 5.50, "CAG", 0.0), (pB, ras_B, 52.0, -5.50, "CAG", -0.05),
        (pA, ras_A, 150.0, -5.50, "CLZ", 0.04), (pA, ras_A, 118.0, -4.40, "SEN", None)):
    e, n = fn(p, o)
    if dz is not None:      # caja en vereda: tapa cerca del nivel de la vereda proyectada
        z = vereda_en(ras(p)) - PV * (OFF_F - abs(o)) + dz
    else:
        z = z_terreno(e, n)
    agregar(e, n, z, cod)

w("levantamiento.csv", ["punto", "este", "norte", "cota", "codigo"], pts)
for viejo in ("terreno.csv", "fachadas.csv", "umbrales.csv", "bm.csv"):
    (OUT / viejo).unlink(missing_ok=True)

from corredor.codigos import Catalogo, guardar_catalogo  # noqa: E402

guardar_catalogo(Catalogo(), OUT / "codigos.csv")
print("  codigos.csv: catálogo por defecto")
print("Listo en", OUT)
