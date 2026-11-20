"""
Genera el conjunto de datos de ejemplo (Paso 1) en la carpeta datos_ejemplo/.

Es reproducible: siempre produce los mismos CSV (semilla fija).
Uso:  python herramientas/generar_ejemplo.py

Escenario: 4 cuadras en una malla
  - EJE-01 "Jr. Los Andes": recto, 250 m, rumbo (azimut) 80°, con quiebre
    de pendiente en 0+120 (+1.5 % y luego -0.8 %).
  - EJE-02 "Jr. Las Flores": recto, 200 m, azimut 350° (perpendicular),
    pendiente única +1.2 %, cruza al EJE-01 en su 0+130 (EJE-02 0+100).
"""
import csv
import math
import random
from pathlib import Path

random.seed(2026)
OUT = Path(__file__).resolve().parent.parent / "datos_ejemplo"
OUT.mkdir(exist_ok=True)

# ---------------------------------------------------------------- geometría
A0 = (390100.000, 8250300.000)          # inicio EJE-01 (UTM WGS84 19S, ficticio)
AZ_A = math.radians(80.0)
AZ_B = math.radians(350.0)
LEN_A, LEN_B = 250.0, 200.0
CRUCE_A, CRUCE_B = 130.0, 100.0          # progresiva del cruce en cada eje

uA = (math.sin(AZ_A), math.cos(AZ_A))    # vector unitario a lo largo del eje
uB = (math.sin(AZ_B), math.cos(AZ_B))
# normal derecha = girar 90° horario el vector de avance
def der(u):
    return (u[1], -u[0])

X = (A0[0] + CRUCE_A * uA[0], A0[1] + CRUCE_A * uA[1])   # punto de cruce
B0 = (X[0] - CRUCE_B * uB[0], X[1] - CRUCE_B * uB[1])


def punto(origen, u, prog, offset):
    """Coordenada a 'prog' metros del origen y 'offset' a la derecha (+) / izquierda (-)."""
    n = der(u)
    return (origen[0] + prog * u[0] + offset * n[0],
            origen[1] + prog * u[1] + offset * n[1])


# ---------------------------------------------------------------- rasantes
def ras_A(p):
    p = max(0.0, min(LEN_A, p))
    if p <= 120:
        return 3820.500 + 0.015 * p
    return 3822.300 - 0.008 * (p - 120)


def ras_B(p):
    return ras_A(CRUCE_A) + 0.012 * (p - CRUCE_B)


# ---------------------------------------------------------------- sección (solo para generar umbrales coherentes)
SEMI_CALZADA = 3.60
BOMBEO = 0.02
CUNETA_ANCHO = 0.40
SARDINEL_ANCHO = 0.15
SARDINEL_ALTO = 0.15
VEREDA_ANCHO = 1.50
VEREDA_PEND = 0.02
OFF_FACHADA = SEMI_CALZADA + CUNETA_ANCHO + SARDINEL_ANCHO + VEREDA_ANCHO   # 5.65


def cota_vereda_fachada(ras):
    borde = ras - BOMBEO * SEMI_CALZADA
    return borde + SARDINEL_ALTO + VEREDA_PEND * VEREDA_ANCHO


# ---------------------------------------------------------------- terreno existente
def coords_locales(e, n):
    """s = distancia a lo largo del EJE-01 desde A0, t = distancia a lo largo del EJE-02 desde el cruce."""
    de, dn = e - A0[0], n - A0[1]
    s = de * uA[0] + dn * uA[1]
    de2, dn2 = e - X[0], n - X[1]
    t = de2 * uB[0] + dn2 * uB[1]
    return s, t


