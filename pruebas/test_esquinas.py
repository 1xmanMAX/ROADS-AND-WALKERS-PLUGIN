"""Esquinas curvas (plano de veredas, rampas y martillos del expediente de Nuñoa): sardinel en arco,
pavimento de esquina, martillo, rampas y badén de arco a arco."""
import math
from pathlib import Path

import pytest

from corredor.datos import leer_proyecto
from corredor.esquinas import modelo, rebaje_rampa, recortar, triangular
from corredor.motor import calcular

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def res():
    return calcular(leer_proyecto(RAIZ / "datos_ejemplo"))


def test_cuatro_esquinas_en_un_cruce_en_x(res):
    assert len(res.esquinas) == 4
    assert all(e["ok"] for e in res.esquinas)
    assert {(e["lado_p"], e["lado_s"]) for e in res.esquinas} == {("I", "I"), ("I", "D"), ("D", "I"), ("D", "D")}


def test_tangencias_y_arco(res):
    """EJE-01 cruza EJE-02 a 90° en 0+130 / 0+100. Cara del sardinel de cada calle a 3.60 + 0.40 m
    del eje; R = 3.00 -> tangencias a 4.00 + 3.00 = 7.00 m del cruce."""
    for e in res.esquinas:
        assert abs(e["tp"] - 130.0) == pytest.approx(7.0, abs=1e-3)
        assert abs(e["ts"] - 100.0) == pytest.approx(7.0, abs=1e-3)
        cx, cy = e["C"]
        assert all(math.hypot(p[0] - cx, p[1] - cy) == pytest.approx(3.0, abs=1e-6) for p in e["arco_cara"][1:-1])


def test_pavimento_de_esquina(res):
    """Entre las dos calzadas y el arco: (0.40 + 3)² − π·3²/4 = 4.49 m² por esquina."""
    for e in res.esquinas:
        assert e["area_calzada"] == pytest.approx((0.40 + 3.0) ** 2 - math.pi * 9 / 4, rel=0.02)


def test_martillo_y_sardinel(res):
    e = res.esquinas[0]
    assert e["area_martillo"] > 3.0
    # sardinel curvo: cuarto de circunferencia al eje del sardinel (R − 0.15/2)
    assert e["long_sardinel"] == pytest.approx(math.pi / 2 * (3.0 - 0.075), rel=1e-3)
    assert e["materiales"]["Concreto cuneta y sardinel"] > 0


def test_calles_sin_sardinel_recto_entre_tangencias(res):
    rc = res.calles["EJE-01"]
    s = min(rc.secciones, key=lambda s: abs(s.prog - 125.0))
    assert s.lateral == {"I": False, "D": False}
    s = min(rc.secciones, key=lambda s: abs(s.prog - 137.0))
    assert s.lateral == {"I": True, "D": True}


def test_rampas(res):
    """Rampa 12 % de 1.00 m, descanso 1.00 m, rampa 1.00 m, a continuación de cada tangencia."""
    rc = res.calles["EJE-01"]
    assert len(rc.rampas) == 4
    par = res.proyecto.parametros
    r = [x for x in rc.rampas if x["lado"] == "D" and x["sentido"] > 0][0]
    assert rebaje_rampa(r["inicio"] + 0.5, rc.rampas, "D", par) == pytest.approx(0.06)
    assert rebaje_rampa(r["inicio"] + 1.5, rc.rampas, "D", par) == pytest.approx(0.12)
    assert rebaje_rampa(r["inicio"] + 3.5, rc.rampas, "D", par) == 0.0
    s = min(rc.secciones, key=lambda s: abs(s.prog - (r["inicio"] + 1.5)))
    p = {c: z for c, o, z in s.puntos}
    assert p["CSD"] - p["BCD"] == pytest.approx(0.15 - 0.12)       # la vereda baja 12 cm
    assert "RAMPA" in {c for c, _ in __import__("corredor.malla", fromlist=["modelo"]).modelo(rc, res.proyecto)}


def test_baden_de_arco_a_arco(res):
    """El badén va de arco a arco: 7.20 + 2·(0.40 + 3.00) = 14.0 m; también cruza las esquinas."""
    for b in res.calles["EJE-02"].badenes:
        assert b["largo"] == pytest.approx(14.0, abs=1e-3)
    assert sum(e["area_baden"] for e in res.esquinas) > 0
    assert any(c == "BADEN" for c, _ in modelo(res))


def test_sin_esquinas_con_radio_cero(tmp_path):
    import shutil
    d = tmp_path / "p"
    shutil.copytree(RAIZ / "datos_ejemplo", d)
    proy = leer_proyecto(d)
    proy.parametros["radio_esquina"] = 0
    r = calcular(proy)
    assert not r.esquinas and not r.calles["EJE-01"].rampas


def test_cruce_oblicuo_y_eje_quebrado():
    """Cruce a 60° (E03) y Nuñoa (ejes con vértices junto al cruce): todas las esquinas se arman y
    ningún triángulo de una esquina se monta sobre otro."""
    import sys
    sys.path.insert(0, str(RAIZ / "herramientas"))
    import generar_escenarios
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        generar_escenarios.main(d)
        r = calcular(leer_proyecto(Path(d) / "E03_cruce_oblicuo_T"))
    assert r.esquinas and all(e["ok"] for e in r.esquinas)

    def dentro(p, t):
        (x1, y1, _), (x2, y2, _), (x3, y3, _) = t
        d = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        a = ((y2 - y3) * (p[0] - x3) + (x3 - x2) * (p[1] - y3)) / d
        b = ((y3 - y1) * (p[0] - x3) + (x1 - x3) * (p[1] - y3)) / d
        return a > 1e-6 and b > 1e-6 and 1 - a - b > 1e-6
    tris = [t for e in r.esquinas for ts in e["caras"].values() for t in ts]
    for i, t in enumerate(tris):
        c = (sum(p[0] for p in t) / 3, sum(p[1] for p in t) / 3)
        assert not any(dentro(c, u) for j, u in enumerate(tris) if j != i)


def test_triangular_y_recortar():
    cuadrado = [(0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0)]
    assert sum(abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) / 2
               for a, b, c in triangular(cuadrado)) == pytest.approx(4.0)
    # forma en L (no convexa)
    L = [(0, 0, 0), (3, 0, 0), (3, 1, 0), (1, 1, 0), (1, 3, 0), (0, 3, 0)]
    assert sum(abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])) / 2
               for a, b, c in triangular(L)) == pytest.approx(5.0)
    franja = recortar(cuadrado, lambda q: q[0], 0.5, 1.5)
    assert min(q[0] for q in franja) == pytest.approx(0.5) and max(q[0] for q in franja) == pytest.approx(1.5)
