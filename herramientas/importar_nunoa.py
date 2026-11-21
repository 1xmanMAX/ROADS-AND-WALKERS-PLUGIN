"""Arma un proyecto de Corredor Simple a partir de los planos CAD del expediente de Nuñoa
(PMB-24, "Mejoramiento del servicio de transitabilidad vehicular y peatonal en los jirones del
barrio San Pedro II etapa", Nuñoa - Melgar - Puno).

Los DWG no traen objetos de Civil 3D (están explotados), así que se leen así:
  * Ejes:      polilíneas de la capa C-ROAD del plano topográfico (con sus progresivas).
  * Rasante:   banda "COTA SUBRASANTE" y líneas de rasante (capa C-ROAD-PROF) del plano de perfiles
               longitudinales; las curvas verticales quedan como cuerdas.
  * Terreno:   curvas de nivel cada 0.20 m del topográfico + cota de terreno de la banda del perfil
               (cada 20 m en el eje) + BMs.
  * Fachadas:  bordes de manzana (capa _Etop Manzanas) paralelos a cada calle.
  * Sección:   anchos de calzada del plano de secciones; cuneta Tipo I y badén (cuneta Tipo II) del
               plano de drenaje pluvial; pavimento rígido f'c=210 e=0.16 sobre subbase 0.20.

Uso:
  1. Extraer los DWG a JSON con Civil 3D sin ventana (comando CS_EXTRAER del complemento):
       python herramientas/extraer_dwg.py <carpeta_planos> <carpeta_json>
  2. python herramientas/importar_nunoa.py <carpeta_json> <carpeta_proyecto>
"""
import csv
import json
import math
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
from corredor.geometria import Alineamiento  # noqa: E402

# nombre en el plano de perfiles -> (eje_id, nombre, calzada, vereda, tramos [(prog_ini, prog_fin, calzada)])
CALLES = [
    # avenidas primero: en un cruce en X la principal es la que va primero (tienen cuneta y badén)
    ("AV. MARISCAL CASTILLA", "Av. Mariscal Castilla", 7.20, 3.00, True),
    ("AV. INCA GARCILAZO VEGA", "Av. Inca Garcilazo de la Vega", 5.40, 1.60, True),
    ("JR. ATAHUALPA", "Jr. Atahualpa", 5.40, 1.60, True),
    ("JR. MAMA OCCLLO", "Jr. Mama Ocllo", 6.60, 2.00, False),
    ("JR. MANCO CAPAC", "Jr. Manco Capac", None, 1.50, False),
    ("JR. TUPAC YUPANQUI", "Jr. Tupac Yupanqui", 5.40, 1.30, False),
    ("JR. SINCHI ROCA", "Jr. Sinchi Roca", 5.40, 1.00, False),
    ("JR. PACHACUTEC", "Jr. Pachacutec", None, 1.60, False),
]
# calzada variable (plano de secciones): se parte el eje en el cruce donde cambia
CALZADA_VARIABLE = {
    "JR. MANCO CAPAC": [(5.70, "AV. INCA GARCILAZO VEGA"), (5.40, None)],
    "JR. PACHACUTEC": [(4.40, "AV. MARISCAL CASTILLA"), (3.60, "AV. INCA GARCILAZO VEGA"), (5.40, None)],
}


def _num(s):
    return float(s.replace(",", ""))


def leer(carpeta, nombre):
    return json.loads((Path(carpeta) / nombre).read_text(encoding="utf-8"))


