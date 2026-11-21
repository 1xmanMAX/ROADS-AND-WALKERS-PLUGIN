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
    "sardinel_ancho": (15.0, "cm", "Ancho de la cara superior del sardinel"),
    "sardinel_altura": (15.0, "cm", "Desnivel entre borde de calzada y vereda terminada"),
    "vereda_pendiente": (2.0, "%", "Pendiente transversal de vereda, cae hacia la calzada"),
    "intervalo_secciones": (10.0, "m", "Intervalo entre secciones de cálculo"),
    "pendiente_long_max": (8.0, "%", "PARÁMETRO A CONFIRMAR con norma/expediente"),
    "pendiente_long_min": (0.5, "%", "PARÁMETRO A CONFIRMAR con norma/expediente"),
    "vereda_ancho_min": (120.0, "cm", "PARÁMETRO A CONFIRMAR con norma/expediente"),
    "tolerancia_fachada": (5.0, "cm", "Si la vereda disponible es menor que la de diseño en más de esto, se avisa"),
    "busqueda_fachada": (10.0, "m", "Distancia máxima desde el borde de vereda para buscar la fachada"),
    "modo_fachada": ("recortar", "-", "recortar = ajusta la vereda al ancho disponible; avisar = solo avisa"),
    "paso_terreno": (0.10, "m", "Paso de muestreo del terreno en cada sección (corte/relleno)"),
    "arista_max_tin": (25.0, "m", "Lado máximo de triángulo del terreno (evita triángulos falsos)"),
    "separacion_max_linea": (30.0, "m", "Distancia máxima entre dos puntos seguidos de una misma línea (CA, MU, LP)"),
    "busqueda_elementos": (15.0, "m", "Distancia máxima al eje para asignar puertas y elementos a una calle"),
    "esponjamiento": (25.0, "%", "Esponjamiento del material de corte al eliminarlo (A CONFIRMAR según suelo)"),
    "contraccion_relleno": (15.0, "%", "Material extra para relleno compactado (A CONFIRMAR según material)"),
    "reutilizacion_corte": (0.0, "%", "Parte del corte que se reutiliza como relleno (0 = todo se elimina)"),
    "tolerancia_tapas": (2.0, "cm", "Tapas de buzón/cajas dentro de esta diferencia se consideran a nivel"),
    "paso_libre_min": (90.0, "cm", "Paso libre mínimo en vereda junto a postes/árboles (A CONFIRMAR, A.120)"),
    "pendiente_rampa_max": (12.0, "%", "Pendiente máxima de rampa de cochera en vereda (A CONFIRMAR)"),
    "rebaje_sardinel": (3.0, "cm", "Altura del sardinel rebajado frente a cocheras sobre el borde de calzada"),
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
    eje_id: str          # puede quedar vacío: la línea vale para cualquier calle
    lado: str            # IZQ / DER / "" (automático)
    tipo: str
    puntos: list = field(default_factory=list)   # [(este, norte, tipo)]
    cotas: list = field(default_factory=list)    # cota de cada punto (si viene del levantamiento)
    numeros: list = field(default_factory=list)  # número de punto de cada vértice


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
    extremos: list = field(default_factory=list)   # cochera: [(e, n, z), (e, n, z)]
    nota: str = ""


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
class Elemento:
    id: str              # número de punto
    codigo: str          # código completo (ej. BZ, PO3)
    tipo_codigo: str     # código del catálogo (BZ, PO...)
    nombre: str
    regla: str           # nivelar / obstaculo / ninguna
    este: float
    norte: float
    cota: float
    nota: str = ""


@dataclass
class BM:
    id: str
    este: float
    norte: float
    cota: float
    descripcion: str = ""
    punto: str = ""


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
    levantamiento: list = field(default_factory=list)   # todos los puntos con su código
    catalogo: object = None
    elementos: list = field(default_factory=list)
    avisos_levantamiento: list = field(default_factory=list)

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
