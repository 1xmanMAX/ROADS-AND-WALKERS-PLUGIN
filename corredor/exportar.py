"""Exportaciones: CSV (estación total y Civil 3D), LandXML, DXF, Excel y PDF.

Pensado para Civil 3D 2025:
  * LandXML 1.2  -> Insertar > LandXML: crea Alineamientos, Perfiles de rasante y Superficies (TN,
                    terminado, subrasante y fondos de capa) como objetos nativos de Civil 3D.
  * DXF (AutoCAD 2018) -> eje, líneas características 3D, caras 3D del corredor y de cada capa,
                    fachadas, puertas, puntos, hoja de secciones y perfil dibujados.
  * CSV PNEZD     -> Insertar > Puntos desde archivo, formato "PNEZD (comma delimited)".
"""
import csv
import datetime as dt
import math
import re
from pathlib import Path
from xml.sax.saxutils import escape

from .geometria import fmt_prog
from .replanteo import (capas_replanteo, descripcion_codigo, puntos_capas, puntos_seccion, tabla_eje)

f3 = lambda v: f"{v:.3f}"


def nombre_seguro(txt):
    """Civil 3D/AutoCAD no aceptan < > / \\ " : ; ? * | , = ` ' en nombres de capas y superficies."""
    txt = txt.replace("ñ", "n").replace("Ñ", "N")
    for a, b in zip("áéíóúÁÉÍÓÚ", "aeiouAEIOU"):
        txt = txt.replace(a, b)
    txt = re.sub(r"[^A-Za-z0-9 _\-.()]", "", txt)
    return re.sub(r"\s+", " ", txt).strip()


def altura_instrumento(proy, bm_id, lectura_atras):
    if bm_id is None or lectura_atras in (None, ""):
        return None
    for b in proy.bms:
        if b.id == bm_id:
            return b.cota + float(lectura_atras)
    return None


# ------------------------------------------------------------------ CSV
def _csv(ruta, cab, filas, bom=True):
    """bom=True para que Excel muestre bien las tildes; los archivos para equipos y
    Civil 3D van sin BOM (texto plano)."""
    with open(ruta, "w", newline="", encoding="utf-8-sig" if bom else "utf-8") as f:
        w = csv.writer(f)
        if cab:
            w.writerow(cab)
        w.writerows(filas)


def exportar_csv(res, carpeta, ai=None):
    c = Path(carpeta)
    c.mkdir(parents=True, exist_ok=True)
    archivos = []
    pnezd, num = [], 1
    for k, rc in res.calles.items():
        # tabla del eje: progresiva, Este, Norte, cota
        ruta = c / f"{k}_eje_progresiva_coordenada.csv"
        _csv(ruta, ["progresiva", "este", "norte", "cota_rasante"],
             [[r["progresiva"], f3(r["este"]), f3(r["norte"]), f3(r["cota"])] for r in tabla_eje(rc)], bom=False)
        archivos.append(ruta)
        # estación total: superficie terminada
        pts = puntos_seccion(rc)
        ruta = c / f"{k}_estacion_total_terminado.csv"
        _csv(ruta, ["nombre", "este", "norte", "cota", "codigo"],
             [[p["nombre"], f3(p["este"]), f3(p["norte"]), f3(p["cota"]), p["codigo"]] for p in pts], bom=False)
        archivos.append(ruta)
        # estación total: capas
        pc = puntos_capas(rc, res.proyecto, ai)
        ruta = c / f"{k}_estacion_total_capas.csv"
        _csv(ruta, ["nombre", "este", "norte", "cota", "codigo"],
             [[p["nombre"], f3(p["este"]), f3(p["norte"]), f3(p["cota"]), f"{p['prefijo']}-{p['codigo']}"] for p in pc], bom=False)
        archivos.append(ruta)
        # tabla de campo por capa con lectura de mira
        ruta = c / f"{k}_tabla_campo_capas.csv"
        _csv(ruta, ["capa", "progresiva", "punto", "offset", "este", "norte", "cota_diseno", "lectura_mira"],
             [[p["capa"], p["progresiva"], p["codigo"], f3(p["offset"]), f3(p["este"]), f3(p["norte"]),
               f3(p["cota"]), f3(p["lectura"]) if p["lectura"] is not None else ""] for p in pc])
        archivos.append(ruta)
        # movimiento de tierras
        ruta = c / f"{k}_movimiento_tierras.csv"
        _csv(ruta, ["desde", "hasta", "distancia", "area_corte_1", "area_corte_2", "area_relleno_1",
                    "area_relleno_2", "vol_corte", "vol_relleno", "acum_corte", "acum_relleno"],
             [[fmt_prog(t["desde"]), fmt_prog(t["hasta"]), f3(t["distancia"]), f3(t["ac1"]), f3(t["ac2"]),
               f3(t["ar1"]), f3(t["ar2"]), f3(t["vol_corte"]), f3(t["vol_relleno"]), f3(t["acum_corte"]),
               f3(t["acum_relleno"])] for t in rc.tramos_volumen])
        archivos.append(ruta)
        for p in pts + pc:
            pnezd.append([num, f3(p["norte"]), f3(p["este"]), f3(p["cota"]), p["nombre"]])
            num += 1
    ruta = c / "civil3d_puntos_PNEZD.csv"
    _csv(ruta, None, pnezd, bom=False)
    archivos.append(ruta)
    ruta = c / "civil3d_terreno_PNEZD.csv"
    _csv(ruta, None, [[p.numero, f3(p.norte), f3(p.este), f3(p.cota), p.codigo] for p in res.proyecto.terreno], bom=False)
    archivos.append(ruta)
    ruta = c / "avisos.txt"
    ruta.write_text("\n".join(a.texto() for a in res.avisos) + "\n", encoding="utf-8")
    archivos.append(ruta)
    return archivos


