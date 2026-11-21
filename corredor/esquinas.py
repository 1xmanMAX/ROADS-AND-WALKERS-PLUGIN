"""Esquinas curvas en los cruces (como el plano de veredas, rampas y martillos del expediente).

En cada esquina de un cruce (4 en una X, 2 en una T):

        principal (cara del sardinel, offset b + c)
   ─────────────────Tp
                      ╲  arco de sardinel, radio R en la cara (R − ancho de sardinel en el dorso)
        MARTILLO        ╲
   (vereda de esquina)   │Ts
                         │  secundaria (cara del sardinel)

* Centro C del arco: a b_p + c_p + R del eje de la principal y a b_s + c_s + R del de la secundaria
  (b = media calzada, c = ancho de cuneta). Tp y Ts son los puntos de tangencia: ahí terminan el
  sardinel, la cuneta y la vereda rectos de cada calle (la app corta lo lateral de cada calle entre
  sus dos Tp) y empieza la pieza de esquina.
* Pavimento de esquina: lo que queda entre las dos calzadas y la cara del arco.
* Sardinel curvo: entre la cara (radio R) y el dorso (R − ancho); la cota pasa linealmente de la de
  la principal en Tp a la de la secundaria en Ts.
* Martillo: vereda de esquina entre el dorso del sardinel y las dos líneas de fachada (pie de vereda).
* Rampas: en cada brazo, a continuación de Tp/Ts (rampa 12 % + descanso + rampa 12 %); bajan la
  vereda en las secciones de la calle (ver motor.py).

Cada esquina da triángulos 3D (superficie terminada y subrasante), áreas, materiales y corte/relleno
contra el terreno (integrando la diferencia de cotas sobre los triángulos).
"""
import math

import numpy as np

# ------------------------------------------------------------------ geometría plana


def _inter(p, u, q, v):
    """Intersección de las rectas p + t·u y q + s·v."""
    den = u[0] * v[1] - u[1] * v[0]
    if abs(den) < 1e-12:
        return None
    t = ((q[0] - p[0]) * v[1] - (q[1] - p[1]) * v[0]) / den
    return (p[0] + t * u[0], p[1] + t * u[1])


def _area2(poly):
    a = 0.0
    for (x1, y1, *_), (x2, y2, *_) in zip(poly, poly[1:] + poly[:1]):
        a += x1 * y2 - x2 * y1
    return a / 2.0


