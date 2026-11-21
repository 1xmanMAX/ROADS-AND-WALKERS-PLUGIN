"""Verificación automática contra Civil 3D 2025.

Calcula un proyecto con la app, exporta todo y le pide a Civil 3D (sin ventana, con
accoreconsole y el complemento civil3d_verificador) que repita las cuentas con su propio motor:

  * importar el LandXML (todas las superficies deben entrar);
  * coordenadas de alineamientos creados con la API nativa (PointLocation);
  * cotas de rasante con un perfil nativo (ElevationAt);
  * cotas de las superficies terminado / subrasante / fondo de capas en puntos de control;
  * TN propio de Civil 3D (triangulación de Civil 3D desde los puntos) frente al TIN de la app;
  * área de corte y relleno en cada sección y volumen entre superficies (superficie de volumen).

Uso:
    python herramientas/verificar_civil3d.py <carpeta_proyecto> <carpeta_salida>
    python herramientas/verificar_civil3d.py --todos escenarios salida_escenarios

Deja en la carpeta de salida: los archivos de la app, verificacion_trabajo.json (lo que se le
pide a Civil 3D), verificacion_civil3d.json (lo que respondió), verificacion_civil3d.dwg (para
abrirlo y revisar) y verificacion.md (comparación con tolerancias).
"""
import json
import math
import os
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from corredor.datos import leer_proyecto, validar_proyecto  # noqa: E402
from corredor.exportar import exportar_todo, nombre_seguro  # noqa: E402
from corredor.motor import calcular  # noqa: E402

from corredor.civil3d import C3D, DLL, PLANTILLA  # noqa: E402  (una sola configuración)

# tolerancias (las de docs/CIVIL3D.md)
TOL = {"xy": 0.002, "z": 0.002, "z_tn": 0.005, "area_rel": 0.01, "area_abs": 0.02, "vol_rel": 0.02, "vol_abs": 0.5}


def _interp(linea, o):
    """Cota de una línea de sección [(cod, o, z)] en el offset o (la línea ya va de izq. a der.)."""
    for (_, oa, za), (_, ob, zb) in zip(linea[:-1], linea[1:]):
        if oa - 1e-9 <= o <= ob + 1e-9 and ob - oa > 1e-9:
            return za + (zb - za) * (o - oa) / (ob - oa)
    return None


def _ajustada(linea):
    """La misma separación de 5 mm que se aplica al exportar la superficie (caras verticales)."""
    from corredor.malla import _ajustar
    return _ajustar(linea, True)


