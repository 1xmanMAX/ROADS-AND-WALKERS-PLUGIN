"""Catálogo de códigos (etiquetas) del levantamiento.

En campo, cada punto lleva un código corto. La app interpreta el código así:

  * Se toma la PRIMERA palabra del código: "CA1 casa verde" -> código "CA1", nota "casa verde".
  * Letras + número opcional: "CA1" -> tipo CA, línea 1.   "BM3" -> BM número 3.
  * Si las letras no están en el catálogo se busca el prefijo más largo que sí esté.

Tipos de código:
  TERRENO  : solo forma la superficie del terreno.
  LINEA    : puntos que se unen en orden de número formando una línea (fachadas, muros, límites).
             Puntos con el mismo código (incluido el número) forman la misma línea; la línea se corta
             si dos puntos seguidos están a más de 'separacion_max_linea' o si cruzan un eje de calle.
  PUERTA   : un punto en el umbral de la puerta (su cota es la cota del umbral).
  COCHERA  : dos puntos, inicio (COI) y fin (COF) del portón; su cota es la del umbral.
  ELEMENTO : objetos sueltos (buzón, poste, árbol...). 'regla' dice qué revisar.
  BM       : punto de control. "BM1", "BM2"... se numeran BM-01, BM-02...

Reglas de revisión de ELEMENTOS:
  nivelar   : tapa/caja que debe quedar a la cota del diseño (buzón, cajas): se calcula cuánto subir/bajar.
  obstaculo : objeto fijo que no debe quedar en calzada, cuneta ni sardinel; en vereda reduce el paso.
  ninguna   : solo se dibuja.
"""
import csv
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Codigo:
    codigo: str
    nombre: str
    tipo: str            # TERRENO / LINEA / PUERTA / COCHERA / ELEMENTO / BM
    terreno: bool        # el punto se usa para la superficie del terreno
    color: str
    simbolo: str         # marcador de matplotlib
    regla: str = "ninguna"
    uso: str = ""


CATALOGO_DEFECTO = [
    Codigo("TN", "Terreno natural", "TERRENO", True, "#8d6e63", ".", "ninguna", "Puntos sueltos del terreno, cada 10-20 m"),
    Codigo("EJ", "Eje de camino existente", "TERRENO", True, "#5d4037", "+", "ninguna", "Centro del camino actual"),
    Codigo("BC", "Borde de camino existente", "TERRENO", True, "#a1887f", "x", "ninguna", "Borde del camino actual"),
    Codigo("VE", "Vereda existente", "TERRENO", True, "#bcaaa4", ".", "ninguna", "Vereda que ya existe (nivel)"),
    Codigo("CA", "Casa (fachada)", "LINEA", True, "#c0392b", "s", "ninguna",
           "Esquinas y quiebres de la fachada al pie del muro. CA1, CA2... una línea por manzana o casa"),
    Codigo("MU", "Muro / cerco", "LINEA", True, "#e67e22", "s", "ninguna", "Cerco o muro de propiedad. MU1, MU2..."),
    Codigo("LP", "Límite de propiedad (lote sin construir)", "LINEA", True, "#d4ac0d", "s", "ninguna",
           "Límite de lote vacío o terreno sin cerco. LP1, LP2..."),
    Codigo("PU", "Puerta", "PUERTA", False, "#8e44ad", "D", "ninguna", "Un punto al centro del umbral de la puerta"),
    Codigo("COI", "Cochera: inicio del portón", "COCHERA", False, "#2471a3", ">", "ninguna",
           "Primer extremo del portón de cochera, a la altura del umbral"),
    Codigo("COF", "Cochera: fin del portón", "COCHERA", False, "#2471a3", "<", "ninguna",
           "Segundo extremo del portón (tomar justo después del COI)"),
    Codigo("BZ", "Buzón (tapa)", "ELEMENTO", False, "#117a65", "o", "nivelar", "Centro de la tapa del buzón"),
    Codigo("CAG", "Caja de agua / medidor", "ELEMENTO", False, "#2e86c1", "p", "nivelar", "Centro de la tapa"),
    Codigo("CDE", "Caja de registro de desagüe", "ELEMENTO", False, "#148f77", "p", "nivelar", "Centro de la tapa"),
    Codigo("CLZ", "Caja de luz / telefonía", "ELEMENTO", False, "#d68910", "p", "nivelar", "Centro de la tapa"),
    Codigo("PO", "Poste", "ELEMENTO", False, "#212f3d", "P", "obstaculo", "Centro del poste al pie"),
    Codigo("AR", "Árbol", "ELEMENTO", False, "#1e8449", "*", "obstaculo", "Centro del tronco al pie"),
    Codigo("GR", "Grifo contra incendio", "ELEMENTO", False, "#cb4335", "h", "obstaculo", "Centro del grifo"),
    Codigo("SEN", "Señal / letrero", "ELEMENTO", False, "#7f8c8d", "^", "obstaculo", "Pie del poste de la señal"),
    Codigo("BM", "BM (punto de control)", "BM", False, "#6c3483", "^", "ninguna",
           "BM1, BM2... sobre el hito; la cota del punto es la cota del BM"),
]