def triangular(poly):
    """Triangulación por recorte de orejas de un polígono simple [(x, y, z), ...] -> [(a, b, c)]."""
    pts = [p for i, p in enumerate(poly) if math.dist(p[:2], poly[i - 1][:2]) > 1e-6]
    if len(pts) < 3:
        return []
    if _area2(pts) < 0:
        pts = pts[::-1]
    idx = list(range(len(pts)))
    out = []

    def cruz(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def dentro(p, a, b, c):
        return cruz(a, b, p) > 1e-12 and cruz(b, c, p) > 1e-12 and cruz(c, a, p) > 1e-12

    guardia = 0
    while len(idx) > 3 and guardia < 10000:
        guardia += 1
        hecho = False
        for k in range(len(idx)):
            i0, i1, i2 = idx[k - 1], idx[k], idx[(k + 1) % len(idx)]
            a, b, c = pts[i0], pts[i1], pts[i2]
            if cruz(a, b, c) <= 1e-12:
                continue
            if any(dentro(pts[j], a, b, c) for j in idx if j not in (i0, i1, i2)):
                continue
            out.append((a, b, c))
            del idx[k]
            hecho = True
            break
        if not hecho:            # polígono degenerado: abanico con lo que queda
            break
    if len(idx) >= 3:
        for k in range(1, len(idx) - 1):
            out.append((pts[idx[0]], pts[idx[k]], pts[idx[k + 1]]))
    return [t for t in out if abs(cruz(*t)) > 2e-4]      # sin astillas (< 1 cm²)


def recortar(poly, f, lo, hi):
    """Sutherland-Hodgman: parte del polígono [(x, y, z)] donde lo <= f(x, y) <= hi (z interpolada)."""
    def corte(pts, dentro, borde):
        out = []
        for i, b in enumerate(pts):
            a = pts[i - 1]
            fa, fb = f(a), f(b)
            if dentro(fb):
                if not dentro(fa):
                    t = (borde - fa) / (fb - fa)
                    out.append(tuple(a[k] + (b[k] - a[k]) * t for k in range(3)))
                out.append(b)
            elif dentro(fa):
                t = (borde - fa) / (fb - fa)
                out.append(tuple(a[k] + (b[k] - a[k]) * t for k in range(3)))
        return out
    pts = list(poly)
    if lo is not None and pts:
        pts = corte(pts, lambda v: v >= lo - 1e-9, lo)
    if hi is not None and pts:
        pts = corte(pts, lambda v: v <= hi + 1e-9, hi)
    limpio = []
    for q in pts:                      # puntos repetidos (a menos de 1 mm) que deja el recorte
        if not limpio or math.dist(q[:2], limpio[-1][:2]) > 1e-3:
            limpio.append(q)
    if len(limpio) > 1 and math.dist(limpio[0][:2], limpio[-1][:2]) <= 1e-3:
        limpio.pop()
    return limpio if len(limpio) >= 3 else []


def _arco(c, r, p_ini, p_fin, z_ini, z_fin, paso_grados=7.5):
    """Puntos del arco de centro c y radio r, de la dirección de p_ini a la de p_fin (por el lado corto)."""
    a0 = math.atan2(p_ini[1] - c[1], p_ini[0] - c[0])
    a1 = math.atan2(p_fin[1] - c[1], p_fin[0] - c[0])
    da = (a1 - a0 + math.pi) % (2 * math.pi) - math.pi
    n = max(3, int(math.ceil(abs(math.degrees(da)) / paso_grados)))
    return [(c[0] + r * math.cos(a0 + da * k / n), c[1] + r * math.sin(a0 + da * k / n),
             z_ini + (z_fin - z_ini) * k / n) for k in range(n + 1)], abs(da)


# ------------------------------------------------------------------ planta (antes de las secciones)
def planta(rp, rs, x, lados_p, R, cuneta_en):
    """Centros y puntos de tangencia de las esquinas de un cruce.

    cuneta_en(eje_id, lado, prog) -> (ancho, profundidad) de cuneta.
    Devuelve [{lado_p, lado_s, C, tp, ts}] con tp/ts = progresivas de tangencia en cada calle."""
    if R <= 0:
        return []
    up = rp.alin.direccion(x["p_principal"])
    us = rs.alin.direccion(min(max(x["p_secundaria"], rs.alin.prog_inicial), rs.alin.prog_final))
    np_ = (up[1], -up[0])
    ns = (us[1], -us[0])
    X0 = (x["e"], x["n"])
    den = up[0] * ns[0] + up[1] * ns[1]
    if abs(den) < 1e-6:
        return []
    out = []
    for lp in lados_p:
        sp = 1.0 if lp == "D" else -1.0
        cp, _ = cuneta_en(rp.calle.eje_id, lp, x["p_principal"])
        o_p = rp.calle.ancho_calzada / 2 + cp
        for ls in ("I", "D"):
            ss = 1.0 if ls == "D" else -1.0
            cs, _ = cuneta_en(rs.calle.eje_id, ls, x["p_secundaria"])
            o_s = rs.calle.ancho_calzada / 2 + cs
            bb = sp * (o_p + R)
            nn = np_[0] * ns[0] + np_[1] * ns[1]
            a = (ss * (o_s + R) - bb * nn) / den
            C = (X0[0] + a * up[0] + bb * np_[0], X0[1] + a * up[1] + bb * np_[1])
            Tp = (C[0] - sp * R * np_[0], C[1] - sp * R * np_[1])
            Ts = (C[0] - ss * R * ns[0], C[1] - ss * R * ns[1])
            tp, offp, fp = rp.alin.proyectar(*Tp)
            ts, offs, fs = rs.alin.proyectar(*Ts)
            # el eje puede quebrar cerca del cruce: se recalcula con la dirección de cada calle en su
            # propia tangencia (si no, el arco no empalma con la sección de tangencia; pasó en
            # Nuñoa, Jr. Tupac Yupanqui, con un vértice de 4.5° a 3 m del cruce)
            up_t, us_t = up, us
            for _ in range(4):
                up_t, us_t = rp.alin.direccion(tp), rs.alin.direccion(ts)
                np_t, ns_t = (up_t[1], -up_t[0]), (us_t[1], -us_t[0])
                A = rp.alin.punto(tp)
                B = rs.alin.punto(ts)
                Ci = _inter((A[0] + sp * (o_p + R) * np_t[0], A[1] + sp * (o_p + R) * np_t[1]), up_t,
                            (B[0] + ss * (o_s + R) * ns_t[0], B[1] + ss * (o_s + R) * ns_t[1]), us_t)
                if Ci is None:
                    break
                C = Ci
                Tp = (C[0] - sp * R * np_t[0], C[1] - sp * R * np_t[1])
                Ts = (C[0] - ss * R * ns_t[0], C[1] - ss * R * ns_t[1])
                tp, offp, fp = rp.alin.proyectar(*Tp)
                ts, offs, fs = rs.alin.proyectar(*Ts)
            # la secundaria tiene que existir hacia el lado lp de la principal (en una T, solo uno)
            if fp > 0.05 or fs > 0.05:
                continue
            _, off_ts_p, _ = rp.alin.proyectar(*rs.alin.punto(ts))
            if off_ts_p * sp <= 0:
                continue
            # al mm: las tangencias de las esquinas de ambos lados caen en la misma sección
            out.append({"lado_p": lp, "lado_s": ls, "C": C, "tp": round(tp, 3), "ts": round(ts, 3), "R": R,
                        "up": up_t, "us": us_t, "X0": X0, "up_cruce": up})
    return out


# ------------------------------------------------------------------ 3D (después de las secciones)
def _seccion(rc, prog, tol=0.02):
    cand = [s for s in rc.secciones if (not s.omitida or s.tipo == "ESQUINA") and abs(s.prog - prog) <= tol]
    return min(cand, key=lambda s: abs(s.prog - prog)) if cand else None


def _pts_lado(s, lado):
    """{código base: (e, n, z, offset)} del lado indicado en la superficie terminada."""
    out = {}
    for c, o, z in s.lineas["TERMINADO"]:
        if c != "EJE" and c[-1] == lado:
            e, n = s.xy(o)
            out[c[:-1]] = (e, n, z, o)
    return out


def _bordes(rc, lado, p_desde, p_hasta):
    """Borde de calzada (BC) de las secciones entre dos progresivas, en orden de p_desde a p_hasta."""
    lo, hi = min(p_desde, p_hasta), max(p_desde, p_hasta)
    secs = [s for s in rc.secciones if not s.omitida and lo + 1e-6 < s.prog < hi - 1e-6]
    secs.sort(key=lambda s: s.prog, reverse=p_desde > p_hasta)
    out = []
    for s in secs:
        p = _pts_lado(s, lado).get("BC")
        if p:
            out.append(p[:3])
    return out


def construir(res, terreno, par, capas_calz, capas_ver):
    """Completa cada esquina de res.esquinas con su 3D, áreas, materiales y movimiento de tierras."""
    ws = par["sardinel_ancho"] / 100.0
    T = sum(c.espesor for c in capas_calz)
    Tv = sum(c.espesor for c in capas_ver)
    t1 = capas_calz[0].espesor if capas_calz else 0.0
    nudge = 0.005
    for esq in res.esquinas:
        rp, rs = res.calles[esq["principal"]], res.calles[esq["secundaria"]]
        lp, ls = esq["lado_p"], esq["lado_s"]
        sp_, ss_ = _seccion(rp, esq["tp"]), _seccion(rs, esq["ts"])
        esq.update(caras={}, sub=[], area_calzada=0.0, area_martillo=0.0, area_sardinel=0.0,
                   long_sardinel=0.0, materiales={}, vol_corte=0.0, vol_relleno=0.0, ok=False)
        if sp_ is None or ss_ is None:
            esq["error"] = "sin sección en el punto de tangencia"
            continue
        P, S = _pts_lado(sp_, lp), _pts_lado(ss_, ls)
        if "CS" not in P or "CS" not in S:
            esq["error"] = "la sección de tangencia no tiene sardinel"
            continue
        C, R = esq["C"], esq["R"]
        # cara del sardinel abajo (fondo de cuneta o borde de calzada) y arriba (cabeza)
        Fp, Fs = P.get("FC", P["BC"]), S.get("FC", S["BC"])
        cara, ang = _arco(C, R, Fp, Fs, Fp[2], Fs[2])
        cara[0], cara[-1] = Fp[:3], Fs[:3]
        cabeza, _ = _arco(C, R - nudge, Fp, Fs, P["CS"][2], S["CS"][2])
        dorso, _ = _arco(C, R - ws, P["BV"], S["BV"], P["BV"][2], S["BV"][2]) if "BV" in P and "BV" in S else \
            _arco(C, R - ws, Fp, Fs, P["CS"][2], S["CS"][2])
        esq["arco_cara"], esq["arco_dorso"] = cara, dorso
        esq["long_sardinel"] = ang * (R - ws / 2)

        # ---- pavimento de esquina: entre las dos calzadas y la cara del arco
        bp, bs = rp.calle.ancho_calzada / 2, rs.calle.ancho_calzada / 2
        sgp, sgs = (1 if lp == "D" else -1), (1 if ls == "D" else -1)
        up, us = esq["up"], esq["us"]
        Ep0 = rp.alin.punto(esq["tp"], sgp * bp)
        Es0 = rs.alin.punto(esq["ts"], sgs * bs)
        K = _inter(Ep0, up, Es0, us)
        if K is None:
            esq["error"] = "calles paralelas"
            continue
        pK, _, _ = rp.alin.proyectar(*K)
        sK, _, _ = rs.alin.proyectar(*K)
        zK_p = rp.perfil.cota(pK) - rp.calle.bombeo_pct / 100 * bp
        zK_s = rs.perfil.cota(sK) - rs.calle.bombeo_pct / 100 * bs
        poly = [(K[0], K[1], (zK_p + zK_s) / 2)]
        poly += _bordes(rp, lp, pK, esq["tp"]) + [P["BC"][:3]]
        if "FC" in P:
            poly.append(P["FC"][:3])
        poly += cara[1:-1]
        if "FC" in S:
            poly.append(S["FC"][:3])
        poly += [S["BC"][:3]] + _bordes(rs, ls, esq["ts"], sK)
        esq["poligono_calzada"] = poly
        # badén (cuneta Tipo II) que sigue por la esquina hasta el arco: franja de la principal entre
        # el borde de calzada y bp + ancho; en V (fondo a bp + ancho/2)
        bd = [b for b in rs.badenes if b["principal"] == rp.calle.eje_id and b["lado_principal"][0] == lp]
        X0, npn = esq["X0"], (esq["up_cruce"][1], -esq["up_cruce"][0])
        off = lambda q: ((q[0] - X0[0]) * npn[0] + (q[1] - X0[1]) * npn[1]) * sgp
        tri_bad = []
        if bd:
            W, hb = bd[0]["ancho"], bd[0]["prof"]
            c0 = bp + W / 2
            hundir = lambda pts: [(q[0], q[1], q[2] - max(0.0, hb * (1 - abs(off(q) - c0) / (W / 2)))) for q in pts]
            for lo, hi in ((None, c0), (c0, bp + W)):
                tri_bad += triangular(hundir(recortar(poly, off, lo, hi)))
            poly_resto = recortar(poly, off, bp + W, None)
            tri_calz = triangular(poly_resto) if poly_resto else []
        else:
            tri_calz = triangular(poly)
        # ---- sardinel curvo: cabeza (entre cara y dorso) y cara vertical
        tri_sard, cara_vert = [], []
        for (a, b), (c, d) in zip(zip(cabeza[:-1], cabeza[1:]), zip(dorso[:-1], dorso[1:])):
            tri_sard += [(a, b, d), (a, d, c)]
        for (a, b), (c, d) in zip(zip(cara[:-1], cara[1:]), zip(cabeza[:-1], cabeza[1:])):
            cara_vert.append([a, b, d, c])
        # ---- martillo: del dorso del sardinel a las fachadas
        tri_mart = []
        if "PF" in P and "PF" in S and abs(P["PF"][3] - P["BV"][3]) > 0.05 and abs(S["PF"][3] - S["BV"][3]) > 0.05:
            Q = _inter(P["PF"], up, S["PF"], us)
            if Q is not None and math.dist(Q, C) < 4 * R + 20:
                zq = (P["PF"][2] + S["PF"][2]) / 2
                mart = dorso + [S["PF"][:3], (Q[0], Q[1], zq), P["PF"][:3]]
                tri_mart = triangular(mart)
        esq["caras"] = {"ESQUINA CALZADA": tri_calz, "BADEN": tri_bad, "ESQUINA SARDINEL": tri_sard,
                        "MARTILLO": tri_mart}
        esq["caras_verticales"] = cara_vert
        area = lambda tris: sum(abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) / 2 for a, b, c in tris)
        esq["area_calzada"], esq["area_sardinel"], esq["area_martillo"] = area(tri_calz) + area(tri_bad), \
            area(tri_sard), area(tri_mart)
        esq["area_baden"] = area(tri_bad)
        # ---- subrasante: calzada a −T; sardinel y martillo al fondo de la vereda (−Tv bajo la cabeza)
        baja = lambda tris, d: [tuple((p[0], p[1], p[2] - d) for p in t) for t in tris]
        # la subrasante bajo el badén es la de la calzada (el badén es más grueso, la subbase más delgada)
        sub_bad = []
        if tri_bad:
            plano = lambda pts: [(q[0], q[1], q[2] + max(0.0, hb * (1 - abs(off(q) - c0) / (W / 2)))) for q in pts]
            sub_bad = [tuple(plano(t)) for t in tri_bad]
        esq["sub"] = baja(tri_calz, T) + baja(sub_bad, T) + baja(tri_sard, Tv) + baja(tri_mart, Tv)
        # ---- materiales
        m = {}
        e_b = par["baden_espesor"] / 100.0
        for k, cp in enumerate(capas_calz):
            a_ = esq["area_calzada"]
            if k == 0:
                a_ -= esq["area_baden"]                 # la losa la reemplaza el concreto del badén
            v = a_ * cp.espesor
            if k == 1 and e_b > t1:
                v -= esq["area_baden"] * min(e_b - t1, cp.espesor)
            m[cp.nombre] = m.get(cp.nombre, 0.0) + v
        for cp in capas_ver:
            m[cp.nombre] = m.get(cp.nombre, 0.0) + esq["area_martillo"] * cp.espesor
        rev = ((P["CS"][2] - Fp[2]) + (S["CS"][2] - Fs[2])) / 2
        m["Concreto cuneta y sardinel"] = esq["long_sardinel"] * ws * (rev + t1)
        esq["materiales"] = m
        # ---- corte / relleno contra el terreno
        if terreno.ok:
            esq["vol_corte"], esq["vol_relleno"] = volumen(terreno, esq["sub"])
        esq["ok"] = True


