"""Motor principal: arma el "corredor" de cada calle y calcula todo.

Pasos:
  1. Eje y perfil de cada calle (con control de pendientes).
  2. Cruces entre calles. La calle que va primero en la lista es la PRINCIPAL:
     conserva su sección en el cruce (solo calzada). La SECUNDARIA no se
     calcula dentro de la calzada de la principal (para no contar dos veces).
  3. Progresivas de cálculo: cada intervalo + inicio/fin + cambios de pendiente
     + vértices + puertas/cocheras + límites del cruce.
  4. En cada progresiva: ancho de vereda disponible (fachadas), cuneta del tramo,
     sección completa, corte y relleno.
  5. Volúmenes por área media y material por capa.
  6. Revisión de umbrales de puertas y cocheras.
"""
import math
from dataclasses import dataclass, field

from .geometria import Alineamiento, Perfil, fmt_prog, interseccion_segmentos
from .modelo import Aviso
from . import codigos as cod_mod
from . import esquinas as esq_mod
from .seccion import calcular_tierras, construir
from .terreno import Terreno

EPS = 0.005


@dataclass
class ResCalle:
    calle: object
    alin: Alineamiento
    perfil: Perfil
    secciones: list = field(default_factory=list)
    tramos_volumen: list = field(default_factory=list)   # filas del informe de tierras
    materiales: dict = field(default_factory=dict)       # capa -> m3
    vol_corte: float = 0.0
    vol_relleno: float = 0.0
    zonas_sin_lateral: list = field(default_factory=list)   # [(p1, p2)] (cualquier lado)
    sin_lateral_lado: dict = field(default_factory=lambda: {"I": [], "D": []})   # por lado
    zonas_omitidas: list = field(default_factory=list)      # [(p1, p2)]
    zonas_vertice: list = field(default_factory=list)       # [(prog_vertice, distancia)]
    badenes: list = field(default_factory=list)             # badenes que cruzan esta calle
    rampas: list = field(default_factory=list)              # rampas de esquina en la vereda

    @property
    def vol_neto(self):
        return self.vol_corte - self.vol_relleno


@dataclass
class Resultado:
    proyecto: object
    calles: dict
    terreno: Terreno
    cruces: list
    umbrales: list
    avisos: list
    esquinas: list = field(default_factory=list)            # esquinas curvas (ver esquinas.py)
    puntos_codificados: list = field(default_factory=list)  # postes, tapas, empalmes... (codigos.py)

    def total(self, campo):
        return sum(getattr(rc, campo) for rc in self.calles.values())

    def materiales_total(self):
        tot = {}
        for rc in self.calles.values():
            for k, v in rc.materiales.items():
                tot[k] = tot.get(k, 0.0) + v
        for e in self.esquinas:
            for k, v in e.get("materiales", {}).items():
                tot[k] = tot.get(k, 0.0) + v
        return tot

    def esquinas_total(self, campo):
        return sum(e.get(campo, 0.0) for e in self.esquinas)


# ------------------------------------------------------------------ cruces
def semiancho_total(calle, par):
    """Del eje al borde exterior de la vereda (pie de fachada de diseño)."""
    return calle.ancho_calzada / 2 + par["cuneta_ancho"] / 100.0 + par["sardinel_ancho"] / 100.0 + calle.ancho_vereda


def _extremo(alin, p, tol=0.05):
    return abs(p - alin.prog_inicial) <= tol or abs(p - alin.prog_final) <= tol


def _cruce(calles, par, ip, isec, sp, ss, tp, us, tipo):
    """Arma el diccionario del cruce: ip/isec = calles principal y secundaria, sp/ss sus tramos,
    tp/us = posición (en metros desde el inicio del tramo, puede salir del tramo en una T)."""
    c_ = par["cuneta_ancho"] / 100.0
    ws = par["sardinel_ancho"] / 100.0
    sen = abs(sp["ux"] * ss["uy"] - sp["uy"] * ss["ux"])
    return {
        "principal": calles[ip].eje_id, "secundaria": calles[isec].eje_id, "tipo": tipo,
        "p_principal": sp["p0"] + tp, "p_secundaria": ss["p0"] + us,
        "e": sp["e0"] + tp * sp["ux"], "n": sp["n0"] + tp * sp["uy"],
        "angulo": math.degrees(math.asin(min(1.0, sen))),
        # semiancho hasta la cara del sardinel de la otra calle, medido sobre este eje
        "h_principal": (calles[isec].ancho_calzada / 2 + c_ + ws) / sen,
        "h_secundaria": (calles[ip].ancho_calzada / 2 + c_ + ws) / sen,
    }


def _linea_tramo(s1, s2):
    """Intersección de las RECTAS de dos tramos: (t, u) en metros desde el inicio de cada uno."""
    den = s1["ux"] * s2["uy"] - s1["uy"] * s2["ux"]
    if abs(den) < 1e-12:
        return None
    we, wn = s2["e0"] - s1["e0"], s2["n0"] - s1["n0"]
    return (we * s2["uy"] - wn * s2["ux"]) / den, (we * s1["uy"] - wn * s1["ux"]) / den


