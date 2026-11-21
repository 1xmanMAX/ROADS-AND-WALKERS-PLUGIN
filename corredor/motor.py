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
    balance: dict = field(default_factory=dict)
    curva_masa: list = field(default_factory=list)          # [(prog, volumen acumulado)]
    seccion_en: object = None                               # función prog -> Seccion (sin guardar)

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
    interferencias: list = field(default_factory=list)
    bm_ubicacion: list = field(default_factory=list)

    def total(self, campo):
        return sum(getattr(rc, campo) for rc in self.calles.values())

    def balance_total(self):
        tot = {}
        for rc in self.calles.values():
            for k, v in rc.balance.items():
                tot[k] = tot.get(k, 0.0) + v
        return tot

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
def segmentos_fachada(proy, alins):
    """Tramos de las líneas de fachada/muro/límite. Se descartan los que cruzan un eje de calle
    (pasa cuando se levantan dos manzanas seguidas con el mismo código)."""
    ejes = []
    for al in alins.values():
        for sg in al.segs:
            ejes.append(((sg["e0"], sg["n0"]), (sg["e0"] + sg["L"] * sg["ux"], sg["n0"] + sg["L"] * sg["uy"])))
    segs, descartados = [], 0
    for l in proy.fachadas:
        for (e1, n1, t1), (e2, n2, t2) in zip(l.puntos[:-1], l.puntos[1:]):
            if any(interseccion_segmentos((e1, n1), (e2, n2), a, b) for a, b in ejes):
                descartados += 1
                continue
            segs.append({"p1": (e1, n1), "p2": (e2, n2), "tipo": t1, "linea": l.linea_id,
                         "eje": l.eje_id or "", "lado": {"IZQ": "I", "DER": "D"}.get(l.lado, "")})
    return segs, descartados


def ancho_disponible(alin, prog, lado, segs, o_bv, busqueda):
    """Distancia desde el borde interior de vereda hasta la fachada, por el rayo perpendicular."""
    e, n = alin.punto(prog)
    nx, ny = alin.normal(prog)
    sg = -1 if lado == "I" else 1
    p1 = (e + sg * nx * o_bv, n + sg * ny * o_bv)
    p2 = (e + sg * nx * (o_bv + busqueda), n + sg * ny * (o_bv + busqueda))
    mejor, tipo = None, None
    for s in segs:
        r = interseccion_segmentos(p1, p2, s["p1"], s["p2"])
        if r is None:
            continue
        d = r[0] * busqueda
        if mejor is None or d < mejor:
            mejor, tipo = d, s["tipo"]
    return mejor, tipo


def z_en_offset(sec, o):
    """Cota de la superficie terminada a 'o' metros del eje (interpolada)."""
    pts = sec.puntos
    if o <= pts[0][1]:
        return pts[0][2]
    if o >= pts[-1][1]:
        return pts[-1][2]
    mejor = None
    for (_, o1, z1), (_, o2, z2) in zip(pts[:-1], pts[1:]):
        if o1 - 1e-9 <= o <= o2 + 1e-9:
            z = z1 if o2 - o1 < 1e-9 else z1 + (z2 - z1) * (o - o1) / (o2 - o1)
            mejor = z if mejor is None else max(mejor, z)
    return mejor


