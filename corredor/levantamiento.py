"""Interpretación del levantamiento codificado.

Entrada: lista de puntos (número, Este, Norte, cota, código) tal como sale de la estación total.
Salida: terreno, líneas de fachada/muro/límite, puertas, cocheras, elementos y BM.
"""
import math
import re
from dataclasses import dataclass, field

from .modelo import BM, Elemento, LineaFachada, PuntoTerreno, Umbral


@dataclass
class Interpretacion:
    terreno: list = field(default_factory=list)
    lineas: list = field(default_factory=list)
    puertas: list = field(default_factory=list)
    cocheras: list = field(default_factory=list)
    elementos: list = field(default_factory=list)
    bms: list = field(default_factory=list)
    avisos: list = field(default_factory=list)      # textos
    conteo: dict = field(default_factory=dict)      # código del catálogo -> cantidad
    desconocidos: dict = field(default_factory=dict)
    clase: dict = field(default_factory=dict)       # número de punto -> código del catálogo (o '?')


def _num_orden(numero):
    """Orden natural de números de punto ('12' < '100', 'A5' después)."""
    m = re.match(r"^(\D*)(\d+)(.*)$", str(numero))
    if m:
        return (m.group(1), int(m.group(2)), m.group(3))
    return (str(numero), 0, "")


def interpretar(puntos, catalogo, separacion_max=30.0):
    it = Interpretacion()
    orden = sorted(puntos, key=lambda p: _num_orden(p.numero))
    grupos_linea = {}
    cocheras_i, cocheras_f = [], []
    for p in orden:
        c, tok, num, nota = catalogo.interpretar(p.codigo)
        if c is None:
            it.desconocidos[tok or "(vacío)"] = it.desconocidos.get(tok or "(vacío)", 0) + 1
            it.terreno.append(p)
            it.clase[p.numero] = "?"
            continue
        it.conteo[c.codigo] = it.conteo.get(c.codigo, 0) + 1
        it.clase[p.numero] = c.codigo
        if c.terreno:
            it.terreno.append(p)
        if c.tipo == "LINEA":
            grupos_linea.setdefault(c.codigo + num, (c, []))[1].append(p)
        elif c.tipo == "PUERTA":
            it.puertas.append(Umbral(f"{c.codigo}-{p.numero}", "", "", p.este, p.norte, p.cota, 1.0, "PUERTA",
                                     nota=nota))
        elif c.tipo == "COCHERA":
            (cocheras_i if c.codigo.endswith("I") or "INI" in c.nombre.upper() or c.codigo == "COI"
             else cocheras_f).append((p, num, nota))
        elif c.tipo == "ELEMENTO":
            it.elementos.append(Elemento(p.numero, tok, c.codigo, c.nombre, c.regla, p.este, p.norte, p.cota, nota))
        elif c.tipo == "BM":
            n = int(num) if num.isdigit() else None
            it.bms.append((n, p, nota))

    # ---- líneas
    for clave, (c, pts) in grupos_linea.items():
        tramo = [pts[0]]
        k = 1
        for a, b in zip(pts[:-1], pts[1:]):
            if math.hypot(b.este - a.este, b.norte - a.norte) > separacion_max:
                if len(tramo) >= 2:
                    it.lineas.append(_linea(clave, k, c, tramo))
                    k += 1
                else:
                    it.avisos.append(f"Punto {tramo[0].numero} ({clave}) quedó solo: no forma línea.")
                tramo = [b]
            else:
                tramo.append(b)
        if len(tramo) >= 2:
            it.lineas.append(_linea(clave, k, c, tramo))
        elif tramo:
            it.avisos.append(f"Punto {tramo[0].numero} ({clave}) quedó solo: no forma línea.")

    # ---- cocheras: cada inicio con el fin más próximo en numeración (o con el mismo número de etiqueta)
    usados = set()
    for p, num, nota in cocheras_i:
        cand = [(q, n2, nt) for q, n2, nt in cocheras_f if id(q) not in usados and (not num or n2 == num)]
        cand = [x for x in cand if math.hypot(x[0].este - p.este, x[0].norte - p.norte) <= 10.0]
        if not cand:
            it.avisos.append(f"Cochera: el punto {p.numero} (inicio) no tiene su punto final COF cerca (10 m).")
            continue
        q = min(cand, key=lambda x: (abs(_num_orden(x[0].numero)[1] - _num_orden(p.numero)[1]),
                                     math.hypot(x[0].este - p.este, x[0].norte - p.norte)))[0]
        usados.add(id(q))
        ancho = math.hypot(q.este - p.este, q.norte - p.norte)
        it.cocheras.append(Umbral(f"CO-{p.numero}/{q.numero}", "", "", (p.este + q.este) / 2, (p.norte + q.norte) / 2,
                                  (p.cota + q.cota) / 2, ancho, "COCHERA",
                                  extremos=[(p.este, p.norte, p.cota), (q.este, q.norte, q.cota)], nota=nota))
    for q, _, _ in cocheras_f:
        if id(q) not in usados:
            it.avisos.append(f"Cochera: el punto {q.numero} (fin) no tiene su punto de inicio COI.")

    # ---- BM numerados
    libres = 1
    tomados = {n for n, _, _ in it.bms if n is not None}
    bms = []
    for n, p, nota in it.bms:
        if n is None:                 # "BM" sin número: se le da el siguiente libre
            while libres in tomados:
                libres += 1
            n = libres
            tomados.add(n)
        bms.append(BM(f"BM-{n:02d}", p.este, p.norte, p.cota, nota or "", punto=str(p.numero)))
    vistos = {}
    for b in bms:
        if b.id in vistos:
            it.avisos.append(f"{b.id} aparece dos veces (puntos {vistos[b.id]} y {b.punto}).")
        vistos[b.id] = b.punto
    it.bms = sorted(bms, key=lambda b: b.id)
    for k, v in it.desconocidos.items():
        it.avisos.append(f"Código '{k}' no está en el catálogo ({v} puntos): se tomó como terreno.")
    return it


def _linea(clave, k, c, pts):
    lid = f"{clave}" if k == 1 else f"{clave}.{k}"
    return LineaFachada(lid, "", "", c.codigo, [(p.este, p.norte, c.codigo) for p in pts],
                        cotas=[p.cota for p in pts], numeros=[p.numero for p in pts])


def aplicar(proy, it):
    """Pasa la interpretación al proyecto."""
    proy.terreno = it.terreno
    proy.fachadas = it.lineas
    proy.umbrales = it.puertas + it.cocheras
    proy.elementos = it.elementos
    proy.bms = it.bms
    proy.avisos_levantamiento = it.avisos
    return proy


def puntos_a_terreno(filas):
    return [PuntoTerreno(str(f[0]), float(f[1]), float(f[2]), float(f[3]), f[4] if len(f) > 4 else "") for f in filas]