# ------------------------------------------------------------------ perfiles
def perfiles(perf):
    T = perf["textos"]
    P = [p for p in perf["polilineas"] if p["c"] == "C-ROAD-PROF" and len(p["v"]) <= 12]
    out = {}
    for t in T:
        m = re.match(r"PERFIL LONGITUDINAL - (.+?)\r?\nKm 0\+000\.000 - (\d+)\+(\d+\.\d+)", t["t"])
        if not m:
            continue
        nombre, L = m.group(1).strip(), int(m.group(2)) * 1000 + float(m.group(3))
        xt, yt = t["p"][:2]
        pr = min((u for u in T if u["t"] == "PROGRESIVAS" and u["p"][1] < yt and abs(u["p"][0] - xt) < 400),
                 key=lambda u: math.hypot(u["p"][0] - xt, (u["p"][1] - yt) * 3))
        x0, y0 = pr["p"][:2]

        def fila(dy):
            return {round(u["p"][0], 2): u["t"] for u in T if abs(u["r"] - 1.5708) < 0.01
                    and abs(u["p"][1] - (y0 + dy)) < 1.0 and x0 < u["p"][0] < x0 + L + 40}
        prog, ter, ras = fila(0), fila(-10), fila(-20)
        filas = []
        for x, s in sorted(prog.items()):
            mm = re.match(r"(\d+)\+(\d+(?:\.\d+)?)", s)
            if mm and x in ter and x in ras:
                st = int(mm.group(1)) * 1000 + float(mm.group(2))
                if st <= L + 1e-6:
                    filas.append((st, _num(ter[x]), _num(ras[x])))
        s0 = min((u for u in T if u["t"] == "0+000" and abs(u["p"][1] - y0) < 1 and x0 < u["p"][0] < x0 + 30),
                 key=lambda u: u["p"][0])
        xs = s0["p"][0]
        band = {round(s, 3): zr for s, zt, zr in filas}

        def y_en(v, s):
            for (a, ya), (b, yb) in zip(v, v[1:]):
                if a - 1e-6 <= s <= b + 1e-6 and b > a:
                    return ya + (yb - ya) * (s - a) / (b - a)
            return None
        segs = []
        for p in P:
            v = [(x - xs, y) for x, y, *_ in p["v"]]
            if min(x for x, _ in v) >= -1 and max(x for x, _ in v) <= L + 1 and y0 < min(y for _, y in v) < yt:
                segs.append(v)
        # escala vertical 10: y = c + 10·cota; c es la que más se repite entre segmentos y banda
        cs = [round(y_en(v, s) - 10 * z, 2) for v in segs for s, z in band.items() if y_en(v, s) is not None]
        pts = set(band.items())
        if cs:
            c = max(set(cs), key=lambda q: sum(1 for x in cs if abs(x - q) < 0.02))
            for v in segs:
                ok = [abs(y_en(v, s) - 10 * z - c) < 0.03 for s, z in band.items() if y_en(v, s) is not None]
                if ok and all(ok):
                    pts |= {(round(x, 3), round((y - c) / 10, 4)) for x, y in v}
        pv = []
        for q in sorted(q for q in pts if -1e-6 <= q[0] <= L + 1e-6):
            if not pv or q[0] - pv[-1][0] > 0.01:
                pv.append(q)
        cambio = True
        while cambio and len(pv) > 2:          # quitar puntos en línea (2 mm)
            cambio = False
            for i in range(1, len(pv) - 1):
                (a, za), (b, zb), (q, zq) = pv[i - 1], pv[i], pv[i + 1]
                if abs(za + (zq - za) * (b - a) / (q - a) - zb) < 0.002:
                    del pv[i]
                    cambio = True
                    break
        out[nombre] = {"L": L, "pvis": pv, "banda": filas}
    return out


# ------------------------------------------------------------------ ejes
def ejes(topo, perf):
    polis = [p for p in topo["polilineas"] if p["c"] == "C-ROAD" and len(p["v"]) >= 2]
    out = {}
    for nombre, info in perf.items():
        L = info["L"]
        cand = []
        for p in polis:
            v = [(x, y) for x, y, *_ in p["v"]]
            lp = sum(math.dist(a, b) for a, b in zip(v, v[1:]))
            if abs(lp - L) < 0.05:
                cand.append(v)
        if cand:
            out[nombre] = cand[0]
            continue
        # sin polilínea (Jr. Mama Ocllo): con los textos de progresiva 0+000 ... final
        etiq = [t for t in topo["textos"] if t["c"] == "C-ROAD-TEXT" and re.fullmatch(r"\d\+\d{3}", t["t"])]
        for t0 in [t for t in etiq if t["t"] == "0+000"]:
            for t1 in etiq:
                st = int(t1["t"][0]) * 1000 + int(t1["t"][2:])
                if abs(st - round(L)) < 1 and abs(math.dist(t0["p"][:2], t1["p"][:2]) - st) < 1.5:
                    a, b = t0["p"][:2], t1["p"][:2]
                    d = math.dist(a, b)
                    out[nombre] = [tuple(a), (a[0] + (b[0] - a[0]) * L / d, a[1] + (b[1] - a[1]) * L / d)]
    return out


