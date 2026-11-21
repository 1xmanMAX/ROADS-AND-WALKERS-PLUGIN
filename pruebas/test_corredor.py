"""Pruebas con los datos de ejemplo. Cada valor esperado está calculado a mano
(ver docs/VERIFICACION.md).   Ejecutar:  python -m pytest pruebas -q
"""
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from corredor.datos import leer_proyecto, leer_terreno, validar_proyecto
from corredor.exportar import altura_instrumento, exportar_dxf, exportar_landxml, exportar_todo
from corredor.geometria import Alineamiento, Perfil, fmt_prog
from corredor.modelo import PuntoTerreno
from corredor.motor import calcular
from corredor.replanteo import puntos_capas
from corredor.seccion import calcular_tierras
from corredor.terreno import Terreno

RAIZ = Path(__file__).resolve().parent.parent
EJEMPLO = RAIZ / "datos_ejemplo"


@pytest.fixture(scope="module")
def proy():
    return leer_proyecto(EJEMPLO)


@pytest.fixture(scope="module")
def res(proy):
    return calcular(proy)


def seccion(res, eje, prog):
    return next(s for s in res.calles[eje].secciones if abs(s.prog - prog) < 1e-6)


# ------------------------------------------------------------------ geometría
def test_formato_progresiva():
    assert fmt_prog(0) == "0+000.00"
    assert fmt_prog(124.35) == "0+124.35"
    assert fmt_prog(1250.5) == "1+250.50"


def test_punto_borde_calzada_0050():
    # E = 390100 + 50 sen80 + 3.60 cos80 ; N = 8250300 + 50 cos80 − 3.60 sen80
    al = Alineamiento([(390100.0, 8250300.0), (390346.202, 8250343.412)])
    e, n = al.punto(50.0, 3.60)
    assert e == pytest.approx(390149.866, abs=0.002)
    assert n == pytest.approx(8250305.137, abs=0.002)
    p, o, fuera = al.proyectar(e, n)
    assert p == pytest.approx(50.0, abs=1e-3) and o == pytest.approx(3.60, abs=1e-3) and fuera < 1e-6


def test_rasante():
    pf = Perfil([(0, 3820.5, 1.5, 120), (120, 3822.3, -0.8, 250)])
    assert pf.cota(50) == pytest.approx(3821.250, abs=1e-6)      # 3820.5 + 0.015·50
    assert pf.cota(120) == pytest.approx(3822.300, abs=1e-6)
    assert pf.cota(200) == pytest.approx(3821.660, abs=1e-6)     # 3822.3 − 0.008·80
    assert pf.quiebres() == [120]


def test_perfil_detecta_escalon_y_pendiente():
    pf = Perfil([(0, 100.0, 9.0, 50), (50, 104.0, 1.0, 100)])   # 100 + 0.09·50 = 104.5 ≠ 104.0
    av = pf.validar("X", pmax=8.0, pmin=0.5)
    textos = " ".join(m for _, _, m in av)
    assert "supera la máxima" in textos
    assert "escalón" in textos


# ------------------------------------------------------------------ sección
def test_seccion_0050_puntos(res):
    s = seccion(res, "EJE-01", 50.0)
    pts = {c: (o, z) for c, o, z in s.puntos}
    assert pts["EJE"][1] == pytest.approx(3821.250, abs=5e-4)
    assert pts["BCD"][1] == pytest.approx(3821.178, abs=5e-4)    # 3821.250 − 0.02·3.60
    assert pts["FCD"][1] == pytest.approx(3821.078, abs=5e-4)    # BC − 0.10
    assert pts["CSD"][1] == pytest.approx(3821.328, abs=5e-4)    # BC + 0.15
    assert pts["BVD"] == pytest.approx((4.15, 3821.328), abs=5e-4)
    # lado izquierdo: muro a 5.30 m -> vereda 1.15 m -> PF = 3821.328 + 0.02·1.15
    assert s.vereda_ancho["I"] == pytest.approx(1.15, abs=0.002)
    assert pts["PFI"][1] == pytest.approx(3821.351, abs=5e-4)


def test_capas_hacia_abajo(res):
    s = seccion(res, "EJE-01", 50.0)
    eje = lambda linea: next(z for c, o, z in s.lineas[linea] if c == "EJE")
    assert eje("C2_TOPE") == pytest.approx(3821.090, abs=5e-4)   # − 0.16
    assert eje("C3_TOPE") == pytest.approx(3820.940, abs=5e-4)   # − 0.15
    assert eje("C4_TOPE") == pytest.approx(3820.790, abs=5e-4)   # − 0.15
    assert eje("SUBRASANTE") == pytest.approx(3820.590, abs=5e-4)  # − 0.20


def test_lectura_mira(proy, res):
    ai = altura_instrumento(proy, "BM-01", 1.425)
    bm = next(b for b in proy.bms if b.id == "BM-01").cota
    assert ai == pytest.approx(bm + 1.425)
    filas = puntos_capas(res.calles["EJE-01"], proy, ai)
    f = next(f for f in filas if f["prefijo"] == "C1" and abs(f["prog"] - 50) < 1e-6 and f["codigo"] == "EJE")
    assert f["lectura"] == pytest.approx(ai - 3821.250, abs=5e-4)