def _subdividir(tri, n):
    a, b, c = (np.array(p, float) for p in tri)
    out = []
    for i in range(n):
        for j in range(n - i):
            p = a + (b - a) * i / n + (c - a) * j / n
            q = a + (b - a) * (i + 1) / n + (c - a) * j / n
            r = a + (b - a) * i / n + (c - a) * (j + 1) / n
            out.append((p, q, r))
            if i + j < n - 1:
                s_ = a + (b - a) * (i + 1) / n + (c - a) * (j + 1) / n
                out.append((q, s_, r))
    return out


def volumen(terreno, tris, n=4):
    """Corte y relleno entre el terreno y los triángulos de subrasante: Σ área·(z_terreno − z) en
    los centroides de n² subtriángulos (separa corte y relleno dentro de cada triángulo)."""
    cent, areas, zs = [], [], []
    for t in tris:
        for p, q, r in _subdividir(t, n):
            cx, cy, cz = (p + q + r) / 3
            areas.append(abs((q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])) / 2)
            cent.append((cx, cy))
            zs.append(cz)
    if not cent:
        return 0.0, 0.0
    cent = np.array(cent)
    zt = np.asarray(terreno.cota(cent[:, 0], cent[:, 1]), float)
    h = zt - np.array(zs)
    a = np.array(areas)
    ok = ~np.isnan(h)
    return float(np.sum(a[ok] * np.clip(h[ok], 0, None))), float(np.sum(a[ok] * np.clip(-h[ok], 0, None)))