# ------------------------------------------------------------------ terreno
def terreno(topo, perf, ejes_xy, paso=2.0):
    pts = []
    for p in topo["polilineas"]:
        if "Curv" not in p["c"] or p.get("z") is None:
            continue
        z = p["z"]
        v = [(x, y) for x, y, *_ in p["v"]]
        acum = paso
        for a, b in zip(v, v[1:]):
            d = math.dist(a, b)
            if d < 1e-9:
                continue
            t = (paso - acum) if acum < paso else 0.0
            while t <= d:
                pts.append((a[0] + (b[0] - a[0]) * t / d, a[1] + (b[1] - a[1]) * t / d, z, "TN / curva de nivel"))
                t += paso
            acum = d - (t - paso)
    for nombre, info in perf.items():
        if nombre not in ejes_xy:
            continue
        al = Alineamiento(ejes_xy[nombre])
        for s, zt, _ in info["banda"]:
            if s <= al.prog_final + 1e-6:
                e, n = al.punto(s)
                pts.append((e, n, zt, "TN / perfil en el eje"))
    for b in bms(topo):
        pts.append((b[1], b[2], b[3], f"BM / {b[0]}"))
    return pts


def bms(topo):
    out = []
    nombres = [t for t in topo["textos"] if t["c"] == "_Etop BMs" and re.match(r"^[A-Z]+-?\d+", t["t"])]
    for b in topo["bloques"]:
        if b["b"] != "BMS":
            continue
        e, n, z = b["p"]
        cerca = min(nombres, key=lambda t: math.dist(t["p"][:2], (e, n)), default=None)
        nom = cerca["t"].split("\r")[0].split("\n")[0] if cerca and math.dist(cerca["p"][:2], (e, n)) < 15 else f"BM-{len(out) + 1}"
        out.append((nom, e, n, z))
    return out


# ------------------------------------------------------------------ fachadas
def fachadas(topo, alins, calles_info):
    """Bordes de manzana paralelos al eje y del lado correcto -> líneas de fachada."""
    bordes = []
    for p in topo["polilineas"]:
        if p["c"] != "_Etop Manzanas":
            continue
        v = [(x, y) for x, y, *_ in p["v"]]
        if p.get("cerrada"):
            v = v + [v[0]]
        bordes += [(a, b) for a, b in zip(v, v[1:]) if math.dist(a, b) > 0.5]
    out = []
    for eje_id, (al, calzada, vereda) in alins.items():
        for lado in ("IZQ", "DER"):
            k = 0
            for a, b in bordes:
                pa, oa, fa = al.proyectar(*a)
                pb, ob, fb = al.proyectar(*b)
                if fa > 0.5 and fb > 0.5:
                    continue
                if (oa < 0) != (lado == "IZQ") or (ob < 0) != (lado == "IZQ"):
                    continue
                lo = calzada / 2 + 0.3
                if not (lo < abs(oa) < calzada / 2 + vereda + 6 and lo < abs(ob) < calzada / 2 + vereda + 6):
                    continue
                ux, uy = al.direccion((pa + pb) / 2)
                d = math.dist(a, b)
                if abs(((b[0] - a[0]) * ux + (b[1] - a[1]) * uy) / d) < 0.94:   # > 20° del eje
                    continue
                k += 1
                lid = f"{eje_id}-{lado}-{k}"
                out.append((eje_id, lado, lid, 1, a[0], a[1]))
                out.append((eje_id, lado, lid, 2, b[0], b[1]))
    return out


