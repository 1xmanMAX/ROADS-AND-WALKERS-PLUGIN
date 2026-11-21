"""Codificación de campo (docs/CODIFICACION_CAMPO.md)."""
import sys
from pathlib import Path

import pytest

from corredor.codigos import CODIGOS, PuntoCodificado, es_terreno, interpretar, lineas
from corredor.datos import leer_proyecto
from corredor.motor import calcular

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "herramientas"))
import generar_escenarios  # noqa: E402


def test_interpretar_descripciones():
    assert interpretar("FAC3 C / esquina") == ("FAC", "FAC3", [], {"C"}, "esquina")
    assert interpretar("pos 0,25 / alumbrado") == ("POS", "POS", [0.25], set(), "alumbrado")
    assert interpretar("PTA 0.90")[2] == [0.90]
    assert interpretar("BM / BM-01")[4] == "BM-01"
    assert interpretar("XYZ")[0] == ""                       # no está en el manual
    assert interpretar("") == ("", "", [], set(), "")


def test_alias():
    alias = {"PF": "FAC", "PT": "POS"}
    assert interpretar("PF2", alias)[:2] == ("FAC", "FAC2")
    assert interpretar("PT 0.30", alias)[:3] == ("POS", "POS", [0.30])


def test_que_va_al_terreno():
    assert es_terreno("TN") and es_terreno("FAC1") and es_terreno("BZD")
    assert not es_terreno("BM / BM-01") and not es_terreno("PTA 0.9") and not es_terreno("SDX1")
    assert es_terreno("BC")                                   # código desconocido: terreno, como antes


def test_lineas_con_comandos():
    def p(i, d):
        c, lin, par, cmd, nota = interpretar(d)
        return PuntoCodificado(str(i), float(i), 0.0, 0.0, d, c, lin, par, cmd, nota)
    pts = [p(1, "FAC1"), p(2, "FAC1"), p(3, "FAC2"), p(4, "FAC1 C"), p(5, "FAC2"), p(6, "FAC1 I"), p(7, "FAC1")]
    ls = lineas(pts)
    por = {(l["linea"], tuple(x.numero for x in l["puntos"])): l["cerrada"] for l in ls}
    assert por[("FAC1", ("1", "2", "4"))] is True
    assert ("FAC2", ("3", "5")) in por
    assert ("FAC1", ("6", "7")) in por


def test_tabla_completa():
    for k, (nom, grupo, geo, ter, como) in CODIGOS.items():
        assert geo in ("punto", "linea") and como and nom


@pytest.fixture(scope="module")
def e09(tmp_path_factory):
    d = tmp_path_factory.mktemp("cod")
    generar_escenarios.main(d)
    return calcular(leer_proyecto(d / "E09_codificado"))


def test_e09_arma_fachadas_puertas_y_bms(e09):
    p = e09.proyecto
    assert len(p.fachadas) >= 40 and {f.eje_id for f in p.fachadas} == {"EJE-01", "EJE-02"}
    assert {(u.tipo, u.lado) for u in p.umbrales} >= {("PUERTA", "DER"), ("COCHERA", "DER")}
    assert {b.id for b in p.bms} == {"BM-01", "BM-02"}
    # los BMs y los umbrales no entran al TIN
    assert len(e09.terreno.puntos) < len(p.terreno)


def test_e09_controles(e09):
    msg = [(a.nivel, a.categoria, a.mensaje) for a in e09.avisos]
    assert any(n == "ERROR" and c == "PUERTA" and "enterrada" in m for n, c, m in msg)
    assert any(n == "ERROR" and c == "OBSTACULO" and "calzada" in m for n, c, m in msg)
    assert sum(1 for n, c, m in msg if c == "TAPA" and "bajar la tapa 30 cm" in m) == 3
    emp = [m for n, c, m in msg if c == "EMPALME"]
    assert len(emp) == 3 and all("-4 cm" in m for m in emp)       # solo el extremo que no calza
    filas = e09.puntos_codificados
    assert {f["codigo"] for f in filas} >= {"POS", "ARB", "BZD", "EMP"}