def buscar_cruces(proy, alins, par):
    """Cruces entre ejes.

    * Cruce en X: los ejes se cortan. Principal = la que va primero en la lista.
    * Cruce en T: un eje termina (o empieza) sobre otro. La que sigue de largo es la principal,
      aunque vaya después en la lista. También se detecta la T cuando el eje de la calle que
      llega se dibujó solo hasta el sardinel o la fachada de la otra (no toca su eje): sin esto
      la principal mantenía sardinel y vereda cruzando la boca de la calle.
    """
    cruces = []
    calles = proy.calles

    def ya_esta(e, n, ids=None):
        # mismo punto Y mismas calles: dos tramos de una calle que llegan al mismo punto de otra
        # (una calle partida en el cruce) son dos T distintas
        return any(math.hypot(x["e"] - e, x["n"] - n) < 0.05 and
                   (ids is None or {x["principal"], x["secundaria"]} == ids) for x in cruces)

    for i in range(len(calles)):
        for j in range(i + 1, len(calles)):
            A, B = alins[calles[i].eje_id], alins[calles[j].eje_id]
            hay = False
            for sa in A.segs:
                pa1 = (sa["e0"], sa["n0"])
                pa2 = (sa["e0"] + sa["L"] * sa["ux"], sa["n0"] + sa["L"] * sa["uy"])
                for sb in B.segs:
                    pb1 = (sb["e0"], sb["n0"])
                    pb2 = (sb["e0"] + sb["L"] * sb["ux"], sb["n0"] + sb["L"] * sb["uy"])
                    r = interseccion_segmentos(pa1, pa2, pb1, pb2)
                    if r is None:
                        continue
                    t, u = r
                    sen = abs(sa["ux"] * sb["uy"] - sa["uy"] * sb["ux"])
                    if sen < 0.1:
                        continue
                    e, n = pa1[0] + t * (pa2[0] - pa1[0]), pa1[1] + t * (pa2[1] - pa1[1])
                    if ya_esta(e, n, {calles[i].eje_id, calles[j].eje_id}):   # vértice: lo encuentran dos tramos
                        hay = True
                        continue
                    hay = True
                    pA, pB = sa["p0"] + t * sa["L"], sb["p0"] + u * sb["L"]
                    if _extremo(A, pA) and not _extremo(B, pB):        # A llega en T a B
                        cruces.append(_cruce(calles, par, j, i, sb, sa, u * sb["L"], t * sa["L"], "T"))
                    else:
                        tipo = "T" if _extremo(B, pB) else "X"
                        cruces.append(_cruce(calles, par, i, j, sa, sb, t * sa["L"], u * sb["L"], tipo))
            if hay:
                continue
            # ---- T que no toca el eje: un extremo de un eje cae dentro del ancho de la otra calle
            for (ip, P), (isec, S) in (((i, A), (j, B)), ((j, B), (i, A))):
                lim = semiancho_total(calles[ip], par) + 1.0
                for ss, p_ext in ((S.segs[0], S.prog_inicial), (S.segs[-1], S.prog_final)):
                    e, n = S.punto(p_ext)
                    pp, off, fuera = P.proyectar(e, n)
                    if fuera > 0.05 or abs(off) > lim:
                        continue
                    sp = P._seg(pp)
                    r = _linea_tramo(sp, ss)
                    if r is None or abs(sp["ux"] * ss["uy"] - sp["uy"] * ss["ux"]) < 0.1:
                        continue
                    tp, us = r
                    if not (-1e-6 <= tp <= sp["L"] + 1e-6):
                        continue
                    x = _cruce(calles, par, ip, isec, sp, ss, tp, us, "T")
                    x["hueco"] = abs(x["p_secundaria"] - p_ext) - x["h_secundaria"]
                    x["p_extremo"] = p_ext
                    if not ya_esta(x["e"], x["n"], {x["principal"], x["secundaria"]}):
                        cruces.append(x)
    return cruces


# ------------------------------------------------------------------ fachadas
def ancho_disponible(alin, prog, lado, lineas, o_bv, busqueda):
    """Distancia desde el borde interior de vereda hasta la fachada, por el rayo perpendicular."""
    e, n = alin.punto(prog)
    nx, ny = alin.normal(prog)
    sg = -1 if lado == "I" else 1
    p1 = (e + sg * nx * o_bv, n + sg * ny * o_bv)
    p2 = (e + sg * nx * (o_bv + busqueda), n + sg * ny * (o_bv + busqueda))
    mejor = None
    tipo = None
    for l in lineas:
        pts = l.puntos
        for (e1, n1, t1), (e2, n2, t2) in zip(pts[:-1], pts[1:]):
            r = interseccion_segmentos(p1, p2, (e1, n1), (e2, n2))
            if r is None:
                continue
            d = r[0] * busqueda
            if mejor is None or d < mejor:
                mejor = d
                tipo = t1 if t1 == t2 else (t1 if r[1] < 0.5 else t2)
    return mejor, tipo


