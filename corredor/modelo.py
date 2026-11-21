"""Estructuras de datos del proyecto y parámetros por defecto.

Todos los valores normativos son parámetros editables (seccion_tipica.csv);
aquí solo están los valores de arranque si el archivo no los trae.
"""
from dataclasses import dataclass, field

# nombre: (valor por defecto, unidad, descripción)
PARAMETROS = {
    "num_carriles": (2, "-", "Número de carriles (informativo)"),
    "cuneta_ancho": (40.0, "cm", "Cuneta básica: ancho (solo geométrica, sin diseño hidráulico)"),
    "cuneta_profundidad": (10.0, "cm", "Cuneta básica: profundidad bajo el borde de calzada"),
    "baden_ancho": (80.0, "cm", "Badén (cuneta Tipo II) en cruces: cruza la calle secundaria en línea con la cuneta de la principal; 0 = sin badén"),
    "baden_profundidad": (7.0, "cm", "Badén: flecha de la V (cuánto baja en el centro)"),
    "baden_espesor": (22.0, "cm", "Badén: espesor del concreto en los bordes"),
    "radio_esquina": (300.0, "cm", "Radio de las esquinas en la cara del sardinel (0 = esquinas en ángulo, sin pieza de esquina)"),
    "rampa_rebaje": (12.0, "cm", "Rampas de esquina: cuánto baja la vereda en el descanso (0 = sin rampas)"),
    "rampa_largo": (100.0, "cm", "Rampas de esquina: largo de cada rampa (12 %)"),
    "rampa_descanso": (100.0, "cm", "Rampas de esquina: largo del descanso entre las dos rampas"),
    "sardinel_ancho": (15.0, "cm", "Ancho de la cara superior del sardinel"),
    "sardinel_altura": (15.0, "cm", "Desnivel entre borde de calzada y vereda terminada"),
    "vereda_pendiente": (2.0, "%", "Pendiente transversal de vereda, cae hacia la calzada"),
    "intervalo_secciones": (10.0, "m", "Intervalo entre secciones de cálculo"),
    "variacion_area_max": (25.0, "%", "Si el corte o relleno cambia más que esto entre dos secciones, se agrega una intermedia (0 = no)"),
    "intervalo_min_secciones": (2.5, "m", "Separación mínima al agregar secciones intermedias"),
    "pendiente_long_max": (8.0, "%", "PARÁMETRO A CONFIRMAR con norma/expediente"),
    "pendiente_long_min": (0.5, "%", "PARÁMETRO A CONFIRMAR con norma/expediente"),
    "vereda_ancho_min": (120.0, "cm", "PARÁMETRO A CONFIRMAR con norma/expediente"),
    "tolerancia_fachada": (5.0, "cm", "Si la vereda disponible es menor que la de diseño en más de esto, se avisa"),
    "busqueda_fachada": (10.0, "m", "Distancia máxima desde el borde de vereda para buscar la fachada"),
    "modo_fachada": ("recortar", "-", "recortar = ajusta la vereda al ancho disponible; avisar = solo avisa"),
    "paso_terreno": (0.10, "m", "Paso de muestreo del terreno en cada sección (corte/relleno)"),
    "arista_max_tin": (25.0, "m", "Lado máximo de triángulo del terreno (evita triángulos falsos)"),
}

TEXTO = {"modo_fachada"}


@dataclass
class Calle:
    eje_id: str
    nombre: str
    bombeo_pct: float = 2.0
    ancho_calzada: float = 7.20
    ancho_vereda: float = 1.50
    vertices: list = field(default_factory=list)      # [(este, norte), ...]
    prog_inicial: float = 0.0
    tramos: list = field(default_factory=list)         # [(prog_ini, cota_ini, pend_pct, prog_fin), ...]

    @property
    def corto(self):
        """Código corto para nombres de puntos: EJE-01 -> E1."""
        dig = "".join(ch for ch in self.eje_id if ch.isdigit())
        return f"E{int(dig)}" if dig else self.eje_id[:3]


@dataclass
class Capa:
    ambito: str          # "calzada" o "vereda"
    orden: int           # 1 = la de arriba
    nombre: str
    espesor_cm: float

    @property
    def espesor(self):
        return self.espesor_cm / 100.0


@dataclass
class LineaFachada:
    linea_id: str
    eje_id: str
    lado: str            # IZQ / DER
    tipo: str
    puntos: list = field(default_factory=list)


@dataclass
class Umbral:
    id: str
    eje_id: str
    lado: str
    este: float
    norte: float
    cota: float
    ancho: float
    tipo: str            # PUERTA / COCHERA


@dataclass
class TramoCuneta:
    eje_id: str
    lado: str            # AMBOS / IZQ / DER
    prog_ini: float
    prog_fin: float
    ancho_cm: float
    profundidad_cm: float
    nota: str = ""


@dataclass
class PuntoTerreno:
    numero: str
    este: float
    norte: float
    cota: float
    codigo: str


@dataclass
class BM:
    id: str
    este: float
    norte: float
    cota: float
    descripcion: str = ""


@dataclass
class Proyecto:
    nombre: str = "Proyecto"
    calles: list = field(default_factory=list)
    capas: list = field(default_factory=list)
    parametros: dict = field(default_factory=lambda: {k: v[0] for k, v in PARAMETROS.items()})
    cunetas: list = field(default_factory=list)
    fachadas: list = field(default_factory=list)
    umbrales: list = field(default_factory=list)
    terreno: list = field(default_factory=list)
    bms: list = field(default_factory=list)
    codigos_alias: dict = field(default_factory=dict)   # códigos propios del topógrafo -> manual

    def capas_de(self, ambito):
        return sorted([c for c in self.capas if c.ambito == ambito], key=lambda c: c.orden)

    def calle(self, eje_id):
        for c in self.calles:
            if c.eje_id == eje_id:
                return c
        return None

    def p(self, nombre):
        return self.parametros.get(nombre, PARAMETROS[nombre][0])


@dataclass
class Aviso:
    nivel: str           # ERROR / AVISO / INFO
    categoria: str
    eje_id: str
    prog: float | None
    mensaje: str

    def texto(self):
        from .geometria import fmt_prog
        pr = f" {fmt_prog(self.prog)}" if self.prog is not None else ""
        return f"[{self.nivel}] {self.categoria} {self.eje_id}{pr}: {self.mensaje}"