def armar_trabajo(res, salida):
    proy = res.proyecto
    xml = salida / "corredor_civil3d.xml"
    sup_nombres = []
    if res.terreno.ok:
        sup_nombres.append(nombre_seguro("TN Terreno existente"))
    trabajo = {"landxml": str(xml), "salida": str(salida / "verificacion_civil3d.json"),
               "dwg": str(salida / "verificacion_civil3d.dwg"), "calles": [], "chequeos_superficie": []}
    if res.terreno.ok:
        trabajo["terreno"] = {"arista_max": float(proy.p("arista_max_tin")),
                              "puntos": [[p.este, p.norte, p.cota] for p in res.terreno.puntos]}
    chk = trabajo["chequeos_superficie"]
    capas = proy.capas_de("calzada")
    for k, rc in res.calles.items():
        n_ter = nombre_seguro(f"{k} TERMINADO")
        n_sub = nombre_seguro(f"{k} SUBRASANTE")
        n_c1 = nombre_seguro(f"{k} FONDO C1 {capas[0].nombre}") if capas else None
        sup_nombres += [n_ter, n_sub] + ([n_c1] if n_c1 else [])
        for j, cp in enumerate(capas[1:], start=2):
            sup_nombres.append(nombre_seguro(f"{k} FONDO C{j} {cp.nombre}"))
        validas = [s for s in rc.secciones if not s.omitida]
        calle = {"id": k, "vertices": [list(v) for v in rc.alin.vertices], "prog_inicial": rc.alin.prog_inicial,
                 "pvis": [list(p) for p in rc.perfil.pvis(rc.alin.prog_inicial, rc.alin.prog_final)], "sup_subrasante": n_sub,
                 "chequeos_eje": [], "chequeos_perfil": [], "secciones": []}
        for s in rc.secciones:
            calle["chequeos_perfil"].append({"prog": s.prog, "z": s.rasante})
            for cod, o, z in s.puntos:
                # en un vértice la app usa la bisectriz (inglete); PointLocation de Civil 3D es
                # perpendicular a un solo tramo, así que ahí solo se compara el punto del eje
                en_vertice = rc.alin.vertice_en(s.prog) is not None
                if cod == "EJE" or (cod[:-1] in ("BC", "PF") and not en_vertice):
                    e, n = s.xy(o)
                    calle["chequeos_eje"].append({"prog": s.prog, "offset": o, "e": e, "n": n})
        # puntos de control en superficies: entre secciones interiores (no en los bordes de la superficie)
        for s in validas[1:-1]:
            ter = _ajustada(s.lineas["TERMINADO"])
            sub = _ajustada(s.lineas["SUBRASANTE"])
            controles = [("EJE", 0.0)]
            for cod, o, _ in ter:
                sg = 1.0 if o > 0 else -1.0
                if cod[:-1] == "BC":
                    # sin cuneta, el borde de calzada está al pie de la cara del sardinel: 2 cm hacia el eje
                    controles.append((cod, o - 0.02 * sg))
                elif cod[:-1] == "FC":
                    # el fondo está al pie de la cara vertical del sardinel: medir 2 cm hacia la calzada,
                    # sobre la pendiente de la cuneta (en la pared, 0.1 mm de redondeo son mm de cota)
                    controles.append((cod, o - 0.02 * sg))
                elif cod[:-1] == "BV":
                    controles.append((cod, o + 0.01 * sg))
            for c_, o, _ in ter:
                if c_[:-1] == "PF":
                    o_bv = next((ob for cb, ob, _ in ter if cb == "BV" + c_[-1]), None)
                    if o_bv is not None and abs(o - o_bv) > 0.05:
                        controles.append(("MEDIO_VEREDA" + c_[-1], (o + o_bv) / 2))
            for cod, o in controles:
                z = _interp(ter, o)
                if z is None:
                    continue
                x, y = s.xy(o)
                chk.append({"superficie": n_ter, "etiqueta": f"{k} {s.prog:.2f} {cod}", "x": x, "y": y, "z": z})
            x, y = s.xy(0.0)
            chk.append({"superficie": n_sub, "etiqueta": f"{k} {s.prog:.2f} SUB-EJE", "x": x, "y": y,
                        "z": _interp(sub, 0.0)})
            if n_c1:
                chk.append({"superficie": n_c1, "etiqueta": f"{k} {s.prog:.2f} C1-EJE", "x": x, "y": y,
                            "z": s.lineas["C1_FONDO"][1][2] if len(s.lineas["C1_FONDO"]) == 3 else
                            _interp(s.lineas["C1_FONDO"], 0.0)})
            if res.terreno.ok:
                for o in (0.0, sub[0][1] + 0.3, sub[-1][1] - 0.3):
                    x, y = s.xy(o)
                    zt = res.terreno.cota(x, y)
                    if zt == zt:
                        for nom in ("TN Terreno existente", "TN Civil3D desde puntos"):
                            chk.append({"superficie": nom, "etiqueta": f"{k} {s.prog:.2f} TN o={o:+.2f}",
                                        "x": x, "y": y, "z": zt})
        for i, s in enumerate(validas):
            sub = _ajustada(s.lineas["SUBRASANTE"])
            # la primera y la última sección están en el borde de la superficie: 1 mm hacia adentro
            d = 0.001 if i == 0 else (-0.001 if i == len(validas) - 1 else 0.0)
            ux, uy = rc.alin.direccion(s.prog)
            calle["secciones"].append({"prog": s.prog, "e": s.e + d * ux, "n": s.n + d * uy, "nx": s.nx, "ny": s.ny,
                                       "quiebres": [o for _, o, _ in sub], "paso": float(proy.p("paso_terreno")),
                                       "corte": s.area_corte, "relleno": s.area_relleno})
        calle["vol_app_corte"], calle["vol_app_relleno"] = rc.vol_corte, rc.vol_relleno
        trabajo["calles"].append(calle)
    # ---- esquinas curvas: superficie terminada (cotas en el centro de cada triángulo) y volumen
    if any(e.get("ok") for e in res.esquinas):
        n_t, n_s = "ESQUINAS TERMINADO", "ESQUINAS SUBRASANTE"
        sup_nombres += [n_t, n_s]
        for e in res.esquinas:
            for cat, tris in e.get("caras", {}).items():
                for t in tris[::3]:
                    a2 = abs((t[1][0] - t[0][0]) * (t[2][1] - t[0][1]) - (t[1][1] - t[0][1]) * (t[2][0] - t[0][0]))
                    if a2 < 0.02:          # triángulos chicos: el centro queda a mm de un borde
                        continue
                    x, y, z = (sum(p[i] for p in t) / 3 for i in range(3))
                    chk.append({"superficie": n_t, "etiqueta": f"{e['id']} {cat}", "x": x, "y": y, "z": z})
        trabajo["volumenes_extra"] = [{"id": "ESQUINAS", "sup_subrasante": n_s,
                                       "corte_app": res.esquinas_total("vol_corte"),
                                       "relleno_app": res.esquinas_total("vol_relleno")}]
    trabajo["superficies_landxml"] = sup_nombres
    return trabajo