def _cuneta_en(proy, eje_id, lado, prog, defecto):
    val = defecto
    nombre = "IZQ" if lado == "I" else "DER"
    for t in proy.cunetas:
        if t.eje_id == eje_id and t.lado in ("AMBOS", nombre) and t.prog_ini - 1e-6 <= prog <= t.prog_fin + 1e-6:
            val = (t.ancho_cm / 100.0, t.profundidad_cm / 100.0)
    return val


def _dentro(p, zonas, estricto=True):
    for a, b in zonas:
        if (a + 1e-6 < p < b - 1e-6) if estricto else (a - 1e-6 <= p <= b + 1e-6):
            return True
    return False


# ------------------------------------------------------------------ badenes
def _ubicar_baden(rp, rs, x, lado, o_c):
    """Progresiva de la secundaria donde su eje queda a 'o_c' metros del eje de la principal,
    del lado 'lado' de la principal. Se corrige dos veces por si los ejes no son rectos."""
    sen = math.sin(math.radians(x["angulo"]))
    sg = 1.0 if lado == "D" else -1.0
    mejor = None
    margen = 2.0          # el eje de la secundaria puede terminar en la cuneta de la principal
    for d0 in (o_c / sen, -o_c / sen):
        p = x["p_secundaria"] + d0
        for _ in range(3):
            if not (rs.alin.prog_inicial - margen <= p <= rs.alin.prog_final + margen):
                break
            _, off, _ = rp.alin.proyectar(*rs.alin.punto(p))   # punto() prolonga el primer/último tramo
            if off * sg <= 0:
                break
            p = x["p_secundaria"] + (p - x["p_secundaria"]) * o_c / abs(off)
        else:
            _, off, _ = rp.alin.proyectar(*rs.alin.punto(p))
            if off * sg > 0 and abs(abs(off) - o_c) < 0.01:
                mejor = p
    return mejor


def baden_dz(p, badenes):
    """Cuánto baja la superficie terminada en la progresiva p por un badén (forma en V)."""
    dz = 0.0
    for b in badenes:
        u = abs(p - b["centro"])
        if u < b["medio"]:
            dz = max(dz, b["prof"] * (1.0 - u / b["medio"]))
    return dz


def _bajar_superficie(sec, dz, ident):
    """Baja la superficie terminada y el tope de la 1.ª capa (el badén reemplaza a la losa;
    la subrasante no cambia: el badén es más grueso y su subbase más delgada, ver expediente)."""
    sec.lineas["TERMINADO"] = [(c, o, z - dz) for c, o, z in sec.lineas["TERMINADO"]]
    if "C1_TOPE" in sec.lineas:
        sec.lineas["C1_TOPE"] = [(c, o, z - dz) for c, o, z in sec.lineas["C1_TOPE"]]
    sec.baden = dz
    sec.baden_id = ident


# ------------------------------------------------------------------ volumen entre secciones
def _factor_excentricidad(s1, s2, d):
    """Entre dos secciones no paralelas la distancia entre sus puntos de offset o es
    L(o) = d + k·o (en un quiebre del eje el lado exterior es más largo que el interior).
    Volumen = ∫ h(o)·L(o) do = área·d + k·momento (teorema de Pappus). Con secciones paralelas
    k = 0 y queda el área media de siempre."""
    if d <= 1e-9:
        return 0.0
    de, dn = s2.e - s1.e, s2.n - s1.n
    return (de * (s2.nx - s1.nx) + dn * (s2.ny - s1.ny)) / d


# ------------------------------------------------------------------ vértices del eje
def _zonas_vertice(alin, semi):
    """[(prog_vertice, d)]: a menos de d del vértice, una sección perpendicular a su tramo se cruza
    con la sección del vértice (bisectriz) por el lado interior, dentro del ancho 'semi'."""
    return [(q, semi * math.tan(math.radians(defl) / 2)) for q, defl in alin.deflexiones() if defl > 0.5]


def _cerca_vertice(p, zonas):
    return any(1e-6 < abs(p - q) < d for q, d in zonas)


# ------------------------------------------------------------------ densificación
def _cambia_mucho(a1, a2, var):
    """True si el área cambia más de 'var' (fracción) entre dos secciones y al menos 0.10 m²
    (con 0.25 m² los rellenos delgados de una ladera quedaban 2 % sobre Civil 3D)."""
    return abs(a1 - a2) > max(0.10, var * max(a1, a2))


