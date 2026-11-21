"""Codificación de campo: qué es cada punto levantado con la estación total y qué hace la app con él.

Formato de la descripción (columna "codigo" de terreno.csv / la D del PENZD):

    CODIGO[n] [parámetros] [comandos] [/ nota libre]

    TN                    punto de terreno natural
    FAC1                  pie de fachada, línea 1 (los puntos FAC1 se unen en el orden en que se toman)
    FAC1 C                ... y cierra la línea con su primer punto
    FAC2 I                empieza OTRA línea 2 (la anterior FAC2 se corta ahí)
    PTA 0.90              puerta de 0.90 m (el punto va en el umbral, al centro de la puerta)
    POS 0.25 / alumbrado  poste de 0.25 m de diámetro; lo que va después de "/" es nota

El manual con la tabla de códigos y cómo tomar cada punto está en docs/CODIFICACION_CAMPO.md. Si el
topógrafo usa sus propios códigos, se agrega en la carpeta del proyecto un codigos_alias.csv
(alias,codigo) y la app los traduce antes de interpretarlos.
"""
import csv
import math
import re
from dataclasses import dataclass, field
from pathlib import Path

# código: (nombre, grupo, geometría, ¿va al TIN del terreno?, cómo se toma)
CODIGOS = {
    # ---- control
    "BM": ("Banco de nivel (BM)", "CONTROL", "punto", False,
           "Sobre la marca del hito, prisma a plomo. Nombre en la nota: 'BM / BM-01'."),
    "EST": ("Estación de la estación total", "CONTROL", "punto", False,
            "Punto de estación (lo registra el equipo). No entra al terreno."),
    "REF": ("Punto de referencia / visado", "CONTROL", "punto", False, "Punto de orientación o de control auxiliar."),
    "PC": ("Punto de control GNSS", "CONTROL", "punto", False, "Punto de control geodésico (GPS)."),
    # ---- terreno
    "TN": ("Terreno natural", "TERRENO", "punto", True,
           "Suelo natural, prisma apoyado en el terreno. Grilla de 5 a 10 m y en todo cambio de pendiente."),
    "TNL": ("Línea de quiebre del terreno", "TERRENO", "linea", True,
            "Quiebre marcado (borde de plataforma, lomo, cambio brusco). Numerar cada línea: TNL1, TNL2..."),
    "CAB": ("Cabeza (borde superior) de talud", "TERRENO", "linea", True, "Por el borde superior, cada 5 m y en los quiebres."),
    "PIE": ("Pie de talud", "TERRENO", "linea", True, "Por el pie, cada 5 m y en los quiebres."),
    "ZJ": ("Fondo de zanja / acequia / canal", "TERRENO", "linea", True, "Por el fondo, en el eje del cauce."),
    "BOR": ("Borde de zanja / canal / río", "TERRENO", "linea", True, "Por el borde superior de cada margen (BOR1, BOR2)."),
    # ---- vía existente (a donde tiene que llegar el diseño)
    "EJX": ("Eje de vía existente", "EXISTENTE", "linea", True, "En el eje de la pista existente, cada 10 m."),
    "PEX": ("Borde de pavimento existente", "EXISTENTE", "linea", True,
            "En el borde del pavimento que se conserva, cada 5 m y donde empieza/termina la obra. El diseño "
            "tiene que empalmar con estas cotas."),
    "EMP": ("Punto de empalme", "EXISTENTE", "punto", True,
            "Donde la obra se une a lo existente (fin de pavimento, sardinel o vereda que se conservan): al menos "
            "eje y dos bordes en cada empalme. La app compara con la cota de diseño."),
    "SDX": ("Cabeza de sardinel existente", "EXISTENTE", "linea", False, "En la arista superior del sardinel."),
    "CNX": ("Fondo de cuneta existente", "EXISTENTE", "linea", True, "En el fondo de la cuneta, junto al sardinel."),
    "VEX": ("Borde de vereda existente", "EXISTENTE", "linea", True, "En la arista exterior de la vereda existente."),
    "AFI": ("Borde de afirmado / trocha", "EXISTENTE", "linea", True, "En el borde de la vía sin pavimentar."),
    # ---- edificaciones y límites
    "FAC": ("Pie de fachada", "LIMITE", "linea", True,
            "Al pie del muro, a nivel del suelo o de la vereda, en cada esquina y quiebre del muro y cada 10 m. "
            "Numerar por manzana/cuadra: FAC1, FAC2... Es el límite de la vereda."),
    "MUR": ("Muro o cerco", "LIMITE", "linea", True, "Al pie del muro o cerco, como FAC."),
    "LP": ("Límite de propiedad sin construir", "LIMITE", "linea", True, "En los hitos o estacas del lindero."),
    "PTA": ("Puerta (umbral)", "ACCESO", "punto", False,
            "Al CENTRO de la puerta, prisma apoyado SOBRE el umbral (la grada o piso de la entrada). Ancho en metros "
            "como parámetro: 'PTA 0.90'. La app verifica que la vereda no tape la puerta."),
    "COC": ("Cochera / portón (umbral)", "ACCESO", "punto", False,
            "Al centro del portón, sobre el piso de la entrada. Ancho: 'COC 3.00'. La app pide rebaje de sardinel."),
    "GRA": ("Grada o escalón existente sobre la vereda", "ACCESO", "punto", False,
            "En la arista exterior del escalón que sobresale de la fachada. La app avisa si invade la vereda."),
    # ---- servicios y obstáculos
    "POS": ("Poste (luz, teléfono)", "OBSTACULO", "punto", True,
            "Prisma pegado al poste, en la cara que mira al EJE de la calle, al pie (nivel del suelo). Diámetro "
            "como parámetro: 'POS 0.25'. La app ubica el centro a medio diámetro detrás y revisa si estorba."),
    "ARB": ("Árbol", "OBSTACULO", "punto", True,
            "Igual que el poste: cara del tronco hacia el eje, al pie; diámetro del tronco: 'ARB 0.40'."),
    "GRI": ("Grifo contra incendio", "OBSTACULO", "punto", True, "Al centro, al pie."),
    "BZD": ("Tapa de buzón de desagüe", "TAPA", "punto", True,
            "Al CENTRO de la tapa, sobre la tapa. La app dice cuánto subir o bajar la tapa para la rasante nueva."),
    "CAJ": ("Caja de registro (desagüe)", "TAPA", "punto", True, "Al centro de la tapa, sobre la tapa."),
    "VAL": ("Caja de válvula (agua)", "TAPA", "punto", True, "Al centro de la tapa, sobre la tapa."),
    "MED": ("Caja de medidor de agua", "TAPA", "punto", True, "Al centro de la tapa, sobre la tapa."),
    "SUM": ("Sumidero / rejilla", "TAPA", "punto", True, "Al centro de la rejilla, sobre la rejilla."),
}

