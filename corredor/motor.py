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
    zonas_sin_lateral: list = field(default_factory=list)   # [(p1, p2)]
    zonas_omitidas: list = field(default_factory=list)      # [(p1, p2)]

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

    def total(self, campo):
        return sum(getattr(rc, campo) for rc in self.calles.values())

    def materiales_total(self):
        tot = {}
        for rc in self.calles.values():
            for k, v in rc.materiales.items():
                tot[k] = tot.get(k, 0.0) + v
        return tot


# ------------------------------------------------------------------ cruces
def buscar_cruces(proy, alins, par):
    c_ = par["cuneta_ancho"] / 100.0
    ws = par["sardinel_ancho"] / 100.0
    cruces = []
    calles = proy.calles
    for i in range(len(calles)):
        for j in range(i + 1, len(calles)):
            A, B = alins[calles[i].eje_id], alins[calles[j].eje_id]
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
                    cruces.append({
                        "principal": calles[i].eje_id, "secundaria": calles[j].eje_id,
                        "p_principal": sa["p0"] + t * sa["L"], "p_secundaria": sb["p0"] + u * sb["L"],
                        "e": pa1[0] + t * (pa2[0] - pa1[0]), "n": pa1[1] + t * (pa2[1] - pa1[1]),
                        "angulo": math.degrees(math.asin(min(1.0, sen))),
                        # semiancho hasta la cara del sardinel de la otra calle, medido sobre este eje
                        "h_principal": (calles[j].ancho_calzada / 2 + c_ + ws) / sen,
                        "h_secundaria": (calles[i].ancho_calzada / 2 + c_ + ws) / sen,
                    })
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


# ------------------------------------------------------------------ cálculo
def calcular(proy):
    par = proy.parametros
    avisos = []
    capas_calz = proy.capas_de("calzada")
    capas_ver = proy.capas_de("vereda")
    terreno = Terreno(proy.terreno, par["arista_max_tin"])
    if not terreno.ok:
        avisos.append(Aviso("AVISO", "TERRENO", "-", None, "No hay terreno cargado: no se calcula corte/relleno."))

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
    for x in cruces:
        rp, rs = res[x["principal"]], res[x["secundaria"]]
        a1, a2 = x["p_principal"] - x["h_principal"], x["p_principal"] + x["h_principal"]
        b1, b2 = x["p_secundaria"] - x["h_secundaria"], x["p_secundaria"] + x["h_secundaria"]
        rp.zonas_sin_lateral.append((a1, a2))
        rs.zonas_sin_lateral.append((b1, b2))
        rs.zonas_omitidas.append((b1, b2))
        zp = rp.perfil.cota(x["p_principal"])
        zs = rs.perfil.cota(x["p_secundaria"])
        x["z_principal"], x["z_secundaria"] = zp, zs
        nivel = "AVISO" if abs(zp - zs) > 0.005 else "INFO"
        avisos.append(Aviso(nivel, "CRUCE", x["secundaria"], x["p_secundaria"],
                            f"cruza {x['principal']} en {fmt_prog(x['p_principal'])} (ángulo {x['angulo']:.1f}°). "
                            f"Rasante principal {zp:.3f}, secundaria {zs:.3f}, diferencia {zs - zp:+.3f} m. "
                            f"Esquinas y chaflanes: pendiente (siguiente fase)."))

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
                        if marcas[q] == "INTERVALO":
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
        k = math.ceil((alin.prog_inicial - 1e-6) / intervalo)
        while k * intervalo <= alin.prog_final + 1e-6:
            marcar(k * intervalo, "INTERVALO")
            k += 1

        defecto_cuneta = (par["cuneta_ancho"] / 100.0, par["cuneta_profundidad"] / 100.0)
        ws = par["sardinel_ancho"] / 100.0
        tol = par["tolerancia_fachada"] / 100.0
        vmin = par["vereda_ancho_min"] / 100.0
        for p in sorted(marcas):
            lateral = {l: not _dentro(p, rc.zonas_sin_lateral) for l in ("I", "D")}
            omitida = _dentro(p, rc.zonas_omitidas)
            cuneta = {l: _cuneta_en(proy, c.eje_id, l, p, defecto_cuneta) for l in ("I", "D")}
            ancho, disp = {}, {}
            for l in ("I", "D"):
                o_bv = c.ancho_calzada / 2 + cuneta[l][0] + ws
                d, tipo = ancho_disponible(alin, p, l, lineas_por.get((c.eje_id, l), []), o_bv,
                                           par["busqueda_fachada"])
                disp[l] = d
                w = c.ancho_vereda
                if d is not None and d < w and par["modo_fachada"] == "recortar":
                    w = max(0.0, d)
                ancho[l] = w
            sec = construir(c, alin, perf, p, par, capas_calz, capas_ver, lateral, ancho, cuneta, marcas[p])
            sec.vereda_disponible = disp
            sec.omitida = omitida
            if not omitida:
                calcular_tierras(sec, terreno, par["paso_terreno"])
            rc.secciones.append(sec)

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
            vc = (s1.area_corte + s2.area_corte) / 2 * d
            vr = (s1.area_relleno + s2.area_relleno) / 2 * d
            acum_c += vc
            acum_r += vr
            fila = {"desde": s1.prog, "hasta": s2.prog, "distancia": d,
                    "ac1": s1.area_corte, "ac2": s2.area_corte, "ar1": s1.area_relleno, "ar2": s2.area_relleno,
                    "vol_corte": vc, "vol_relleno": vr, "acum_corte": acum_c, "acum_relleno": acum_r}
            for nm in nombres_capas:
                v = (s1.area(nm) + s2.area(nm)) / 2 * d
                rc.materiales[nm] += v
            rc.tramos_volumen.append(fila)
        rc.vol_corte, rc.vol_relleno = acum_c, acum_r
        falt = [s for s in validas if s.terreno_faltante > 0.30]
        if terreno.ok and falt:
            avisos.append(Aviso("AVISO", "TERRENO", c.eje_id, falt[0].prog,
                                f"{len(falt)} secciones salen del terreno levantado en parte de su ancho "
                                f"(primera en {fmt_prog(falt[0].prog)}); esa parte no se metra."))

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
        zv = bv[1] + pv * (o - abs(bv[0]))
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

    orden = {"ERROR": 0, "AVISO": 1, "INFO": 2}
    avisos.sort(key=lambda a: (orden.get(a.nivel, 3), a.eje_id, a.prog if a.prog is not None else -1))
    return Resultado(proy, res, terreno, cruces, umbrales, avisos)