TIPOS = ("TERRENO", "LINEA", "PUERTA", "COCHERA", "ELEMENTO", "BM")
REGLAS = ("ninguna", "nivelar", "obstaculo")


def separar_codigo(texto):
    """'ca1 casa verde' -> ('CA1', 'CA', '1', 'casa verde')."""
    texto = (texto or "").strip()
    partes = texto.split(None, 1)
    tok = partes[0].upper() if partes else ""
    nota = partes[1] if len(partes) > 1 else ""
    m = re.match(r"^([A-ZÑ_]+)-?(\d*)$", tok)
    if m:
        return tok, m.group(1), m.group(2), nota
    return tok, tok, "", nota


class Catalogo:
    def __init__(self, codigos=None):
        self.codigos = list(codigos or [Codigo(**c.__dict__) for c in CATALOGO_DEFECTO])

    def __iter__(self):
        return iter(self.codigos)

    def __len__(self):
        return len(self.codigos)

    def buscar(self, letras):
        """Código del catálogo para las letras dadas (prefijo más largo)."""
        mapa = {c.codigo: c for c in self.codigos}
        if letras in mapa:
            return mapa[letras]
        for n in range(len(letras) - 1, 0, -1):
            if letras[:n] in mapa:
                return mapa[letras[:n]]
        return None

    def interpretar(self, texto):
        """Devuelve (Codigo o None, código completo, número, nota)."""
        tok, letras, num, nota = separar_codigo(texto)
        c = self.buscar(letras)
        if c is not None and letras != c.codigo:
            # prefijo: el resto de letras pasa a formar parte del número de línea (ej. 'CAX')
            num = letras[len(c.codigo):] + num
        return c, tok, num, nota


def leer_catalogo(ruta):
    filas = []
    with open(ruta, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            r = {k.strip().lower(): (v or "").strip() for k, v in r.items()}
            filas.append(Codigo(r["codigo"].upper(), r.get("nombre", ""), r.get("tipo", "TERRENO").upper(),
                                r.get("terreno", "no").lower() in ("si", "sí", "1", "true", "s"),
                                r.get("color", "#888888") or "#888888", r.get("simbolo", "o") or "o",
                                r.get("regla", "ninguna") or "ninguna", r.get("uso", "")))
    return Catalogo(filas)


def guardar_catalogo(cat, ruta):
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["codigo", "nombre", "tipo", "terreno", "color", "simbolo", "regla", "uso"])
        for c in cat:
            w.writerow([c.codigo, c.nombre, c.tipo, "si" if c.terreno else "no", c.color, c.simbolo, c.regla, c.uso])


def catalogo_en(carpeta):
    r = Path(carpeta) / "codigos.csv"
    return leer_catalogo(r) if r.exists() else Catalogo()