COMANDOS = {"I": "inicia una línea nueva", "C": "cierra la línea con su primer punto", "F": "termina la línea"}


@dataclass
class PuntoCodificado:
    numero: str
    este: float
    norte: float
    cota: float
    original: str              # descripción tal como vino del equipo
    codigo: str = ""           # código normalizado (vacío si no se reconoce)
    linea: str = ""            # código + número de línea (FAC1)
    parametros: list = field(default_factory=list)
    comandos: set = field(default_factory=set)
    nota: str = ""

    @property
    def info(self):
        return CODIGOS.get(self.codigo)


_RX = re.compile(r"^([A-ZÑ]+?)(\d*)$")


def leer_alias(carpeta):
    """codigos_alias.csv (alias,codigo): códigos propios del topógrafo -> códigos de este manual."""
    f = Path(carpeta) / "codigos_alias.csv"
    out = {}
    if f.exists():
        for fila in csv.DictReader(f.open(encoding="utf-8-sig")):
            a, c = (fila.get("alias") or "").strip().upper(), (fila.get("codigo") or "").strip().upper()
            if a and c:
                out[a] = c
    return out


def interpretar(desc, alias=None):
    """'FAC1 C / esquina' -> (codigo, linea, parametros, comandos, nota)."""
    alias = alias or {}
    texto, _, nota = (desc or "").partition("/")
    tokens = texto.strip().upper().replace(",", ".").split()
    if not tokens:
        return "", "", [], set(), nota.strip()
    cab = tokens[0]
    cab = alias.get(cab, cab)
    m = _RX.match(cab)
    codigo, num = (m.group(1), m.group(2)) if m else (cab, "")
    if codigo not in CODIGOS and cab in CODIGOS:
        codigo, num = cab, ""
    if codigo not in CODIGOS:
        # alias de la parte sin número (p. ej. 'F1' con alias F -> FAC)
        if m and alias.get(m.group(1)) in CODIGOS:
            codigo = alias[m.group(1)]
        else:
            return "", "", [], set(), (desc or "").strip()
    params, cmds = [], set()
    for t in tokens[1:]:
        if t in COMANDOS:
            cmds.add(t)
        else:
            try:
                params.append(float(t))
            except ValueError:
                nota = (t + " " + nota).strip()
    return codigo, codigo + num, params, cmds, nota.strip()


