"""Lectura, validación y guardado de los datos del proyecto (carpeta de CSV).

Acepta CSV con coma o punto y coma (Excel en español), y decimales con
punto o con coma. Los mensajes de error indican archivo, fila y columna.
"""
import csv
from pathlib import Path

from .modelo import (BM, PARAMETROS, TEXTO, Calle, Capa, LineaFachada, Proyecto,
                     PuntoTerreno, TramoCuneta, Umbral)


class DatoError(Exception):
    pass


def _abrir(ruta):
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            texto = Path(ruta).read_text(encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    primera = texto.splitlines()[0] if texto else ""
    sep = ";" if primera.count(";") > primera.count(",") else ","
    filas = list(csv.DictReader(texto.splitlines(), delimiter=sep))
    limpias = []
    for f in filas:
        f = {(k or "").strip().lower(): (v or "").strip() for k, v in f.items()}
        if any(f.values()):
            limpias.append(f)
    return limpias, sep


def leer_csv(ruta):
    """Devuelve lista de diccionarios (columnas en minúscula)."""
    filas, sep = _abrir(ruta)
    if sep == ";":   # decimales con coma
        for f in filas:
            for k, v in f.items():
                if v.count(",") == 1 and v.replace(",", "").replace("-", "").replace(".", "").isdigit():
                    f[k] = v.replace(",", ".")
    return filas


def _num(f, col, archivo, fila, opcional=False, defecto=None):
    v = f.get(col, "")
    if v == "":
        if opcional:
            return defecto
        raise DatoError(f"{archivo}, fila {fila}: la columna '{col}' está vacía.")
    try:
        return float(v)
    except ValueError:
        raise DatoError(f"{archivo}, fila {fila}: '{v}' en la columna '{col}' no es un número.")


def _req(filas, columnas, archivo):
    if not filas:
        return
    faltan = [c for c in columnas if c not in filas[0]]
    if faltan:
        raise DatoError(f"{archivo}: faltan las columnas {', '.join(faltan)}. "
                        f"Columnas encontradas: {', '.join(filas[0].keys())}")


# ----------------------------------------------------------------- lectores individuales
def leer_terreno(ruta):
    filas = leer_csv(ruta)
    nombre = Path(ruta).name
    # se acepta cabecera 'punto/este/norte/cota/codigo' o archivos PENZD sin cabecera
    if filas and "este" not in filas[0]:
        filas = _penzd_sin_cabecera(ruta)
    _req(filas, ["punto", "este", "norte", "cota"], nombre)
    pts = []
    for i, f in enumerate(filas, start=2):
        pts.append(PuntoTerreno(f.get("punto", str(i)), _num(f, "este", nombre, i),
                                _num(f, "norte", nombre, i), _num(f, "cota", nombre, i),
                                f.get("codigo", "")))
    return pts


def _penzd_sin_cabecera(ruta):
    filas = []
    texto = Path(ruta).read_text(encoding="utf-8-sig", errors="replace")
    sep = ";" if texto.count(";") > texto.count(",") else ","
    for linea in csv.reader(texto.splitlines(), delimiter=sep):
        if len(linea) >= 4:
            filas.append({"punto": linea[0], "este": linea[1].replace(",", "."),
                          "norte": linea[2].replace(",", "."), "cota": linea[3].replace(",", "."),
                          "codigo": linea[4] if len(linea) > 4 else ""})
    return filas


def leer_fachadas(ruta):
    filas = leer_csv(ruta)
    nombre = Path(ruta).name
    _req(filas, ["eje_id", "lado", "linea_id", "este", "norte"], nombre)
    lineas = {}
    for i, f in enumerate(filas, start=2):
        lid = f["linea_id"]
        if lid not in lineas:
            lado = f["lado"].upper()
            if lado not in ("IZQ", "DER"):
                raise DatoError(f"{nombre}, fila {i}: lado debe ser IZQ o DER (es '{f['lado']}').")
            lineas[lid] = LineaFachada(lid, f["eje_id"], lado, f.get("tipo", "FACHADA") or "FACHADA")
        orden = _num(f, "orden", nombre, i, opcional=True, defecto=len(lineas[lid].puntos) + 1)
        lineas[lid].puntos.append((orden, _num(f, "este", nombre, i), _num(f, "norte", nombre, i),
                                   f.get("tipo", "") or lineas[lid].tipo))
    for l in lineas.values():
        l.puntos.sort(key=lambda p: p[0])
        l.puntos = [(e, n, t) for _, e, n, t in l.puntos]
    return list(lineas.values())


def leer_umbrales(ruta):
    filas = leer_csv(ruta)
    nombre = Path(ruta).name
    _req(filas, ["id", "eje_id", "este", "norte", "cota_umbral"], nombre)
    return [Umbral(f["id"], f["eje_id"], f.get("lado", "").upper(), _num(f, "este", nombre, i),
                   _num(f, "norte", nombre, i), _num(f, "cota_umbral", nombre, i),
                   _num(f, "ancho_m", nombre, i, True, 1.0), (f.get("tipo") or "PUERTA").upper())
            for i, f in enumerate(filas, start=2)]


def leer_bms(ruta):
    filas = leer_csv(ruta)
    nombre = Path(ruta).name
    _req(filas, ["bm_id", "cota"], nombre)
    return [BM(f["bm_id"], _num(f, "este", nombre, i, True, 0.0), _num(f, "norte", nombre, i, True, 0.0),
               _num(f, "cota", nombre, i), f.get("descripcion", "")) for i, f in enumerate(filas, start=2)]


# ----------------------------------------------------------------- proyecto completo
def leer_proyecto(carpeta):
    c = Path(carpeta)
    if not c.is_dir():
        raise DatoError(f"No existe la carpeta {c}")
    proy = Proyecto(nombre=c.name)

    # --- calles
    arch = c / "calles.csv"
    if not arch.exists():
        raise DatoError("Falta calles.csv (una fila por calle: eje_id, nombre, bombeo_pct, "
                        "ancho_calzada_m, ancho_vereda_m).")
    filas = leer_csv(arch)
    _req(filas, ["eje_id", "nombre", "bombeo_pct", "ancho_calzada_m", "ancho_vereda_m"], arch.name)
    for i, f in enumerate(filas, start=2):
        proy.calles.append(Calle(f["eje_id"], f["nombre"], _num(f, "bombeo_pct", arch.name, i),
                                 _num(f, "ancho_calzada_m", arch.name, i),
                                 _num(f, "ancho_vereda_m", arch.name, i)))

    # --- ejes
    arch = c / "ejes.csv"
    filas = leer_csv(arch)
    _req(filas, ["eje_id", "este", "norte"], arch.name)
    for i, f in enumerate(filas, start=2):
        calle = proy.calle(f["eje_id"])
        if calle is None:
            raise DatoError(f"ejes.csv, fila {i}: el eje '{f['eje_id']}' no está en calles.csv.")
        calle.vertices.append((_num(f, "este", arch.name, i), _num(f, "norte", arch.name, i)))
        p0 = _num(f, "prog_inicial", arch.name, i, opcional=True)
        if p0 is not None and len(calle.vertices) == 1:
            calle.prog_inicial = p0

    # --- perfil
    arch = c / "perfil.csv"
    filas = leer_csv(arch)
    _req(filas, ["eje_id", "prog_inicio", "cota_inicio", "pendiente_pct", "prog_fin"], arch.name)
    for i, f in enumerate(filas, start=2):
        calle = proy.calle(f["eje_id"])
        if calle is None:
            raise DatoError(f"perfil.csv, fila {i}: el eje '{f['eje_id']}' no está en calles.csv.")
        cota = _num(f, "cota_inicio", arch.name, i, opcional=True)
        calle.tramos.append([_num(f, "prog_inicio", arch.name, i), cota,
                             _num(f, "pendiente_pct", arch.name, i), _num(f, "prog_fin", arch.name, i)])
    for calle in proy.calles:
        calle.tramos.sort(key=lambda t: t[0])
        encadenar_cotas(calle)

    # --- parámetros
    arch = c / "seccion_tipica.csv"
    if arch.exists():
        for i, f in enumerate(leer_csv(arch), start=2):
            k = f.get("parametro", "")
            if k in PARAMETROS:
                proy.parametros[k] = f["valor"] if k in TEXTO else _num(f, "valor", arch.name, i)

    # --- capas
    arch = c / "capas.csv"
    filas = leer_csv(arch)
    _req(filas, ["ambito", "orden_desde_arriba", "nombre", "espesor_cm"], arch.name)
    for i, f in enumerate(filas, start=2):
        amb = f["ambito"].lower()
        if amb not in ("calzada", "vereda"):
            raise DatoError(f"capas.csv, fila {i}: ámbito debe ser 'calzada' o 'vereda'.")
        proy.capas.append(Capa(amb, int(_num(f, "orden_desde_arriba", arch.name, i)), f["nombre"],
                               _num(f, "espesor_cm", arch.name, i)))

    # --- opcionales
    arch = c / "cunetas_por_tramo.csv"
    if arch.exists():
        for i, f in enumerate(leer_csv(arch), start=2):
            proy.cunetas.append(TramoCuneta(f["eje_id"], (f.get("lado") or "AMBOS").upper(),
                                            _num(f, "prog_ini", arch.name, i), _num(f, "prog_fin", arch.name, i),
                                            _num(f, "ancho_cm", arch.name, i),
                                            _num(f, "profundidad_cm", arch.name, i), f.get("nota", "")))
    if (c / "fachadas.csv").exists():
        proy.fachadas = leer_fachadas(c / "fachadas.csv")
    if (c / "umbrales.csv").exists():
        proy.umbrales = leer_umbrales(c / "umbrales.csv")
    if (c / "terreno.csv").exists():
        proy.terreno = leer_terreno(c / "terreno.csv")
    if (c / "bm.csv").exists():
        proy.bms = leer_bms(c / "bm.csv")
    return proy


def encadenar_cotas(calle):
    """Si un tramo no trae cota de inicio, se toma la cota final del tramo anterior."""
    for k, t in enumerate(calle.tramos):
        if t[1] is None:
            if k == 0:
                raise DatoError(f"perfil.csv: el primer tramo de {calle.eje_id} necesita cota de inicio.")
            a = calle.tramos[k - 1]
            t[1] = round(a[1] + a[2] / 100.0 * (a[3] - a[0]), 4)


def validar_proyecto(proy):
    """Errores que impiden calcular (lista de textos)."""
    err = []
    if not proy.calles:
        err.append("No hay calles definidas.")
    for c in proy.calles:
        if len(c.vertices) < 2:
            err.append(f"{c.eje_id}: el eje necesita al menos 2 vértices.")
        if not c.tramos:
            err.append(f"{c.eje_id}: no tiene tramos de perfil.")
        if c.ancho_calzada <= 0:
            err.append(f"{c.eje_id}: ancho de calzada debe ser mayor que 0.")
        if c.ancho_vereda < 0:
            err.append(f"{c.eje_id}: ancho de vereda no puede ser negativo.")
        if not -10 <= c.bombeo_pct <= 10:
            err.append(f"{c.eje_id}: bombeo de {c.bombeo_pct}% fuera de rango razonable.")
        for t in c.tramos:
            if t[3] <= t[0]:
                err.append(f"{c.eje_id}: tramo de perfil con prog_fin ({t[3]}) <= prog_inicio ({t[0]}).")
    if not proy.capas_de("calzada"):
        err.append("No hay capas de calzada.")
    for cp in proy.capas:
        if cp.espesor_cm <= 0:
            err.append(f"Capa '{cp.nombre}': el espesor debe ser mayor que 0.")
    if proy.p("modo_fachada") not in ("recortar", "avisar"):
        err.append("modo_fachada debe ser 'recortar' o 'avisar'.")
    return err


# ----------------------------------------------------------------- guardar
def _w(ruta, cab, filas):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cab)
        w.writerows(filas)


