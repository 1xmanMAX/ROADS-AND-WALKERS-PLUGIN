"""Ventana principal de Corredor Simple (Tkinter).

Pestañas:
  1 Levantamiento   2 Calles y ejes   3 Sección y capas   4 Revisión   5 Interferencias
  6 Movimiento de tierras   7 Puntos y BM   8 Exportar
"""
import math
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, simpledialog, ttk

import matplotlib

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from . import __version__  # noqa: E402
from .codigos import REGLAS, TIPOS, Catalogo, Codigo  # noqa: E402
from .datos import (DatoError, guardar_proyecto, leer_proyecto, leer_terreno, reinterpretar,  # noqa: E402
                    validar_proyecto)
from .exportar import altura_instrumento, exportar_todo  # noqa: E402
from .geometria import Alineamiento, Perfil, fmt_prog  # noqa: E402
from .graficos import (dibujar_3d, dibujar_perfil, dibujar_planta, dibujar_seccion,  # noqa: E402
                       dibujar_tierras)
from .modelo import PARAMETROS, TEXTO, Calle, Capa, Proyecto, TramoCuneta  # noqa: E402
from .motor import calcular  # noqa: E402
from .replanteo import puntos_capas, puntos_seccion  # noqa: E402
from .seccion import construir  # noqa: E402
from .terreno import Terreno  # noqa: E402

AZUL = "#1a5276"
FONDO = "#f4f6f7"
NIVEL_FG = {"ERROR": "#c0392b", "AVISO": "#b9770e", "INFO": "#1e8449"}
GRUPOS_PARAM = {
    "Sección": ["cuneta_ancho", "cuneta_profundidad", "sardinel_ancho", "sardinel_altura", "vereda_pendiente",
                "intervalo_secciones", "num_carriles"],
    "Fachadas y elementos": ["modo_fachada", "tolerancia_fachada", "busqueda_fachada", "separacion_max_linea",
                             "busqueda_elementos", "tolerancia_tapas", "rebaje_sardinel"],
    "Normativa (confirmar)": ["pendiente_long_max", "pendiente_long_min", "vereda_ancho_min", "paso_libre_min",
                              "pendiente_rampa_max"],
    "Tierras": ["esponjamiento", "contraccion_relleno", "reutilizacion_corte", "paso_terreno", "arista_max_tin"],
}


def recurso(rel):
    base = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)
    return Path(base) / rel


def numero(txt):
    txt = str(txt).strip().replace(",", ".")
    if txt.count("+") == 1 and txt.replace("+", "").replace(".", "").replace("-", "").isdigit():
        km, m = txt.split("+")
        return float(km) * 1000 + float(m)
    return float(txt)


def f3(v):
    return "" if v is None else f"{v:.3f}"