def correr_civil3d(trabajo_json, salida, timeout=900):
    if not DLL.exists():
        raise RuntimeError(f"Falta {DLL}. Compílalo con: dotnet build -c Release civil3d_verificador")
    scr = salida / "verificacion.scr"
    dll = str(DLL).replace("\\", "/")
    dwg = str(salida / "verificacion_civil3d.dwg").replace("\\", "/")
    if Path(dwg).exists():
        Path(dwg).unlink()
    scr.write_text(f'(setvar "SECURELOAD" 0)\n(setvar "FILEDIA" 0)\n(command "_.NETLOAD" "{dll}")\nCS_VERIFICAR\n'
                   f'(command "_.SAVEAS" "2018" "{dwg}")\n_.QUIT\n_Y\n', encoding="utf-8")
    res_json = salida / "verificacion_civil3d.json"
    if res_json.exists():
        res_json.unlink()
    env = dict(os.environ, CS_VERIF_TRABAJO=str(trabajo_json))
    cmd = [str(C3D / "accoreconsole.exe"), "/i", str(PLANTILLA), "/s", str(scr),
           "/ld", str(C3D / "AecBase.dbx"), "/p", "<<C3D_Metric>>", "/product", "C3D", "/language", "en-US"]
    t0 = time.time()
    p = subprocess.run(cmd, env=env, capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL)
    texto = p.stdout.decode("utf-16-le", errors="replace") if p.stdout[:200].count(b"\x00") > 20 \
        else p.stdout.decode("utf-8", errors="replace")
    (salida / "accoreconsole.log").write_text(texto, encoding="utf-8")
    if not res_json.exists():
        raise RuntimeError(f"Civil 3D no devolvió resultados (ver {salida / 'accoreconsole.log'}).")
    return json.loads(res_json.read_text(encoding="utf-8")), time.time() - t0


