"""Cuneta según RNE CE.040 (triángulo rectángulo con el sardinel como cateto vertical) y badén
(cuneta Tipo II del expediente de Nuñoa) en los cruces."""
from pathlib import Path

import pytest

from corredor.datos import leer_proyecto
from corredor.malla import modelo
from corredor.motor import baden_dz, calcular

RAIZ = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def res():
    return calcular(leer_proyecto(RAIZ / "datos_ejemplo"))


def _sec(res, eje, prog):
    return min(res.calles[eje].secciones, key=lambda s: abs(s.prog - prog))


def test_cuneta_fondo_pegado_al_sardinel(res):
    """El fondo (FC) está en la cara del sardinel, no a la mitad del ancho (era una V simétrica)."""
    s = _sec(res, "EJE-01", 50.0)
    p = {c: (o, z) for c, o, z in s.puntos}
    b = 3.60
    assert p["FCD"][0] == pytest.approx(b + 0.40)           # mismo offset que la cara del sardinel
    assert p["CSD"][0] == pytest.approx(p["FCD"][0])
    assert p["FCD"][1] == pytest.approx(p["BCD"][1] - 0.10, abs=1e-9)
    assert "PSD" not in p                                   # ya no hay "pie de sardinel" aparte
    # la cara del sardinel mide altura + profundidad de cuneta
    assert p["CSD"][1] - p["FCD"][1] == pytest.approx(0.15 + 0.10)


def test_badenes_en_linea_con_la_cuneta(res):
    """EJE-02 cruza EJE-01 en 0+100: un badén a cada lado, centrado a 3.60 + 0.40 m del eje de EJE-01."""
    bs = sorted(res.calles["EJE-02"].badenes, key=lambda b: b["centro"])
    assert [round(b["centro"], 2) for b in bs] == [96.0, 104.0]
    assert all(b["principal"] == "EJE-01" for b in bs)
    assert not res.calles["EJE-01"].badenes                 # la principal sigue de largo


def test_baden_baja_la_superficie_en_v(res):
    rc = res.calles["EJE-02"]
    centro = _sec(res, "EJE-02", 104.0)
    borde = _sec(res, "EJE-02", 104.4)
    assert centro.baden == pytest.approx(0.07)
    assert borde.baden == pytest.approx(0.0)
    eje = lambda s, l: next(z for c, o, z in s.lineas[l] if c == "EJE")
    assert eje(centro, "TERMINADO") == pytest.approx(centro.rasante - 0.07)
    # la subrasante no cambia: el badén es más grueso (0.22) y su subbase más delgada
    assert eje(centro, "SUBRASANTE") == pytest.approx(centro.rasante - 0.66)
    assert baden_dz(102.0, rc.badenes) == 0.0


def test_baden_en_modelo_3d_y_materiales(res):
    rc = res.calles["EJE-02"]
    cats = {c for c, _ in modelo(rc, res.proyecto)}
    assert "BADEN" in cats
    b = rc.badenes[0]
    # de arco a arco de las esquinas: 0.80 × (7.20 + 2·(0.40 + 3.00)) = 0.80 × 14.0;
    # concreto = largo × (ancho × 0.22 − ancho × 0.07 / 2)
    assert b["area"] == pytest.approx(0.80 * 14.0)
    assert rc.materiales["Concreto badén (cuneta Tipo II)"] == pytest.approx(2 * 14.0 * (0.80 * 0.22 - 0.80 * 0.07 / 2))


def test_sin_cuneta_no_hay_baden(tmp_path):
    """Si la principal no tiene cuneta en ese tramo, el agua no corre por ahí: no se pone badén."""
    import shutil
    d = tmp_path / "p"
    shutil.copytree(RAIZ / "datos_ejemplo", d)
    (d / "cunetas_por_tramo.csv").write_text(
        "eje_id,lado,prog_ini,prog_fin,ancho_cm,profundidad_cm,nota\nEJE-01,AMBOS,0,250,0,0,sin cuneta\n",
        encoding="utf-8")
    r = calcular(leer_proyecto(d))
    assert not r.calles["EJE-02"].badenes


def test_baden_desactivado(tmp_path):
    import shutil
    d = tmp_path / "p"
    shutil.copytree(RAIZ / "datos_ejemplo", d)
    proy = leer_proyecto(d)
    proy.parametros["baden_ancho"] = 0
    assert not calcular(proy).calles["EJE-02"].badenes