def es_terreno(desc, alias=None):
    """¿El punto va al TIN del terreno? Sin código reconocido: sí (como siempre hizo la app)."""
    c = interpretar(desc, alias)[0]
    return CODIGOS[c][3] if c else True


def lineas(puntos):
    """Une en polilíneas los puntos de código 'linea' por su número, en orden de toma, con I/C/F."""
    abiertas, out = {}, []
    for p in puntos:
        if not p.codigo or CODIGOS[p.codigo][2] != "linea":
            continue
        if "I" in p.comandos and p.linea in abiertas:
            out.append(abiertas.pop(p.linea))
        lin = abiertas.setdefault(p.linea, {"linea": p.linea, "codigo": p.codigo, "puntos": [], "cerrada": False})
        lin["puntos"].append(p)
        if "C" in p.comandos:
            lin["cerrada"] = True
            out.append(abiertas.pop(p.linea))
        elif "F" in p.comandos:
            out.append(abiertas.pop(p.linea))
    out += list(abiertas.values())
    return [l for l in out if len(l["puntos"]) >= 2]


def puntos_codificados(proy, alias=None):
    out = []
    for p in proy.terreno:
        c, lin, par, cmd, nota = interpretar(p.codigo, alias)
        out.append(PuntoCodificado(p.numero, p.este, p.norte, p.cota, p.codigo, c, lin, par, cmd, nota))
    return out