def _densificar(rc, seccion_en, par):
    """Agrega secciones intermedias donde el corte o el relleno cambian rápido entre dos secciones.

    El área media supone que el área varía en línea recta entre secciones; con una hondonada o
    un montículo más corto que el intervalo eso falla (en el ejemplo, el relleno de EJE-02 salía
    16 % más alto que el volumen entre superficies de Civil 3D). Se parte el tramo por la mitad
    hasta que el cambio sea suave o el tramo llegue a 'intervalo_min_secciones'.
    """
    var = float(par.get("variacion_area_max", 0) or 0) / 100.0
    dmin = float(par.get("intervalo_min_secciones", 0) or 0)
    if var <= 0 or dmin <= 0:
        return
    for _ in range(8):      # cada vuelta parte en dos los tramos que siguen cambiando mucho
        nuevas = []
        validas = [s for s in rc.secciones if not s.omitida]
        for s1, s2 in zip(validas[:-1], validas[1:]):
            d = s2.prog - s1.prog
            if d < 2 * dmin - 1e-6 or _dentro((s1.prog + s2.prog) / 2, rc.zonas_omitidas):
                continue
            if _dentro((s1.prog + s2.prog) / 2, rc.zonas_sin_lateral) != _dentro(s1.prog, rc.zonas_sin_lateral):
                continue
            pm = round((s1.prog + s2.prog) / 2, 4)
            if _cerca_vertice(pm, rc.zonas_vertice):
                continue
            if _cambia_mucho(s1.area_corte, s2.area_corte, var) or \
                    _cambia_mucho(s1.area_relleno, s2.area_relleno, var):
                nuevas.append(seccion_en(pm, "DENSIFICADA"))
        if not nuevas:
            return
        rc.secciones = sorted(rc.secciones + nuevas, key=lambda s: s.prog)