# ------------------------------------------------------------------ tabla editable
class Tabla(ttk.Frame):
    """Treeview con edición por doble clic, filas alternadas y colores por etiqueta."""

    def __init__(self, master, columnas, anchos=None, al_editar=None, editable=None, alto=8, al_doble=None,
                 opciones=None):
        super().__init__(master)
        self.al_editar = al_editar
        self.al_doble = al_doble
        self.opciones = opciones or {}       # columna -> lista de valores (combo)
        self.editable = editable if editable is not None else set(range(len(columnas)))
        self.tree = ttk.Treeview(self, show="headings", height=alto, selectmode="browse")
        self.poner_columnas(columnas, anchos)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        sx = ttk.Scrollbar(self, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=sb.set, xscrollcommand=sx.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        sx.grid(row=1, column=0, sticky="ew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.tree.bind("<Double-1>", self._doble)
        self.tree.tag_configure("par", background="#f8f9f9")
        for k, v in NIVEL_FG.items():
            self.tree.tag_configure(k, foreground=v)

    def poner_columnas(self, columnas, anchos=None):
        self.columnas = columnas
        self.tree.configure(columns=[f"c{i}" for i in range(len(columnas))])
        for i, c in enumerate(columnas):
            self.tree.heading(f"c{i}", text=c)
            self.tree.column(f"c{i}", width=(anchos or {}).get(i, 95), anchor="center", stretch=True)

    def cargar(self, filas, tags=None):
        self.tree.delete(*self.tree.get_children())
        for i, f in enumerate(filas):
            t = [tags[i]] if tags and tags[i] else []
            if i % 2:
                t.append("par")
            self.tree.insert("", "end", iid=str(i), values=["" if v is None else v for v in f], tags=t)

    def seleccion(self):
        s = self.tree.selection()
        return int(s[0]) if s else None

    def seleccionar(self, i):
        if str(i) in self.tree.get_children():
            self.tree.selection_set(str(i))
            self.tree.see(str(i))

    def _doble(self, ev):
        if self.tree.identify_region(ev.x, ev.y) != "cell":
            return
        fila = self.tree.identify_row(ev.y)
        col = int(self.tree.identify_column(ev.x)[1:]) - 1
        if self.al_editar is None or col not in self.editable:
            if self.al_doble:
                self.al_doble(int(fila))
            return
        x, y, w, h = self.tree.bbox(fila, f"c{col}")
        valor = self.tree.set(fila, f"c{col}")
        if col in self.opciones:
            e = ttk.Combobox(self.tree, values=self.opciones[col], state="readonly")
            e.set(valor)
        else:
            e = ttk.Entry(self.tree)
            e.insert(0, valor)
            e.select_range(0, "end")
        e.place(x=x, y=y, width=max(w, 80), height=h)
        e.focus_set()
        hecho = {"v": False}

        def fin(guardar):
            if hecho["v"]:
                return
            hecho["v"] = True
            nuevo = e.get()
            e.destroy()
            if guardar and nuevo != valor:
                try:
                    self.al_editar(int(fila), col, nuevo)
                except (ValueError, DatoError, IndexError) as err:
                    messagebox.showerror("Dato no válido", f"'{nuevo}': {err}")

        e.bind("<Return>", lambda _: fin(True))
        e.bind("<KP_Enter>", lambda _: fin(True))
        e.bind("<Escape>", lambda _: fin(False))
        e.bind("<FocusOut>", lambda _: fin(True))
        if isinstance(e, ttk.Combobox):
            e.bind("<<ComboboxSelected>>", lambda _: fin(True))


class Lienzo(ttk.Frame):
    """Figura de matplotlib con barra de herramientas."""

    def __init__(self, master, figsize=(8, 6), barra=True):
        super().__init__(master)
        self.fig = Figure(figsize=figsize, dpi=96)
        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        if barra:
            tb = NavigationToolbar2Tk(self.canvas, self, pack_toolbar=False)
            tb.update()
            tb.pack(side="bottom", fill="x")
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def limpiar(self):
        self.fig.clear()

    def dibujar(self):
        try:
            self.fig.tight_layout()
        except Exception:
            pass
        self.canvas.draw_idle()


# ------------------------------------------------------------------ aplicación
class App(tk.Tk):
    def __init__(self, carpeta=None):
        super().__init__()
        self.title(f"Corredor Simple {__version__} — diseño de pistas y veredas")
        self.geometry("1560x960")
        self.minsize(1180, 720)
        self.configure(bg=FONDO)
        self._estilos()
        self.proy = Proyecto(catalogo=Catalogo())
        self.carpeta = None
        self.res = None
        self._tin = None
        self.modo_eje = False
        self._construir()
        self.bind("<F5>", lambda _: self.calcular())
        if carpeta:
            self.abrir(carpeta)

    def _estilos(self):
        st = ttk.Style(self)
        if "clam" in st.theme_names():
            st.theme_use("clam")
        base = ("Segoe UI", 9)
        st.configure(".", font=base, background=FONDO)
        st.configure("TFrame", background=FONDO)
        st.configure("TLabelframe", background=FONDO)
        st.configure("TLabelframe.Label", font=("Segoe UI", 9, "bold"), foreground=AZUL, background=FONDO)
        st.configure("TLabel", background=FONDO)
        st.configure("TCheckbutton", background=FONDO)
        st.configure("TRadiobutton", background=FONDO)
        st.configure("Treeview", rowheight=22, font=base)
        st.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"), background="#d6eaf8", foreground=AZUL)
        st.configure("TNotebook.Tab", padding=(12, 6), font=("Segoe UI", 9, "bold"))
        st.configure("Grande.TButton", font=("Segoe UI", 11, "bold"), padding=(14, 6), foreground="white",
                     background="#1e8449")
        st.map("Grande.TButton", background=[("active", "#239b56")])
        st.configure("Barra.TFrame", background=AZUL)
        st.configure("Barra.TLabel", background=AZUL, foreground="white", font=("Segoe UI", 9))
        st.configure("Titulo.TLabel", background=AZUL, foreground="white", font=("Segoe UI", 13, "bold"))
        st.configure("Ficha.TLabel", font=("Segoe UI", 10, "bold"), foreground=AZUL)

    # ================================================================ estructura
    def _construir(self):
        barra = ttk.Frame(self, style="Barra.TFrame", padding=(10, 6))
        barra.pack(fill="x")
        ttk.Label(barra, text="CORREDOR SIMPLE", style="Titulo.TLabel").pack(side="left", padx=(0, 16))
        for txt, cmd in (("📂 Abrir proyecto", self.abrir_dialogo), ("💾 Guardar", self.guardar),
                         ("🧪 Cargar ejemplo", self.cargar_ejemplo)):
            ttk.Button(barra, text=txt, command=cmd).pack(side="left", padx=3)
        ttk.Button(barra, text="▶  CALCULAR  (F5)", style="Grande.TButton", command=self.calcular).pack(side="left", padx=16)
        self.estado = tk.StringVar(value="Abra un proyecto o cargue el ejemplo.")
        ttk.Label(barra, textvariable=self.estado, style="Barra.TLabel").pack(side="left", padx=10)

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=6, pady=6)
        self.tabs = {}
        for clave, titulo in (("lev", "1 · Levantamiento"), ("cal", "2 · Calles y ejes"), ("cap", "3 · Sección y capas"),
                              ("rev", "4 · Revisión"), ("int", "5 · Interferencias"), ("tie", "6 · Movimiento de tierras"),
                              ("pun", "7 · Puntos y BM"), ("exp", "8 · Exportar")):
            f = ttk.Frame(self.nb, padding=6)
            self.nb.add(f, text=titulo)
            self.tabs[clave] = f
        self._tab_levantamiento()
        self._tab_calles()
        self._tab_capas()
        self._tab_revision()
        self._tab_interferencias()
        self._tab_tierras()
        self._tab_puntos()
        self._tab_exportar()

    # ================================================================ 1 levantamiento
    def _tab_levantamiento(self):
        t = self.tabs["lev"]
        pan = ttk.PanedWindow(t, orient="horizontal")
        pan.pack(fill="both", expand=True)
        izq = ttk.Frame(pan)
        pan.add(izq, weight=2)
        b = ttk.Frame(izq)
        b.pack(fill="x")
        ttk.Button(b, text="📥 Importar levantamiento (punto, Este, Norte, cota, código)…",
                   command=self.imp_levantamiento).pack(side="left")
        ttk.Button(b, text="↻ Reinterpretar códigos", command=self.reinterpretar).pack(side="left", padx=4)
        self.lev_info = tk.StringVar()
        ttk.Label(izq, textvariable=self.lev_info, foreground=AZUL).pack(anchor="w", pady=4)

        fc = ttk.LabelFrame(izq, text="Lista de etiquetas (códigos de campo) — doble clic para editar", padding=4)
        fc.pack(fill="x")
        self.tab_cod = Tabla(fc, ["Código", "Nombre", "Tipo", "Terreno", "Revisión", "Color", "Puntos", "Cómo tomarlo"],
                             {0: 55, 1: 170, 2: 80, 3: 55, 4: 75, 5: 65, 6: 50, 7: 300}, self.editar_codigo,
                             editable={1, 2, 3, 4, 5, 7}, alto=9, opciones={2: list(TIPOS), 3: ["si", "no"], 4: list(REGLAS)})
        self.tab_cod.pack(fill="x")
        bb = ttk.Frame(fc)
        bb.pack(fill="x", pady=2)
        ttk.Button(bb, text="Agregar código", command=self.agregar_codigo).pack(side="left")
        ttk.Button(bb, text="Quitar código", command=self.quitar_codigo).pack(side="left", padx=4)
        ttk.Label(bb, text="  Ver puntos con código:").pack(side="left")
        self.v_filtro_cod = tk.StringVar(value="Todos")
        self.cb_filtro_cod = ttk.Combobox(bb, textvariable=self.v_filtro_cod, width=10, state="readonly")
        self.cb_filtro_cod.pack(side="left", padx=4)
        self.cb_filtro_cod.bind("<<ComboboxSelected>>", lambda _: self.refrescar_puntos_lev())
        ttk.Button(bb, text="Exportar puntos filtrados…", command=self.exportar_puntos_filtrados).pack(side="left", padx=4)

        fp = ttk.LabelFrame(izq, text="Puntos del levantamiento (doble clic: ubicar en planta)", padding=4)
        fp.pack(fill="both", expand=True, pady=(6, 0))
        self.tab_pts = Tabla(fp, ["Punto", "Este", "Norte", "Cota", "Código", "Interpretado como"],
                             {0: 55, 1: 95, 2: 105, 3: 75, 4: 90, 5: 180}, alto=10, al_doble=self.ubicar_punto)
        self.tab_pts.pack(fill="both", expand=True)
        self.lev_avisos = tk.Text(izq, height=4, font=("Segoe UI", 8), fg="#b9770e", bg="#fef9e7", relief="flat")
        self.lev_avisos.pack(fill="x", pady=(4, 0))
        der = ttk.Frame(pan)
        pan.add(der, weight=3)
        self.lz_lev = Lienzo(der, (9, 7))
        self.lz_lev.pack(fill="both", expand=True)

    def refrescar_levantamiento(self, resaltar=None):
        p = self.proy
        cat = p.catalogo or Catalogo()
        conteo = {}
        for q in p.levantamiento:
            c, *_ = cat.interpretar(q.codigo)
            k = c.codigo if c else "?"
            conteo[k] = conteo.get(k, 0) + 1
        self.lev_info.set(f"{len(p.levantamiento)} puntos · {len(p.terreno)} para terreno · {len(p.fachadas)} líneas de "
                          f"fachada/muro · {sum(u.tipo == 'PUERTA' for u in p.umbrales)} puertas · "
                          f"{sum(u.tipo == 'COCHERA' for u in p.umbrales)} cocheras · {len(p.elementos)} elementos · "
                          f"{len(p.bms)} BM")
        self.tab_cod.cargar([[c.codigo, c.nombre, c.tipo, "si" if c.terreno else "no", c.regla, c.color,
                              conteo.get(c.codigo, 0), c.uso] for c in cat])
        for c in cat:
            self.tab_cod.tree.tag_configure("cod_" + c.codigo, foreground=c.color)
        for i, c in enumerate(cat):
            self.tab_cod.tree.item(str(i), tags=("cod_" + c.codigo,))
        self.cb_filtro_cod["values"] = ["Todos"] + [c.codigo for c in cat] + (["?"] if "?" in conteo else [])
        self.refrescar_puntos_lev()
        self.lev_avisos.delete("1.0", "end")
        self.lev_avisos.insert("end", "\n".join(p.avisos_levantamiento) or "Sin observaciones en el levantamiento.")
        self.lz_lev.limpiar()
        ax = self.lz_lev.fig.add_subplot(111)
        if self.res is not None:
            dibujar_planta(ax, self.res, resaltar=resaltar)
        else:
            self._planta_simple(ax, resaltar)
        self.lz_lev.dibujar()

    def _planta_simple(self, ax, resaltar=None, eje_sel=None):
        p = self.proy
        cat = p.catalogo or Catalogo()
        grupos = {}
        for q in p.levantamiento or p.terreno:
            c, *_ = cat.interpretar(q.codigo)
            grupos.setdefault(c.codigo if c else "?", (c, []))[1].append(q)
        for cod, (c, pts) in grupos.items():
            ms = 7 if c and c.tipo in ("ELEMENTO", "PUERTA", "COCHERA", "BM") else 3
            ax.plot([q.este for q in pts], [q.norte for q in pts], ls="none", marker=c.simbolo if c else "x",
                    color=c.color if c else "black", ms=ms, label=f"{cod} ({len(pts)})")
        for l in p.fachadas:
            ax.plot([q[0] for q in l.puntos], [q[1] for q in l.puntos], color="#c0392b", lw=1.5)
        for c in p.calles:
            if len(c.vertices) >= 1:
                sel = c.eje_id == eje_sel
                ax.plot([v[0] for v in c.vertices], [v[1] for v in c.vertices], "-o" if sel else "-.",
                        color="#e67e22" if sel else AZUL, lw=2.5 if sel else 1.5, ms=6)
                if sel:
                    for i, v in enumerate(c.vertices, start=1):
                        ax.annotate(f"V{i}", v, fontsize=8, color="#e67e22", weight="bold", xytext=(5, 5),
                                    textcoords="offset points")
        for b in p.bms:
            ax.plot(b.este, b.norte, "^", color="#6c3483", ms=10)
            ax.annotate(b.id, (b.este, b.norte), fontsize=7, color="#6c3483", xytext=(5, 5), textcoords="offset points")
        if resaltar is not None:
            ax.plot(*resaltar, "o", ms=24, mfc="none", mec="#00bcd4", mew=2.5)
        ax.set_aspect("equal", adjustable="datalim")
        ax.ticklabel_format(useOffset=False, style="plain")
        ax.grid(alpha=0.25)
        if grupos:
            ax.legend(fontsize=6.5, loc="center left", bbox_to_anchor=(1.01, 0.5))

    def _puntos_filtrados(self):
        cat = self.proy.catalogo or Catalogo()
        f = self.v_filtro_cod.get()
        out = []
        for q in self.proy.levantamiento:
            c, tok, num, nota = cat.interpretar(q.codigo)
            k = c.codigo if c else "?"
            if f in ("Todos", "", k):
                out.append((q, c))
        return out

    def refrescar_puntos_lev(self):
        filas, tags = [], []
        for q, c in self._puntos_filtrados():
            filas.append([q.numero, f3(q.este), f3(q.norte), f3(q.cota), q.codigo,
                          f"{c.nombre} ({c.tipo.lower()})" if c else "¿desconocido? (terreno)"])
            tags.append("" if c else "ERROR")
        self.tab_pts.cargar(filas, tags)

    def ubicar_punto(self, i):
        lista = self._puntos_filtrados()
        if i < len(lista):
            q = lista[i][0]
            self.refrescar_levantamiento(resaltar=(q.este, q.norte))
            ax = self.lz_lev.fig.axes[0]
            ax.set_xlim(q.este - 25, q.este + 25)
            ax.set_ylim(q.norte - 18, q.norte + 18)
            self.lz_lev.canvas.draw_idle()

    def imp_levantamiento(self):
        ruta = filedialog.askopenfilename(title="Levantamiento", filetypes=[("CSV / texto", "*.csv *.txt"), ("Todos", "*.*")])
        if not ruta:
            return
        try:
            self.proy.levantamiento = leer_terreno(ruta)
        except (DatoError, KeyError, ValueError) as e:
            return messagebox.showerror("No se pudo leer", str(e))
        self.reinterpretar()

    def reinterpretar(self):
        if self.proy.catalogo is None:
            self.proy.catalogo = Catalogo()
        if self.proy.levantamiento:
            reinterpretar(self.proy)
        self._tin = None
        self.modificado()
        self.refrescar_levantamiento()

    def editar_codigo(self, i, col, v):
        c = list(self.proy.catalogo)[i]
        if col == 1:
            c.nombre = v
        elif col == 2:
            c.tipo = v
        elif col == 3:
            c.terreno = v == "si"
        elif col == 4:
            c.regla = v
        elif col == 5:
            col_ = colorchooser.askcolor(c.color, title=f"Color de {c.codigo}")[1] if v == c.color else v
            c.color = col_ or c.color
        elif col == 7:
            c.uso = v
        self.reinterpretar()

    def agregar_codigo(self):
        cod = simpledialog.askstring("Nuevo código", "Código (letras, ej. BZD, VT, MED):", parent=self)
        if not cod:
            return
        cod = cod.strip().upper()
        if self.proy.catalogo.buscar(cod) and self.proy.catalogo.buscar(cod).codigo == cod:
            return messagebox.showwarning("Ya existe", f"El código {cod} ya está en la lista.")
        self.proy.catalogo.codigos.append(Codigo(cod, f"Nuevo {cod}", "ELEMENTO", False, "#7f8c8d", "o", "ninguna", ""))
        self.reinterpretar()

    def quitar_codigo(self):
        i = self.tab_cod.seleccion()
        if i is None:
            return
        c = self.proy.catalogo.codigos[i]
        if messagebox.askyesno("Quitar código", f"¿Quitar {c.codigo}? Sus puntos pasarán a 'desconocido'."):
            del self.proy.catalogo.codigos[i]
            self.reinterpretar()

    def exportar_puntos_filtrados(self):
        ruta = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")],
                                            initialfile=f"puntos_{self.v_filtro_cod.get()}.csv")
        if not ruta:
            return
        import csv
        with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(["punto", "este", "norte", "cota", "codigo", "tipo"])
            for q, c in self._puntos_filtrados():
                w.writerow([q.numero, f3(q.este), f3(q.norte), f3(q.cota), q.codigo, c.nombre if c else "desconocido"])
        self.estado.set(f"Puntos exportados a {ruta}")

    # ================================================================ 2 calles y ejes
    def _tab_calles(self):
        t = self.tabs["cal"]
        pan = ttk.PanedWindow(t, orient="horizontal")
        pan.pack(fill="both", expand=True)
        izq = ttk.Frame(pan)
        pan.add(izq, weight=3)
        fcal = ttk.LabelFrame(izq, text="Calles — una fila por calle (la primera manda en los cruces). Doble clic para editar",
                              padding=4)
        fcal.pack(fill="x")
        self.tab_calles = Tabla(fcal, ["Eje", "Nombre de la calle", "Bombeo %", "Calzada (m)", "Vereda (m)", "Longitud (m)"],
                                {0: 65, 1: 170, 2: 75, 3: 85, 4: 80, 5: 90}, self.editar_calle, editable={0, 1, 2, 3, 4}, alto=5)
        self.tab_calles.pack(fill="x")
        self.tab_calles.tree.bind("<<TreeviewSelect>>", lambda _: self.refrescar_calle_sel())
        b = ttk.Frame(fcal)
        b.pack(fill="x", pady=2)
        for txt, cmd in (("➕ Nueva calle", self.agregar_calle), ("Quitar", self.quitar_calle),
                         ("↑", lambda: self.mover_calle(-1)), ("↓", lambda: self.mover_calle(1))):
            ttk.Button(b, text=txt, command=cmd).pack(side="left", padx=2)

        fv = ttk.LabelFrame(izq, text="① Eje en planta — vértices (V1 = punto de origen). En 'Punto' puede escribir un "
                                      "número del levantamiento", padding=4)
        fv.pack(fill="both", expand=True, pady=(6, 0))
        fila = ttk.Frame(fv)
        fila.pack(fill="x")
        ttk.Label(fila, text="Progresiva inicial:").pack(side="left")
        self.prog0 = tk.StringVar()
        en = ttk.Entry(fila, textvariable=self.prog0, width=10)
        en.pack(side="left", padx=4)
        en.bind("<Return>", lambda _: self.aplicar_prog0())
        en.bind("<FocusOut>", lambda _: self.aplicar_prog0())
        self.tab_vert = Tabla(fv, ["V", "Este", "Norte", "Punto", "Progresiva", "Azimut →", "Tramo (m)"],
                              {0: 35, 1: 100, 2: 110, 3: 60, 4: 85, 5: 85, 6: 75}, self.editar_vertice,
                              editable={1, 2, 3}, alto=6)
        self.tab_vert.pack(fill="both", expand=True, pady=2)
        bv = ttk.Frame(fv)
        bv.pack(fill="x")
        ttk.Button(bv, text="📍 Origen + azimut + longitud…", command=self.eje_desde_origen).pack(side="left", padx=1)
        ttk.Button(bv, text="➕ Tramo (azimut, L)…", command=self.agregar_tramo_eje).pack(side="left", padx=1)
        self.bt_clic = ttk.Button(bv, text="✏ Dibujar con clic en planta", command=self.alternar_modo_eje)
        self.bt_clic.pack(side="left", padx=1)
        ttk.Button(bv, text="Quitar vértice", command=self.quitar_vertice).pack(side="left", padx=1)
        ttk.Button(bv, text="Invertir sentido", command=self.invertir_eje).pack(side="left", padx=1)

        fp = ttk.LabelFrame(izq, text="② Perfil de rasante — tramos encadenados (edite pendiente o cota final)", padding=4)
        fp.pack(fill="both", expand=True, pady=(6, 0))
        self.tab_perf = Tabla(fp, ["Desde", "Cota inicio", "Pendiente %", "Hasta", "Cota fin", "Longitud"],
                              {0: 80, 1: 90, 2: 85, 3: 80, 4: 90, 5: 75}, self.editar_tramo, editable={1, 2, 3, 4}, alto=5)
        self.tab_perf.pack(fill="both", expand=True, pady=2)
        bp = ttk.Frame(fp)
        bp.pack(fill="x")
        ttk.Button(bp, text="➕ Tramo", command=self.agregar_tramo).pack(side="left", padx=1)
        ttk.Button(bp, text="✂ Partir en progresiva…", command=self.partir_tramo).pack(side="left", padx=1)
        ttk.Button(bp, text="Quitar tramo", command=self.quitar_tramo).pack(side="left", padx=1)
        ttk.Button(bp, text="⛰ Proponer desde el terreno", command=self.perfil_desde_terreno).pack(side="left", padx=1)
        self.perf_info = tk.StringVar()
        ttk.Label(fp, textvariable=self.perf_info, foreground="#b03a2e").pack(anchor="w")

        der = ttk.Frame(pan)
        pan.add(der, weight=4)
        self.lz_cal = Lienzo(der, (8, 8))
        self.lz_cal.pack(fill="both", expand=True)
        self.lz_cal.canvas.mpl_connect("button_press_event", self._clic_planta_calle)
        self.lbl_clic = ttk.Label(der, text="", foreground="#e67e22", font=("Segoe UI", 9, "bold"))
        self.lbl_clic.pack(anchor="w")

    def calle_sel(self):
        i = self.tab_calles.seleccion()
        if i is None or i >= len(self.proy.calles):
            return None
        return self.proy.calles[i]

    def refrescar_calles(self, sel=None):
        filas = []
        for c in self.proy.calles:
            L = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(c.vertices[:-1], c.vertices[1:]))
            filas.append([c.eje_id, c.nombre, f"{c.bombeo_pct:.2f}", f"{c.ancho_calzada:.2f}", f"{c.ancho_vereda:.2f}",
                          f"{L:.3f}"])
        actual = self.tab_calles.seleccion() if sel is None else sel
        self.tab_calles.cargar(filas)
        if self.proy.calles:
            self.tab_calles.seleccionar(min(actual or 0, len(self.proy.calles) - 1))
        self.refrescar_calle_sel()

    def refrescar_calle_sel(self):
        c = self.calle_sel()
        if c is None:
            self.tab_vert.cargar([])
            self.tab_perf.cargar([])
            self.vista_previa_calle()
            return
        self.prog0.set(f"{c.prog_inicial:.3f}")
        filas, p = [], c.prog_inicial
        refs = getattr(c, "refs", {})
        for i, (e, n) in enumerate(c.vertices):
            az = L = ""
            if i + 1 < len(c.vertices):
                e2, n2 = c.vertices[i + 1]
                az = f"{math.degrees(math.atan2(e2 - e, n2 - n)) % 360:.4f}°"
                L = f"{math.hypot(e2 - e, n2 - n):.3f}"
            filas.append([f"V{i + 1}", f3(e), f3(n), refs.get(i, ""), fmt_prog(p), az, L])
            if i + 1 < len(c.vertices):
                p += math.hypot(c.vertices[i + 1][0] - e, c.vertices[i + 1][1] - n)
        self.tab_vert.cargar(filas)
        self._encadenar(c)
        self.tab_perf.cargar([[fmt_prog(t[0]), f3(t[1]), f"{t[2]:+.3f}", fmt_prog(t[3]),
                               f3(t[1] + t[2] / 100 * (t[3] - t[0])), f"{t[3] - t[0]:.2f}"] for t in c.tramos])
        pmax, pmin = self.proy.p("pendiente_long_max"), self.proy.p("pendiente_long_min")
        txt = []
        for t in c.tramos:
            if abs(t[2]) > pmax:
                txt.append(f"⚠ {fmt_prog(t[0])}: {t[2]:+.2f} % supera la máxima ({pmax:.2f} %)")
            elif abs(t[2]) < pmin:
                txt.append(f"⚠ {fmt_prog(t[0])}: {t[2]:+.2f} % menor que la mínima ({pmin:.2f} %)")
        if c.tramos and len(c.vertices) >= 2:
            L = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(c.vertices[:-1], c.vertices[1:]))
            fin = c.prog_inicial + L
            if abs(c.tramos[-1][3] - fin) > 0.01:
                txt.append(f"⚠ El perfil termina en {fmt_prog(c.tramos[-1][3])} y el eje en {fmt_prog(fin)}")
        self.perf_info.set("   ".join(txt))
        self.vista_previa_calle()

    @staticmethod
    def _encadenar(c):
        """Cada tramo empieza donde terminó el anterior (progresiva y cota)."""
        for k in range(1, len(c.tramos)):
            a = c.tramos[k - 1]
            c.tramos[k][0] = a[3]
            c.tramos[k][1] = round(a[1] + a[2] / 100 * (a[3] - a[0]), 4)

    def tin(self):
        if self._tin is None:
            self._tin = Terreno(self.proy.terreno, self.proy.p("arista_max_tin"))
        return self._tin

    def vista_previa_calle(self):
        """Planta con la calle resaltada y perfil rápido (sin calcular todo)."""
        c = self.calle_sel()
        self.lz_cal.limpiar()
        fig = self.lz_cal.fig
        gs = fig.add_gridspec(2, 1, height_ratios=[1.6, 1])
        ax = fig.add_subplot(gs[0])
        self._planta_simple(ax, eje_sel=c.eje_id if c else None)
        ax.set_title("Planta — " + ("modo dibujo: clic para agregar vértices" if self.modo_eje else
                                    (f"{c.eje_id} {c.nombre}" if c else "")), fontsize=9, weight="bold",
                     color="#e67e22" if self.modo_eje else "black")
        if self.modo_eje and c and c.vertices:
            xs = [v[0] for v in c.vertices]
            ys = [v[1] for v in c.vertices]
            ax.set_xlim(min(xs) - 60, max(xs) + 60)
            ax.set_ylim(min(ys) - 60, max(ys) + 60)
        ax2 = fig.add_subplot(gs[1])
        if c and len(c.vertices) >= 2 and c.tramos:
            try:
                al, pf = Alineamiento(c.vertices, c.prog_inicial), Perfil(c.tramos)
                import numpy as np
                ps = np.linspace(al.prog_inicial, al.prog_final, max(2, int(al.longitud) + 1))
                zr = [pf.cota(x) for x in ps]
                ax2.plot(ps, zr, color="#154360", lw=2, label="Rasante")
                T = sum(cp.espesor for cp in self.proy.capas_de("calzada"))
                ax2.plot(ps, [z - T for z in zr], color="#922b21", lw=0.8, ls="--", label="Subrasante")
                t = self.tin()
                if t.ok:
                    xy = [al.punto(x) for x in ps]
                    zt = t.cota([a for a, _ in xy], [b for _, b in xy])
                    ax2.plot(ps, zt, color="#6d4c41", lw=1.3, label="Terreno")
                    ax2.fill_between(ps, zt, [z - T for z in zr], color="#e74c3c", alpha=0.1)
                for tr in pf.tramos:
                    pm = (tr[0] + tr[3]) / 2
                    ax2.annotate(f"{tr[2]:+.2f}%", (pm, pf.cota(pm)), xytext=(0, 8), textcoords="offset points",
                                 ha="center", fontsize=8, weight="bold", color="#154360")
                for q in pf.quiebres():
                    ax2.axvline(q, color="#154360", lw=0.6, ls=":")
                ax2.legend(fontsize=7, loc="best")
            except ValueError as e:
                ax2.text(0.5, 0.5, str(e), transform=ax2.transAxes, ha="center")
        ax2.set_xlabel("Progresiva (m)")
        ax2.set_ylabel("Cota (m)")
        ax2.ticklabel_format(useOffset=False, style="plain", axis="y")
        ax2.grid(alpha=0.25)
        ax2.set_title("Perfil rápido (vista previa)", fontsize=9)
        self.lz_cal.dibujar()

    def alternar_modo_eje(self):
        self.modo_eje = not self.modo_eje
        self.bt_clic.configure(text="✔ Terminar dibujo" if self.modo_eje else "✏ Dibujar con clic en planta")
        self.lbl_clic.configure(text="Clic en la planta: agrega un vértice al final (se ajusta a un punto del "
                                     "levantamiento si está a menos de 1 m)." if self.modo_eje else "")
        self.vista_previa_calle()

    def _clic_planta_calle(self, ev):
        if not self.modo_eje or ev.inaxes is None or ev.inaxes != self.lz_cal.fig.axes[0] or ev.button != 1:
            return
        if self.lz_cal.canvas.toolbar is not None and self.lz_cal.canvas.toolbar.mode:
            return
        c = self.calle_sel()
        if c is None:
            return
        e, n = ev.xdata, ev.ydata
        ref = ""
        cerca = min(self.proy.levantamiento, key=lambda q: math.hypot(q.este - e, q.norte - n), default=None)
        if cerca and math.hypot(cerca.este - e, cerca.norte - n) < 1.0:
            e, n, ref = cerca.este, cerca.norte, cerca.numero
        c.vertices.append((round(e, 3), round(n, 3)))
        if ref:
            if not hasattr(c, "refs"):
                c.refs = {}
            c.refs[len(c.vertices) - 1] = ref
        self.modificado()
        self.refrescar_calles()

    def editar_calle(self, i, col, v):
        c = self.proy.calles[i]
        if col == 0:
            v = v.strip()
            if any(o.eje_id == v and o is not c for o in self.proy.calles):
                raise ValueError("ya existe otro eje con ese nombre")
            for t in self.proy.cunetas:
                if t.eje_id == c.eje_id:
                    t.eje_id = v
            c.eje_id = v
        elif col == 1:
            c.nombre = v
        elif col == 2:
            c.bombeo_pct = numero(v)
        elif col == 3:
            c.ancho_calzada = numero(v)
        elif col == 4:
            c.ancho_vereda = numero(v)
        self.modificado()
        self.refrescar_calles(i)

    def agregar_calle(self):
        n = len(self.proy.calles) + 1
        eid = f"EJE-{n:02d}"
        while self.proy.calle(eid):
            n += 1
            eid = f"EJE-{n:02d}"
        base = self.proy.calles[-1] if self.proy.calles else None
        self.proy.calles.append(Calle(eid, f"Calle {n}", base.bombeo_pct if base else 2.0,
                                      base.ancho_calzada if base else 7.2, base.ancho_vereda if base else 1.5))
        self.modificado()
        self.refrescar_calles(len(self.proy.calles) - 1)
        self.estado.set(f"{eid} creada: defina el eje (origen + azimut, puntos o clic en planta) y luego el perfil.")

    def quitar_calle(self):
        i = self.tab_calles.seleccion()
        if i is not None and messagebox.askyesno("Quitar calle", f"¿Quitar {self.proy.calles[i].eje_id}?"):
            del self.proy.calles[i]
            self.modificado()
            self.refrescar_calles(max(0, i - 1))

    def mover_calle(self, d):
        i = self.tab_calles.seleccion()
        if i is None or not 0 <= i + d < len(self.proy.calles):
            return
        cs = self.proy.calles
        cs[i], cs[i + d] = cs[i + d], cs[i]
        self.modificado()
        self.refrescar_calles(i + d)

    def aplicar_prog0(self):
        c = self.calle_sel()
        if c is None:
            return
        try:
            v = numero(self.prog0.get())
        except ValueError:
            return
        if abs(v - c.prog_inicial) > 1e-9:
            d = v - c.prog_inicial
            c.prog_inicial = v
            for t in c.tramos:
                t[0] += d
                t[3] += d
            self.modificado()
            self.refrescar_calle_sel()

    def editar_vertice(self, i, col, v):
        c = self.calle_sel()
        e, n = c.vertices[i]
        if col == 3:
            q = next((q for q in self.proy.levantamiento if q.numero == v.strip()), None)
            if q is None:
                raise ValueError("no existe ese número de punto en el levantamiento")
            c.vertices[i] = (q.este, q.norte)
            if not hasattr(c, "refs"):
                c.refs = {}
            c.refs[i] = q.numero
        else:
            c.vertices[i] = (numero(v), n) if col == 1 else (e, numero(v))
            getattr(c, "refs", {}).pop(i, None)
        self.modificado()
        self.refrescar_calles()

    def eje_desde_origen(self):
        c = self.calle_sel()
        if c is None:
            return
        d = DialogoOrigen(self, "Eje desde punto de origen", c.vertices[0] if c.vertices else (0.0, 0.0),
                          self.proy.levantamiento)
        if d.resultado:
            e, n, az, L = d.resultado
            a = math.radians(az)
            c.vertices = [(e, n), (round(e + L * math.sin(a), 3), round(n + L * math.cos(a), 3))]
            c.refs = {}
            if not c.tramos:
                self._perfil_inicial(c)
            self.modificado()
            self.refrescar_calles()

    def agregar_tramo_eje(self):
        c = self.calle_sel()
        if c is None or not c.vertices:
            return self.eje_desde_origen()
        txt = simpledialog.askstring("Agregar tramo", "Azimut (grados) y longitud (m), ej.: 80 120.5", parent=self)
        if not txt:
            return
        try:
            az, L = (numero(x) for x in txt.replace(";", " ").split()[:2])
        except ValueError:
            return messagebox.showerror("Dato no válido", "Escriba por ejemplo: 80 120.5")
        e, n = c.vertices[-1]
        c.vertices.append((round(e + L * math.sin(math.radians(az)), 3), round(n + L * math.cos(math.radians(az)), 3)))
        self.modificado()
        self.refrescar_calles()

    def quitar_vertice(self):
        c = self.calle_sel()
        i = self.tab_vert.seleccion()
        if c is None:
            return
        if i is None:
            i = len(c.vertices) - 1
        if 0 <= i < len(c.vertices):
            del c.vertices[i]
            c.refs = {}
            self.modificado()
            self.refrescar_calles()

    def invertir_eje(self):
        c = self.calle_sel()
        if c is None or len(c.vertices) < 2:
            return
        c.vertices.reverse()
        c.refs = {}
        if c.tramos:
            al = Alineamiento(c.vertices, c.prog_inicial)
            pf = Perfil(c.tramos)
            L = al.longitud
            nuevos = []
            for t in reversed(c.tramos):
                a, b = c.prog_inicial + L - (t[3] - c.prog_inicial), c.prog_inicial + L - (t[0] - c.prog_inicial)
                nuevos.append([round(a, 3), round(pf.cota(t[3]), 4), -t[2], round(b, 3)])
            nuevos[0][0] = c.prog_inicial
            c.tramos = nuevos
            self._encadenar(c)
        self.modificado()
        self.refrescar_calles()

    def _perfil_inicial(self, c):
        L = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(c.vertices[:-1], c.vertices[1:]))
        t = self.tin()
        z0 = t.cota(*c.vertices[0]) if t.ok else float("nan")
        z1 = t.cota(*c.vertices[-1]) if t.ok else float("nan")
        if z0 != z0 or z1 != z1:
            z0, z1 = 0.0, 0.0
        T = sum(cp.espesor for cp in self.proy.capas_de("calzada"))
        c.tramos = [[c.prog_inicial, round(z0 - 0.0, 3), round((z1 - z0) / max(L, 1e-6) * 100, 3), round(c.prog_inicial + L, 3)]]
        return T

    def editar_tramo(self, i, col, v):
        c = self.calle_sel()
        t = c.tramos[i]
        if col == 1:
            if i > 0:
                raise ValueError("solo se edita la cota del primer tramo; las demás se encadenan")
            t[1] = numero(v)
        elif col == 2:
            t[2] = numero(v)
        elif col == 3:
            val = numero(v)
            if val <= t[0]:
                raise ValueError("debe ser mayor que la progresiva de inicio del tramo")
            t[3] = val
        elif col == 4:            # cota final -> recalcula la pendiente
            t[2] = round((numero(v) - t[1]) / (t[3] - t[0]) * 100, 4)
        self._encadenar(c)
        self.modificado()
        self.refrescar_calle_sel()

    def agregar_tramo(self):
        c = self.calle_sel()
        if c is None:
            return
        if c.tramos:
            a = c.tramos[-1]
            L = sum(math.hypot(b[0] - q[0], b[1] - q[1]) for q, b in zip(c.vertices[:-1], c.vertices[1:]))
            fin = max(a[3] + 20.0, c.prog_inicial + L) if a[3] < c.prog_inicial + L - 0.01 else a[3] + 20.0
            c.tramos.append([a[3], 0.0, a[2], round(fin, 3)])
            self._encadenar(c)
        elif len(c.vertices) >= 2:
            self._perfil_inicial(c)
        else:
            c.tramos.append([c.prog_inicial, 0.0, 1.0, c.prog_inicial + 50.0])
        self.modificado()
        self.refrescar_calle_sel()

    def partir_tramo(self):
        c = self.calle_sel()
        if c is None or not c.tramos:
            return
        txt = simpledialog.askstring("Partir tramo", "Progresiva del nuevo quiebre (ej. 0+080 u 80):", parent=self)
        if not txt:
            return
        try:
            p = numero(txt)
        except ValueError:
            return
        for k, t in enumerate(c.tramos):
            if t[0] + 0.01 < p < t[3] - 0.01:
                c.tramos.insert(k + 1, [p, 0.0, t[2], t[3]])
                t[3] = p
                self._encadenar(c)
                self.modificado()
                self.refrescar_calle_sel()
                return
        messagebox.showwarning("Fuera de rango", "Esa progresiva no está dentro de ningún tramo.")

    def quitar_tramo(self):
        c = self.calle_sel()
        i = self.tab_perf.seleccion()
        if c is None or i is None or len(c.tramos) <= 1:
            return
        fin = c.tramos[i][3]
        del c.tramos[i]
        if i > 0:
            c.tramos[i - 1][3] = fin if i == len(c.tramos) else c.tramos[i - 1][3]
            if i < len(c.tramos):
                c.tramos[i - 1][3] = c.tramos[i][0]
        self._encadenar(c)
        self.modificado()
        self.refrescar_calle_sel()

    def perfil_desde_terreno(self):
        c = self.calle_sel()
        if c is None or len(c.vertices) < 2:
            return
        t = self.tin()
        if not t.ok:
            return messagebox.showwarning("Sin terreno", "Primero importe el levantamiento.")
        al = Alineamiento(c.vertices, c.prog_inicial)
        z0, z1 = t.cota(*al.punto(al.prog_inicial)), t.cota(*al.punto(al.prog_final))
        if z0 != z0 or z1 != z1:
            return messagebox.showwarning("Fuera del terreno", "El inicio o el fin del eje está fuera del levantamiento.")
        c.tramos = [[al.prog_inicial, round(z0, 3), round((z1 - z0) / al.longitud * 100, 3), round(al.prog_final, 3)]]
        self.modificado()
        self.refrescar_calle_sel()
        self.estado.set("Perfil propuesto siguiendo el terreno: ajuste cotas y pendientes, use '✂ Partir' para quiebres.")

    # ================================================================ 3 sección y capas
    def _tab_capas(self):
        t = self.tabs["cap"]
        izq = ttk.Frame(t)
        izq.pack(side="left", fill="both", expand=True)
        f = ttk.LabelFrame(izq, text="Capas (de arriba hacia abajo) — espesor uniforme en cm", padding=4)
        f.pack(fill="x")
        self.tab_capas = Tabla(f, ["Ámbito", "Orden", "Material", "Espesor (cm)"], {0: 80, 1: 50, 2: 240, 3: 90},
                               self.editar_capa, editable={2, 3}, alto=8)
        self.tab_capas.pack(fill="x")
        b = ttk.Frame(f)
        b.pack(fill="x", pady=2)
        ttk.Button(b, text="➕ Capa de calzada", command=lambda: self.agregar_capa("calzada")).pack(side="left", padx=1)
        ttk.Button(b, text="➕ Capa de vereda", command=lambda: self.agregar_capa("vereda")).pack(side="left", padx=1)
        ttk.Button(b, text="Quitar", command=self.quitar_capa).pack(side="left", padx=1)
        ttk.Button(b, text="↑", command=lambda: self.mover_capa(-1)).pack(side="left", padx=1)
        ttk.Button(b, text="↓", command=lambda: self.mover_capa(1)).pack(side="left", padx=1)
        self.capas_info = tk.StringVar()
        ttk.Label(f, textvariable=self.capas_info, foreground=AZUL).pack(anchor="w")
        fc = ttk.LabelFrame(izq, text="Cuneta por tramo (si no hay tramo se usa la estándar)", padding=4)
        fc.pack(fill="x", pady=(6, 0))
        self.tab_cun = Tabla(fc, ["Eje", "Lado", "Desde", "Hasta", "Ancho cm", "Prof. cm", "Nota"],
                             {0: 65, 1: 65, 2: 75, 3: 75, 4: 65, 5: 60, 6: 170}, self.editar_cuneta, alto=4,
                             opciones={1: ["AMBOS", "IZQ", "DER"]})
        self.tab_cun.pack(fill="x")
        b = ttk.Frame(fc)
        b.pack(fill="x", pady=2)
        ttk.Button(b, text="➕ Tramo de cuneta", command=self.agregar_cuneta).pack(side="left")
        ttk.Button(b, text="Quitar", command=self.quitar_cuneta).pack(side="left", padx=2)
        self.lz_tip = Lienzo(izq, (7, 4), barra=False)
        self.lz_tip.pack(fill="both", expand=True, pady=(6, 0))

        der = ttk.Frame(t)
        der.pack(side="left", fill="y", padx=(8, 0))
        self.vars_par = {}
        for grupo, claves in GRUPOS_PARAM.items():
            g = ttk.LabelFrame(der, text=grupo, padding=4)
            g.pack(fill="x", pady=2)
            for r, k in enumerate(claves):
                v, u, d = PARAMETROS[k]
                ttk.Label(g, text=k.replace("_", " ").capitalize(), width=22).grid(row=r, column=0, sticky="w")
                var = tk.StringVar()
                if k == "modo_fachada":
                    w = ttk.Combobox(g, textvariable=var, values=["recortar", "avisar"], width=9, state="readonly")
                else:
                    w = ttk.Entry(g, textvariable=var, width=10)
                w.grid(row=r, column=1, padx=3)
                ttk.Label(g, text=u, width=3).grid(row=r, column=2, sticky="w")
                ttk.Label(g, text=d, foreground="#b03a2e" if "CONFIRMAR" in d else "#566573", wraplength=330,
                          font=("Segoe UI", 8)).grid(row=r, column=3, sticky="w")
                self.vars_par[k] = var
        ttk.Button(der, text="✔ Aplicar parámetros", command=self.aplicar_parametros).pack(anchor="w", pady=6)

    def refrescar_capas(self):
        p = self.proy
        capas = p.capas_de("calzada") + p.capas_de("vereda")
        self.tab_capas.cargar([[c.ambito, c.orden, c.nombre, f"{c.espesor_cm:g}"] for c in capas])
        tc = sum(c.espesor_cm for c in p.capas_de("calzada"))
        tv = sum(c.espesor_cm for c in p.capas_de("vereda"))
        self.capas_info.set(f"Paquete de calzada: {tc:g} cm · paquete de vereda: {tv:g} cm")
        self.tab_cun.cargar([[t.eje_id, t.lado, fmt_prog(t.prog_ini), fmt_prog(t.prog_fin), f"{t.ancho_cm:g}",
                              f"{t.profundidad_cm:g}", t.nota] for t in p.cunetas])
        for k, var in self.vars_par.items():
            var.set(str(p.parametros.get(k, PARAMETROS[k][0])))
        self.dibujar_tipica()

    def _capas_ordenadas(self):
        return self.proy.capas_de("calzada") + self.proy.capas_de("vereda")

    def editar_capa(self, i, col, v):
        c = self._capas_ordenadas()[i]
        if col == 2:
            c.nombre = v
        else:
            val = numero(v)
            if val <= 0:
                raise ValueError("el espesor debe ser mayor que 0")
            c.espesor_cm = val
        self.modificado()
        self.refrescar_capas()

    def agregar_capa(self, amb):
        n = len(self.proy.capas_de(amb)) + 1
        self.proy.capas.append(Capa(amb, n, "Pedraplén" if amb == "calzada" else f"Capa vereda {n}", 20.0))
        self.modificado()
        self.refrescar_capas()

    def quitar_capa(self):
        i = self.tab_capas.seleccion()
        if i is None:
            return
        c = self._capas_ordenadas()[i]
        self.proy.capas.remove(c)
        for k, x in enumerate(self.proy.capas_de(c.ambito), start=1):
            x.orden = k
        self.modificado()
        self.refrescar_capas()

    def mover_capa(self, d):
        i = self.tab_capas.seleccion()
        if i is None:
            return
        c = self._capas_ordenadas()[i]
        grupo = self.proy.capas_de(c.ambito)
        j = grupo.index(c)
        if 0 <= j + d < len(grupo):
            grupo[j].orden, grupo[j + d].orden = grupo[j + d].orden, grupo[j].orden
            self.modificado()
            self.refrescar_capas()
            self.tab_capas.seleccionar(i + d)

    def editar_cuneta(self, i, col, v):
        t = self.proy.cunetas[i]
        if col == 0:
            t.eje_id = v
        elif col == 1:
            t.lado = v.upper()
        elif col == 2:
            t.prog_ini = numero(v)
        elif col == 3:
            t.prog_fin = numero(v)
        elif col == 4:
            t.ancho_cm = numero(v)
        elif col == 5:
            t.profundidad_cm = numero(v)
        else:
            t.nota = v
        self.modificado()
        self.refrescar_capas()

    def agregar_cuneta(self):
        eje = self.proy.calles[0].eje_id if self.proy.calles else "EJE-01"
        self.proy.cunetas.append(TramoCuneta(eje, "AMBOS", 0.0, 50.0, self.proy.p("cuneta_ancho"),
                                             self.proy.p("cuneta_profundidad"), ""))
        self.modificado()
        self.refrescar_capas()

    def quitar_cuneta(self):
        i = self.tab_cun.seleccion()
        if i is not None:
            del self.proy.cunetas[i]
            self.modificado()
            self.refrescar_capas()

    def aplicar_parametros(self):
        k = None
        try:
            for k, var in self.vars_par.items():
                self.proy.parametros[k] = var.get().strip() if k in TEXTO else numero(var.get())
        except ValueError:
            return messagebox.showerror("Dato no válido", f"Revise el parámetro '{k}'.")
        self._tin = None
        if self.proy.levantamiento:
            reinterpretar(self.proy)
        self.modificado()
        self.dibujar_tipica()
        if self.res is None and self.proy.calles:
            self.calcular()

    def dibujar_tipica(self):
        self.lz_tip.limpiar()
        p = self.proy
        c = self.calle_sel() or (p.calles[0] if p.calles else None)
        if c is None or len(c.vertices) < 2 or not c.tramos or not p.capas_de("calzada"):
            self.lz_tip.dibujar()
            return
        try:
            al, pf = Alineamiento(c.vertices, c.prog_inicial), Perfil(c.tramos)
            cun = (p.p("cuneta_ancho") / 100, p.p("cuneta_profundidad") / 100)
            sec = construir(c, al, pf, c.prog_inicial, p.parametros, p.capas_de("calzada"), p.capas_de("vereda"),
                            {"I": True, "D": True}, {"I": c.ancho_vereda, "D": c.ancho_vereda}, {"I": cun, "D": cun})
        except Exception:
            return
        ax = self.lz_tip.fig.add_subplot(111)
        dibujar_seccion(ax, sec, p, None)
        ax.set_title(f"Sección típica {c.eje_id} {c.nombre}", fontsize=9, weight="bold")
        ax.get_legend().remove()
        self.lz_tip.dibujar()

    # ================================================================ 4 revisión
    def _tab_revision(self):
        t = self.tabs["rev"]
        ctl = ttk.Frame(t)
        ctl.pack(fill="x")
        ttk.Label(ctl, text="Calle:").pack(side="left")
        self.v_calle = tk.StringVar()
        self.cb_calle = ttk.Combobox(ctl, textvariable=self.v_calle, width=24, state="readonly")
        self.cb_calle.pack(side="left", padx=4)
        self.cb_calle.bind("<<ComboboxSelected>>", lambda _: (self._llenar_progs(), self.dibujar_vista()))
        self.v_vista = tk.StringVar(value="Sección")
        for v in ("Sección", "Perfil", "Planta", "3D"):
            ttk.Radiobutton(ctl, text=v, value=v, variable=self.v_vista, command=self.dibujar_vista).pack(side="left", padx=2)
        ttk.Label(ctl, text="   Progresiva:").pack(side="left")
        self.v_prog = tk.StringVar()
        self.cb_prog = ttk.Combobox(ctl, textvariable=self.v_prog, width=12, state="readonly")
        self.cb_prog.pack(side="left", padx=3)
        self.cb_prog.bind("<<ComboboxSelected>>", lambda _: self._ir_seccion())
        ttk.Button(ctl, text="◀", width=3, command=lambda: self._paso_prog(-1)).pack(side="left")
        ttk.Button(ctl, text="▶", width=3, command=lambda: self._paso_prog(1)).pack(side="left")
        ttk.Label(ctl, text="   Ir a:").pack(side="left")
        self.v_ir = tk.StringVar()
        e = ttk.Entry(ctl, textvariable=self.v_ir, width=9)
        e.pack(side="left")
        e.bind("<Return>", lambda _: self._ir_a_prog())
        ttk.Label(ctl, text="   3D: exag.").pack(side="left")
        self.v_exag = tk.StringVar(value="4")
        ttk.Spinbox(ctl, from_=1, to=50, textvariable=self.v_exag, width=4, command=self.dibujar_vista).pack(side="left")
        self.v_tramo = tk.BooleanVar(value=True)
        ttk.Checkbutton(ctl, text="solo ±20 m", variable=self.v_tramo, command=self.dibujar_vista).pack(side="left", padx=4)
        self.v_tn = tk.BooleanVar(value=True)
        ttk.Checkbutton(ctl, text="terreno", variable=self.v_tn, command=self.dibujar_vista).pack(side="left")
        self.lbl_rev = ttk.Label(t, text="En 'Planta' haga clic sobre una calle para abrir la sección más cercana.",
                                 foreground="#566573")
        self.lbl_rev.pack(anchor="w")
        cuerpo = ttk.PanedWindow(t, orient="horizontal")
        cuerpo.pack(fill="both", expand=True)
        self.lz_rev = Lienzo(cuerpo, (11, 7))
        cuerpo.add(self.lz_rev, weight=5)
        self.lz_rev.canvas.mpl_connect("button_press_event", self._clic_revision)
        ficha = ttk.LabelFrame(cuerpo, text="Ficha de la sección", padding=4)
        cuerpo.add(ficha, weight=1)
        self.tab_ficha = Tabla(ficha, ["Punto", "Offset", "Cota"], {0: 70, 1: 60, 2: 80}, alto=18)
        self.tab_ficha.pack(fill="both", expand=True)
        self.ficha_txt = tk.Text(ficha, height=12, width=34, font=("Segoe UI", 8), relief="flat", bg="#fbfcfc")
        self.ficha_txt.pack(fill="x", pady=(4, 0))

    def _rc(self):
        if self.res is None:
            return None
        return self.res.calles.get(self.v_calle.get()) or next(iter(self.res.calles.values()))

    def _llenar_progs(self):
        rc = self._rc()
        if rc is None:
            return
        vals = [fmt_prog(s.prog) for s in rc.secciones if not s.omitida]
        self.cb_prog["values"] = vals
        if self.v_prog.get() not in vals and vals:
            self.v_prog.set(vals[min(5, len(vals) - 1)])

    def _ir_seccion(self):
        self.v_vista.set("Sección")
        self.dibujar_vista()

    def _paso_prog(self, d):
        vals = list(self.cb_prog["values"])
        if not vals:
            return
        i = vals.index(self.v_prog.get()) if self.v_prog.get() in vals else 0
        self.v_prog.set(vals[max(0, min(len(vals) - 1, i + d))])
        self._ir_seccion()

    def _ir_a_prog(self):
        try:
            p = numero(self.v_ir.get())
        except ValueError:
            return
        rc = self._rc()
        if rc is None:
            return
        s = min((s for s in rc.secciones if not s.omitida), key=lambda s: abs(s.prog - p))
        if abs(s.prog - p) > 0.01:      # sección exacta en esa progresiva (consulta)
            s = rc.seccion_en(p, "CONSULTA")
            self._sec_consulta = s
            self.v_prog.set(fmt_prog(p))
        else:
            self._sec_consulta = None
            self.v_prog.set(fmt_prog(s.prog))
        self.v_vista.set("Sección")
        self.dibujar_vista()

    def _seccion_elegida(self, rc):
        sc = getattr(self, "_sec_consulta", None)
        if sc is not None and sc.eje_id == rc.calle.eje_id and fmt_prog(sc.prog) == self.v_prog.get():
            return sc
        txt = self.v_prog.get()
        sec = next((s for s in rc.secciones if fmt_prog(s.prog) == txt and not s.omitida), None)
        return sec or next(s for s in rc.secciones if not s.omitida)

    def dibujar_vista(self):
        self.lz_rev.limpiar()
        rc = self._rc()
        if rc is None:
            self.lz_rev.dibujar()
            return
        v = self.v_vista.get()
        fig = self.lz_rev.fig
        if v == "Sección":
            sec = self._seccion_elegida(rc)
            dibujar_seccion(fig.add_subplot(111), sec, self.proy, self.res)
            self._llenar_ficha(sec)
        elif v == "Perfil":
            dibujar_perfil(fig, rc, self.res)
            self.lz_rev.canvas.draw_idle()
            return
        elif v == "Planta":
            dibujar_planta(fig.add_subplot(111), self.res, rc.calle.eje_id)
        else:
            try:
                exag = float(self.v_exag.get())
            except ValueError:
                exag = 4.0
            ax = fig.add_subplot(111, projection="3d")
            tramo = (rc.calle.eje_id, self._seccion_elegida(rc).prog, 20.0) if self.v_tramo.get() else None
            dibujar_3d(ax, self.res, [rc.calle.eje_id] if tramo else None, exag, self.v_tn.get(), True, tramo)
            ax.view_init(elev=28, azim=-60 if tramo else -120)
        self.lz_rev.dibujar()

    def _llenar_ficha(self, sec):
        self.tab_ficha.cargar([[c, f"{o:+.2f}", f3(z)] for c, o, z in sec.puntos])
        t = self.ficha_txt
        t.delete("1.0", "end")
        t.insert("end", f"{sec.eje_id}  {fmt_prog(sec.prog)}  ({sec.tipo.lower()})\n")
        t.insert("end", f"Este {sec.e:.3f}   Norte {sec.n:.3f}\nRasante {sec.rasante:.3f}   pendiente {sec.pendiente:+.2f} %\n")
        t.insert("end", f"Corte {sec.area_corte:.3f} m²   Relleno {sec.area_relleno:.3f} m²\n")
        for l, nom in (("I", "Izq."), ("D", "Der.")):
            d = sec.vereda_disponible.get(l)
            t.insert("end", f"Vereda {nom}: {sec.vereda_ancho.get(l, 0):.2f} m"
                            + (f" (fachada a {d:.2f} m del sardinel)" if d is not None else " (sin fachada)") + "\n")
        for nombre in sec.poligonos:
            a = sec.area(nombre)
            if a > 0:
                t.insert("end", f"{nombre}: {a:.3f} m²\n")

    def _clic_revision(self, ev):
        if self.v_vista.get() != "Planta" or ev.inaxes is None or self.res is None:
            return
        if self.lz_rev.canvas.toolbar is not None and self.lz_rev.canvas.toolbar.mode:
            return
        mejor = None
        for k, rc in self.res.calles.items():
            p, off, fuera = rc.alin.proyectar(ev.xdata, ev.ydata)
            if fuera < 1 and (mejor is None or abs(off) < mejor[2]):
                mejor = (k, p, abs(off))
        if mejor and mejor[2] < 15:
            self.v_calle.set(mejor[0])
            self._llenar_progs()
            self.v_ir.set(f"{mejor[1]:.2f}")
            self._ir_a_prog()

    def ir_a(self, eje, prog):
        if self.res is None or eje not in self.res.calles or prog is None:
            return
        self.v_calle.set(eje)
        self._llenar_progs()
        self.v_ir.set(f"{prog:.2f}")
        self._ir_a_prog()
        self.nb.select(self.tabs["rev"])

    # ================================================================ 5 interferencias
    def _tab_interferencias(self):
        t = self.tabs["int"]
        ctl = ttk.Frame(t)
        ctl.pack(fill="x")
        ttk.Label(ctl, text="Mostrar:").pack(side="left")
        self.v_niv = tk.StringVar(value="ERROR y AVISO")
        cb = ttk.Combobox(ctl, textvariable=self.v_niv, values=["Todos", "ERROR y AVISO", "ERROR", "AVISO", "INFO"],
                          width=14, state="readonly")
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda _: self.refrescar_interferencias())
        self.int_info = tk.StringVar()
        ttk.Label(ctl, textvariable=self.int_info, style="Ficha.TLabel").pack(side="left", padx=12)
        ttk.Label(t, text="Puertas, cocheras, buzones, postes y demás elementos contra el diseño. "
                          "Doble clic en una fila: abre su sección.", foreground="#566573").pack(anchor="w")
        self.tab_int = Tabla(t, ["Nivel", "Tipo", "Id", "Elemento", "Eje", "Progresiva", "Lado", "Offset", "Zona",
                                 "Cota campo", "Cota diseño", "Dif. (m)", "Estado", "Qué hacer"],
                             {0: 55, 1: 75, 2: 95, 3: 150, 4: 60, 5: 80, 6: 40, 7: 60, 8: 80, 9: 80, 10: 80, 11: 65,
                              12: 260, 13: 420}, alto=14, al_doble=self._doble_interf)
        self.tab_int.tree.column("c12", anchor="w")
        self.tab_int.tree.column("c13", anchor="w")
        self.tab_int.pack(fill="both", expand=True)
        f = ttk.LabelFrame(t, text="Todos los avisos del cálculo (perfil, veredas, cruces, levantamiento)", padding=4)
        f.pack(fill="both", expand=True, pady=(6, 0))
        self.tab_av = Tabla(f, ["Nivel", "Categoría", "Eje", "Progresiva", "Mensaje"], {0: 60, 1: 100, 2: 60, 3: 80, 4: 1100},
                            alto=8, al_doble=self._doble_aviso)
        self.tab_av.tree.column("c4", anchor="w")
        self.tab_av.pack(fill="both", expand=True)

    def _interf_visibles(self):
        if self.res is None:
            return []
        f = self.v_niv.get()
        ok = {"Todos": {"ERROR", "AVISO", "INFO"}, "ERROR y AVISO": {"ERROR", "AVISO"}}.get(f, {f})
        return [x for x in self.res.interferencias if x["nivel"] in ok]

    def refrescar_interferencias(self):
        lista = self._interf_visibles()
        self.tab_int.cargar([[x["nivel"], x["tipo"].lower(), x["id"], x["nombre"], x["eje"],
                              fmt_prog(x["prog"]) if x["prog"] is not None else "", x["lado"],
                              f"{x['offset']:+.2f}" if x["offset"] is not None else "", x["zona"].lower(),
                              f3(x["cota_campo"]), f3(x["cota_diseno"]),
                              f"{x['diferencia']:+.3f}" if x["diferencia"] is not None else "", x["estado"], x["accion"]]
                             for x in lista], [x["nivel"] for x in lista])
        if self.res is not None:
            todos = self.res.interferencias
            self.int_info.set(f"{sum(x['nivel'] == 'ERROR' for x in todos)} errores · "
                              f"{sum(x['nivel'] == 'AVISO' for x in todos)} avisos · {len(todos)} elementos revisados")
            av = self.res.avisos
            self.tab_av.cargar([[a.nivel, a.categoria, a.eje_id, fmt_prog(a.prog) if a.prog is not None else "", a.mensaje]
                                for a in av], [a.nivel for a in av])

    def _doble_interf(self, i):
        lista = self._interf_visibles()
        if i < len(lista):
            self.ir_a(lista[i]["eje"], lista[i]["prog"])

    def _doble_aviso(self, i):
        if self.res and i < len(self.res.avisos):
            a = self.res.avisos[i]
            self.ir_a(a.eje_id, a.prog)

    # ================================================================ 6 tierras
    def _tab_tierras(self):
        t = self.tabs["tie"]
        ctl = ttk.Frame(t)
        ctl.pack(fill="x")
        ttk.Label(ctl, text="Calle:").pack(side="left")
        self.v_calle_t = tk.StringVar(value="Resumen total")
        self.cb_calle_t = ttk.Combobox(ctl, textvariable=self.v_calle_t, width=26, state="readonly")
        self.cb_calle_t.pack(side="left", padx=4)
        self.cb_calle_t.bind("<<ComboboxSelected>>", lambda _: self.refrescar_tierras())
        for k, txt in (("esponjamiento", "Esponjamiento %"), ("contraccion_relleno", "Contracción relleno %"),
                       ("reutilizacion_corte", "Reutilizar corte %")):
            ttk.Label(ctl, text="   " + txt).pack(side="left")
            var = tk.StringVar()
            e = ttk.Entry(ctl, textvariable=var, width=6)
            e.pack(side="left", padx=2)
            e.bind("<Return>", lambda _, k=k, var=var: self._factor(k, var))
            setattr(self, "v_" + k, var)
        ttk.Button(ctl, text="Aplicar", command=lambda: [self._factor(k, getattr(self, "v_" + k)) for k in
                                                         ("esponjamiento", "contraccion_relleno", "reutilizacion_corte")]
                   ).pack(side="left", padx=4)
        cuerpo = ttk.PanedWindow(t, orient="horizontal")
        cuerpo.pack(fill="both", expand=True, pady=(4, 0))
        izq = ttk.Frame(cuerpo)
        cuerpo.add(izq, weight=3)
        self.tot_t = tk.StringVar()
        ttk.Label(izq, textvariable=self.tot_t, style="Ficha.TLabel").pack(anchor="w", pady=2)
        self.tab_tie = Tabla(izq, ["Desde"], alto=12)
        self.tab_tie.pack(fill="both", expand=True)
        fb = ttk.LabelFrame(izq, text="Balance y metrado de partidas (m³)", padding=4)
        fb.pack(fill="x", pady=(6, 0))
        self.tab_bal = Tabla(fb, ["Partida"], alto=11)
        self.tab_bal.pack(fill="x")
        self.lz_tie = Lienzo(cuerpo, (7, 6))
        cuerpo.add(self.lz_tie, weight=2)

    def _factor(self, k, var):
        try:
            self.proy.parametros[k] = numero(var.get())
        except ValueError:
            return
        if self.vars_par.get(k):
            self.vars_par[k].set(var.get())
        self.calcular()

    def refrescar_tierras(self):
        for k in ("esponjamiento", "contraccion_relleno", "reutilizacion_corte"):
            getattr(self, "v_" + k).set(f"{self.proy.p(k):g}")
        if self.res is None:
            return
        r = self.res
        k = self.v_calle_t.get()
        self.lz_tie.limpiar()
        if k in r.calles:
            rc = r.calles[k]
            self.tab_tie.poner_columnas(["Desde", "Hasta", "Dist.", "A. corte 1", "A. corte 2", "A. rell. 1", "A. rell. 2",
                                         "V. corte", "V. relleno", "Acum. corte", "Acum. relleno"],
                                        {i: 78 for i in range(11)})
            self.tab_tie.cargar([[fmt_prog(t["desde"]), fmt_prog(t["hasta"]), f"{t['distancia']:.2f}", f"{t['ac1']:.3f}",
                                  f"{t['ac2']:.3f}", f"{t['ar1']:.3f}", f"{t['ar2']:.3f}", f"{t['vol_corte']:.2f}",
                                  f"{t['vol_relleno']:.2f}", f"{t['acum_corte']:.2f}", f"{t['acum_relleno']:.2f}"]
                                 for t in rc.tramos_volumen])
            self.tot_t.set(f"{k} {rc.calle.nombre}: corte {rc.vol_corte:.2f} m³ · relleno {rc.vol_relleno:.2f} m³ · "
                           f"neto {rc.vol_neto:.2f} m³")
            dibujar_tierras(self.lz_tie.fig, rc)
            calles = [rc]
        else:
            self.tab_tie.poner_columnas(["Eje", "Calle", "Longitud", "Corte", "Relleno", "Neto", "Eliminación", "Préstamo"],
                                        {1: 170})
            filas = [[kk, rc.calle.nombre, f"{rc.alin.longitud:.2f}", f"{rc.vol_corte:.2f}", f"{rc.vol_relleno:.2f}",
                      f"{rc.vol_neto:.2f}", f"{rc.balance['eliminacion']:.2f}", f"{rc.balance['prestamo']:.2f}"]
                     for kk, rc in r.calles.items()]
            b = r.balance_total()
            filas.append(["TOTAL", "", f"{sum(rc.alin.longitud for rc in r.calles.values()):.2f}", f"{b['corte']:.2f}",
                          f"{b['relleno']:.2f}", f"{b['corte'] - b['relleno']:.2f}", f"{b['eliminacion']:.2f}",
                          f"{b['prestamo']:.2f}"])
            self.tab_tie.cargar(filas, [""] * (len(filas) - 1) + ["INFO"])
            self.tot_t.set(f"TOTAL: corte {b['corte']:.2f} m³ · relleno {b['relleno']:.2f} m³ · eliminación "
                           f"{b['eliminacion']:.2f} m³ · préstamo {b['prestamo']:.2f} m³")
            ax = self.lz_tie.fig.add_subplot(111)
            nombres = list(r.calles.keys())
            import numpy as np
            x = np.arange(len(nombres))
            ax.bar(x - 0.2, [r.calles[n].vol_corte for n in nombres], 0.4, color="#e74c3c", label="Corte")
            ax.bar(x + 0.2, [r.calles[n].vol_relleno for n in nombres], 0.4, color="#27ae60", label="Relleno")
            ax.set_xticks(x, nombres)
            ax.set_ylabel("m³")
            ax.grid(alpha=0.25, axis="y")
            ax.legend()
            ax.set_title("Corte y relleno por calle", fontsize=10, weight="bold")
            calles = list(r.calles.values())
        self.lz_tie.dibujar()
        # balance y partidas
        cols = ["Partida"] + [c.calle.eje_id for c in calles] + (["TOTAL"] if len(calles) > 1 else [])
        self.tab_bal.poner_columnas(cols, {0: 300})
        partidas = [("Excavación / corte (en banco)", "corte"), ("Relleno compactado", "relleno"),
                    ("Corte reutilizado como relleno", "reutilizado"),
                    (f"Eliminación de excedente (esponjado {self.proy.p('esponjamiento'):g} %)", "eliminacion"),
                    (f"Material de préstamo para relleno (+{self.proy.p('contraccion_relleno'):g} %)", "prestamo")]
        filas = []
        for txt, k_ in partidas:
            vals = [c.balance.get(k_, 0) for c in calles]
            filas.append([txt] + [f"{v:.2f}" for v in vals] + ([f"{sum(vals):.2f}"] if len(calles) > 1 else []))
        for nm in calles[0].materiales:
            vals = [c.materiales.get(nm, 0) for c in calles]
            filas.append([nm] + [f"{v:.2f}" for v in vals] + ([f"{sum(vals):.2f}"] if len(calles) > 1 else []))
        self.tab_bal.cargar(filas)

    # ================================================================ 7 puntos y BM
    def _tab_puntos(self):
        t = self.tabs["pun"]
        fb = ttk.LabelFrame(t, text="BM de la obra — numerados y ubicados respecto a las calles", padding=4)
        fb.pack(fill="x")
        self.tab_bm = Tabla(fb, ["BM", "Punto", "Este", "Norte", "Cota", "Ubicación", "Descripción"],
                            {0: 60, 1: 50, 2: 100, 3: 110, 4: 80, 5: 430, 6: 220}, alto=5, al_doble=self._doble_bm)
        self.tab_bm.tree.column("c5", anchor="w")
        self.tab_bm.pack(fill="x")
        fl = ttk.Frame(t)
        fl.pack(fill="x", pady=4)
        ttk.Label(fl, text="Lectura de mira:  BM").pack(side="left")
        self.v_bm = tk.StringVar()
        self.cb_bm = ttk.Combobox(fl, textvariable=self.v_bm, width=8, state="readonly")
        self.cb_bm.pack(side="left", padx=3)
        ttk.Label(fl, text="lectura atrás (m)").pack(side="left")
        self.v_la = tk.StringVar(value="1.500")
        ttk.Entry(fl, textvariable=self.v_la, width=8).pack(side="left", padx=3)
        self.v_ai = tk.StringVar()
        ttk.Label(fl, textvariable=self.v_ai, style="Ficha.TLabel").pack(side="left", padx=8)
        for v in (self.v_bm, self.v_la):
            v.trace_add("write", lambda *_: self._mostrar_ai())

        fp = ttk.LabelFrame(t, text="Puntos de replanteo — filtre y exporte", padding=4)
        fp.pack(fill="both", expand=True)
        ff = ttk.Frame(fp)
        ff.pack(fill="x")
        ttk.Label(ff, text="Calle").pack(side="left")
        self.v_pcalle = tk.StringVar(value="Todas")
        self.cb_pcalle = ttk.Combobox(ff, textvariable=self.v_pcalle, width=10, state="readonly")
        self.cb_pcalle.pack(side="left", padx=3)
        ttk.Label(ff, text="Superficie").pack(side="left")
        self.v_pcapa = tk.StringVar(value="Terminado")
        self.cb_pcapa = ttk.Combobox(ff, textvariable=self.v_pcapa, width=34, state="readonly")
        self.cb_pcapa.pack(side="left", padx=3)
        ttk.Label(ff, text="Código contiene").pack(side="left")
        self.v_pcod = tk.StringVar()
        ttk.Entry(ff, textvariable=self.v_pcod, width=8).pack(side="left", padx=3)
        ttk.Button(ff, text="Filtrar", command=self.refrescar_puntos).pack(side="left", padx=3)
        ttk.Button(ff, text="📤 Exportar CSV (estación total)…", command=self.exportar_puntos).pack(side="left", padx=6)
        ttk.Button(ff, text="📋 Copiar", command=self.copiar_puntos).pack(side="left")
        for cb in (self.cb_pcalle, self.cb_pcapa):
            cb.bind("<<ComboboxSelected>>", lambda _: self.refrescar_puntos())
        self.p_info = tk.StringVar()
        ttk.Label(fp, textvariable=self.p_info, foreground=AZUL).pack(anchor="w")
        self.tab_rep = Tabla(fp, ["Nombre", "Eje", "Progresiva", "Código", "Descripción", "Offset", "Este", "Norte", "Cota",
                                  "Lectura mira"], {0: 140, 1: 60, 2: 80, 3: 60, 4: 220, 5: 60, 6: 100, 7: 110, 8: 80, 9: 80},
                             alto=14)
        self.tab_rep.pack(fill="both", expand=True)

    def _mostrar_ai(self):
        ai = self._ai()
        self.v_ai.set(f"AI = {ai:.3f}" if ai is not None else "")
        if self.res is not None:
            self.refrescar_puntos()

    def _ai(self):
        try:
            return altura_instrumento(self.proy, self.v_bm.get() or None, numero(self.v_la.get()))
        except ValueError:
            return None

    def _filas_puntos(self):
        if self.res is None:
            return []
        ai = self._ai()
        sup = self.v_pcapa.get()
        cod = self.v_pcod.get().strip().upper()
        out = []
        for k, rc in self.res.calles.items():
            if self.v_pcalle.get() not in ("Todas", k):
                continue
            if sup == "Terminado":
                pts = puntos_seccion(rc)
                for p in pts:
                    p["lectura"] = (ai - p["cota"]) if ai is not None else None
            else:
                pts = [p for p in puntos_capas(rc, self.proy, ai) if p["capa"] == sup]
                for p in pts:
                    p["descripcion"] = p["capa"]
            out += [p for p in pts if not cod or cod in p["codigo"]]
        return out

    def refrescar_puntos(self):
        if self.res is None:
            return
        from .replanteo import capas_replanteo
        self.cb_pcalle["values"] = ["Todas"] + list(self.res.calles.keys())
        self.cb_pcapa["values"] = ["Terminado"] + [n for _, n, _ in capas_replanteo(self.proy)]
        filas = self._filas_puntos()
        self.tab_rep.cargar([[p["nombre"], p["eje_id"], p["progresiva"], p["codigo"], p.get("descripcion", ""),
                              f"{p['offset']:+.2f}", f3(p["este"]), f3(p["norte"]), f3(p["cota"]), f3(p.get("lectura"))]
                             for p in filas])
        self.p_info.set(f"{len(filas)} puntos")
        bms = {b["bm"].id: b for b in self.res.bm_ubicacion}
        self.tab_bm.cargar([[b.id, b.punto, f3(b.este), f3(b.norte), f3(b.cota), bms.get(b.id, {}).get("texto", ""),
                             b.descripcion] for b in self.proy.bms])

    def _doble_bm(self, i):
        if self.res and i < len(self.res.bm_ubicacion):
            b = self.res.bm_ubicacion[i]
            self.nb.select(self.tabs["lev"])
            self.refrescar_levantamiento(resaltar=(b["bm"].este, b["bm"].norte))

    def exportar_puntos(self):
        ruta = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")],
                                            initialfile="replanteo.csv")
        if not ruta:
            return
        import csv
        with open(ruta, "w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["nombre", "este", "norte", "cota", "codigo"])
            for p in self._filas_puntos():
                w.writerow([p["nombre"], f3(p["este"]), f3(p["norte"]), f3(p["cota"]), p["codigo"]])
        self.estado.set(f"Puntos exportados: {ruta}")

    def copiar_puntos(self):
        txt = "\n".join(f"{p['nombre']}\t{p['este']:.3f}\t{p['norte']:.3f}\t{p['cota']:.3f}\t{p['codigo']}"
                        for p in self._filas_puntos())
        self.clipboard_clear()
        self.clipboard_append(txt)
        self.estado.set("Puntos copiados al portapapeles (pegue en Excel).")

    # ================================================================ 8 exportar
    def _tab_exportar(self):
        t = self.tabs["exp"]
        g = ttk.LabelFrame(t, text="Exportar resultados", padding=10)
        g.pack(fill="x")
        ttk.Label(g, text="Carpeta de salida:").grid(row=0, column=0, sticky="w")
        self.v_sal = tk.StringVar()
        ttk.Entry(g, textvariable=self.v_sal, width=90).grid(row=0, column=1, padx=4)
        ttk.Button(g, text="…", width=3, command=self._elegir_salida).grid(row=0, column=2)
        self.v_fmt = {}
        textos = [("excel", "📊 Informe Excel (resumen, secciones, puntos, capas, tierras, interferencias, BM)", True),
                  ("pdf", "📄 Informe PDF (planta, perfiles con guitarra, secciones, tierras, interferencias, BM)", True),
                  ("csv", "📍 CSV: eje progresiva-coordenada, estación total, tablas de campo con lectura de mira", True),
                  ("civil3d", "🏗 Civil 3D 2025: paquete para el complemento (comando CSIMPORTAR)", True),
                  ("landxml", "Civil 3D: LandXML (alineamientos, perfiles, superficies) — alternativa sin complemento", False),
                  ("dxf", "Civil 3D / AutoCAD: DXF 3D con hojas de secciones y perfil", False)]
        for i, (k, txt, val) in enumerate(textos):
            v = tk.BooleanVar(value=val)
            ttk.Checkbutton(g, text=txt, variable=v).grid(row=1 + i, column=1, sticky="w", pady=1)
            self.v_fmt[k] = v
        ttk.Button(g, text="💾  EXPORTAR", style="Grande.TButton", command=self.exportar).grid(row=7, column=1, sticky="w",
                                                                                            pady=8)
        h = ttk.LabelFrame(t, text="Civil 3D 2025", padding=8)
        h.pack(fill="x", pady=(6, 0))
        ttk.Label(h, text="1) Instale una vez el complemento: civil3d\\instalar_en_civil3d.bat   "
                          "2) Exporte aquí con la opción Civil 3D   3) En Civil 3D escriba CSIMPORTAR y elija "
                          "corredor_civil3d.json. Se crean puntos COGO y grupos, superficies, alineamientos, perfiles, "
                          "líneas 3D, capas 3D, interferencias y BM.", wraplength=1300, justify="left").pack(anchor="w")
        self.log = tk.Text(t, height=14, font=("Consolas", 9), relief="flat", bg="#fbfcfc")
        self.log.pack(fill="both", expand=True, pady=(6, 0))

    def _elegir_salida(self):
        d = filedialog.askdirectory(title="Carpeta de salida")
        if d:
            self.v_sal.set(d)

    def exportar(self, formatos=None, carpeta=None):
        if self.res is None and not self.calcular():
            return None
        carpeta = carpeta or self.v_sal.get() or filedialog.askdirectory(title="Carpeta de salida")
        if not carpeta:
            return None
        formatos = formatos or [k for k, v in self.v_fmt.items() if v.get()]
        try:
            arch = exportar_todo(self.res, carpeta, self._ai(), formatos)
        except PermissionError as e:
            messagebox.showerror("No se pudo guardar", f"¿Tiene el archivo abierto en Excel?\n{e}")
            return None
        self.log.delete("1.0", "end")
        self.log.insert("end", f"Exportado en {carpeta}:\n" + "\n".join(f"  {a}" for a in arch))
        self.estado.set(f"Exportados {len(arch)} archivos en {carpeta}")
        return arch

    # ================================================================ acciones generales
    def modificado(self):
        self.res = None
        self.estado.set("Datos modificados: presione CALCULAR (F5).")

    def abrir_dialogo(self):
        d = filedialog.askdirectory(title="Carpeta del proyecto")
        if d:
            self.abrir(d)

    def cargar_ejemplo(self):
        self.abrir(recurso("datos_ejemplo"))

    def abrir(self, carpeta):
        try:
            self.proy = leer_proyecto(carpeta)
        except (DatoError, OSError, KeyError) as e:
            messagebox.showerror("No se pudo abrir el proyecto", str(e))
            return
        self.carpeta = str(carpeta)
        self.v_sal.set(str(Path(carpeta) / "salida"))
        self.res = None
        self._tin = None
        self.refrescar_todo()
        self.calcular()

    def guardar(self):
        d = self.carpeta
        if not d or Path(d).resolve() == recurso("datos_ejemplo").resolve():
            d = filedialog.askdirectory(title="Guardar proyecto en carpeta")
        if not d:
            return
        guardar_proyecto(self.proy, d)
        self.carpeta = d
        self.estado.set(f"Proyecto guardado en {d}")

    def calcular(self):
        self.aplicar_prog0()
        err = validar_proyecto(self.proy)
        if err:
            messagebox.showerror("Faltan datos", "\n".join(err))
            return False
        try:
            self.res = calcular(self.proy)
        except (ValueError, ZeroDivisionError) as e:
            messagebox.showerror("Error de cálculo", str(e))
            return False
        r = self.res
        ne = sum(a.nivel == "ERROR" for a in r.avisos)
        na = sum(a.nivel == "AVISO" for a in r.avisos)
        b = r.balance_total()
        self.estado.set(f"✔ {len(r.calles)} calles · {sum(len(rc.secciones) for rc in r.calles.values())} secciones · "
                        f"corte {b['corte']:.1f} m³ · relleno {b['relleno']:.1f} m³ · ⛔ {ne} errores · ⚠ {na} avisos")
        self.cb_calle["values"] = list(r.calles.keys())
        if self.v_calle.get() not in r.calles:
            self.v_calle.set(next(iter(r.calles)))
        self.cb_calle_t["values"] = ["Resumen total"] + list(r.calles.keys())
        self.cb_bm["values"] = [x.id for x in self.proy.bms]
        if self.proy.bms and self.v_bm.get() not in self.cb_bm["values"]:
            self.v_bm.set(self.proy.bms[0].id)
        self._llenar_progs()
        self.refrescar_levantamiento()
        self.refrescar_interferencias()
        self.refrescar_tierras()
        self.refrescar_puntos()
        self.dibujar_vista()
        return True

    def refrescar_todo(self):
        self.refrescar_levantamiento()
        self.refrescar_calles(0)
        self.refrescar_capas()


class DialogoOrigen(simpledialog.Dialog):
    def __init__(self, master, titulo, origen, puntos):
        self.origen = origen
        self.puntos = puntos
        self.resultado = None
        super().__init__(master, titulo)

    def body(self, m):
        ttk.Label(m, text="Punto de origen del eje (donde empieza la calzada) y su dirección.\n"
                          "Puede escribir un número de punto del levantamiento en 'Punto origen' y 'Punto final'.").grid(
            row=0, column=0, columnspan=3, pady=(0, 6))
        self.vars = []
        campos = (("Este (m)", f"{self.origen[0]:.3f}"), ("Norte (m)", f"{self.origen[1]:.3f}"),
                  ("Azimut (°, 0 = Norte, horario)", "90"), ("Longitud (m)", "100"),
                  ("Punto origen (opcional)", ""), ("Punto final (opcional)", ""))
        for i, (t, v) in enumerate(campos):
            ttk.Label(m, text=t).grid(row=i + 1, column=0, sticky="w")
            var = tk.StringVar(value=v)
            ttk.Entry(m, textvariable=var, width=18).grid(row=i + 1, column=1, padx=4, pady=2)
            self.vars.append(var)
        return None

    def _punto(self, num):
        return next((q for q in self.puntos if q.numero == num.strip()), None)

    def validate(self):
        try:
            e, n, az, L = (numero(v.get()) for v in self.vars[:4])
        except ValueError:
            messagebox.showerror("Dato no válido", "Revise los números.")
            return False
        po, pf = self.vars[4].get().strip(), self.vars[5].get().strip()
        if po:
            q = self._punto(po)
            if q is None:
                messagebox.showerror("Punto", f"No existe el punto {po}.")
                return False
            e, n = q.este, q.norte
        if pf:
            q = self._punto(pf)
            if q is None:
                messagebox.showerror("Punto", f"No existe el punto {pf}.")
                return False
            az = math.degrees(math.atan2(q.este - e, q.norte - n)) % 360
            L = math.hypot(q.este - e, q.norte - n)
        if L <= 0:
            messagebox.showerror("Dato no válido", "La longitud debe ser mayor que 0.")
            return False
        self.resultado = (e, n, az, L)
        return True


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    app = App(argv[0] if argv else None)
    app.mainloop()