# ------------------------------------------------------------------ al proyecto (antes de calcular)
def aplicar(proy, alias=None):
    """Agrega al proyecto lo que sale de los códigos: fachadas (FAC/MUR/LP), umbrales (PTA/COC) y BMs.
    Devuelve el resumen de lo interpretado. Las calles tienen que estar cargadas (para saber de qué
    calle y de qué lado es cada fachada o puerta)."""
    from .geometria import Alineamiento
    from .modelo import BM, LineaFachada, Umbral
    pts = puntos_codificados(proy, alias)
    alins = {c.eje_id: Alineamiento(c.vertices, c.prog_inicial) for c in proy.calles if len(c.vertices) >= 2}
    busq = float(proy.p("busqueda_fachada"))
    res = {"puntos": pts, "lineas": lineas(pts), "fachadas": 0, "umbrales": 0, "bms": 0,
           "sin_codigo": [p for p in pts if not p.codigo and p.original.strip()]}

    def calle_de(e, n, lim_extra=busq):
        mejor = None
        for c in proy.calles:
            al = alins.get(c.eje_id)
            if al is None:
                continue
            prog, off, fuera = al.proyectar(e, n)
            semi = c.ancho_calzada / 2 + proy.p("cuneta_ancho") / 100 + proy.p("sardinel_ancho") / 100 + c.ancho_vereda
            if fuera < 1.0 and abs(off) <= semi + lim_extra and (mejor is None or abs(off) < abs(mejor[2])):
                mejor = (c.eje_id, prog, off)
        return mejor

    # ---- fachadas: cada tramo de la línea se asigna a la calle más cercana a su punto medio
    ya = {l.linea_id for l in proy.fachadas}
    for lin in res["lineas"]:
        if lin["codigo"] not in ("FAC", "MUR", "LP"):
            continue
        tipo = {"FAC": "FACHADA", "MUR": "MURO", "LP": "LIMITE"}[lin["codigo"]]
        pp = [(p.este, p.norte) for p in lin["puntos"]] + ([(lin["puntos"][0].este, lin["puntos"][0].norte)] if lin["cerrada"] else [])
        grupos = {}
        for a, b in zip(pp[:-1], pp[1:]):
            m = calle_de((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            if m is None:
                continue
            al = alins[m[0]]
            ux, uy = al.direccion(m[1])
            d = math.dist(a, b)
            if d < 0.05 or abs(((b[0] - a[0]) * ux + (b[1] - a[1]) * uy) / d) < 0.5:   # perpendicular: no da a esa calle
                continue
            clave = (m[0], "DER" if m[2] > 0 else "IZQ")
            grupos.setdefault(clave, []).append((a, b))
        for (eje, lado), segs in grupos.items():
            for k, (a, b) in enumerate(segs, start=1):
                lid = f"{lin['linea']}-{eje}-{lado}-{k}"
                if lid in ya:
                    continue
                proy.fachadas.append(LineaFachada(lid, eje, lado, tipo, [(a[0], a[1], 0.0), (b[0], b[1], 0.0)]))
                res["fachadas"] += 1
    # ---- puertas y cocheras (si el proyecto no trae umbrales.csv)
    if not proy.umbrales:
        for p in pts:
            if p.codigo not in ("PTA", "COC"):
                continue
            m = calle_de(p.este, p.norte)
            if m is None:
                continue
            ancho = p.parametros[0] if p.parametros else (0.90 if p.codigo == "PTA" else 3.00)
            proy.umbrales.append(Umbral(f"{p.codigo}-{p.numero}", m[0], "DER" if m[2] > 0 else "IZQ", p.este, p.norte,
                                        p.cota, ancho, "PUERTA" if p.codigo == "PTA" else "COCHERA"))
            res["umbrales"] += 1
    # ---- BMs
    ids = {b.id for b in proy.bms}
    for p in pts:
        if p.codigo == "BM":
            nombre = p.nota or f"BM-{p.numero}"
            if nombre not in ids:
                proy.bms.append(BM(nombre, p.este, p.norte, p.cota, "BM del levantamiento"))
                ids.add(nombre)
                res["bms"] += 1
    return res


# ------------------------------------------------------------------ controles (después de calcular)
def _cota_diseno(rc, e, n):
    """Cota de la superficie terminada en (e, n) según la sección más cercana (None si cae fuera)."""
    prog, off, fuera = rc.alin.proyectar(e, n)
    if fuera > 0.5:
        return None, prog, off
    secs = [s for s in rc.secciones if not s.omitida]
    if not secs:
        return None, prog, off
    s = min(secs, key=lambda s: abs(s.prog - prog))
    t = s.lineas["TERMINADO"]
    for (_, oa, za), (_, ob, zb) in zip(t[:-1], t[1:]):
        if oa - 1e-6 <= off <= ob + 1e-6 and ob - oa > 1e-6:
            z = za + (zb - za) * (off - oa) / (ob - oa)
            return z + rc.perfil.cota(prog) - rc.perfil.cota(s.prog), prog, off
    return None, prog, off


def controles(res, info, tol_tapa=0.01, tol_empalme=0.02, libre_min=0.90):
    """Avisos de los puntos codificados contra el diseño: postes y árboles que estorban, tapas a
    nivelar y empalmes con lo existente. Devuelve (avisos, filas para el informe)."""
    from .geometria import fmt_prog
    from .modelo import Aviso
    avisos, filas = [], []
    proy = res.proyecto

    def calle_mas_cercana(e, n):
        mejor = None
        for k, rc in res.calles.items():
            prog, off, fuera = rc.alin.proyectar(e, n)
            if fuera < 0.5 and (mejor is None or abs(off) < abs(mejor[2])):
                mejor = (k, prog, off)
        return mejor

    for p in info["puntos"]:
        if not p.codigo:
            continue
        grupo = CODIGOS[p.codigo][1]
        if grupo not in ("OBSTACULO", "TAPA", "EXISTENTE") or (grupo == "EXISTENTE" and p.codigo not in ("EMP", "PEX")):
            continue
        m = calle_mas_cercana(p.este, p.norte)
        if m is None:
            continue
        k, prog, off = m
        rc = res.calles[k]
        sec = min((s for s in rc.secciones if not s.omitida), key=lambda s: abs(s.prog - prog), default=None)
        if sec is None:
            continue
        lado = "D" if off > 0 else "I"
        nom_lado = "DER" if lado == "D" else "IZQ"
        pts = {c: o for c, o, _ in sec.puntos}
        b = rc.calle.ancho_calzada / 2
        fila = {"punto": p.numero, "codigo": p.codigo, "descripcion": CODIGOS[p.codigo][0], "eje": k,
                "progresiva": fmt_prog(prog), "offset": round(off, 3), "cota": p.cota, "resultado": ""}
        if grupo == "OBSTACULO":
            d = p.parametros[0] if p.parametros else (0.25 if p.codigo == "POS" else 0.0)
            centro = abs(off) + d / 2          # el punto es la cara que mira al eje
            o_bv = abs(pts.get("BV" + lado, b))
            o_pf = abs(pts.get("PF" + lado, o_bv))
            o_cs = abs(pts.get("CS" + lado, b))
            if centro - d / 2 < b - 1e-3:
                nivel, txt = "ERROR", f"dentro de la calzada ({abs(off) - b:+.2f} m del borde): hay que reubicarlo."
            elif centro - d / 2 < o_cs:
                nivel, txt = "ERROR", "sobre la cuneta o el sardinel: hay que reubicarlo."
            elif centro - d / 2 < o_pf:
                libre = max(o_pf - (centro + d / 2), (centro - d / 2) - o_bv)
                nivel = "AVISO" if libre < libre_min else "INFO"
                txt = f"en la vereda; paso libre {libre:.2f} m (mínimo {libre_min:.2f})."
            else:
                nivel, txt = "INFO", "fuera de la vereda (detrás del pie de fachada de diseño)."
            fila["resultado"] = txt
            avisos.append(Aviso(nivel, "OBSTACULO", k, prog,
                                f"{CODIGOS[p.codigo][0]} {p.numero} (lado {nom_lado}, Ø {d:.2f} m): {txt}"))
        else:
            zd, _, _ = _cota_diseno(rc, p.este, p.norte)
            if zd is None:
                fila["resultado"] = "fuera de la sección de diseño"
                if p.codigo == "EMP":
                    avisos.append(Aviso("AVISO", "EMPALME", k, prog,
                                        f"Empalme {p.numero} fuera de la sección de diseño (offset {off:+.2f} m): "
                                        f"revise que la obra llegue hasta ahí."))
                filas.append(fila)
                continue
            dif = zd - p.cota
            fila["cota_diseno"] = round(zd, 3)
            fila["diferencia"] = round(dif, 3)
            if grupo == "TAPA":
                if abs(dif) > tol_tapa:
                    txt = f"{'subir' if dif > 0 else 'bajar'} la tapa {abs(dif) * 100:.0f} cm (de {p.cota:.3f} a {zd:.3f})."
                    avisos.append(Aviso("AVISO", "TAPA", k, prog, f"{CODIGOS[p.codigo][0]} {p.numero}: {txt}"))
                else:
                    txt = "a nivel con el diseño."
                fila["resultado"] = txt
            else:
                if abs(dif) > tol_empalme:
                    txt = (f"el diseño queda {dif * 100:+.0f} cm respecto a lo existente ({zd:.3f} vs {p.cota:.3f}): "
                           f"ajuste la rasante para empalmar.")
                    avisos.append(Aviso("AVISO", "EMPALME", k, prog, f"{CODIGOS[p.codigo][0]} {p.numero}: {txt}"))
                else:
                    txt = f"empalma ({dif * 100:+.1f} cm)."
                fila["resultado"] = txt
        filas.append(fila)
    if info["sin_codigo"]:
        ej = ", ".join(sorted({p.original.split()[0].upper() for p in info["sin_codigo"]})[:12])
        avisos.append(Aviso("INFO", "CODIGOS", "-", None,
                            f"{len(info['sin_codigo'])} puntos con códigos que no están en el manual ({ej}); se usan "
                            f"como terreno. Agregue un codigos_alias.csv para traducirlos."))
    if info["fachadas"] or info["umbrales"] or info["bms"]:
        avisos.append(Aviso("INFO", "CODIGOS", "-", None,
                            f"Desde los códigos de campo: {info['fachadas']} tramos de fachada, {info['umbrales']} "
                            f"puertas/cocheras y {info['bms']} BMs."))
    return avisos, filas