# ------------------------------------------------------------------ LandXML
def exportar_landxml(res, ruta):
    from .malla import superficie
    proy = res.proyecto
    ahora = dt.datetime.now()
    L = []
    a = L.append
    a('<?xml version="1.0" encoding="UTF-8"?>')
    a('<LandXML xmlns="http://www.landxml.org/schema/LandXML-1.2" '
      'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
      'xsi:schemaLocation="http://www.landxml.org/schema/LandXML-1.2 '
      'http://www.landxml.org/schema/LandXML-1.2/LandXML-1.2.xsd" '
      f'version="1.2" date="{ahora:%Y-%m-%d}" time="{ahora:%H:%M:%S}">')
    a('  <Units><Metric areaUnit="squareMeter" linearUnit="meter" volumeUnit="cubicMeter" '
      'temperatureUnit="celsius" pressureUnit="milliBars" diameterUnit="millimeter" '
      'angularUnit="decimal degrees" directionUnit="decimal degrees"/></Units>')
    a(f'  <Project name="{escape(nombre_seguro(proy.nombre))}"/>')
    a('  <Application name="Corredor Simple" manufacturer="Corredor Simple" version="0.1.0"/>')
    a('  <Alignments name="Ejes Corredor Simple">')
    for k, rc in res.calles.items():
        al = rc.alin
        nom = escape(nombre_seguro(f"{k} {rc.calle.nombre}"))
        a(f'    <Alignment name="{nom}" length="{al.longitud:.4f}" staStart="{al.prog_inicial:.4f}" '
          f'desc="{escape(nombre_seguro(rc.calle.nombre))}">')
        a('      <CoordGeom>')
        for s in al.segs:
            e1, n1 = s["e0"] + s["L"] * s["ux"], s["n0"] + s["L"] * s["uy"]
            a(f'        <Line staStart="{s["p0"]:.4f}" length="{s["L"]:.4f}">'
              f'<Start>{s["n0"]:.4f} {s["e0"]:.4f}</Start><End>{n1:.4f} {e1:.4f}</End></Line>')
        a('      </CoordGeom>')
        a(f'      <Profile name="{nom}">')
        a(f'        <ProfAlign name="{escape(nombre_seguro(k))} Rasante">')
        for sta, z in rc.perfil.pvis():
            a(f'          <PVI>{sta:.4f} {z:.4f}</PVI>')
        a('        </ProfAlign>')
        a('      </Profile>')
        a('    </Alignment>')
    a('  </Alignments>')
    a('  <Surfaces name="Superficies Corredor Simple">')

    def surf(nombre, pts, caras, desc=""):
        if not caras:
            return
        a(f'    <Surface name="{escape(nombre_seguro(nombre))}" desc="{escape(nombre_seguro(desc))}">')
        a('      <Definition surfType="TIN">')
        a('        <Pnts>')
        for i, (e, n, z) in enumerate(pts, start=1):
            a(f'          <P id="{i}">{n:.4f} {e:.4f} {z:.4f}</P>')
        a('        </Pnts>')
        a('        <Faces>')
        for f in caras:
            a(f'          <F>{f[0] + 1} {f[1] + 1} {f[2] + 1}</F>')
        a('        </Faces>')
        a('      </Definition>')
        a('    </Surface>')

    t = res.terreno
    if t.ok:
        pts = [(p.este, p.norte, p.cota) for p in proy.terreno]
        surf("TN Terreno existente", pts, t.triangulos(), "Levantamiento topografico")
    calles = list(res.calles.values())
    for rc in calles:
        k = rc.calle.eje_id
        surf(f"{k} TERMINADO", *superficie([rc], "TERMINADO"), "Superficie terminada")
        surf(f"{k} SUBRASANTE", *superficie([rc], "SUBRASANTE"), "Fondo de excavacion")
        for j, cp in enumerate(proy.capas_de("calzada"), start=1):
            surf(f"{k} FONDO C{j} {cp.nombre}", *superficie([rc], f"C{j}_FONDO"), f"Fondo de {cp.nombre}")
    a('  </Surfaces>')
    a('</LandXML>')
    Path(ruta).write_text("\n".join(L) + "\n", encoding="utf-8")
    return ruta