def zona_en(sec, o):
    """CALZADA / CUNETA / SARDINEL / VEREDA / PREDIO según el offset."""
    lado = "D" if o >= 0 else "I"
    a = abs(o)
    bc = sec.punto("TERMINADO", "BC" + lado)
    if bc is None or a <= abs(bc[0]) + 1e-6:
        return "CALZADA"
    ps, bv, pf = (sec.punto("TERMINADO", c + lado) for c in ("PS", "BV", "PF"))
    if ps is None:
        return "CRUCE"
    if a <= abs(ps[0]) + 1e-6:
        return "CUNETA"
    if a <= abs(bv[0]) + 1e-6:
        return "SARDINEL"
    if a <= abs(pf[0]) + 0.05:
        return "VEREDA"
    return "PREDIO"


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

    # ---- fachadas y asignación de puertas/elementos a la calle más cercana
    segs_fachada, descartados = segmentos_fachada(proy, alins)
    if descartados:
        avisos.append(Aviso("INFO", "LEVANTAMIENTO", "-", None,
                            f"{descartados} tramos de fachada cruzaban un eje y no se usaron "
                            f"(use CA1, CA2... para separar manzanas)."))
    for t in proy.avisos_levantamiento:
        avisos.append(Aviso("AVISO", "LEVANTAMIENTO", "-", None, t))

    def asignar(e, n, eje_pref=""):
        mejor = None
        for k, al in alins.items():
            if eje_pref and k != eje_pref:
                continue
            p, off, fuera = al.proyectar(e, n)
            if fuera > 0.5 or abs(off) > par["busqueda_elementos"]:
                continue
            if mejor is None or abs(off) < abs(mejor[2]):
                mejor = (k, p, off)
        return mejor

    umbr_info = []
    for u in proy.umbrales:
        a = asignar(u.este, u.norte, u.eje_id if u.eje_id in alins else "")
        if a is None:
            avisos.append(Aviso("AVISO", u.tipo, "-", None, f"{u.id}: está lejos de todas las calles; no se revisa."))
            continue
        umbr_info.append((u, a[0], a[1], a[2]))

    intervalo = max(0.5, float(par["intervalo_secciones"]))
    defecto_cuneta = (par["cuneta_ancho"] / 100.0, par["cuneta_profundidad"] / 100.0)
    ws = par["sardinel_ancho"] / 100.0
    tol = par["tolerancia_fachada"] / 100.0
    vmin = par["vereda_ancho_min"] / 100.0
    nombres_capas = [cp.nombre for cp in capas_calz] + ["Concreto cuneta y sardinel"] + [cp.nombre for cp in capas_ver]
    for c in proy.calles:
        rc = res[c.eje_id]
        alin, perf = rc.alin, rc.perfil
        marcas = {}

        def marcar(p, tipo, alin=alin, marcas=marcas):
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
        for u, eje, p, off in umbr_info:
            if eje == c.eje_id:
                marcar(p, u.tipo)
                if u.tipo == "COCHERA":
                    marcar(p - u.ancho / 2, "COCHERA")
                    marcar(p + u.ancho / 2, "COCHERA")
        for a, b in rc.zonas_sin_lateral:
            marcar(a, "CRUCE")
            marcar(b, "CRUCE")
            marcar(a + 0.01, "CRUCE")      # transición: desde aquí ya no hay vereda/sardinel
            marcar(b - 0.01, "CRUCE")
        k = math.ceil((alin.prog_inicial - 1e-6) / intervalo)
        while k * intervalo <= alin.prog_final + 1e-6:
            marcar(k * intervalo, "INTERVALO")
            k += 1

        segs_calle = {l: [sg for sg in segs_fachada if sg["eje"] in ("", c.eje_id) and sg["lado"] in ("", l)]
                      for l in ("I", "D")}

        def seccion_en(p, tipo="CONSULTA", tierras=True, c=c, alin=alin, perf=perf, rc=rc, segs_calle=segs_calle):
            lateral = {l: not _dentro(p, rc.zonas_sin_lateral) for l in ("I", "D")}
            omitida = _dentro(p, rc.zonas_omitidas)
            cuneta = {l: _cuneta_en(proy, c.eje_id, l, p, defecto_cuneta) for l in ("I", "D")}
            ancho, disp, tipo_f = {}, {}, {}
            for l in ("I", "D"):
                o_bv = c.ancho_calzada / 2 + cuneta[l][0] + ws
                d, tf = ancho_disponible(alin, p, l, segs_calle[l], o_bv, par["busqueda_fachada"])
                disp[l], tipo_f[l] = d, tf
                w = c.ancho_vereda
                if d is not None and d < w and par["modo_fachada"] == "recortar":
                    w = max(0.0, d)
                ancho[l] = w
            sec = construir(c, alin, perf, p, par, capas_calz, capas_ver, lateral, ancho, cuneta, tipo)
            sec.vereda_disponible = disp
            sec.tipo_fachada = tipo_f
            sec.omitida = omitida
            if tierras and not omitida:
                calcular_tierras(sec, terreno, par["paso_terreno"])
            return sec

        rc.seccion_en = seccion_en
        for p in sorted(marcas):
            rc.secciones.append(seccion_en(p, marcas[p]))

        # ---- avisos de vereda agrupados por tramos
        for l, nom in (("I", "IZQ"), ("D", "DER")):
            grupo = []
            for s_ in rc.secciones + [None]:
                malo = s_ is not None and s_.lateral[l] and not s_.omitida and s_.vereda_disponible.get(l) is not None \
                    and s_.vereda_disponible[l] < c.ancho_vereda - tol
                if malo:
                    grupo.append(s_)
                elif grupo:
                    dmin = min(g.vereda_disponible[l] for g in grupo)
                    tipos = {g.tipo_fachada.get(l) for g in grupo} - {None}
                    nivel = "ERROR" if dmin < vmin else "AVISO"
                    accion = "se recortó la vereda" if par["modo_fachada"] == "recortar" else "solo aviso"
                    avisos.append(Aviso(nivel, "VEREDA", c.eje_id, grupo[0].prog,
                                        f"lado {nom} de {fmt_prog(grupo[0].prog)} a {fmt_prog(grupo[-1].prog)}: "
                                        f"{'/'.join(sorted(tipos)) or 'fachada'} a {dmin:.2f} m del sardinel "
                                        f"(diseño {c.ancho_vereda:.2f} m, mínimo {vmin:.2f} m); {accion}."))
                    grupo = []

        # ---- volúmenes por área media
        validas = [s_ for s_ in rc.secciones if not s_.omitida]
        rc.materiales = {n: 0.0 for n in nombres_capas}
        acum_c = acum_r = masa = 0.0
        fc = 1 + par["contraccion_relleno"] / 100.0
        rc.curva_masa = [(validas[0].prog, 0.0)] if validas else []
        for s1, s2 in zip(validas[:-1], validas[1:]):
            d = s2.prog - s1.prog
            if _dentro((s1.prog + s2.prog) / 2, rc.zonas_omitidas):
                continue
            vc = (s1.area_corte + s2.area_corte) / 2 * d
            vr = (s1.area_relleno + s2.area_relleno) / 2 * d
            acum_c += vc
            acum_r += vr
            masa += vc - vr * fc
            rc.curva_masa.append((s2.prog, masa))
            fila = {"desde": s1.prog, "hasta": s2.prog, "distancia": d,
                    "ac1": s1.area_corte, "ac2": s2.area_corte, "ar1": s1.area_relleno, "ar2": s2.area_relleno,
                    "vol_corte": vc, "vol_relleno": vr, "acum_corte": acum_c, "acum_relleno": acum_r}
            for nm in nombres_capas:
                rc.materiales[nm] += (s1.area(nm) + s2.area(nm)) / 2 * d
            rc.tramos_volumen.append(fila)
        rc.vol_corte, rc.vol_relleno = acum_c, acum_r
        rc.balance = balance(acum_c, acum_r, par)
        falt = [s_ for s_ in validas if s_.terreno_faltante > 0.30]
        if terreno.ok and falt:
            avisos.append(Aviso("AVISO", "TERRENO", c.eje_id, falt[0].prog,
                                f"{len(falt)} secciones salen del terreno levantado en parte de su ancho "
                                f"(primera en {fmt_prog(falt[0].prog)}); esa parte no se metra."))

    # ---- puertas, cocheras y elementos: interferencias
    interf, umbrales = revisar_interferencias(proy, res, umbr_info, asignar, avisos)

    # ---- ubicación de los BM
    bm_ub = []
    for b in proy.bms:
        a = asignar(b.este, b.norte)
        if a is None:
            a2 = min(((k, *al.proyectar(b.este, b.norte)) for k, al in alins.items()),
                     key=lambda x: abs(x[2]) + x[3], default=None)
            a = (a2[0], a2[1], a2[2]) if a2 else None
        if a is None:
            bm_ub.append({"bm": b, "eje": "", "prog": None, "offset": None, "texto": "sin calle cercana"})
            continue
        k, p, off = a
        lado = "izquierda" if off < 0 else "derecha"
        bm_ub.append({"bm": b, "eje": k, "prog": p, "offset": off,
                      "texto": f"{k} {res[k].calle.nombre}, progresiva {fmt_prog(p)}, a la {lado} a "
                               f"{abs(off):.2f} m del eje"})

    orden = {"ERROR": 0, "AVISO": 1, "INFO": 2}
    avisos.sort(key=lambda a: (orden.get(a.nivel, 3), a.eje_id, a.prog if a.prog is not None else -1))
    return Resultado(proy, res, terreno, cruces, umbrales, avisos, interf, bm_ub)