# ------------------------------------------------------------------ cálculo
def calcular(proy):
    par = proy.parametros
    avisos = []
    capas_calz = proy.capas_de("calzada")
    capas_ver = proy.capas_de("vereda")
    # códigos de campo: fachadas, puertas y BMs que vienen en el levantamiento; al TIN solo va lo que
    # es suelo (un BM, una puerta o la cabeza de un sardinel no son terreno)
    alias = getattr(proy, "codigos_alias", {}) or {}
    info_cod = cod_mod.aplicar(proy, alias)
    terreno = Terreno([p for p in proy.terreno if cod_mod.es_terreno(p.codigo, alias)], par["arista_max_tin"])
    if not terreno.ok:
        msg = f"No se pudo armar la superficie del terreno: {terreno.error}" if terreno.error else             "No hay terreno cargado"
        avisos.append(Aviso("AVISO", "TERRENO", "-", None, msg + " No se calcula corte/relleno."))
    if terreno.repetidos:
        dz = max(abs(a.cota - b.cota) for a, b in terreno.repetidos)
        peor = max(terreno.repetidos, key=lambda ab: abs(ab[0].cota - ab[1].cota))
        avisos.append(Aviso("AVISO" if dz > 0.05 else "INFO", "TERRENO", "-", None,
                            f"{len(terreno.repetidos)} puntos repetidos (misma Este/Norte); se usa el primero. "
                            f"Mayor diferencia de cota {dz:.3f} m (puntos {peor[0].numero} y {peor[1].numero})."))

    alins, perfiles, res = {}, {}, {}
    for c in proy.calles:
        alin = Alineamiento(c.vertices, c.prog_inicial)
        perf = Perfil(c.tramos)
        alins[c.eje_id], perfiles[c.eje_id] = alin, perf
        for nivel, p, m in perf.validar(c.eje_id, par["pendiente_long_max"], par["pendiente_long_min"], alin):
            avisos.append(Aviso(nivel, "PERFIL", c.eje_id, p, m))
        res[c.eje_id] = ResCalle(c, alin, perf)

    # ---- cruces
    cruces = buscar_cruces(proy, alins, par)
    esquinas = []
    for x in cruces:
        rp, rs = res[x["principal"]], res[x["secundaria"]]
        a1, a2 = x["p_principal"] - x["h_principal"], x["p_principal"] + x["h_principal"]
        b1, b2 = x["p_secundaria"] - x["h_secundaria"], x["p_secundaria"] + x["h_secundaria"]
        rp.zonas_sin_lateral.append((a1, a2))
        rs.zonas_sin_lateral.append((b1, b2))
        # en una T la principal solo se abre del lado por donde llega la otra calle
        lados_p = ("I", "D")
        if x.get("tipo") == "T":
            ext = [rs.alin.punto(rs.alin.prog_inicial), rs.alin.punto(rs.alin.prog_final)]
            lejos = max(ext, key=lambda q: math.hypot(q[0] - x["e"], q[1] - x["n"]))
            lados_p = ("I",) if rp.alin.proyectar(*lejos)[1] < 0 else ("D",)
        x["lados_principal"] = lados_p
        for l in lados_p:
            rp.sin_lateral_lado[l].append((a1, a2))
        for l in ("I", "D"):
            rs.sin_lateral_lado[l].append((b1, b2))
        # ---- esquinas curvas: el sardinel, la cuneta y la vereda rectos de cada calle terminan en los
        # puntos de tangencia del arco; entre ellos va la pieza de esquina (esquinas.py)
        defecto_c = (par["cuneta_ancho"] / 100.0, par["cuneta_profundidad"] / 100.0)
        cun = lambda eje, lado, prog: _cuneta_en(proy, eje, lado, prog, defecto_c)
        esq_x = esq_mod.planta(rp, rs, x, lados_p, par["radio_esquina"] / 100.0, cun)
        x["esquinas"] = esq_x
        for l in ("I", "D"):
            # la zona sin sardinel ni vereda de cada lado va de tangencia a tangencia y REEMPLAZA a la
            # simétrica de antes: en un cruce oblicuo las tangencias no son simétricas
            tps = [e["tp"] for e in esq_x if e["lado_p"] == l]
            if tps:
                z = (min(tps + [a1]), max(tps + [a2])) if len(tps) == 1 else (min(tps), max(tps))
                if (a1, a2) in rp.sin_lateral_lado[l] and len(tps) == 2:
                    rp.sin_lateral_lado[l].remove((a1, a2))
                rp.sin_lateral_lado[l].append(z)
                rp.zonas_sin_lateral.append(z)
            tss = [e["ts"] for e in esq_x if e["lado_s"] == l]
            if tss:
                z = (min(tss + [x["p_secundaria"]]), max(tss + [x["p_secundaria"]]))
                if len(tss) == 2 and (b1, b2) in rs.sin_lateral_lado[l]:
                    rs.sin_lateral_lado[l].remove((b1, b2))
                rs.sin_lateral_lado[l].append(z)
                rs.zonas_sin_lateral.append(z)
        for e in esq_x:
            e.update(principal=rp.calle.eje_id, secundaria=rs.calle.eje_id,
                     id=f"ES-{len(esquinas) + 1:02d}", cruce=f'{rp.calle.eje_id} x {rs.calle.eje_id}')
            esquinas.append(e)
            # rampas en los dos brazos, hacia afuera del cruce desde la tangencia
            rp.rampas.append({"lado": e["lado_p"], "inicio": e["tp"],
                              "sentido": 1.0 if e["tp"] > x["p_principal"] else -1.0, "esquina": e["id"]})
            rs.rampas.append({"lado": e["lado_s"], "inicio": e["ts"],
                              "sentido": 1.0 if e["ts"] > x["p_secundaria"] else -1.0, "esquina": e["id"]})
        # la secundaria se omite solo dentro de la CALZADA de la principal: la boca (donde la
        # principal no tiene cuneta, sardinel ni vereda) la pavimenta la secundaria
        sen_x = math.sin(math.radians(x["angulo"]))
        h_calz = rp.calle.ancho_calzada / 2 / sen_x
        rs.zonas_omitidas.append((x["p_secundaria"] - h_calz, x["p_secundaria"] + h_calz))
        # badén (cuneta Tipo II): cruza la secundaria en línea con la cuneta de la principal
        W, hb = par["baden_ancho"] / 100.0, par["baden_profundidad"] / 100.0
        if W > 0 and hb > 0:
            defecto = (par["cuneta_ancho"] / 100.0, par["cuneta_profundidad"] / 100.0)
            for l in lados_p:
                c_l, _ = _cuneta_en(proy, rp.calle.eje_id, l, x["p_principal"], defecto)
                if c_l <= 1e-6:
                    continue                       # sin cuneta en la principal: no hace falta badén
                o_c = rp.calle.ancho_calzada / 2 + W / 2   # desde el borde de losa, fondo = línea de cuneta
                pc = _ubicar_baden(rp, rs, x, l, o_c)
                if pc is None:
                    continue
                largo = rs.calle.ancho_calzada / sen_x
                tps = sorted(e["tp"] for e in esq_x if e["lado_p"] == l)
                if len(tps) == 2:                 # de arco a arco de las esquinas (plano de drenaje)
                    largo = (tps[1] - tps[0]) * sen_x
                b = {"eje": rs.calle.eje_id, "centro": pc, "largo_calzada": rs.calle.ancho_calzada / sen_x,
                     "medio": W / 2 / sen_x, "prof": hb, "ancho": W, "largo": largo,
                     "principal": rp.calle.eje_id, "lado_principal": "IZQ" if l == "I" else "DER",
                     "e": rs.alin.punto(pc)[0], "n": rs.alin.punto(pc)[1]}
                b["id"] = f"BD-{rs.calle.eje_id}-{len(rs.badenes) + 1}"
                rs.badenes.append(b)
        zp = rp.perfil.cota(x["p_principal"])
        zs = rs.perfil.cota(x["p_secundaria"])
        x["z_principal"], x["z_secundaria"] = zp, zs
        nivel = "AVISO" if abs(zp - zs) > 0.005 else "INFO"
        verbo = "llega en T a" if x.get("tipo") == "T" else "cruza"
        avisos.append(Aviso(nivel, "CRUCE", x["secundaria"], x["p_secundaria"],
                            f"{verbo} {x['principal']} en {fmt_prog(x['p_principal'])} (ángulo {x['angulo']:.1f}°). "
                            f"Rasante principal {zp:.3f}, secundaria {zs:.3f}, diferencia {zs - zp:+.3f} m. "
                            f"Esquinas curvas: ver tabla de esquinas."))
        if x.get("hueco", 0) > 0.05:
            avisos.append(Aviso("AVISO", "CRUCE", x["secundaria"], x["p_extremo"],
                                f"el eje termina a {x['hueco']:.2f} m de la cara del sardinel de {x['principal']}: "
                                f"ese tramo de la boca no se metra. Prolongue el eje hasta el eje de "
                                f"{x['principal']} (la app recorta lo que entre en su calzada)."))

    # ---- progresivas de cálculo
    lineas_por = {}
    for l in proy.fachadas:
        lineas_por.setdefault((l.eje_id, "I" if l.lado == "IZQ" else "D"), []).append(l)
    umbr_info = []
    for u in proy.umbrales:
        if u.eje_id not in alins:
            avisos.append(Aviso("ERROR", "PUERTA", u.eje_id, None, f"{u.id}: el eje no existe."))
            continue
        p, off, fuera = alins[u.eje_id].proyectar(u.este, u.norte)
        umbr_info.append((u, p, off, fuera))

    intervalo = max(0.5, float(par["intervalo_secciones"]))
    for c in proy.calles:
        rc = res[c.eje_id]
        alin, perf = rc.alin, rc.perfil
        marcas = {}

        def marcar(p, tipo):
            if alin.prog_inicial - 1e-6 <= p <= alin.prog_final + 1e-6:
                p = min(max(p, alin.prog_inicial), alin.prog_final)
                for q in list(marcas):
                    if abs(q - p) < EPS:
                        if tipo == "ESQUINA" and marcas[q] == "ESQUINA" and abs(q - p) > 1e-4:
                            continue          # tangencias de dos esquinas a mm: las dos secciones
                        if tipo == "ESQUINA" and marcas[q] not in ("INICIO", "FIN", "VERTICE", "ESQUINA"):
                            # la sección de tangencia tiene que estar justo en la tangencia (ahí
                            # empieza el sardinel recto): reemplaza a una marca de transición vecina
                            del marcas[q]
                            marcas[p] = tipo
                        elif marcas[q] == "INTERVALO":
                            marcas[q] = tipo
                        return
                marcas[p] = tipo

        marcar(alin.prog_inicial, "INICIO")
        marcar(alin.prog_final, "FIN")
        for q in perf.quiebres():
            marcar(q, "QUIEBRE")
        for q in alin.progs_vertices()[1:-1]:
            marcar(q, "VERTICE")
        for u, p, off, fuera in umbr_info:
            if u.eje_id == c.eje_id:
                marcar(p, u.tipo)
        for a, b in rc.zonas_sin_lateral:
            marcar(a, "CRUCE")
            marcar(b, "CRUCE")
            marcar(a + 0.01, "CRUCE")      # transición: desde aquí ya no hay vereda/sardinel
            marcar(b - 0.01, "CRUCE")
        for b in rc.badenes:
            for q in (b["centro"] - b["medio"], b["centro"], b["centro"] + b["medio"]):
                marcar(q, "BADEN")
        lr, ld = par["rampa_largo"] / 100.0, par["rampa_descanso"] / 100.0
        for r in rc.rampas:
            marcar(r["inicio"], "ESQUINA")
            if par["rampa_rebaje"] > 0 and lr > 0:
                for d in (lr, lr + ld, 2 * lr + ld):
                    marcar(r["inicio"] + r["sentido"] * d, "RAMPA")
        k = math.ceil((alin.prog_inicial - 1e-6) / intervalo)
        while k * intervalo <= alin.prog_final + 1e-6:
            marcar(k * intervalo, "INTERVALO")
            k += 1
        semi_max = c.ancho_calzada / 2 + par["cuneta_ancho"] / 100 + par["sardinel_ancho"] / 100 + c.ancho_vereda + 0.5
        zona_v = _zonas_vertice(alin, semi_max)
        for q in list(marcas):
            # cerca de un quiebre del eje solo queda la sección del vértice (en la bisectriz): las de
            # cruce o badén que caen ahí se cruzarían con ella (pasó en Nuñoa, Jr. Tupac Yupanqui
            # 0+086.83 a 5 cm de un vértice: superficie doblada, 107 mm de error en Civil 3D)
            if marcas[q] not in ("INICIO", "FIN", "VERTICE", "QUIEBRE", "ESQUINA") and _cerca_vertice(q, zona_v):
                del marcas[q]
        rc.zonas_vertice = zona_v

        defecto_cuneta = (par["cuneta_ancho"] / 100.0, par["cuneta_profundidad"] / 100.0)
        ws = par["sardinel_ancho"] / 100.0
        tol = par["tolerancia_fachada"] / 100.0
        vmin = par["vereda_ancho_min"] / 100.0
        def seccion_en(p, tipo):
            lateral = {l: not _dentro(p, rc.sin_lateral_lado[l]) for l in ("I", "D")}
            # (en un cruce oblicuo la sección de tangencia de una esquina puede caer en la franja que se
            # omite; se arma igual, sin metrar, porque la esquina toma de ella sus cotas)
            omitida = _dentro(p, rc.zonas_omitidas)
            cuneta = {l: _cuneta_en(proy, c.eje_id, l, p, defecto_cuneta) for l in ("I", "D")}
            ancho, disp = {}, {}
            for l in ("I", "D"):
                o_bv = c.ancho_calzada / 2 + cuneta[l][0] + ws
                d, _tipo_fachada = ancho_disponible(alin, p, l, lineas_por.get((c.eje_id, l), []), o_bv,
                                                    par["busqueda_fachada"])
                disp[l] = d
                w = c.ancho_vereda
                if d is not None and d < w and par["modo_fachada"] == "recortar":
                    w = max(0.0, d)
                ancho[l] = w
            rebaje = {l: esq_mod.rebaje_rampa(p, rc.rampas, l, par) for l in ("I", "D") if lateral[l]}
            rebaje = {l: v for l, v in rebaje.items() if v > 0}
            sec = construir(c, alin, perf, p, par, capas_calz, capas_ver, lateral, ancho, cuneta, tipo, rebaje)
            sec.rebaje = rebaje
            sec.vereda_disponible = disp
            sec.omitida = omitida
            dz = baden_dz(p, rc.badenes)
            if dz > 1e-9:
                b = min(rc.badenes, key=lambda b: abs(p - b["centro"]))
                _bajar_superficie(sec, dz, b["id"])
            elif any(abs(p - b["centro"]) <= b["medio"] + 1e-6 for b in rc.badenes):
                sec.baden_id = min(rc.badenes, key=lambda b: abs(p - b["centro"]))["id"]
            if not omitida:
                calcular_tierras(sec, terreno, par["paso_terreno"])
            return sec

        rc.secciones = [seccion_en(p, marcas[p]) for p in sorted(marcas)]
        if terreno.ok:
            _densificar(rc, seccion_en, par)

        # ---- avisos de vereda agrupados por tramos
        for l, nom in (("I", "IZQ"), ("D", "DER")):
            grupo = []
            for s in rc.secciones + [None]:
                malo = s is not None and s.lateral[l] and s.vereda_disponible.get(l) is not None \
                    and s.vereda_disponible[l] < c.ancho_vereda - tol
                if malo:
                    grupo.append(s)
                elif grupo:
                    dmin = min(g.vereda_disponible[l] for g in grupo)
                    nivel = "ERROR" if dmin < vmin else "AVISO"
                    accion = "se recortó la vereda" if par["modo_fachada"] == "recortar" else "solo aviso"
                    avisos.append(Aviso(nivel, "VEREDA", c.eje_id, grupo[0].prog,
                                        f"lado {nom} de {fmt_prog(grupo[0].prog)} a {fmt_prog(grupo[-1].prog)}: "
                                        f"ancho disponible mín. {dmin:.2f} m (diseño {c.ancho_vereda:.2f} m, "
                                        f"mínimo {vmin:.2f} m); {accion}."))
                    grupo = []

        # ---- volúmenes por área media
        validas = [s for s in rc.secciones if not s.omitida]
        nombres_capas = [cp.nombre for cp in capas_calz] + ["Concreto cuneta y sardinel"] + [cp.nombre for cp in capas_ver]
        rc.materiales = {n: 0.0 for n in nombres_capas}
        acum_c = acum_r = 0.0
        for s1, s2 in zip(validas[:-1], validas[1:]):
            d = s2.prog - s1.prog
            if _dentro((s1.prog + s2.prog) / 2, rc.zonas_omitidas):
                continue
            k_ = _factor_excentricidad(s1, s2, d)
            vc = (s1.area_corte + s2.area_corte) / 2 * d + k_ * (s1.mom_corte + s2.mom_corte) / 2
            vr = (s1.area_relleno + s2.area_relleno) / 2 * d + k_ * (s1.mom_relleno + s2.mom_relleno) / 2
            acum_c += vc
            acum_r += vr
            fila = {"desde": s1.prog, "hasta": s2.prog, "distancia": d,
                    "ac1": s1.area_corte, "ac2": s2.area_corte, "ar1": s1.area_relleno, "ar2": s2.area_relleno,
                    "vol_corte": vc, "vol_relleno": vr, "acum_corte": acum_c, "acum_relleno": acum_r}
            for nm in nombres_capas:
                v = (s1.area(nm) + s2.area(nm)) / 2 * d + k_ * (s1.momento(nm) + s2.momento(nm)) / 2
                rc.materiales[nm] += v
            rc.tramos_volumen.append(fila)
        rc.vol_corte, rc.vol_relleno = acum_c, acum_r
        # ---- badenes: concreto propio; reemplaza a la losa y a parte de la capa de abajo
        if rc.badenes:
            e_b = par["baden_espesor"] / 100.0
            t1 = capas_calz[0].espesor if capas_calz else 0.0
            nb = "Concreto badén (cuneta Tipo II)"
            rc.materiales[nb] = 0.0
            for b in rc.badenes:
                area_planta = b["largo_calzada"] * b["ancho"]     # lo que cae en la calzada de esta calle
                b["area"] = b["largo"] * b["ancho"]                 # de arco a arco (con las esquinas)
                b["concreto"] = b["largo"] * (b["ancho"] * e_b - b["ancho"] * b["prof"] / 2)
                rc.materiales[nb] += b["concreto"]
                if capas_calz:
                    rc.materiales[capas_calz[0].nombre] -= area_planta * t1
                if len(capas_calz) > 1 and e_b > t1:
                    rc.materiales[capas_calz[1].nombre] -= area_planta * min(e_b - t1, capas_calz[1].espesor)
                avisos.append(Aviso("INFO", "BADEN", c.eje_id, b["centro"],
                                    f"{b['id']}: badén de {b['ancho']:.2f} m × {b['largo']:.2f} m, "
                                    f"{b['prof'] * 100:.0f} cm de flecha, en la línea de cuneta de "
                                    f"{b['principal']} (lado {b['lado_principal']}); concreto {b['concreto']:.2f} m³."))
        falt = [s for s in validas if s.terreno_faltante > 0.30]
        if terreno.ok and falt:
            ancho = lambda s: s.lineas["SUBRASANTE"][-1][1] - s.lineas["SUBRASANTE"][0][1]
            total = [s for s in falt if s.terreno_faltante >= ancho(s) - 0.05]
            parcial = [s for s in falt if s not in total]
            if total:
                avisos.append(Aviso("ERROR", "TERRENO", c.eje_id, total[0].prog,
                                    f"{len(total)} secciones quedan FUERA del levantamiento (de "
                                    f"{fmt_prog(total[0].prog)} a {fmt_prog(total[-1].prog)}): ahí no se calcula "
                                    f"corte ni relleno. Complete el levantamiento."))
            if parcial:
                avisos.append(Aviso("AVISO", "TERRENO", c.eje_id, parcial[0].prog,
                                    f"{len(parcial)} secciones salen del terreno levantado en parte de su ancho "
                                    f"(primera en {fmt_prog(parcial[0].prog)}); esa parte no se metra."))

    # ---- umbrales
    umbrales = []
    pv = par["vereda_pendiente"] / 100.0
    for u, p, off, fuera in umbr_info:
        rc = res[u.eje_id]
        sec = min(rc.secciones, key=lambda s: abs(s.prog - p))
        lado = "I" if off < 0 else "D"
        nom = "IZQ" if lado == "I" else "DER"
        if u.lado and u.lado != nom:
            avisos.append(Aviso("AVISO", "PUERTA", u.eje_id, p,
                                f"{u.id}: está indicado al lado {u.lado} pero sus coordenadas caen al lado {nom}."))
        if not sec.lateral[lado]:
            avisos.append(Aviso("AVISO", "PUERTA", u.eje_id, p, f"{u.id}: cae dentro de un cruce, sin vereda."))
            continue
        bv = sec.punto("TERMINADO", "BV" + lado)
        pf = sec.punto("TERMINADO", "PF" + lado)
        o = min(max(abs(off), abs(bv[0])), abs(pf[0]))
        # la sección más cercana puede no estar en la progresiva de la puerta (por ejemplo cerca
        # de un vértice): se corrige con la rasante en la progresiva exacta
        zv = bv[1] + pv * (o - abs(bv[0])) + rc.perfil.cota(p) - sec.rasante
        dif = u.cota - zv
        info = {"umbral": u, "prog": p, "offset": off, "cota_vereda": zv, "diferencia": dif,
                "lado": nom, "fuera": fuera}
        umbrales.append(info)
        if dif < 0:
            avisos.append(Aviso("ERROR", u.tipo, u.eje_id, p,
                                f"{u.id} ({u.tipo.lower()}, lado {nom}): el umbral {u.cota:.3f} quedaría "
                                f"{-dif:.3f} m DEBAJO de la vereda proyectada ({zv:.3f}): puerta enterrada."))
        else:
            avisos.append(Aviso("INFO", u.tipo, u.eje_id, p,
                                f"{u.id} ({u.tipo.lower()}, lado {nom}): umbral {dif:.3f} m sobre la vereda. OK."))
        if u.tipo == "COCHERA":
            avisos.append(Aviso("AVISO", "COCHERA", u.eje_id, p,
                                f"{u.id}: cochera de {u.ancho:.2f} m. Prever rebaje de sardinel y rampa en vereda "
                                f"de {fmt_prog(p - u.ancho / 2)} a {fmt_prog(p + u.ancho / 2)} (se define en campo)."))

    # ---- esquinas curvas (3D, áreas, materiales, corte/relleno)
    out = Resultado(proy, res, terreno, cruces, umbrales, avisos, esquinas)
    esq_mod.construir(out, terreno, par, capas_calz, capas_ver)
    av_cod, out.puntos_codificados = cod_mod.controles(out, info_cod)
    avisos.extend(av_cod)
    for e in esquinas:
        if not e.get("ok"):
            avisos.append(Aviso("AVISO", "ESQUINA", e["principal"], e["tp"],
                                f"{e['id']} ({e['cruce']}): no se pudo armar la esquina ({e.get('error', '?')})."))
    if esquinas:
        avisos.append(Aviso("INFO", "ESQUINA", "-", None,
                            f"{len(esquinas)} esquinas curvas R = {par['radio_esquina'] / 100:.2f} m: "
                            f"pavimento {out.esquinas_total('area_calzada'):.1f} m², martillos "
                            f"{out.esquinas_total('area_martillo'):.1f} m², sardinel curvo "
                            f"{out.esquinas_total('long_sardinel'):.1f} m, {2 * len(esquinas)} rampas."))

    orden = {"ERROR": 0, "AVISO": 1, "INFO": 2}
    avisos.sort(key=lambda a: (orden.get(a.nivel, 3), a.eje_id, a.prog if a.prog is not None else -1))
    return out