# ------------------------------------------------------------------ DXF
COLOR_DXF = {"CALZADA": 8, "CUNETA": 5, "SARDINEL": 9, "VEREDA": 41, "FACHADA": 1}


def exportar_dxf(res, ruta, hoja_secciones=True):
    import ezdxf
    from ezdxf.enums import TextEntityAlignment

    from .malla import fachadas_3d, lineas_caracteristicas, modelo

    proy = res.proyecto
    doc = ezdxf.new("R2018", setup=True)
    doc.header["$INSUNITS"] = 6      # metros
    msp = doc.modelspace()
    capas_hechas = set()

    def capa(nombre, color=7):
        n = nombre_seguro(nombre).replace(" ", "_")
        if n not in capas_hechas:
            if n not in doc.layers:
                doc.layers.add(n, color=color)
            capas_hechas.add(n)
        return n

    def texto(txt, p, h, lay, rot=0.0, al=TextEntityAlignment.LEFT):
        t = msp.add_text(txt, dxfattribs={"layer": lay, "height": h, "rotation": rot})
        t.set_placement(p, align=al)
        return t

    for k, rc in res.calles.items():
        c = rc.calle
        # eje 2D (para "Crear alineamiento desde objetos") y eje 3D con rasante
        msp.add_lwpolyline(rc.alin.vertices, dxfattribs={"layer": capa("C3D-EJE-2D", 6)})
        msp.add_polyline3d([(s.e, s.n, s.rasante) for s in rc.secciones], dxfattribs={"layer": capa("C3D-EJE-3D", 6)})
        lay_p = capa("C3D-EJE-PROGRESIVAS", 6)
        for s in rc.secciones:
            ux, uy = rc.alin.direccion(s.prog)
            nx, ny = uy, -ux
            largo = 1.0 if s.tipo == "INTERVALO" else 1.5
            msp.add_line((s.e - nx * largo, s.n - ny * largo), (s.e + nx * largo, s.n + ny * largo),
                         dxfattribs={"layer": lay_p})
            if s.tipo != "INTERVALO" or abs(s.prog % 20) < 0.01:
                rot = math.degrees(math.atan2(ny, nx))
                texto(f"{fmt_prog(s.prog)}  {s.rasante:.3f}", (s.e + nx * 1.7, s.n + ny * 1.7), 0.35, lay_p, rot)
        mid = rc.alin.punto((rc.alin.prog_inicial + rc.alin.prog_final) / 2, -2.5)
        rot = math.degrees(math.atan2(*reversed(rc.alin.direccion(rc.alin.prog_inicial))))
        texto(f"{k} {c.nombre}", mid, 0.8, capa("C3D-NOMBRE-CALLE", 7), rot)
        # líneas características 3D
        for linea, pref in (("TERMINADO", "C3D-LF-"), ("SUBRASANTE", "C3D-LF-SUB-")):
            for cod, polis in lineas_caracteristicas(rc, linea).items():
                base = cod if cod == "EJE" else cod[:-1]
                lay = capa(pref + base, 3 if linea == "TERMINADO" else 1)
                for pl in polis:
                    msp.add_polyline3d(pl, dxfattribs={"layer": lay})
        # caras 3D
        for cat, q in modelo(rc, proy):
            lay = capa("C3D-3D-" + cat, COLOR_DXF.get(cat, 30 + (hash(cat) % 200)))
            msp.add_3dface(q, dxfattribs={"layer": lay})
        # puntos de replanteo
        lay_pt, lay_tx = capa("C3D-PUNTOS", 2), capa("C3D-PUNTOS-TEXTO", 2)
        for p in puntos_seccion(rc):
            msp.add_point((p["este"], p["norte"], p["cota"]), dxfattribs={"layer": lay_pt})
            texto(p["nombre"], (p["este"] + 0.05, p["norte"] + 0.05, p["cota"]), 0.08, lay_tx)
    # fachadas y puertas
    for l in proy.fachadas:
        msp.add_lwpolyline([(e, n) for e, n, _ in l.puntos], dxfattribs={"layer": capa("C3D-FACHADA", 1)})
    for cat, q in fachadas_3d(proy, res.terreno, res):
        msp.add_3dface(q, dxfattribs={"layer": capa("C3D-3D-FACHADA", 1)})
    for u in res.umbrales:
        uu = u["umbral"]
        lay = capa("C3D-PUERTAS", 1 if u["diferencia"] < 0 else 3)
        msp.add_circle((uu.este, uu.norte), uu.ancho / 2, dxfattribs={"layer": lay})
        texto(f"{uu.id} umbral {uu.cota:.3f} vereda {u['cota_vereda']:.3f} dif {u['diferencia']:+.3f}",
              (uu.este + 0.3, uu.norte + 0.3), 0.18, lay)
    # terreno
    lay_tn = capa("C3D-TN-PUNTOS", 32)
    for p in proy.terreno:
        msp.add_point((p.este, p.norte, p.cota), dxfattribs={"layer": lay_tn})
    for b in proy.bms:
        lay = capa("C3D-BM", 4)
        msp.add_circle((b.este, b.norte, b.cota), 0.4, dxfattribs={"layer": lay})
        texto(f"{b.id} {b.cota:.3f}", (b.este + 0.5, b.norte + 0.5), 0.3, lay)

    if hoja_secciones:
        _dxf_hojas(res, msp, capa, texto)
    doc.saveas(ruta)
    return ruta