def z_terreno(e, n):
    s, t = coords_locales(e, n)
    z = ras_A(s) + 0.012 * t + 0.30
    z += 0.12 * math.sin(s / 23.0) * math.cos(t / 31.0)
    # hondonada (zona de relleno) cerca de EJE-02 0+175
    z -= 1.60 * math.exp(-(((s - CRUCE_A) / 14.0) ** 2 + ((t - 75.0) / 12.0) ** 2))
    # terreno más bajo hacia los costados del camino actual (camino abombado)
    d_axis = min(abs(t), abs(s - CRUCE_A))
    z -= 0.010 * min(d_axis, 6.0)
    z += random.uniform(-0.015, 0.015)
    return z


def w(nombre, cabecera, filas):
    with open(OUT / nombre, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(cabecera)
        wr.writerows(filas)
    print(f"  {nombre}: {len(filas)} filas")


f3 = lambda v: f"{v:.3f}"

# ================================================================ 1. ejes.csv
ejes = [
    ["EJE-01", "Jr. Los Andes", 1, f3(A0[0]), f3(A0[1]), "0.000"],
    ["EJE-01", "Jr. Los Andes", 2, *map(f3, punto(A0, uA, LEN_A, 0)), ""],
    ["EJE-02", "Jr. Las Flores", 1, f3(B0[0]), f3(B0[1]), "0.000"],
    ["EJE-02", "Jr. Las Flores", 2, *map(f3, punto(B0, uB, LEN_B, 0)), ""],
]
w("ejes.csv", ["eje_id", "nombre", "vertice", "este", "norte", "prog_inicial"], ejes)

# ================================================================ 2. perfil.csv
perfil = [
    ["EJE-01", "0.000", "3820.500", "1.500", "120.000"],
    ["EJE-01", "120.000", "3822.300", "-0.800", "250.000"],
    ["EJE-02", "0.000", f3(ras_B(0)), "1.200", "200.000"],
]
w("perfil.csv", ["eje_id", "prog_inicio", "cota_inicio", "pendiente_pct", "prog_fin"], perfil)

# ================================================================ 3a. calles.csv (una fila por calle)
calles = [
    ["EJE-01", "Jr. Los Andes", "2.0", "7.20", "1.50"],
    ["EJE-02", "Jr. Las Flores", "2.0", "7.20", "1.50"],
]
w("calles.csv", ["eje_id", "nombre", "bombeo_pct", "ancho_calzada_m", "ancho_vereda_m"], calles)

# ================================================================ 3b. seccion_tipica.csv (lo común a todas las calles)
seccion = [
    ["num_carriles", "2", "-", "Número de carriles"],
    ["cuneta_ancho", "40", "cm", "Cuneta básica: ancho (solo geométrica, sin diseño hidráulico)"],
    ["cuneta_profundidad", "10", "cm", "Cuneta básica: profundidad bajo el borde de calzada"],
    ["sardinel_ancho", "15", "cm", "Ancho de la cara superior del sardinel"],
    ["sardinel_altura", "15", "cm", "Desnivel entre borde de calzada y vereda terminada"],
    ["vereda_pendiente", "2.0", "%", "Pendiente transversal de vereda, cae hacia la calzada"],
    ["intervalo_secciones", "10", "m", "Intervalo entre secciones de cálculo"],
    ["pendiente_long_max", "8.0", "%", "PARÁMETRO A CONFIRMAR con norma/expediente"],
    ["pendiente_long_min", "0.5", "%", "PARÁMETRO A CONFIRMAR con norma/expediente"],
    ["vereda_ancho_min", "120", "cm", "PARÁMETRO A CONFIRMAR con norma/expediente"],
]
w("seccion_tipica.csv", ["parametro", "valor", "unidad", "descripcion"], seccion)

# ================================================================ 4. capas.csv
capas = [
    ["calzada", 1, "Losa de concreto f'c=210", "16"],
    ["calzada", 2, "Base granular", "15"],
    ["calzada", 3, "Subbase granular", "15"],
    ["calzada", 4, "Mejoramiento / pedraplén", "20"],
    ["vereda", 1, "Concreto vereda f'c=175", "10"],
    ["vereda", 2, "Base granular vereda", "10"],
]
w("capas.csv", ["ambito", "orden_desde_arriba", "nombre", "espesor_cm"], capas)

# ================================================================ 5. cunetas_por_tramo.csv
cunetas = [
    ["EJE-01", "AMBOS", "0.000", "250.000", "40", "10", "Sección estándar"],
    ["EJE-02", "AMBOS", "0.000", "200.000", "40", "10", "Sección estándar"],
    ["EJE-02", "DER", "150.000", "200.000", "50", "15", "Tramo de hondonada: cuneta mayor"],
]
w("cunetas_por_tramo.csv",
  ["eje_id", "lado", "prog_ini", "prog_fin", "ancho_cm", "profundidad_cm", "nota"], cunetas)

# ================================================================ 6. fachadas.csv
# Cada línea es una polilínea continua de límite de propiedad.
# offset nominal 5.65 m; se agregan invasiones para probar la detección.
def offset_fachada(eje, lado, p):
    o = OFF_FACHADA + random.uniform(-0.03, 0.03)
    if eje == "EJE-01" and lado == "IZQ" and 40 <= p <= 60:
        o = 5.30                      # muro adelantado: vereda disponible 1.15 m
    if eje == "EJE-01" and lado == "DER" and 200 <= p <= 215:
        o = 5.45                      # fachada adelantada: vereda disponible 1.30 m
    if eje == "EJE-02" and lado == "DER" and 20 <= p <= 32:
        o = 5.05                      # escalón de ingreso invadiendo: 0.90 m
    return o


def offset_fachada_nominal(eje, lado, p):
    """Offset de la fachada sin la variación aleatoria (para el levantamiento)."""
    if eje == "EJE-01" and lado == "IZQ" and 40 <= p <= 60:
        return 5.30
    if eje == "EJE-01" and lado == "DER" and 200 <= p <= 215:
        return 5.45
    if eje == "EJE-02" and lado == "DER" and 20 <= p <= 32:
        return 5.05
    return OFF_FACHADA + 0.03


fachadas = []
tramos = {
    "EJE-01": (A0, uA, [(0.0, CRUCE_A - OFF_FACHADA), (CRUCE_A + OFF_FACHADA, LEN_A)]),
    "EJE-02": (B0, uB, [(0.0, CRUCE_B - OFF_FACHADA), (CRUCE_B + OFF_FACHADA, LEN_B)]),
}
quiebres = {"EJE-01": [40, 60, 200, 215], "EJE-02": [20, 32]}
for eje, (org, u, rangos) in tramos.items():
    for lado, signo in (("IZQ", -1), ("DER", 1)):
        for k, (p0, p1) in enumerate(rangos, start=1):
            progs = sorted(set([p0, p1] + [p for p in range(0, 260, 10) if p0 < p < p1]
                               + [q for q in quiebres[eje] if p0 < q < p1]
                               + [q - 0.01 for q in quiebres[eje] if p0 < q - 0.01 < p1]
                               + [q + 0.01 for q in quiebres[eje] if p0 < q + 0.01 < p1]))
            linea = f"{eje}-{lado}-{k}"
            for i, p in enumerate(progs, start=1):
                e, n = punto(org, u, p, signo * offset_fachada(eje, lado, p))
                tipo = "MURO" if (eje == "EJE-01" and lado == "IZQ" and 40 <= p <= 60) else "FACHADA"
                fachadas.append([eje, lado, linea, i, f3(e), f3(n), tipo])
w("fachadas.csv", ["eje_id", "lado", "linea_id", "orden", "este", "norte", "tipo"], fachadas)

# ================================================================ 7. umbrales.csv (puertas y cocheras)
umbrales_def = [
    # id, eje, lado, prog, ancho_m, tipo, diferencia respecto a vereda proyectada (m)
    ("PU-01", "EJE-01", "DER", 35.0, 0.90, "PUERTA", +0.06),
    ("PU-02", "EJE-01", "IZQ", 85.0, 1.00, "PUERTA", -0.08),   # quedaría enterrada
    ("CO-01", "EJE-01", "DER", 170.0, 3.00, "COCHERA", +0.02),
    ("PU-03", "EJE-02", "IZQ", 50.0, 0.90, "PUERTA", +0.12),
    ("PU-04", "EJE-02", "DER", 140.0, 1.20, "PUERTA", -0.03),  # quedaría enterrada
]
umbrales = []
for uid, eje, lado, p, ancho, tipo, dz in umbrales_def:
    org, u = (A0, uA) if eje == "EJE-01" else (B0, uB)
    ras = ras_A(p) if eje == "EJE-01" else ras_B(p)
    signo = -1 if lado == "IZQ" else 1
    e, n = punto(org, u, p, signo * OFF_FACHADA)
    umbrales.append([uid, eje, lado, f3(e), f3(n), f3(cota_vereda_fachada(ras) + dz), f"{ancho:.2f}", tipo])
w("umbrales.csv", ["id", "eje_id", "lado", "este", "norte", "cota_umbral", "ancho_m", "tipo"], umbrales)

# ================================================================ 8. terreno.csv (formato PENZD)
terreno = []
num = 1001
offs = [(-5.5, "PF"), (-3.5, "BC"), (0.0, "EJ"), (3.5, "BC"), (5.5, "PF")]
for eje, org, u, L, cruce in (("EJE-01", A0, uA, LEN_A, CRUCE_A), ("EJE-02", B0, uB, LEN_B, CRUCE_B)):
    # el levantamiento se extiende 3 m antes y después de cada calle
    progs = [-3.0] + [p for p in range(0, int(L) + 1, 15)]
    if progs[-1] != L:
        progs.append(L)
    progs.append(L + 3.0)
    for p in progs:
        if eje == "EJE-02" and abs(p - cruce) < 8:      # el cruce ya lo cubre el EJE-01
            continue
        for o, cod in offs:
            if abs(p - cruce) < 6 and cod == "PF":      # no hay fachada en la esquina
                cod = "TN"
            pj = p if p in (-3.0, 0, L, L + 3.0) else p + random.uniform(-0.8, 0.8)
            if cod == "PF":     # el pie de fachada se levanta pegado al muro
                lado = "IZQ" if o < 0 else "DER"
                oo = (offset_fachada_nominal(eje, lado, pj) + 0.05) * (1 if o > 0 else -1)
            elif cod == "TN":   # esquina sin fachada
                oo = 6.0 * (1 if o > 0 else -1)
            else:
                oo = o + random.uniform(-0.2, 0.2)
            e, n = punto(org, u, pj, oo)
            terreno.append([num, f3(e), f3(n), f3(z_terreno(e, n)), cod])
            num += 1
# relleno de la intersección (rejilla de 4 m)
for di in (-8, -4, 4, 8):
    for dj in (-8, -4, 4, 8):
        if abs(di) == 8 and abs(dj) == 8:
            continue
        e = X[0] + di * uA[0] + dj * uB[0]
        n = X[1] + di * uA[1] + dj * uB[1]
        terreno.append([num, f3(e), f3(n), f3(z_terreno(e, n)), "TN"])
        num += 1
w("terreno.csv", ["punto", "este", "norte", "cota", "codigo"], terreno)

# ================================================================ 9. bm.csv
bms = []
for bid, org, u, p, o in (("BM-01", A0, uA, 5.0, -7.5), ("BM-02", X, uA, 10.0, 7.5),
                          ("BM-03", B0, uB, 195.0, 7.5)):
    e, n = punto(org, u, p, o)
    bms.append([bid, f3(e), f3(n), f3(z_terreno(e, n) + 0.40), "Hito de concreto"])
w("bm.csv", ["bm_id", "este", "norte", "cota", "descripcion"], bms)

print("Listo en", OUT)