# ------------------------------------------------------------------ proyecto
def escribir(carpeta, nombre, cab, filas):
    with open(Path(carpeta) / nombre, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cab)
        w.writerows(filas)


def main(dir_json, destino):
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    topo = leer(dir_json, "24.6 Topografico Nuñoa.json")
    perf = perfiles(leer(dir_json, "24.10 Plano de perfiles longitudinales.json"))
    perf.pop("JR. ATAHUALPA 02", None)        # tramo de 41 m sin eje en el topográfico
    xy = ejes(topo, perf)
    faltan = [n for n, *_ in CALLES if n not in xy]
    if faltan:
        raise SystemExit(f"Sin eje en planta: {faltan}")

    al_full = {n: Alineamiento(xy[n]) for n in xy}

    def cruce(n1, n2):
        """Progresiva de n1 donde cruza el eje de n2 (por proyección, sirve también si n1 empieza
        justo sobre n2)."""
        a, b = al_full[n1], al_full[n2]
        f = lambda p: b.proyectar(*a.punto(p))[1]
        ps = [a.prog_inicial + i * 0.5 for i in range(int(a.longitud * 2) + 1)]
        p = min(ps, key=lambda q: abs(f(q)))
        lo, hi = max(a.prog_inicial, p - 0.5), min(a.prog_final, p + 0.5)
        for _ in range(60):                       # bisección sobre el offset
            mid = (lo + hi) / 2
            if f(lo) * f(mid) <= 0:
                hi = mid
            else:
                lo = mid
        return (lo + hi) / 2

    filas_ejes, filas_calles, filas_perfil, filas_cun = [], [], [], []
    alins_fach = {}
    k = 0
    for nombre, nom_corto, calzada, vereda, con_cuneta in CALLES:
        partes = []
        if nombre in CALZADA_VARIABLE:
            p0 = 0.0
            for w, hasta in CALZADA_VARIABLE[nombre]:
                p1 = cruce(nombre, hasta) if hasta else al_full[nombre].prog_final
                partes.append((p0, p1, w))
                p0 = p1
        else:
            partes.append((0.0, al_full[nombre].prog_final, calzada))
        for (p0, p1, w) in partes:
            k += 1
            eje_id = f"EJE-{k:02d}"
            sufijo = f" ({p0:.0f}-{p1:.0f})" if len(partes) > 1 else ""
            al = al_full[nombre]
            # vértices del tramo p0..p1
            vs = [al.punto(p0)] + [v for q, v in zip(al.progs_vertices(), al.vertices) if p0 + 0.01 < q < p1 - 0.01] + [al.punto(p1)]
            for i, (e, n) in enumerate(vs, start=1):
                filas_ejes.append([eje_id, nom_corto + sufijo, i, f"{e:.4f}", f"{n:.4f}", f"{p0:.4f}" if i == 1 else ""])
            filas_calles.append([eje_id, nom_corto + sufijo, 2.5, f"{w:.2f}", f"{vereda:.2f}"])
            pv = perf[nombre]["pvis"]
            for (a, za), (b, zb) in zip(pv, pv[1:]):
                if b < p0 - 1e-6 or a > p1 + 1e-6:
                    continue
                filas_perfil.append([eje_id, f"{a:.3f}", f"{za:.4f}", f"{(zb - za) / (b - a) * 100:.4f}", f"{b:.3f}"])
            if not con_cuneta:
                filas_cun.append([eje_id, "AMBOS", f"{p0:.3f}", f"{p1:.3f}", 0, 0, "Sin cuneta (expediente: solo avenidas y Jr. Atahualpa)"])
            alins_fach[eje_id] = (Alineamiento(vs, p0), w, vereda)

    escribir(destino, "ejes.csv", ["eje_id", "nombre", "vertice", "este", "norte", "prog_inicial"], filas_ejes)
    escribir(destino, "calles.csv", ["eje_id", "nombre", "bombeo_pct", "ancho_calzada_m", "ancho_vereda_m"], filas_calles)
    escribir(destino, "perfil.csv", ["eje_id", "prog_inicio", "cota_inicio", "pendiente_pct", "prog_fin"], filas_perfil)
    escribir(destino, "cunetas_por_tramo.csv", ["eje_id", "lado", "prog_ini", "prog_fin", "ancho_cm", "profundidad_cm", "nota"], filas_cun)
    pts = terreno(topo, perf, xy)
    escribir(destino, "terreno.csv", ["punto", "este", "norte", "cota", "codigo"],
             [[i, f"{e:.3f}", f"{n:.3f}", f"{z:.3f}", c] for i, (e, n, z, c) in enumerate(pts, start=1)])
    escribir(destino, "bm.csv", ["bm_id", "este", "norte", "cota", "descripcion"],
             [[nm, f"{e:.3f}", f"{n:.3f}", f"{z:.3f}", "BM del topográfico"] for nm, e, n, z in bms(topo)])
    escribir(destino, "fachadas.csv", ["eje_id", "lado", "linea_id", "orden", "este", "norte", "tipo"],
             [[a, b, c, d, f"{e:.3f}", f"{n:.3f}", "FACHADA"] for a, b, c, d, e, n in fachadas(topo, alins_fach, None)])
    escribir(destino, "umbrales.csv", ["id", "eje_id", "lado", "este", "norte", "cota_umbral", "ancho_m", "tipo"], [])
    escribir(destino, "capas.csv", ["ambito", "orden_desde_arriba", "nombre", "espesor_cm"], [
        ["calzada", 1, "Pavimento rigido f'c=210", 16],
        ["calzada", 2, "Subbase granular", 20],
        ["vereda", 1, "Concreto vereda f'c=175", 10],
        ["vereda", 2, "Subbase vereda", 10],
    ])
    escribir(destino, "seccion_tipica.csv", ["parametro", "valor", "unidad", "descripcion"], [
        ["cuneta_ancho", 40, "cm", "Cuneta Tipo I (plano de drenaje PDP-01): 0.40 m, f'c=175"],
        ["cuneta_profundidad", 10, "cm", "Cuneta Tipo I: fondo junto al sardinel"],
        ["baden_ancho", 80, "cm", "Cuneta Tipo II (badén) en cruces: 0.80 m, f'c=210"],
        ["baden_profundidad", 7, "cm", "Cuneta Tipo II: 0.22 en bordes, 0.15 al centro"],
        ["baden_espesor", 22, "cm", "Cuneta Tipo II: espesor en los bordes"],
        ["sardinel_ancho", 15, "cm", "Sardinel h=45 cm, e=15 cm, f'c=175"],
        ["sardinel_altura", 17, "cm", "Corte vereda (AVR-05): 0.27 sobre el fondo de cuneta = 0.17 sobre la losa"],
        ["radio_esquina", 300, "cm", "Esquinas: arcos R = 3.00 en la cara del sardinel (C-ROAD-MARK, _Martillos)"],
        ["rampa_rebaje", 12, "cm", "Detalle de rampa: 12 % en 1.00 m"],
        ["rampa_largo", 100, "cm", "Detalle de rampa: 1.00 + 1.00 (descanso) + 1.00"],
        ["rampa_descanso", 100, "cm", "Detalle de rampa: descanso de 1.00 al 2 %"],
        ["vereda_pendiente", 2.0, "%", "Secciones: +2.00 %"],
        ["intervalo_secciones", 10, "m", "Como el plano de secciones"],
        ["pendiente_long_max", 8.0, "%", "PARÁMETRO A CONFIRMAR con norma/expediente"],
        ["pendiente_long_min", 0.5, "%", "PARÁMETRO A CONFIRMAR con norma/expediente"],
        ["vereda_ancho_min", 90, "cm", "PARÁMETRO A CONFIRMAR con norma/expediente"],
        ["arista_max_tin", 40, "m", "Curvas cada 0.20 m en zona plana: triángulos largos"],
        ["busqueda_fachada", 8, "m", "Bordes de manzana"],
    ])
    print(f"{len(filas_calles)} ejes, {len(filas_perfil)} tramos de rasante, {len(pts)} puntos de terreno -> {destino}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
