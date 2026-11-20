"""Superficies 3D del corredor a partir de las secciones.

Entre dos secciones seguidas se unen los puntos del mismo código con
cuadriláteros (como las "feature lines" y la superficie de un corredor de
Civil 3D). Se usan para el modelo 3D, el DXF (3DFACE) y el LandXML (TIN).
"""
from .motor import _dentro

CATEGORIA_PAR = {
    frozenset(("EJE", "BC")): "CALZADA",
    frozenset(("BC", "FC")): "CUNETA", frozenset(("FC", "PS")): "CUNETA",
    frozenset(("PS", "CS")): "SARDINEL", frozenset(("CS", "BV")): "SARDINEL",
    frozenset(("BV", "PF")): "VEREDA",
}


def _base(c):
    return c if c == "EJE" else c[:-1]


def pares(rc):
    """Pares de secciones consecutivas que forman superficie."""
    val = [s for s in rc.secciones if not s.omitida]
    for s1, s2 in zip(val[:-1], val[1:]):
        if not _dentro((s1.prog + s2.prog) / 2, rc.zonas_omitidas):
            yield s1, s2


def _ajustar(lista, nudge):
    """Quita puntos repetidos y, si nudge, separa 5 mm los que tienen el mismo offset
    (caras verticales del sardinel), porque una superficie TIN no admite paredes verticales."""
    out = []
    for c, o, z in lista:
        if out and abs(o - out[-1][1]) < 1e-6 and abs(z - out[-1][2]) < 1e-6:
            continue
        if nudge and out and o <= out[-1][1] + 1e-6:
            o = out[-1][1] + 0.005
        out.append((c, o, z))
    return out


def quads(rc, linea, nudge=False):
    """[(cod_a, cod_b, [(e,n,z) x4])] para la línea indicada."""
    res = []
    for s1, s2 in pares(rc):
        l1 = _ajustar(s1.lineas.get(linea, []), nudge)
        l2 = _ajustar(s2.lineas.get(linea, []), nudge)
        idx2 = {c: i for i, (c, _, _) in enumerate(l2)}
        for i in range(len(l1) - 1):
            ca, cb = l1[i][0], l1[i + 1][0]
            if ca in idx2 and cb in idx2 and idx2[cb] == idx2[ca] + 1:
                a1, b1 = l1[i], l1[i + 1]
                a2, b2 = l2[idx2[ca]], l2[idx2[cb]]
                q = [(*s1.xy(a1[1]), a1[2]), (*s1.xy(b1[1]), b1[2]),
                     (*s2.xy(b2[1]), b2[2]), (*s2.xy(a2[1]), a2[2])]
                res.append((ca, cb, q))
    return res


def bordes(rc, tope, fondo):
    """Caras laterales (espesor) de una capa en sus dos extremos."""
    res = []
    for s1, s2 in pares(rc):
        t1, f1 = s1.lineas.get(tope), s1.lineas.get(fondo)
        t2, f2 = s2.lineas.get(tope), s2.lineas.get(fondo)
        if not (t1 and f1 and t2 and f2):
            continue
        for k in (0, -1):
            if t1[k][0] != t2[k][0]:
                continue
            q = [(*s1.xy(t1[k][1]), t1[k][2]), (*s1.xy(f1[k][1]), f1[k][2]),
                 (*s2.xy(f2[k][1]), f2[k][2]), (*s2.xy(t2[k][1]), t2[k][2])]
            res.append(q)
    return res


def modelo(rc, proy):
    """Lista de (categoría, cuadrilátero) para ver en 3D o exportar a DXF."""
    out = []
    for ca, cb, q in quads(rc, "TERMINADO"):
        out.append((CATEGORIA_PAR.get(frozenset((_base(ca), _base(cb))), "CALZADA"), q))
    for k, cp in enumerate(proy.capas_de("calzada"), start=1):
        cat = f"CAPA C{k} {cp.nombre}"
        out += [(cat, q) for _, _, q in quads(rc, f"C{k}_FONDO")]
        out += [(cat, q) for q in bordes(rc, f"C{k}_TOPE", f"C{k}_FONDO")]
    for k, cp in enumerate(proy.capas_de("vereda"), start=1):
        cat = f"CAPA V{k} {cp.nombre}"
        for l in ("I", "D"):
            out += [(cat, q) for _, _, q in quads(rc, f"V{k}_FONDO_{l}")]
            out += [(cat, q) for q in bordes(rc, f"V{k}_TOPE_{l}", f"V{k}_FONDO_{l}")]
    return out


def fachadas_3d(proy, terreno, res, altura=1.5):
    """Muros referenciales de fachada (para ver en 3D)."""
    out = []
    for l in proy.fachadas:
        rc = res.calles.get(l.eje_id)
        for (e1, n1, t1), (e2, n2, t2) in zip(l.puntos[:-1], l.puntos[1:]):
            z = []
            for e, n in ((e1, n1), (e2, n2)):
                zt = terreno.cota(e, n) if terreno.ok else float("nan")
                if zt != zt and rc is not None:
                    p, _, _ = rc.alin.proyectar(e, n)
                    zt = rc.perfil.cota(p)
                z.append(zt)
            out.append(("FACHADA", [(e1, n1, z[0]), (e2, n2, z[1]), (e2, n2, z[1] + altura), (e1, n1, z[0] + altura)]))
    return out


def superficie(rcs, linea):
    """Superficie TIN (puntos y triángulos) uniendo las calles dadas."""
    pts, idx, caras = [], {}, []

    def pid(p):
        key = (round(p[0], 3), round(p[1], 3))
        if key not in idx:
            idx[key] = len(pts)
            pts.append((round(p[0], 4), round(p[1], 4), round(p[2], 4)))
        return idx[key]

    for rc in rcs:
        for _, _, q in quads(rc, linea, nudge=True):
            a, b, c, d = (pid(p) for p in q)
            for tri in ((a, b, c), (a, c, d)):
                if len(set(tri)) == 3:
                    caras.append(tri)
    return pts, caras


def lineas_caracteristicas(rc, linea="TERMINADO"):
    """Polilíneas 3D por código (feature lines): {codigo: [[(e,n,z), ...], ...]}."""
    out = {}
    abiertas = {}
    previo = None
    for s in [x for x in rc.secciones if not x.omitida]:
        corte = previo is not None and _dentro((previo.prog + s.prog) / 2, rc.zonas_omitidas)
        presentes = set()
        for c, o, z in s.lineas.get(linea, []):
            presentes.add(c)
            if corte or c not in abiertas:
                abiertas[c] = []
                out.setdefault(c, []).append(abiertas[c])
            abiertas[c].append((*s.xy(o), z))
        for c in list(abiertas):
            if c not in presentes:
                del abiertas[c]
        previo = s
    for c in out:
        out[c] = [l for l in out[c] if len(l) >= 2]
    return out