# ------------------------------------------------------------------ fachadas y puertas
def test_veredas_recortadas(res):
    av = [a for a in res.avisos if a.categoria == "VEREDA"]
    textos = " ".join(a.mensaje for a in av)
    assert "MU a 1.15" in textos and "0.90" in textos and "1.30" in textos


def test_puertas(res):
    """Umbral − vereda proyectada en la fachada, identificadas por calle y progresiva."""
    d = {(u["eje"], round(u["prog"])): u["diferencia"] for u in res.umbrales}
    assert d[("EJE-01", 85)] == pytest.approx(-0.080, abs=0.002)     # enterrada
    assert d[("EJE-02", 140)] == pytest.approx(-0.030, abs=0.002)    # enterrada
    assert d[("EJE-01", 35)] == pytest.approx(0.060, abs=0.002)
    assert d[("EJE-02", 50)] == pytest.approx(0.120, abs=0.002)
    assert d[("EJE-01", 170)] == pytest.approx(0.025, abs=0.003)     # cochera (promedio de COI y COF)
    assert d[("EJE-02", 122)] == pytest.approx(-0.045, abs=0.003)    # cochera enterrada
    enterradas = [x for x in res.interferencias if x["tipo"] in ("PUERTA", "COCHERA") and x["nivel"] == "ERROR"]
    assert len(enterradas) == 3


def test_levantamiento_codificado(proy):
    p = proy
    assert len(p.bms) == 3 and [b.id for b in p.bms] == ["BM-01", "BM-02", "BM-03"]
    assert sum(u.tipo == "PUERTA" for u in p.umbrales) == 5
    coch = [u for u in p.umbrales if u.tipo == "COCHERA"]
    assert len(coch) == 2 and all(u.ancho == pytest.approx(3.0, abs=0.01) for u in coch)
    tipos = {l.tipo for l in p.fachadas}
    assert {"CA", "MU", "LP"} <= tipos
    assert {e.tipo_codigo for e in p.elementos} >= {"BZ", "PO", "AR", "GR", "CAG", "CLZ", "SEN"}
    assert p.avisos_levantamiento == []


def test_codigos():
    from corredor.codigos import Catalogo, separar_codigo
    assert separar_codigo("ca1 casa verde") == ("CA1", "CA", "1", "casa verde")
    cat = Catalogo()
    c, tok, num, nota = cat.interpretar("BM3 hito")
    assert c.codigo == "BM" and num == "3"
    assert cat.interpretar("COI")[0].codigo == "COI"
    assert cat.interpretar("XYZ")[0] is None


def test_interferencias(res):
    by_id = {x["id"].split("-")[0] + "@" + x["eje"] + f"{x['prog']:.0f}": x for x in res.interferencias if x["prog"]}
    poste_cuneta = by_id["PO@EJE-01150"]
    assert poste_cuneta["zona"] == "CUNETA" and poste_cuneta["nivel"] == "ERROR"
    arbol = by_id["AR@EJE-01230"]
    assert arbol["zona"] == "VEREDA" and arbol["nivel"] == "ERROR"           # paso libre 0.85 < 0.90
    bz = by_id["BZ@EJE-0160"]
    assert bz["zona"] == "CALZADA" and bz["cota_diseno"] == pytest.approx(3820.5 + 0.015 * 60, abs=0.002)
    assert "bajar la tapa" in bz["accion"]
    assert "subir la tapa" in by_id["BZ@EJE-02175"]["accion"]               # buzón en la hondonada


def test_bm_ubicados(res):
    t = {b["bm"].id: b for b in res.bm_ubicacion}
    assert t["BM-01"]["eje"] == "EJE-01" and t["BM-01"]["prog"] == pytest.approx(5.0, abs=0.01)
    assert t["BM-03"]["eje"] == "EJE-02" and t["BM-03"]["offset"] < 0


def test_balance(res, proy):
    rc = res.calles["EJE-02"]
    b = rc.balance
    assert b["eliminacion"] == pytest.approx(rc.vol_corte * (1 + proy.p("esponjamiento") / 100))
    assert b["prestamo"] == pytest.approx(rc.vol_relleno * (1 + proy.p("contraccion_relleno") / 100))
    assert rc.curva_masa[-1][1] == pytest.approx(rc.vol_corte - rc.vol_relleno * (1 + proy.p("contraccion_relleno") / 100))


# ------------------------------------------------------------------ cruce
def test_cruce(res):
    assert len(res.cruces) == 1
    x = res.cruces[0]
    assert x["p_principal"] == pytest.approx(130.0, abs=0.01)
    assert x["p_secundaria"] == pytest.approx(100.0, abs=0.01)
    assert x["z_principal"] == pytest.approx(x["z_secundaria"], abs=0.001)


