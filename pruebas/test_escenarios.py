"""Pruebas con los levantamientos de herramientas/generar_escenarios.py y con casos límite.

Los volúmenes de referencia (pruebas/referencias_civil3d.json) los calculó Civil 3D 2025 con su
propio motor (superficie de volumen TN − subrasante), corriendo
    python herramientas/verificar_civil3d.py --todos <carpeta_con_escenarios> <salida>
Así estas pruebas comparan la app contra Civil 3D aunque Civil 3D no esté instalado.
"""
import json
import math
import sys
from pathlib import Path

import pytest

from corredor.datos import leer_csv, leer_proyecto
from corredor.geometria import Alineamiento, Perfil
from corredor.modelo import PuntoTerreno
from corredor.motor import calcular
from corredor.terreno import Terreno

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "herramientas"))
import generar_escenarios  # noqa: E402

REF = json.loads((RAIZ / "pruebas" / "referencias_civil3d.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def carpeta(tmp_path_factory):
    d = tmp_path_factory.mktemp("escenarios")
    generar_escenarios.main(d)
    d_ej = RAIZ / "datos_ejemplo"
    return d, d_ej


@pytest.fixture(scope="module")
def resultados(carpeta):
    d, d_ej = carpeta
    out = {"datos_ejemplo": calcular(leer_proyecto(d_ej))}
    for nombre in generar_escenarios.ESCENARIOS:
        out[nombre] = calcular(leer_proyecto(d / nombre))
    return out


# ------------------------------------------------------------------ contra Civil 3D
CASOS = [(esc, eje) for esc, ejes in REF.items() for eje in ejes]


@pytest.mark.parametrize("esc,eje", CASOS)
def test_volumen_igual_a_civil3d(resultados, esc, eje):
    """Corte y relleno de la app frente a la superficie de volumen de Civil 3D: ±1 % o ±0.5 m³."""
    res = resultados[esc]
    ref = REF[esc][eje]
    if eje == "ESQUINAS":          # esquinas curvas: triángulos de la app vs superficie de volumen de Civil 3D
        vols = (res.esquinas_total("vol_corte"), res.esquinas_total("vol_relleno"))
    else:
        vols = (res.calles[eje].vol_corte, res.calles[eje].vol_relleno)
    for app, c3d in zip(vols, (ref["corte"], ref["relleno"])):
        assert abs(app - c3d) <= max(0.5, 0.01 * c3d), (esc, eje, app, c3d)


# ------------------------------------------------------------------ casos que fallaban
def test_perfil_cubre_todo_el_eje():
    """El LandXML llevaba el último PVI en 250.000 con un eje de 250.00005 m: Civil 3D no daba cota."""
    perf = Perfil([(0, 100, 1.0, 120), (120, 101.2, -0.5, 250)])
    pv = perf.pvis(0.0, 250.00005)
    assert pv[0] == (0.0, 100.0)
    assert pv[-1][0] == 250.00005 and abs(pv[-1][1] - perf.cota(250.00005)) < 1e-9
    assert len(pv) == 3
    # perfil más largo que el eje: se recorta y se quitan los quiebres de fuera
    pv = Perfil([(0, 100, 1.0, 50), (50, 100.5, 2.0, 300)]).pvis(10, 40)
    assert [p[0] for p in pv] == [10, 40]


def test_csv_con_columnas_de_mas(tmp_path):
    """Excel deja ';' sueltos al final de las filas: antes la lectura se caía (AttributeError)."""
    f = tmp_path / "x.csv"
    f.write_text("a;b;c\n1,5;2;texto\n3;4;con; separador;;\n", encoding="utf-8")
    filas = leer_csv(f)
    assert filas[0] == {"a": "1.5", "b": "2", "c": "texto"}
    assert filas[1]["c"] == "con;separador"


def test_terreno_colineal_no_se_cae():
    """Solo puntos del eje (en línea): antes, error de qhull y la app se cerraba."""
    t = Terreno([PuntoTerreno(str(i), i * 10.0, i * 5.0, 100 + i, "EJ") for i in range(6)])
    assert not t.ok and "línea" in t.error
    assert math.isnan(t.cota(5.0, 2.5))


def test_terreno_puntos_repetidos():
    pts = [PuntoTerreno("1", 0, 0, 1, ""), PuntoTerreno("2", 10, 0, 2, ""), PuntoTerreno("3", 0, 10, 3, ""),
           PuntoTerreno("4", 0, 10, 3.5, ""), PuntoTerreno("5", 10, 10, 3, "")]
    t = Terreno(pts)
    assert len(t.puntos) == 4 and len(t.repetidos) == 1
    assert abs(t.cota(0.0, 10.0) - 3.0) < 1e-9          # se queda el primero


def test_normal_en_vertice_es_bisectriz():
    """En un quiebre del eje la sección va por la bisectriz y el offset queda a 'o' de los dos tramos."""
    al = Alineamiento([(0, 0), (100, 0), (100 + 100 * math.cos(math.radians(-40)), 100 * math.sin(math.radians(-40)))])
    pe, pn = al.punto(100.0, 5.0)
    # distancia a la recta del primer tramo (y = 0) y a la del segundo
    assert abs(abs(pn) - 5.0) < 1e-9
    ux, uy = math.cos(math.radians(-40)), math.sin(math.radians(-40))
    d2 = abs((pe - 100) * uy - pn * ux)
    assert abs(d2 - 5.0) < 1e-9


def test_eje_quebrado_sin_secciones_cruzadas(resultados):
    """Ninguna sección cae tan cerca de un vértice como para cruzarse con la del vértice."""
    rc = resultados["E02_eje_quebrado"].calles["EJE-01"]
    for q, d in rc.zonas_vertice:
        assert not [s.prog for s in rc.secciones if 1e-6 < abs(s.prog - q) < d]


def test_T_al_sardinel_detectada_y_de_un_solo_lado(resultados):
    """EJE-04 empieza en la cara del sardinel de EJE-01 (no toca su eje): antes no era cruce y la
    principal seguía con sardinel y vereda cruzando la boca de la calle."""
    res = resultados["E03_cruce_oblicuo_T"]
    t = [x for x in res.cruces if x["secundaria"] == "EJE-04"]
    assert len(t) == 1 and t[0]["principal"] == "EJE-01" and t[0]["tipo"] == "T"
    rc = res.calles["EJE-01"]
    s = min(rc.secciones, key=lambda s: abs(s.prog - 210))
    assert s.lateral == {"I": False, "D": True}       # llega por la izquierda: la derecha conserva vereda
    s = min(rc.secciones, key=lambda s: abs(s.prog - 160))
    assert s.lateral == {"I": True, "D": False}       # EJE-03 llega por la derecha


def test_avisos_de_terreno_incompleto(resultados):
    av = [a.mensaje for a in resultados["E05_irregular"].avisos if a.categoria == "TERRENO"]
    assert any("FUERA del levantamiento" in m for m in av)
    assert any("repetidos" in m for m in av)


def test_densificacion_en_hondonada(resultados):
    rc = resultados["datos_ejemplo"].calles["EJE-02"]
    assert any(s.tipo == "DENSIFICADA" for s in rc.secciones)
    assert all(s2.prog - s1.prog >= 2.5 - 1e-6 or s1.omitida or s2.omitida
               for s1, s2 in zip(rc.secciones, rc.secciones[1:]) if "DENSIFICADA" in (s1.tipo, s2.tipo))


@pytest.mark.parametrize("esc", list(generar_escenarios.ESCENARIOS))
def test_escenario_exporta(resultados, esc, tmp_path):
    """Todos los escenarios calculan y exportan sin errores (CSV, LandXML y DXF)."""
    from corredor.exportar import exportar_todo
    archivos = exportar_todo(resultados[esc], tmp_path, formatos=("csv", "landxml", "dxf"))
    assert all(Path(a).exists() for a in archivos)