def comparar(trabajo, r):
    """Devuelve (lineas_md, resumen) con OK/FALLA por grupo."""
    md, resumen = [], {}

    def grupo(nombre, ok, detalle):
        resumen[nombre] = ok
        md.append(f"| {nombre} | {'OK' if ok else '**FALLA**'} | {detalle} |")

    md += ["| Control | Resultado | Detalle |", "|---|---|---|"]
    if not r.get("ok"):
        grupo("Civil 3D ejecutó", False, r.get("error", "")[:300].replace("\n", " "))
        return md, resumen
    imp = r.get("landxml", {})
    malas = [k for k, v in imp.items() if "error" in v]
    grupo("LandXML importado", not malas,
          f"{len(imp) - len(malas)}/{len(imp)} superficies" + (f"; fallan: {', '.join(malas)}" if malas else ""))
    for c in r["calles"]:
        k = c["id"]
        ce = c["chequeos_eje"]
        dxy = max((math.hypot(p["e_c3d"] - p["e_app"], p["n_c3d"] - p["n_app"]) for p in ce), default=0)
        grupo(f"{k} coordenadas eje/bordes", dxy <= TOL["xy"], f"{len(ce)} puntos, dif. máx. {dxy * 1000:.2f} mm")
        cp = c["chequeos_perfil"]
        sin = [p for p in cp if p["z_c3d"] is None]
        dz = max((abs(p["z_c3d"] - p["z_app"]) for p in cp if p["z_c3d"] is not None), default=0)
        grupo(f"{k} rasante", dz <= TOL["z"] and not sin,
              f"{len(cp)} progresivas, dif. máx. {dz * 1000:.2f} mm" + (f", {len(sin)} sin cota" if sin else ""))
        secs = c.get("secciones", [])
        if secs:
            peor, peor_s = 0.0, None
            for s in secs:
                for a, b in (("corte_app", "corte_c3d"), ("relleno_app", "relleno_c3d")):
                    d = abs(s[a] - s[b])
                    lim = max(TOL["area_abs"], TOL["area_rel"] * max(s[a], s[b]))
                    if d / lim > peor:
                        peor, peor_s = d / lim, (s["prog"], a[:-4], s[a], s[b])
            det = f"{len(secs)} secciones"
            if peor_s:
                det += f"; peor en {peor_s[0]:.2f} ({peor_s[1]}: app {peor_s[2]:.3f} / C3D {peor_s[3]:.3f} m²)"
            grupo(f"{k} áreas corte/relleno por sección", peor <= 1.0, det)
        if "vol_c3d_corte" in c:
            tc = next(x for x in trabajo["calles"] if x["id"] == k)
            res_ok, det = True, []
            for nom, a, b in (("corte", tc["vol_app_corte"], c["vol_c3d_corte"]),
                              ("relleno", tc["vol_app_relleno"], c["vol_c3d_relleno"])):
                lim = max(TOL["vol_abs"], TOL["vol_rel"] * max(a, b))
                res_ok &= abs(a - b) <= lim
                det.append(f"{nom} app {a:.2f} / C3D {b:.2f} m³ ({(a - b) / b * 100 if b else 0:+.2f} %)")
            grupo(f"{k} volumen (área media vs superficie de volumen)", res_ok, "; ".join(det))
        elif "vol_error" in c:
            grupo(f"{k} volumen", False, c["vol_error"])
    for v in r.get("volumenes_extra", []):
        tv = next(x for x in trabajo.get("volumenes_extra", []) if x["id"] == v["id"])
        if "vol_c3d_corte" not in v:
            grupo(f"{v['id']} volumen", False, v.get("vol_error", "sin resultado"))
            continue
        res_ok, det = True, []
        for nom, a, b in (("corte", tv["corte_app"], v["vol_c3d_corte"]), ("relleno", tv["relleno_app"], v["vol_c3d_relleno"])):
            lim = max(TOL["vol_abs"], TOL["vol_rel"] * max(a, b))
            res_ok &= abs(a - b) <= lim
            det.append(f"{nom} app {a:.2f} / C3D {b:.2f} m³ ({(a - b) / b * 100 if b else 0:+.2f} %)")
        grupo(f"{v['id']} volumen (triángulos vs superficie de volumen)", res_ok, "; ".join(det))
    por_sup = {}
    for x in r.get("chequeos_superficie", []):
        por_sup.setdefault(x["superficie"], []).append(x)
    for nom, lst in por_sup.items():
        sin = [x for x in lst if x["z_c3d"] is None]
        con = [x for x in lst if x["z_c3d"] is not None]
        dif = sorted(con, key=lambda x: -abs(x["z_c3d"] - x["z_app"]))
        dz = abs(dif[0]["z_c3d"] - dif[0]["z_app"]) if dif else 0
        tol = TOL["z_tn"] if nom.startswith("TN") else TOL["z"]
        det = f"{len(lst)} puntos, dif. máx. {dz * 1000:.1f} mm"
        if dif and dz > tol:
            det += f" en {dif[0]['etiqueta']}"
        if sin:
            det += f"; {len(sin)} fuera de la superficie (p. ej. {sin[0]['etiqueta']})"
        grupo(f"cotas superficie '{nom}'", dz <= tol and len(sin) <= max(1, len(lst) // 50), det)
    return md, resumen


def verificar(carpeta, salida):
    carpeta, salida = Path(carpeta).resolve(), Path(salida).resolve()   # accoreconsole necesita rutas absolutas
    salida.mkdir(parents=True, exist_ok=True)
    proy = leer_proyecto(carpeta)
    err = validar_proyecto(proy)
    if err:
        raise RuntimeError("Datos con errores: " + "; ".join(err))
    t0 = time.time()
    res = calcular(proy)
    t_calc = time.time() - t0
    exportar_todo(res, salida, formatos=("csv", "landxml", "dxf"))
    trabajo = armar_trabajo(res, salida)
    tj = salida / "verificacion_trabajo.json"
    tj.write_text(json.dumps(trabajo), encoding="utf-8")
    r, t_c3d = correr_civil3d(tj, salida)
    md, resumen = comparar(trabajo, r)
    cab = [f"# Verificación en Civil 3D: {carpeta.name}", "",
           f"Cálculo de la app: {t_calc:.1f} s. Civil 3D (accoreconsole): {t_c3d:.1f} s.", "",
           "Avisos de la app: " + ", ".join(f"{n} {sum(1 for a in res.avisos if a.nivel == n)}"
                                            for n in ("ERROR", "AVISO", "INFO")), ""]
    for k, rc in res.calles.items():
        cab.append(f"- {k}: corte {rc.vol_corte:.2f} m³, relleno {rc.vol_relleno:.2f} m³, "
                   f"{len(rc.secciones)} secciones")
    cab.append("")
    (salida / "verificacion.md").write_text("\n".join(cab + md) + "\n", encoding="utf-8")
    return resumen, res


def main(argv):
    if argv and argv[0] == "--todos":
        base, out = Path(argv[1]), Path(argv[2])
        carpetas = sorted(p for p in base.iterdir() if (p / "calles.csv").exists())
    else:
        carpetas, out = [Path(argv[0])], None
    fallas = 0
    referencias = {}
    for c in carpetas:
        sal = (out / c.name) if out else Path(argv[1])
        print(f"== {c.name}")
        try:
            resumen, _ = verificar(c, sal)
        except Exception as ex:      # se informa y se sigue con el siguiente escenario
            print(f"   ERROR: {ex}")
            fallas += 1
            continue
        for k, ok in resumen.items():
            if not ok:
                fallas += 1
            print(f"   {'OK   ' if ok else 'FALLA'} {k}")
        print(f"   -> {sal / 'verificacion.md'}")
        r = json.loads((sal / "verificacion_civil3d.json").read_text(encoding="utf-8"))
        referencias[c.name] = {x["id"]: {"corte": round(x["vol_c3d_corte"], 2), "relleno": round(x["vol_c3d_relleno"], 2)}
                               for x in r.get("calles", []) if "vol_c3d_corte" in x}
        for x in r.get("volumenes_extra", []):          # esquinas curvas
            if "vol_c3d_corte" in x:
                referencias[c.name][x["id"]] = {"corte": round(x["vol_c3d_corte"], 2), "relleno": round(x["vol_c3d_relleno"], 2)}
    if out:
        # volúmenes de Civil 3D por escenario: sirven de referencia para pruebas/test_escenarios.py
        (out / "referencias_civil3d.json").write_text(json.dumps(referencias, indent=1, ensure_ascii=False),
                                                      encoding="utf-8")
        print(f"Referencias de Civil 3D: {out / 'referencias_civil3d.json'}")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