def guardar_proyecto(proy, carpeta):
    c = Path(carpeta)
    c.mkdir(parents=True, exist_ok=True)
    f3 = lambda v: f"{v:.3f}"
    _w(c / "calles.csv", ["eje_id", "nombre", "bombeo_pct", "ancho_calzada_m", "ancho_vereda_m"],
       [[k.eje_id, k.nombre, k.bombeo_pct, f"{k.ancho_calzada:.2f}", f"{k.ancho_vereda:.2f}"] for k in proy.calles])
    filas = []
    for k in proy.calles:
        for i, (e, n) in enumerate(k.vertices, start=1):
            filas.append([k.eje_id, k.nombre, i, f3(e), f3(n), f3(k.prog_inicial) if i == 1 else ""])
    _w(c / "ejes.csv", ["eje_id", "nombre", "vertice", "este", "norte", "prog_inicial"], filas)
    _w(c / "perfil.csv", ["eje_id", "prog_inicio", "cota_inicio", "pendiente_pct", "prog_fin"],
       [[k.eje_id, f3(t[0]), f3(t[1]), f3(t[2]), f3(t[3])] for k in proy.calles for t in k.tramos])
    _w(c / "seccion_tipica.csv", ["parametro", "valor", "unidad", "descripcion"],
       [[k, proy.parametros.get(k, v[0]), v[1], v[2]] for k, v in PARAMETROS.items()])
    _w(c / "capas.csv", ["ambito", "orden_desde_arriba", "nombre", "espesor_cm"],
       [[cp.ambito, cp.orden, cp.nombre, cp.espesor_cm] for cp in sorted(proy.capas, key=lambda x: (x.ambito, x.orden))])
    _w(c / "cunetas_por_tramo.csv", ["eje_id", "lado", "prog_ini", "prog_fin", "ancho_cm", "profundidad_cm", "nota"],
       [[t.eje_id, t.lado, f3(t.prog_ini), f3(t.prog_fin), t.ancho_cm, t.profundidad_cm, t.nota] for t in proy.cunetas])
    _w(c / "fachadas.csv", ["eje_id", "lado", "linea_id", "orden", "este", "norte", "tipo"],
       [[l.eje_id, l.lado, l.linea_id, i, f3(e), f3(n), t] for l in proy.fachadas
        for i, (e, n, t) in enumerate(l.puntos, start=1)])
    _w(c / "umbrales.csv", ["id", "eje_id", "lado", "este", "norte", "cota_umbral", "ancho_m", "tipo"],
       [[u.id, u.eje_id, u.lado, f3(u.este), f3(u.norte), f3(u.cota), f"{u.ancho:.2f}", u.tipo] for u in proy.umbrales])
    _w(c / "terreno.csv", ["punto", "este", "norte", "cota", "codigo"],
       [[p.numero, f3(p.este), f3(p.norte), f3(p.cota), p.codigo] for p in proy.terreno])
    _w(c / "bm.csv", ["bm_id", "este", "norte", "cota", "descripcion"],
       [[b.id, f3(b.este), f3(b.norte), f3(b.cota), b.descripcion] for b in proy.bms])