def balance(corte, relleno, par):
    """Balance de tierras.
    reutilizado = parte del corte que sirve como relleno (limitada al relleno necesario)
    préstamo    = (relleno − reutilizado) × (1 + contracción)   -> material a traer
    eliminación = (corte − reutilizado) × (1 + esponjamiento)    -> material a botar (suelto)
    """
    reut = min(corte * par["reutilizacion_corte"] / 100.0, relleno)
    return {"corte": corte, "relleno": relleno, "reutilizado": reut,
            "prestamo": (relleno - reut) * (1 + par["contraccion_relleno"] / 100.0),
            "eliminacion": (corte - reut) * (1 + par["esponjamiento"] / 100.0)}


def revisar_interferencias(proy, res, umbr_info, asignar, avisos):
    par = proy.parametros
    pv = par["vereda_pendiente"] / 100.0
    tol_tapa = par["tolerancia_tapas"] / 100.0
    paso_min = par["paso_libre_min"] / 100.0
    interf, umbrales = [], []

    def fila(tipo, ident, eje, p, off, zona, zc, zd, estado, nivel, accion, nombre, e, n):
        d = (zc - zd) if (zc is not None and zd is not None) else None
        interf.append({"tipo": tipo, "id": ident, "nombre": nombre, "eje": eje, "prog": p, "offset": off,
                       "lado": "" if off is None else ("IZQ" if off < 0 else "DER"), "zona": zona,
                       "cota_campo": zc, "cota_diseno": zd, "diferencia": d, "estado": estado, "nivel": nivel,
                       "accion": accion, "este": e, "norte": n})
        if nivel in ("ERROR", "AVISO"):
            avisos.append(Aviso(nivel, tipo, eje or "-", p, f"{ident} {nombre}: {estado}. {accion}".strip()))

    # puertas y cocheras
    for u, eje, p, off in umbr_info:
        rc = res[eje]
        sec = rc.seccion_en(p, tierras=False)
        lado = "I" if off < 0 else "D"
        nom = "IZQ" if lado == "I" else "DER"
        nombre = "Puerta" if u.tipo == "PUERTA" else f"Cochera {u.ancho:.2f} m"
        if not sec.lateral[lado] or sec.omitida:
            fila(u.tipo, u.id, eje, p, off, "CRUCE", u.cota, None, "cae dentro de un cruce", "AVISO",
                 "revisar en la esquina", nombre, u.este, u.norte)
            continue
        bv = sec.punto("TERMINADO", "BV" + lado)
        pf = sec.punto("TERMINADO", "PF" + lado)
        o = min(max(abs(off), abs(bv[0])), abs(pf[0]))
        zv = bv[1] + pv * (o - abs(bv[0]))
        dif = u.cota - zv
        info = {"umbral": u, "eje": eje, "prog": p, "offset": off, "cota_vereda": zv, "diferencia": dif, "lado": nom}
        umbrales.append(info)
        if dif < -0.005:
            estado, nivel = f"umbral {-dif:.3f} m DEBAJO de la vereda (enterrada)", "ERROR"
            accion = (f"bajar la vereda frente a la puerta a {u.cota - 0.02:.3f} (2 cm bajo el umbral) con transición "
                      f"a ambos lados, o coordinar con el propietario")
        elif dif < 0.02:
            estado, nivel = f"umbral casi a nivel de la vereda ({dif:+.3f} m)", "AVISO"
            accion = "verificar que el agua no entre a la vivienda"
        else:
            estado, nivel, accion = f"umbral {dif:.3f} m sobre la vereda", "INFO", "OK"
        if u.tipo == "COCHERA":
            bc = sec.punto("TERMINADO", "BC" + lado)
            ps = sec.punto("TERMINADO", "PS" + lado)
            z_reb = bc[1] + par["rebaje_sardinel"] / 100.0
            largo = max(0.01, abs(off) - abs(ps[0]))
            pend = (u.cota - z_reb) / largo * 100
            info["rampa_pct"] = pend
            txt = (f"rebajar sardinel a {z_reb:.3f} de {fmt_prog(p - u.ancho / 2)} a {fmt_prog(p + u.ancho / 2)}; "
                   f"rampa de {pend:.1f} % en {largo:.2f} m")
            if pend > par["pendiente_rampa_max"]:
                nivel = "ERROR" if nivel != "ERROR" else nivel
                txt += f" (supera {par['pendiente_rampa_max']:.0f} %)"
            elif nivel == "INFO":
                nivel = "AVISO"
            accion = txt if accion == "OK" else accion + "; " + txt
        fila(u.tipo, u.id, eje, p, off, "VEREDA/FACHADA", u.cota, zv, estado, nivel, accion, nombre, u.este, u.norte)

    # elementos sueltos
    for el in proy.elementos:
        a = asignar(el.este, el.norte)
        if a is None:
            fila("ELEMENTO", f"{el.codigo}-{el.id}", "", None, None, "LEJOS", el.cota, None,
                 "fuera del área de las calles", "INFO", "", el.nombre, el.este, el.norte)
            continue
        eje, p, off = a
        sec = res[eje].seccion_en(p, tierras=False)
        zona = "CRUCE" if sec.omitida else zona_en(sec, off)
        zd = z_en_offset(sec, off)
        ident = f"{el.tipo_codigo}-{el.id}"
        if el.regla == "nivelar":
            if zona == "PREDIO":
                fila("ELEMENTO", ident, eje, p, off, zona, el.cota, None, "dentro del predio", "INFO", "",
                     el.nombre, el.este, el.norte)
                continue
            d = el.cota - zd
            if abs(d) <= tol_tapa:
                estado, nivel, accion = "tapa a nivel del diseño", "INFO", "OK"
            else:
                estado = f"tapa {abs(d):.3f} m {'ARRIBA' if d > 0 else 'DEBAJO'} del diseño"
                accion = f"{'bajar' if d > 0 else 'subir'} la tapa {abs(d):.3f} m hasta {zd:.3f}"
                nivel = "AVISO"
            if zona in ("CUNETA", "SARDINEL"):
                nivel, accion = "ERROR", accion + f"; está en {zona.lower()}: reubicar o adaptar"
            fila("ELEMENTO", ident, eje, p, off, zona, el.cota, zd, estado, nivel, accion, el.nombre, el.este, el.norte)
        elif el.regla == "obstaculo":
            lado = "I" if off < 0 else "D"
            if zona in ("CALZADA", "CUNETA", "SARDINEL"):
                fila("ELEMENTO", ident, eje, p, off, zona, el.cota, zd, f"queda dentro de la {zona.lower()}",
                     "ERROR", "reubicar antes de construir", el.nombre, el.este, el.norte)
            elif zona == "VEREDA":
                bv = abs(sec.punto("TERMINADO", "BV" + lado)[0])
                pf = abs(sec.punto("TERMINADO", "PF" + lado)[0])
                libre = max(abs(off) - bv, pf - abs(off))
                nivel = "ERROR" if libre < paso_min else "AVISO"
                fila("ELEMENTO", ident, eje, p, off, zona, el.cota, zd, f"en vereda, paso libre {libre:.2f} m",
                     nivel, "reubicar" if nivel == "ERROR" else "dejar como está o reubicar junto al sardinel",
                     el.nombre, el.este, el.norte)
            else:
                fila("ELEMENTO", ident, eje, p, off, zona, el.cota, None, "fuera de la vía", "INFO", "",
                     el.nombre, el.este, el.norte)
        else:
            fila("ELEMENTO", ident, eje, p, off, zona, el.cota, zd, "registrado", "INFO", "", el.nombre,
                 el.este, el.norte)
    orden = {"ERROR": 0, "AVISO": 1, "INFO": 2}
    interf.sort(key=lambda f: (orden[f["nivel"]], f["eje"], f["prog"] if f["prog"] is not None else 0))
    return interf, umbrales