# ------------------------------------------------------------------ metrados
def test_volumen_losa(res):
    # losa: 7.20 m × 0.16 m = 1.152 m² por metro
    assert res.calles["EJE-01"].materiales["Losa de concreto f'c=210"] == pytest.approx(250.0 * 1.152, rel=1e-4)
    # EJE-02 sin los 8.30 m dentro de la calzada del EJE-01 (3.60 + 0.40 + 0.15 a cada lado)
    assert res.calles["EJE-02"].materiales["Losa de concreto f'c=210"] == pytest.approx(191.70 * 1.152, rel=1e-4)


def test_area_con_terreno_plano(res):
    """Con un terreno plano la integral se puede hacer a mano: área = Σ trapecios bajo la subrasante."""
    s = seccion(res, "EJE-01", 50.0)
    zt = 3822.000
    pts = []
    for de in (-30, 0, 30):
        for dn in (-30, 0, 30):
            pts.append(PuntoTerreno("x", s.e + de, s.n + dn, zt, ""))
    t = Terreno(pts, 100)
    corte, relleno = calcular_tierras(s, t, 0.05)
    linea = s.lineas["SUBRASANTE"]
    esperado = sum((ob - oa) * ((zt - za) + (zt - zb)) / 2 for (_, oa, za), (_, ob, zb) in zip(linea[:-1], linea[1:]))
    assert corte == pytest.approx(esperado, abs=1e-6)
    assert relleno == pytest.approx(0.0, abs=1e-9)


def test_volumen_area_media(res):
    rc = res.calles["EJE-01"]
    t = rc.tramos_volumen[0]
    assert t["vol_corte"] == pytest.approx((t["ac1"] + t["ac2"]) / 2 * t["distancia"])
    assert rc.vol_corte == pytest.approx(sum(x["vol_corte"] for x in rc.tramos_volumen))


def test_hay_relleno_en_hondonada(res):
    s = seccion(res, "EJE-02", 180.0)
    assert s.area_relleno > 1.0


def test_volumen_contra_superficies(res):
    """Volumen por área media vs. volumen entre superficies (como hace Civil 3D), ±3 %."""
    import numpy as np
    from corredor.malla import superficie
    from matplotlib.tri import LinearTriInterpolator, Triangulation
    for k, rc in res.calles.items():
        pts, caras = superficie([rc], "SUBRASANTE")
        P = np.array(pts)
        tri = Triangulation(P[:, 0] - P[:, 0].min(), P[:, 1] - P[:, 1].min(), np.array(caras))
        f = LinearTriInterpolator(tri, P[:, 2])
        paso = 0.25
        xs = np.arange(0, np.ptp(P[:, 0]), paso)
        ys = np.arange(0, np.ptp(P[:, 1]), paso)
        X, Y = np.meshgrid(xs, ys)
        zs = np.ma.filled(f(X, Y), np.nan)
        zt = res.terreno.cota(X.ravel() + P[:, 0].min(), Y.ravel() + P[:, 1].min()).reshape(X.shape)
        d = zt - zs
        ok = ~np.isnan(d)
        corte = np.sum(np.where(d[ok] > 0, d[ok], 0)) * paso * paso
        print(k, "superficies", round(corte, 2), "area media", round(rc.vol_corte, 2))
        assert corte == pytest.approx(rc.vol_corte, rel=0.03), k


# ------------------------------------------------------------------ datos y exportación
def test_csv_punto_y_coma(tmp_path):
    f = tmp_path / "t.csv"
    f.write_text("punto;este;norte;cota;codigo\n1;390100,5;8250300,25;3820,123;TN\n", encoding="cp1252")
    p = leer_terreno(f)[0]
    assert (p.este, p.norte, p.cota) == (390100.5, 8250300.25, 3820.123)


def test_validacion(proy):
    assert validar_proyecto(proy) == []


def test_exportaciones(res, tmp_path):
    arch = exportar_todo(res, tmp_path, 3822.0)
    assert all(Path(a).exists() for a in arch)
    raiz = ET.parse(tmp_path / "corredor_civil3d.xml").getroot()
    ns = {"l": "http://www.landxml.org/schema/LandXML-1.2"}
    assert len(raiz.findall(".//l:Alignment", ns)) == 2
    sup = raiz.findall(".//l:Surface", ns)
    assert len(sup) == 1 + 2 * 6
    for s in sup:   # cada cara usa ids existentes
        n = len(s.findall(".//l:P", ns))
        for f in s.findall(".//l:F", ns):
            assert all(1 <= int(i) <= n for i in f.text.split())
    import ezdxf
    doc = ezdxf.readfile(tmp_path / "corredor_civil3d.dxf")
    assert len(doc.audit().errors) == 0
    lineas = (tmp_path / "csv" / "civil3d_puntos_PNEZD.csv").read_text(encoding="utf-8").splitlines()
    assert lineas[0].split(",")[0] == "1"       # sin BOM ni cabecera
    n_, e_ = map(float, lineas[0].split(",")[1:3])
    assert n_ > 8_000_000 and 300_000 < e_ < 500_000   # orden N, E