def _dxf_hojas(res, msp, capa, texto):
    """Dibuja (lejos de la obra, a la derecha) las secciones a escala 1:1 y el perfil con exageración 10."""
    from ezdxf.enums import TextEntityAlignment
    proy = res.proyecto
    todas_e = [s.e for rc in res.calles.values() for s in rc.secciones]
    todas_n = [s.n for rc in res.calles.values() for s in rc.secciones]
    X0 = max(todas_e) + 80.0
    Y0 = max(todas_n)
    ancho_celda, alto_celda, cols = 16.0, 5.0, 6
    y = Y0
    lay_t = capa("C3D-HOJA-TEXTO", 7)
    from .graficos import COLORES_CAPAS
    for k, rc in res.calles.items():
        texto(f"SECCIONES TRANSVERSALES {k} {rc.calle.nombre}  (escala 1:1)", (X0, y + 1.0), 0.5, lay_t)
        secs = [s for s in rc.secciones if not s.omitida]
        for i, s in enumerate(secs):
            col, fil = i % cols, i // cols
            cx = X0 + col * ancho_celda + ancho_celda / 2
            base = y - (fil + 1) * alto_celda
            zmin = min(z for _, _, z in s.lineas["SUBRASANTE"]) - 0.6
            zref = math.floor(zmin * 10) / 10
            Y = lambda z: base + 0.6 + (z - zref)
            # marco y referencia
            msp.add_lwpolyline([(cx - 7.8, base), (cx + 7.8, base), (cx + 7.8, base + alto_celda - 0.2),
                                (cx - 7.8, base + alto_celda - 0.2)], close=True, dxfattribs={"layer": capa("C3D-HOJA-MARCO", 8)})
            msp.add_line((cx - 7.0, Y(zref)), (cx + 7.0, Y(zref)), dxfattribs={"layer": capa("C3D-HOJA-MARCO", 8)})
            texto(f"REF {zref:.2f}", (cx - 7.6, Y(zref) + 0.05), 0.12, lay_t)
            texto(f"{fmt_prog(s.prog)}  RAS {s.rasante:.3f}", (cx, base + alto_celda - 0.6), 0.25, lay_t,
                  al=TextEntityAlignment.CENTER)
            texto(f"Corte {s.area_corte:.2f} m2   Relleno {s.area_relleno:.2f} m2", (cx, base + 0.15), 0.16,
                  lay_t, al=TextEntityAlignment.CENTER)
            for nombre, polys in s.poligonos.items():
                lay = capa("C3D-HOJA-CAPA-" + nombre, 30)
                for poly in polys:
                    msp.add_lwpolyline([(cx + o, Y(z)) for o, z in poly], close=True, dxfattribs={"layer": lay})
            msp.add_lwpolyline([(cx + o, Y(z)) for _, o, z in s.puntos], dxfattribs={"layer": capa("C3D-HOJA-TERMINADO", 7)})
            msp.add_lwpolyline([(cx + o, Y(z)) for _, o, z in s.lineas["SUBRASANTE"]],
                               dxfattribs={"layer": capa("C3D-HOJA-SUBRASANTE", 1)})
            pt = [(cx + o, Y(z)) for o, z in s.perfil_terreno if z == z]
            if len(pt) > 1:
                msp.add_lwpolyline(pt, dxfattribs={"layer": capa("C3D-HOJA-TERRENO", 32)})
            for c, o, z in s.puntos:
                if c.startswith("PS"):
                    continue
                texto(f"{z:.3f}", (cx + o, Y(z) + 0.35), 0.09, lay_t, rot=90)
        filas = (len(secs) + cols - 1) // cols
        y -= (filas + 1) * alto_celda
        # perfil longitudinal con exageración vertical 10
        EX = 10.0
        p0, p1 = rc.alin.prog_inicial, rc.alin.prog_final
        zs = [rc.perfil.cota(p) for p in (p0, p1)] + [rc.perfil.cota(q) for q in rc.perfil.quiebres()]
        T = sum(cp.espesor for cp in proy.capas_de("calzada"))
        zb = math.floor(min(zs) - T - 1.0)
        yb = y - 40
        P = lambda p, z: (X0 + (p - p0), yb + (z - zb) * EX)
        texto(f"PERFIL LONGITUDINAL {k} {rc.calle.nombre}  (H 1:1, V x10)", (X0, yb + 45), 0.6, lay_t)
        lay_g = capa("C3D-PERFIL-GRILLA", 8)
        ztop = max(zs) + 1.5
        z = zb
        while z <= ztop + 1e-6:
            msp.add_line(P(p0, z), P(p1, z), dxfattribs={"layer": lay_g})
            texto(f"{z:.1f}", (P(p0, z)[0] - 4, P(p0, z)[1] - 0.15), 0.35, lay_g)
            z += 0.5
        p = math.ceil(p0 / 10) * 10
        while p <= p1 + 1e-6:
            msp.add_line(P(p, zb), P(p, ztop), dxfattribs={"layer": lay_g})
            texto(fmt_prog(p, 0), (P(p, zb)[0], P(p, zb)[1] - 1.2), 0.35, lay_g, rot=90,
                  al=TextEntityAlignment.MIDDLE_RIGHT)
            p += 10
        n = max(2, int(p1 - p0) + 1)
        ps = [p0 + (p1 - p0) * i / (n - 1) for i in range(n)]
        msp.add_lwpolyline([P(p, rc.perfil.cota(p)) for p in ps], dxfattribs={"layer": capa("C3D-PERFIL-RASANTE", 5)})
        msp.add_lwpolyline([P(p, rc.perfil.cota(p) - T) for p in ps], dxfattribs={"layer": capa("C3D-PERFIL-SUBRASANTE", 1)})
        if res.terreno.ok:
            pt = []
            for p in ps:
                e, nn = rc.alin.punto(p)
                zt = res.terreno.cota(e, nn)
                if zt == zt:
                    pt.append(P(p, zt))
            if len(pt) > 1:
                msp.add_lwpolyline(pt, dxfattribs={"layer": capa("C3D-PERFIL-TERRENO", 32)})
        for t in rc.perfil.tramos:
            pm = (t[0] + t[3]) / 2
            texto(f"{t[2]:+.2f}%", P(pm, rc.perfil.cota(pm) + 0.3), 0.6, capa("C3D-PERFIL-RASANTE", 5),
                  al=TextEntityAlignment.CENTER)
        for q in [p0] + rc.perfil.quiebres() + [p1]:
            texto(f"{fmt_prog(q)}  {rc.perfil.cota(q):.3f}", P(q, rc.perfil.cota(q) + 0.6), 0.4,
                  capa("C3D-PERFIL-RASANTE", 5), rot=90)
        y = yb - 15



