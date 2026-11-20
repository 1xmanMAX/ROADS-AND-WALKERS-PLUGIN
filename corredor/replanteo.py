"""Tablas de replanteo: eje, puntos de la sección y puntos por capa con lectura de mira.

Lectura teórica de mira:
    AI (altura del instrumento) = cota del BM + lectura atrás
    lectura = AI − cota de diseño
Ejemplo: BM-01 = 3821.316, lectura atrás 1.425 -> AI = 3822.741.
         Losa en el eje 0+050 (3821.250) -> lectura 3822.741 − 3821.250 = 1.491
"""
from .geometria import fmt_prog, fmt_prog_corto

NOMBRES_PUNTO = {
    "EJE": "Eje", "BC": "Borde de calzada", "FC": "Fondo de cuneta", "PS": "Pie de sardinel",
    "CS": "Cabeza de sardinel", "BV": "Borde interior de vereda", "PF": "Borde de vereda / pie de fachada",
    "LI": "Borde de capa izq.", "LD": "Borde de capa der.",
}


def descripcion_codigo(cod):
    base = cod[:-1] if cod not in ("EJE",) and cod[-1] in "ID" else cod
    lado = {"I": " izq.", "D": " der."}.get(cod[-1], "") if cod != "EJE" else ""
    return NOMBRES_PUNTO.get(base, base) + lado


def nombre_punto(calle, prog, codigo, capa=""):
    partes = [calle.corto, fmt_prog_corto(prog)]
    if capa:
        partes.append(capa)
    partes.append(codigo)
    return "-".join(partes)


def tabla_eje(rc):
    """Progresiva, Este, Norte, cota de rasante (todas las progresivas calculadas)."""
    filas = []
    for s in rc.secciones:
        filas.append({"eje_id": rc.calle.eje_id, "prog": s.prog, "progresiva": fmt_prog(s.prog),
                      "este": s.e, "norte": s.n, "cota": s.rasante, "pendiente": s.pendiente, "tipo": s.tipo,
                      "nombre": nombre_punto(rc.calle, s.prog, "EJE")})
    return filas


def puntos_seccion(rc):
    """Puntos de la superficie terminada en cada sección."""
    filas = []
    for s in rc.secciones:
        lista = s.puntos if not s.omitida else [p for p in s.puntos if p[0] == "EJE"]
        for cod, o, z in lista:
            e, n = s.xy(o)
            filas.append({"eje_id": rc.calle.eje_id, "prog": s.prog, "progresiva": fmt_prog(s.prog),
                          "codigo": cod, "descripcion": descripcion_codigo(cod), "offset": o,
                          "este": e, "norte": n, "cota": z, "rasante": s.rasante,
                          "nombre": nombre_punto(rc.calle, s.prog, cod), "capa": "TERMINADO"})
    return filas


def capas_replanteo(proy):
    """Lista (prefijo, nombre, línea) de superficies a replantear, de arriba hacia abajo."""
    out = []
    for k, cp in enumerate(proy.capas_de("calzada"), start=1):
        out.append((f"C{k}", f"Tope de {cp.nombre}", f"C{k}_TOPE"))
    out.append(("SR", "Subrasante (fondo de excavación)", "SUBRASANTE"))
    for k, cp in enumerate(proy.capas_de("vereda"), start=1):
        out.append((f"V{k}", f"Tope de {cp.nombre}", f"V{k}_TOPE"))
    return out


def puntos_capas(rc, proy, ai=None):
    """Puntos por capa con lectura teórica de mira (si se da la altura instrumental)."""
    filas = []
    for pref, nombre, linea in capas_replanteo(proy):
        for s in rc.secciones:
            if s.omitida:
                continue
            if linea.startswith("V"):
                pts = s.lineas.get(linea + "_I", []) + s.lineas.get(linea + "_D", [])
            elif linea == "SUBRASANTE":
                pts = [p for p in s.lineas["SUBRASANTE"] if p[0] in ("EJE", "SBCI", "SBCD")]
            else:
                pts = [p for p in s.lineas.get(linea, []) if p[0] in ("EJE", "BCI", "BCD")]
            for cod, o, z in pts:
                e, n = s.xy(o)
                filas.append({"eje_id": rc.calle.eje_id, "capa": nombre, "prefijo": pref, "prog": s.prog,
                              "progresiva": fmt_prog(s.prog), "codigo": cod, "offset": o, "este": e,
                              "norte": n, "cota": z, "lectura": (ai - z) if ai is not None else None,
                              "nombre": nombre_punto(rc.calle, s.prog, cod, pref)})
    return filas