def rebaje_rampa(p, rampas, lado, par):
    """Cuánto baja la vereda en la progresiva p por una rampa (rampa 12 % - descanso - rampa 12 %)."""
    d = par["rampa_rebaje"] / 100.0
    lr, ld = par["rampa_largo"] / 100.0, par["rampa_descanso"] / 100.0
    if d <= 0 or lr <= 0:
        return 0.0
    dz = 0.0
    for r in rampas:
        if r["lado"] != lado:
            continue
        u = (p - r["inicio"]) * r["sentido"]
        if u <= 0 or u >= 2 * lr + ld:
            continue
        if u < lr:
            v = d * u / lr
        elif u <= lr + ld:
            v = d
        else:
            v = d * (2 * lr + ld - u) / lr
        dz = max(dz, v)
    return dz


def modelo(res):
    """[(categoría, polígono 3D)] de todas las esquinas, para el 3D y el DXF."""
    out = []
    for e in res.esquinas:
        for cat, tris in e.get("caras", {}).items():
            out += [(cat, list(t)) for t in tris]
        out += [("ESQUINA SARDINEL", q) for q in e.get("caras_verticales", [])]
    return out


def superficie(res, linea="TERMINADO"):
    """Puntos y triángulos (índices) de las esquinas: superficie terminada o subrasante."""
    pts, idx, caras = [], {}, []

    def pid(p):
        key = (round(p[0], 3), round(p[1], 3))
        if key not in idx:
            idx[key] = len(pts)
            pts.append((round(p[0], 4), round(p[1], 4), round(p[2], 4)))
        return idx[key]

    for e in res.esquinas:
        tris = [t for ts in e.get("caras", {}).values() for t in ts] if linea == "TERMINADO" else e.get("sub", [])
        for t in tris:
            f = tuple(pid(p) for p in t)
            if len(set(f)) == 3:
                caras.append(f)
    return pts, caras