# ------------------------------------------------------------------ Excel
def exportar_excel(res, ruta, ai=None):
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    proy = res.proyecto
    wb = Workbook()
    cab = Font(bold=True, color="FFFFFF")
    fondo = PatternFill("solid", fgColor="1A5276")

    def hoja(nombre, encabezado, filas, anchos=None, primera=False):
        ws = wb.active if primera else wb.create_sheet()
        ws.title = nombre[:31]
        ws.append(encabezado)
        for c in ws[1]:
            c.font, c.fill = cab, fondo
            c.alignment = Alignment(horizontal="center", wrap_text=True)
        for f in filas:
            ws.append(f)
        for i, h in enumerate(encabezado, start=1):
            ws.column_dimensions[get_column_letter(i)].width = (anchos or {}).get(i, max(11, min(40, len(str(h)) + 2)))
        for row in ws.iter_rows(min_row=2):
            for c in row:
                if isinstance(c.value, float):
                    c.number_format = "0.000"
        ws.freeze_panes = "A2"
        return ws

    capas_n = [cp.nombre for cp in proy.capas_de("calzada")] + ["Concreto cuneta y sardinel"] + \
              [cp.nombre for cp in proy.capas_de("vereda")]
    filas = []
    for k, rc in res.calles.items():
        filas.append([k, rc.calle.nombre, round(rc.alin.longitud, 3), rc.vol_corte, rc.vol_relleno, rc.vol_neto] +
                     [rc.materiales.get(n, 0.0) for n in capas_n])
    mt = res.materiales_total()
    filas.append(["TOTAL", "", sum(rc.alin.longitud for rc in res.calles.values()), res.total("vol_corte"),
                  res.total("vol_relleno"), res.total("vol_corte") - res.total("vol_relleno")] +
                 [mt.get(n, 0.0) for n in capas_n])
    ws = hoja("Resumen", ["Eje", "Calle", "Longitud (m)", "Corte (m3)", "Relleno (m3)", "Neto (m3)"] +
              [f"{n} (m3)" for n in capas_n], filas, {2: 18}, primera=True)
    for c in ws[ws.max_row]:
        c.font = Font(bold=True)
    hoja("Avisos", ["Nivel", "Categoría", "Eje", "Progresiva", "Mensaje"],
         [[a.nivel, a.categoria, a.eje_id, fmt_prog(a.prog) if a.prog is not None else "", a.mensaje] for a in res.avisos],
         {5: 120})
    codigos = ["PFI", "BVI", "CSI", "PSI", "FCI", "BCI", "EJE", "BCD", "FCD", "PSD", "CSD", "BVD", "PFD"]
    for k, rc in res.calles.items():
        hoja(f"Eje {k}", ["Progresiva", "Este", "Norte", "Cota rasante", "Pendiente %", "Tipo", "Nombre"],
             [[r["progresiva"], r["este"], r["norte"], r["cota"], r["pendiente"], r["tipo"], r["nombre"]]
              for r in tabla_eje(rc)])
        filas = []
        for s in rc.secciones:
            d = {c: z for c, o, z in s.puntos}
            filas.append([fmt_prog(s.prog), s.e, s.n, s.rasante] + [d.get(c, "") if not s.omitida or c == "EJE" else ""
                                                                     for c in codigos] +
                         [s.vereda_ancho.get("I", 0), s.vereda_ancho.get("D", 0)])
        hoja(f"Secciones {k}", ["Progresiva", "Este eje", "Norte eje", "Rasante"] +
             [f"{c} {descripcion_codigo(c)}" for c in codigos] + ["Vereda izq (m)", "Vereda der (m)"], filas)
        hoja(f"Puntos {k}", ["Nombre", "Progresiva", "Código", "Descripción", "Offset", "Este", "Norte", "Cota",
                             "Rasante"],
             [[p["nombre"], p["progresiva"], p["codigo"], p["descripcion"], p["offset"], p["este"], p["norte"],
               p["cota"], p["rasante"]] for p in puntos_seccion(rc)], {1: 20, 4: 28})
        hoja(f"Capas {k}", ["Capa", "Nombre", "Progresiva", "Punto", "Offset", "Este", "Norte", "Cota diseño",
                            "Lectura mira"],
             [[p["capa"], p["nombre"], p["progresiva"], p["codigo"], p["offset"], p["este"], p["norte"], p["cota"],
               p["lectura"] if p["lectura"] is not None else ""] for p in puntos_capas(rc, proy, ai)], {1: 34, 2: 22})
        filas = []
        for s in rc.secciones:
            if not s.omitida:
                filas.append([fmt_prog(s.prog), s.area_corte, s.area_relleno])
        ws = hoja(f"Tierras {k}", ["Desde", "Hasta", "Distancia", "Área corte 1", "Área corte 2", "Área relleno 1",
                                   "Área relleno 2", "Vol. corte", "Vol. relleno", "Acum. corte", "Acum. relleno"],
                  [[fmt_prog(t["desde"]), fmt_prog(t["hasta"]), t["distancia"], t["ac1"], t["ac2"], t["ar1"],
                    t["ar2"], t["vol_corte"], t["vol_relleno"], t["acum_corte"], t["acum_relleno"]]
                   for t in rc.tramos_volumen])
        ws.append([])
        ws.append(["TOTAL", "", "", "", "", "", "", rc.vol_corte, rc.vol_relleno, "Neto", rc.vol_neto])
        for c in ws[ws.max_row]:
            c.font = Font(bold=True)
            if isinstance(c.value, float):
                c.number_format = "0.000"
    if ai is not None:
        ws = wb["Resumen"]
        ws.append([])
        ws.append(["Altura instrumental usada para lecturas de mira:", ai])
    wb.save(ruta)
    return ruta


# ------------------------------------------------------------------ PDF
def exportar_pdf(res, ruta):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    from .graficos import dibujar_perfil, dibujar_planta, dibujar_seccion
    proy = res.proyecto
    capas_n = [cp.nombre for cp in proy.capas_de("calzada")] + ["Concreto cuneta y sardinel"] + \
              [cp.nombre for cp in proy.capas_de("vereda")]
    with PdfPages(ruta) as pdf:
        # portada / resumen
        fig = plt.figure(figsize=(11.69, 8.27))
        fig.text(0.05, 0.93, f"Informe de movimiento de tierras y materiales — {proy.nombre}", fontsize=16, weight="bold")
        fig.text(0.05, 0.89, f"Generado {dt.datetime.now():%d/%m/%Y %H:%M} con Corredor Simple. Método: área media "
                             f"entre secciones cada {proy.p('intervalo_secciones'):g} m + quiebres y puntos notables.",
                 fontsize=9)
        ax = fig.add_axes([0.05, 0.35, 0.9, 0.5])
        ax.axis("off")
        filas = []
        for k, rc in res.calles.items():
            filas.append([k, rc.calle.nombre, f"{rc.alin.longitud:.2f}", f"{rc.vol_corte:.2f}", f"{rc.vol_relleno:.2f}",
                          f"{rc.vol_neto:.2f}"])
        filas.append(["TOTAL", "", f"{sum(rc.alin.longitud for rc in res.calles.values()):.2f}",
                      f"{res.total('vol_corte'):.2f}", f"{res.total('vol_relleno'):.2f}",
                      f"{res.total('vol_corte') - res.total('vol_relleno'):.2f}"])
        tb = ax.table(cellText=filas, colLabels=["Eje", "Calle", "Longitud m", "Corte m³", "Relleno m³", "Neto m³"],
                      loc="upper center", cellLoc="center")
        tb.scale(1, 1.6)
        mt = res.materiales_total()
        filas = [[n] + [f"{rc.materiales.get(n, 0):.2f}" for rc in res.calles.values()] + [f"{mt.get(n, 0):.2f}"]
                 for n in capas_n]
        ax2 = fig.add_axes([0.05, 0.05, 0.9, 0.3])
        ax2.axis("off")
        tb = ax2.table(cellText=filas, colLabels=["Material (m³)"] + list(res.calles.keys()) + ["TOTAL"],
                       loc="upper center", cellLoc="center")
        tb.scale(1, 1.4)
        pdf.savefig(fig)
        plt.close(fig)
        # planta
        fig, ax = plt.subplots(figsize=(11.69, 8.27))
        dibujar_planta(ax, res)
        pdf.savefig(fig)
        plt.close(fig)
        for k, rc in res.calles.items():
            fig, ax = plt.subplots(figsize=(11.69, 8.27))
            dibujar_perfil(ax, rc, res)
            pdf.savefig(fig)
            plt.close(fig)
            secs = [s for s in rc.secciones if not s.omitida and s.tipo in ("INICIO", "QUIEBRE", "FIN", "PUERTA", "COCHERA")]
            secs = (secs or [s for s in rc.secciones if not s.omitida])[:4]
            fig, axs = plt.subplots(len(secs), 1, figsize=(11.69, 8.27), squeeze=False)
            for a_, s in zip(axs[:, 0], secs):
                dibujar_seccion(a_, s, proy, etiquetas=False)
            fig.tight_layout()
            pdf.savefig(fig)
            plt.close(fig)
            filas = [[fmt_prog(t["desde"]), fmt_prog(t["hasta"]), f"{t['distancia']:.2f}", f"{t['ac2']:.3f}",
                      f"{t['ar2']:.3f}", f"{t['vol_corte']:.2f}", f"{t['vol_relleno']:.2f}", f"{t['acum_corte']:.2f}",
                      f"{t['acum_relleno']:.2f}"] for t in rc.tramos_volumen]
            for i in range(0, max(1, len(filas)), 30):
                fig = plt.figure(figsize=(8.27, 11.69))
                fig.text(0.05, 0.96, f"Movimiento de tierras {k} {rc.calle.nombre}", fontsize=13, weight="bold")
                ax = fig.add_axes([0.03, 0.05, 0.94, 0.88])
                ax.axis("off")
                parte = filas[i:i + 30]
                if i + 30 >= len(filas):
                    parte = parte + [["TOTAL", "", "", "", "", f"{rc.vol_corte:.2f}", f"{rc.vol_relleno:.2f}",
                                      "Neto", f"{rc.vol_neto:.2f}"]]
                tb = ax.table(cellText=parte, colLabels=["Desde", "Hasta", "Dist.", "A. corte", "A. relleno",
                                                         "V. corte", "V. relleno", "Acum. C", "Acum. R"],
                              loc="upper center", cellLoc="center")
                tb.auto_set_font_size(False)
                tb.set_fontsize(8)
                tb.scale(1, 1.35)
                pdf.savefig(fig)
                plt.close(fig)
        # avisos
        fig = plt.figure(figsize=(11.69, 8.27))
        fig.text(0.04, 0.95, "Avisos de revisión", fontsize=14, weight="bold")
        y = 0.91
        for a in res.avisos[:45]:
            col = {"ERROR": "#c0392b", "AVISO": "#b9770e"}.get(a.nivel, "#1e8449")
            fig.text(0.04, y, a.texto()[:190], fontsize=7, color=col)
            y -= 0.019
        pdf.savefig(fig)
        plt.close(fig)
    return ruta


def exportar_todo(res, carpeta, ai=None, formatos=("csv", "landxml", "dxf", "excel", "pdf")):
    c = Path(carpeta)
    c.mkdir(parents=True, exist_ok=True)
    salida = []
    if "csv" in formatos:
        salida += exportar_csv(res, c / "csv", ai)
    if "landxml" in formatos:
        salida.append(exportar_landxml(res, c / "corredor_civil3d.xml"))
    if "dxf" in formatos:
        salida.append(exportar_dxf(res, c / "corredor_civil3d.dxf"))
    if "excel" in formatos:
        salida.append(exportar_excel(res, c / "informe.xlsx", ai))
    if "pdf" in formatos:
        salida.append(exportar_pdf(res, c / "informe.pdf"))
    return salida
