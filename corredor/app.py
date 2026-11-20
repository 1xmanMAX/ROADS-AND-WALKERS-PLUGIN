"""Ventana principal de Corredor Simple (Tkinter).

Una sola ventana con 6 pestañas:
  1. Levantamiento   2. Calles   3. Capas   4. Modelo 3D   5. Movimiento de tierras   6. Exportar
"""
import math
import os
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import matplotlib

matplotlib.use("TkAgg")
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from . import __version__  # noqa: E402
from .datos import (DatoError, encadenar_cotas, guardar_proyecto, leer_bms, leer_fachadas,  # noqa: E402
                    leer_proyecto, leer_terreno, leer_umbrales, validar_proyecto)
from .exportar import altura_instrumento, exportar_todo  # noqa: E402
from .geometria import fmt_prog  # noqa: E402
from .graficos import dibujar_3d, dibujar_perfil, dibujar_planta, dibujar_seccion  # noqa: E402
from .modelo import PARAMETROS, TEXTO, Calle, Capa, Proyecto, TramoCuneta  # noqa: E402
from .motor import calcular  # noqa: E402
from .terreno import Terreno  # noqa: E402


def recurso(rel):
    """Ruta a un recurso (funciona también dentro del .exe de PyInstaller)."""
    base = getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent)
    return Path(base) / rel


COLS_TIERRAS = ["Desde", "Hasta", "Dist. (m)", "Área corte 1 (m²)", "Área corte 2 (m²)", "Área relleno 1 (m²)",
                "Área relleno 2 (m²)", "Vol. corte (m³)", "Vol. relleno (m³)", "Acum. corte", "Acum. relleno"]


# ------------------------------------------------------------------ tabla editable
class Tabla(ttk.Frame):
    """Treeview con edición por doble clic."""

    def __init__(self, master, columnas, anchos=None, al_editar=None, editable=None, alto=8):
        super().__init__(master)
        self.columnas = columnas
        self.al_editar = al_editar
        self.editable = editable if editable is not None else set(range(len(columnas)))
        self.tree = ttk.Treeview(self, columns=[f"c{i}" for i in range(len(columnas))], show="headings",
                                 height=alto, selectmode="browse")
        for i, c in enumerate(columnas):
            self.tree.heading(f"c{i}", text=c)
            self.tree.column(f"c{i}", width=(anchos or {}).get(i, 90), anchor="center", stretch=True)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.tree.bind("<Double-1>", self._editar)
        self._entry = None

    def poner_columnas(self, columnas, anchos=None):
        self.columnas = columnas
        self.tree.configure(columns=[f"c{i}" for i in range(len(columnas))])
        for i, c in enumerate(columnas):
            self.tree.heading(f"c{i}", text=c)
            self.tree.column(f"c{i}", width=(anchos or {}).get(i, 110), anchor="center", stretch=True)

    def cargar(self, filas, tags=None):
        self.tree.delete(*self.tree.get_children())
        for i, f in enumerate(filas):
            self.tree.insert("", "end", iid=str(i), values=f, tags=(tags[i],) if tags else ())

    def seleccion(self):
        s = self.tree.selection()
        return int(s[0]) if s else None

    def seleccionar(self, i):
        if str(i) in self.tree.get_children():
            self.tree.selection_set(str(i))
            self.tree.see(str(i))

    def _editar(self, ev):
        if self.tree.identify_region(ev.x, ev.y) != "cell":
            return
        fila = self.tree.identify_row(ev.y)
        col = int(self.tree.identify_column(ev.x)[1:]) - 1
        if col not in self.editable or self.al_editar is None:
            return
        x, y, w, h = self.tree.bbox(fila, f"c{col}")
        valor = self.tree.set(fila, f"c{col}")
        e = ttk.Entry(self.tree)
        e.insert(0, valor)
        e.select_range(0, "end")
        e.place(x=x, y=y, width=w, height=h)
        e.focus_set()

        def fin(guardar):
            if guardar:
                nuevo = e.get()
                e.destroy()
                try:
                    self.al_editar(int(fila), col, nuevo)
                except (ValueError, DatoError) as err:
                    messagebox.showerror("Dato no válido", f"'{nuevo}': {err}")
            else:
                e.destroy()

        e.bind("<Return>", lambda _: fin(True))
        e.bind("<KP_Enter>", lambda _: fin(True))
        e.bind("<Escape>", lambda _: fin(False))
        e.bind("<FocusOut>", lambda _: fin(True))


def numero(txt):
    txt = str(txt).strip().replace(",", ".")
    if txt.count("+") == 1 and txt.replace("+", "").replace(".", "").isdigit():   # 0+120.00
        km, m = txt.split("+")
        return float(km) * 1000 + float(m)
    return float(txt)


# ------------------------------------------------------------------ aplicación
class App(tk.Tk):
    def __init__(self, carpeta=None):
        super().__init__()
        self.title(f"Corredor Simple {__version__} — pistas y veredas para Civil 3D")
        self.geometry("1500x930")
        self.minsize(1100, 700)
        estilo = ttk.Style(self)
        if "clam" in estilo.theme_names():
            estilo.theme_use("clam")
        estilo.configure("Treeview", rowheight=22)
        estilo.configure("Grande.TButton", font=("Segoe UI", 11, "bold"), padding=6)
        self.proy = Proyecto()
        self.carpeta = None
        self.res = None
        self._construir()
        if carpeta:
            self.abrir(carpeta)

    # ---------------------------------------------------------------- estructura
    def _construir(self):
        barra = ttk.Frame(self, padding=(8, 6))
        barra.pack(fill="x")
        ttk.Button(barra, text="📂 Abrir proyecto…", command=self.abrir_dialogo).pack(side="left", padx=3)
        ttk.Button(barra, text="💾 Guardar proyecto", command=self.guardar).pack(side="left", padx=3)
        ttk.Button(barra, text="Cargar ejemplo", command=self.cargar_ejemplo).pack(side="left", padx=3)
        ttk.Button(barra, text="▶  CALCULAR", style="Grande.TButton", command=self.calcular).pack(side="left", padx=16)
        self.estado = tk.StringVar(value="Abra un proyecto (carpeta con CSV) o cargue el ejemplo.")
        ttk.Label(barra, textvariable=self.estado, foreground="#1a5276").pack(side="left", padx=10)

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.t_lev = ttk.Frame(self.nb, padding=6)
        self.t_cal = ttk.Frame(self.nb, padding=6)
        self.t_cap = ttk.Frame(self.nb, padding=6)
        self.t_3d = ttk.Frame(self.nb, padding=6)
        self.t_tie = ttk.Frame(self.nb, padding=6)
        self.t_exp = ttk.Frame(self.nb, padding=6)
        for f, t in ((self.t_lev, "1. Levantamiento"), (self.t_cal, "2. Calles"), (self.t_cap, "3. Capas"),
                     (self.t_3d, "4. Modelo 3D y vistas"), (self.t_tie, "5. Movimiento de tierras"),
                     (self.t_exp, "6. Exportar y avisos")):
            self.nb.add(f, text=t)
        self._tab_levantamiento()
        self._tab_calles()
        self._tab_capas()
        self._tab_3d()
        self._tab_tierras()
        self._tab_exportar()

    # ---------------------------------------------------------------- 1 levantamiento
    def _tab_levantamiento(self):
        izq = ttk.Frame(self.t_lev)
        izq.pack(side="left", fill="y")
        ttk.Label(izq, text="Datos del levantamiento", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(0, 6))
        for txt, cmd in (("Importar terreno (punto, Este, Norte, cota, código)…", self.imp_terreno),
                         ("Importar fachadas / límites de propiedad…", self.imp_fachadas),
                         ("Importar puertas y cocheras (umbrales)…", self.imp_umbrales),
                         ("Importar BM…", self.imp_bms)):
            ttk.Button(izq, text=txt, command=cmd, width=48).pack(anchor="w", pady=2)
        self.lev_info = tk.StringVar()
        ttk.Label(izq, textvariable=self.lev_info, justify="left").pack(anchor="w", pady=10)
        ttk.Label(izq, text="Puntos del terreno").pack(anchor="w")
        self.tab_tn = Tabla(izq, ["Punto", "Este", "Norte", "Cota", "Código"], {0: 60, 1: 95, 2: 105, 3: 80, 4: 60},
                            alto=22)
        self.tab_tn.pack(fill="both", expand=True)
        der = ttk.Frame(self.t_lev)
        der.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self.fig_lev = Figure(figsize=(8, 6), dpi=100)
        self.can_lev = FigureCanvasTkAgg(self.fig_lev, master=der)
        NavigationToolbar2Tk(self.can_lev, der).update()
        self.can_lev.get_tk_widget().pack(fill="both", expand=True)

    def refrescar_levantamiento(self):
        p = self.proy
        self.lev_info.set(f"Puntos de terreno: {len(p.terreno)}\nLíneas de fachada: {len(p.fachadas)} "
                          f"({sum(len(l.puntos) for l in p.fachadas)} puntos)\nPuertas/cocheras: {len(p.umbrales)}\n"
                          f"BM: {len(p.bms)}  " + ", ".join(f"{b.id}={b.cota:.3f}" for b in p.bms))
        self.tab_tn.cargar([[t.numero, f"{t.este:.3f}", f"{t.norte:.3f}", f"{t.cota:.3f}", t.codigo]
                            for t in p.terreno])
        self.fig_lev.clear()
        ax = self.fig_lev.add_subplot(111)
        if self.res is not None:
            dibujar_planta(ax, self.res)
        else:
            if p.terreno:
                ax.scatter([t.este for t in p.terreno], [t.norte for t in p.terreno], s=4, c="#8d6e63")
            for l in p.fachadas:
                ax.plot([q[0] for q in l.puntos], [q[1] for q in l.puntos], color="#c0392b", lw=1)
            for c in p.calles:
                if c.vertices:
                    ax.plot([v[0] for v in c.vertices], [v[1] for v in c.vertices], color="#1a5276", lw=2)
            ax.set_aspect("equal", adjustable="datalim")
            ax.ticklabel_format(useOffset=False, style="plain")
            ax.grid(alpha=0.3)
            ax.set_title("Planta (presione CALCULAR para ver el corredor)")
        self.fig_lev.tight_layout()
        self.can_lev.draw_idle()

    def _importar(self, lector, atributo, titulo):
        ruta = filedialog.askopenfilename(title=titulo, filetypes=[("CSV / texto", "*.csv *.txt"), ("Todos", "*.*")])
        if not ruta:
            return
        try:
            setattr(self.proy, atributo, lector(ruta))
        except (DatoError, KeyError, ValueError) as e:
            messagebox.showerror("No se pudo leer", str(e))
            return
        self.modificado()
        self.refrescar_levantamiento()

    def imp_terreno(self):
        self._importar(leer_terreno, "terreno", "Terreno levantado")

    def imp_fachadas(self):
        self._importar(leer_fachadas, "fachadas", "Fachadas")

    def imp_umbrales(self):
        self._importar(leer_umbrales, "umbrales", "Puertas y cocheras")

    def imp_bms(self):
        self._importar(leer_bms, "bms", "BM")

    # ---------------------------------------------------------------- 2 calles
    def _tab_calles(self):
        arriba = ttk.LabelFrame(self.t_cal, text="Calles (una fila por calle; la primera manda en los cruces)",
                                padding=6)
        arriba.pack(fill="x")
        self.tab_calles = Tabla(arriba, ["Eje", "Nombre de la calle", "Bombeo %", "Ancho calzada (m)",
                                         "Ancho vereda (m)", "Longitud (m)"],
                                {0: 80, 1: 220, 2: 90, 3: 130, 4: 130, 5: 100}, self.editar_calle,
                                editable={0, 1, 2, 3, 4}, alto=6)
        self.tab_calles.pack(side="left", fill="x", expand=True)
        self.tab_calles.tree.bind("<<TreeviewSelect>>", lambda _: self.refrescar_calle_sel())
        bt = ttk.Frame(arriba)
        bt.pack(side="left", padx=6)
        for txt, cmd in (("Agregar calle", self.agregar_calle), ("Quitar calle", self.quitar_calle),
                         ("Subir ↑", lambda: self.mover_calle(-1)), ("Bajar ↓", lambda: self.mover_calle(1))):
            ttk.Button(bt, text=txt, command=cmd, width=16).pack(pady=2)
        ttk.Label(self.t_cal, text="Doble clic en una celda para editarla. Las distancias en metros; "
                                   "progresivas como 120 o 0+120.", foreground="#555").pack(anchor="w", pady=4)
        abajo = ttk.Frame(self.t_cal)
        abajo.pack(fill="both", expand=True)
        fv = ttk.LabelFrame(abajo, text="Eje en planta: vértices (punto de origen = vértice 1)", padding=6)
        fv.pack(side="left", fill="both", expand=True)
        fila = ttk.Frame(fv)
        fila.pack(fill="x")
        ttk.Label(fila, text="Progresiva inicial:").pack(side="left")
        self.prog0 = tk.StringVar()
        en = ttk.Entry(fila, textvariable=self.prog0, width=10)
        en.pack(side="left", padx=4)
        en.bind("<Return>", lambda _: self.aplicar_prog0())
        en.bind("<FocusOut>", lambda _: self.aplicar_prog0())
        self.tab_vert = Tabla(fv, ["Vértice", "Este", "Norte", "Progresiva", "Azimut siguiente"],
                              {0: 60, 1: 110, 2: 120, 3: 90, 4: 110}, self.editar_vertice, editable={1, 2}, alto=10)
        self.tab_vert.pack(fill="both", expand=True, pady=4)
        bv = ttk.Frame(fv)
        bv.pack(fill="x")
        ttk.Button(bv, text="Punto de origen + azimut + longitud…", command=self.eje_desde_origen).pack(side="left", padx=2)
        ttk.Button(bv, text="Agregar tramo (azimut, longitud)…", command=self.agregar_tramo_eje).pack(side="left", padx=2)
        ttk.Button(bv, text="Agregar vértice", command=self.agregar_vertice).pack(side="left", padx=2)
        ttk.Button(bv, text="Quitar vértice", command=self.quitar_vertice).pack(side="left", padx=2)

        fp = ttk.LabelFrame(abajo, text="Perfil de rasante: tramos (progresiva, cota inicial, pendiente %)", padding=6)
        fp.pack(side="left", fill="both", expand=True, padx=(8, 0))
        self.tab_perf = Tabla(fp, ["Prog. inicio", "Cota inicio", "Pendiente %", "Prog. fin", "Cota fin"],
                              {0: 90, 1: 100, 2: 90, 3: 90, 4: 100}, self.editar_tramo, editable={0, 1, 2, 3}, alto=10)
        self.tab_perf.pack(fill="both", expand=True, pady=4)
        bp = ttk.Frame(fp)
        bp.pack(fill="x")
        ttk.Button(bp, text="Agregar tramo", command=self.agregar_tramo).pack(side="left", padx=2)
        ttk.Button(bp, text="Quitar tramo", command=self.quitar_tramo).pack(side="left", padx=2)
        ttk.Button(bp, text="Encadenar cotas", command=self.encadenar).pack(side="left", padx=2)
        ttk.Button(bp, text="Proponer desde el terreno", command=self.perfil_desde_terreno).pack(side="left", padx=2)
        self.perf_info = tk.StringVar()
        ttk.Label(fp, textvariable=self.perf_info, foreground="#1a5276", justify="left").pack(anchor="w", pady=4)

    def calle_sel(self):
        i = self.tab_calles.seleccion()
        if i is None or i >= len(self.proy.calles):
            return None
        return self.proy.calles[i]

    def refrescar_calles(self, sel=None):
        filas = []
        for c in self.proy.calles:
            L = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(c.vertices[:-1], c.vertices[1:]))
            filas.append([c.eje_id, c.nombre, f"{c.bombeo_pct:.2f}", f"{c.ancho_calzada:.2f}",
                          f"{c.ancho_vereda:.2f}", f"{L:.3f}"])
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
            return
        self.prog0.set(f"{c.prog_inicial:.3f}")
        filas, p = [], c.prog_inicial
        for i, (e, n) in enumerate(c.vertices):
            az = ""
            if i + 1 < len(c.vertices):
                e2, n2 = c.vertices[i + 1]
                az = f"{math.degrees(math.atan2(e2 - e, n2 - n)) % 360:.4f}°"
            filas.append([i + 1, f"{e:.3f}", f"{n:.3f}", fmt_prog(p), az])
            if i + 1 < len(c.vertices):
                p += math.hypot(c.vertices[i + 1][0] - e, c.vertices[i + 1][1] - n)
        self.tab_vert.cargar(filas)
        filas = []
        for t in c.tramos:
            zf = t[1] + t[2] / 100 * (t[3] - t[0]) if t[1] is not None else float("nan")
            filas.append([fmt_prog(t[0]), f"{t[1]:.3f}" if t[1] is not None else "", f"{t[2]:+.3f}", fmt_prog(t[3]),
                          f"{zf:.3f}"])
        self.tab_perf.cargar(filas)
        pmax = self.proy.p("pendiente_long_max")
        txt = [f"Pendiente máxima configurada: {pmax:.2f} %"]
        for t in c.tramos:
            if abs(t[2]) > pmax:
                txt.append(f"⚠ Tramo desde {fmt_prog(t[0])}: {t[2]:+.2f} % supera la máxima")
        self.perf_info.set("\n".join(txt))

    def editar_calle(self, i, col, v):
        c = self.proy.calles[i]
        if col == 0:
            if any(o.eje_id == v and o is not c for o in self.proy.calles):
                raise ValueError("ya existe otro eje con ese nombre")
            for l in self.proy.fachadas:
                if l.eje_id == c.eje_id:
                    l.eje_id = v
            for u in self.proy.umbrales:
                if u.eje_id == c.eje_id:
                    u.eje_id = v
            c.eje_id = v.strip()
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
        self.proy.calles.append(Calle(eid, f"Calle {n}"))
        self.modificado()
        self.refrescar_calles(len(self.proy.calles) - 1)
        messagebox.showinfo("Nueva calle", "Defina el eje con 'Punto de origen + azimut + longitud…' "
                                           "y luego el perfil (puede usar 'Proponer desde el terreno').")

    def quitar_calle(self):
        i = self.tab_calles.seleccion()
        if i is None:
            return
        if messagebox.askyesno("Quitar calle", f"¿Quitar {self.proy.calles[i].eje_id}?"):
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
            c.prog_inicial = v
            self.modificado()
            self.refrescar_calle_sel()

    def editar_vertice(self, i, col, v):
        c = self.calle_sel()
        e, n = c.vertices[i]
        c.vertices[i] = (numero(v), n) if col == 1 else (e, numero(v))
        self.modificado()
        self.refrescar_calles()

    def eje_desde_origen(self):
        c = self.calle_sel()
        if c is None:
            return
        d = DialogoOrigen(self, "Eje desde punto de origen",
                          c.vertices[0] if c.vertices else (0.0, 0.0))
        if d.resultado:
            e, n, az, L = d.resultado
            a = math.radians(az)
            c.vertices = [(e, n), (e + L * math.sin(a), n + L * math.cos(a))]
            self.modificado()
            self.refrescar_calles()

    def agregar_tramo_eje(self):
        c = self.calle_sel()
        if c is None or not c.vertices:
            return self.eje_desde_origen()
        txt = simpledialog.askstring("Agregar tramo", "Azimut (grados) y longitud (m) separados por espacio:",
                                     parent=self)
        if not txt:
            return
        try:
            az, L = (numero(x) for x in txt.replace(";", " ").split()[:2])
        except ValueError:
            return messagebox.showerror("Dato no válido", "Escriba por ejemplo: 80 120.5")
        e, n = c.vertices[-1]
        c.vertices.append((e + L * math.sin(math.radians(az)), n + L * math.cos(math.radians(az))))
        self.modificado()
        self.refrescar_calles()

    def agregar_vertice(self):
        c = self.calle_sel()
        if c is None:
            return
        e, n = c.vertices[-1] if c.vertices else (0.0, 0.0)
        c.vertices.append((e + 10.0, n))
        self.modificado()
        self.refrescar_calles()

    def quitar_vertice(self):
        c = self.calle_sel()
        i = self.tab_vert.seleccion()
        if c is None or i is None:
            return
        del c.vertices[i]
        self.modificado()
        self.refrescar_calles()

    def editar_tramo(self, i, col, v):
        c = self.calle_sel()
        t = c.tramos[i]
        idx = {0: 0, 1: 1, 2: 2, 3: 3}[col]
        t[idx] = numero(v)
        if col == 3 and i + 1 < len(c.tramos):
            c.tramos[i + 1][0] = t[3]
        c.tramos.sort(key=lambda x: x[0])
        self.modificado()
        self.refrescar_calle_sel()

    def agregar_tramo(self):
        c = self.calle_sel()
        if c is None:
            return
        if c.tramos:
            a = c.tramos[-1]
            zf = a[1] + a[2] / 100 * (a[3] - a[0])
            c.tramos.append([a[3], round(zf, 3), a[2], a[3] + 50.0])
        else:
            c.tramos.append([c.prog_inicial, 0.0, 1.0, c.prog_inicial + 50.0])
        self.modificado()
        self.refrescar_calle_sel()

    def quitar_tramo(self):
        c = self.calle_sel()
        i = self.tab_perf.seleccion()
        if c is None or i is None:
            return
        del c.tramos[i]
        self.modificado()
        self.refrescar_calle_sel()

    def encadenar(self):
        c = self.calle_sel()
        if c is None or not c.tramos:
            return
        for k in range(1, len(c.tramos)):
            a = c.tramos[k - 1]
            c.tramos[k][0] = a[3]
            c.tramos[k][1] = round(a[1] + a[2] / 100 * (a[3] - a[0]), 4)
        self.modificado()
        self.refrescar_calle_sel()

    def perfil_desde_terreno(self):
        c = self.calle_sel()
        if c is None or len(c.vertices) < 2:
            return
        t = Terreno(self.proy.terreno, self.proy.p("arista_max_tin"))
        if not t.ok:
            return messagebox.showwarning("Sin terreno", "Primero importe el terreno.")
        L = sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(c.vertices[:-1], c.vertices[1:]))
        z0 = t.cota(*c.vertices[0])
        z1 = t.cota(*c.vertices[-1])
        if z0 != z0 or z1 != z1:
            return messagebox.showwarning("Fuera del terreno", "El inicio o el fin del eje está fuera del levantamiento.")
        T = sum(cp.espesor for cp in self.proy.capas_de("calzada"))
        c.tramos = [[c.prog_inicial, round(z0, 3), round((z1 - z0) / L * 100, 3), round(c.prog_inicial + L, 3)]]
        self.modificado()
        self.refrescar_calle_sel()
        messagebox.showinfo("Perfil propuesto", f"Un tramo que sigue el terreno de {z0:.3f} a {z1:.3f}. "
                                                f"Ajuste cotas y pendientes según el expediente "
                                                f"(el paquete de capas mide {T:.2f} m).")

    # ---------------------------------------------------------------- 3 capas
    def _tab_capas(self):
        izq = ttk.Frame(self.t_cap)
        izq.pack(side="left", fill="both", expand=True)
        f = ttk.LabelFrame(izq, text="Capas (de arriba hacia abajo). Espesor en cm, uniforme en toda la vía", padding=6)
        f.pack(fill="both", expand=True)
        self.tab_capas = Tabla(f, ["Ámbito", "Orden", "Nombre", "Espesor (cm)"], {0: 90, 1: 60, 2: 260, 3: 100},
                               self.editar_capa, editable={2, 3}, alto=10)
        self.tab_capas.pack(fill="both", expand=True)
        b = ttk.Frame(f)
        b.pack(fill="x", pady=4)
        ttk.Button(b, text="Agregar capa de calzada", command=lambda: self.agregar_capa("calzada")).pack(side="left", padx=2)
        ttk.Button(b, text="Agregar capa de vereda", command=lambda: self.agregar_capa("vereda")).pack(side="left", padx=2)
        ttk.Button(b, text="Quitar", command=self.quitar_capa).pack(side="left", padx=2)
        ttk.Button(b, text="Subir ↑", command=lambda: self.mover_capa(-1)).pack(side="left", padx=2)
        ttk.Button(b, text="Bajar ↓", command=lambda: self.mover_capa(1)).pack(side="left", padx=2)
        self.capas_info = tk.StringVar()
        ttk.Label(f, textvariable=self.capas_info, foreground="#1a5276").pack(anchor="w")
        fc = ttk.LabelFrame(izq, text="Cuneta básica por tramo (si no hay tramo, se usa la estándar)", padding=6)
        fc.pack(fill="both", expand=True, pady=(8, 0))
        self.tab_cun = Tabla(fc, ["Eje", "Lado (AMBOS/IZQ/DER)", "Desde", "Hasta", "Ancho cm", "Profundidad cm", "Nota"],
                             {0: 70, 1: 140, 2: 80, 3: 80, 4: 70, 5: 100, 6: 200}, self.editar_cuneta, alto=6)
        self.tab_cun.pack(fill="both", expand=True)
        b = ttk.Frame(fc)
        b.pack(fill="x", pady=4)
        ttk.Button(b, text="Agregar tramo de cuneta", command=self.agregar_cuneta).pack(side="left", padx=2)
        ttk.Button(b, text="Quitar", command=self.quitar_cuneta).pack(side="left", padx=2)

        der = ttk.LabelFrame(self.t_cap, text="Sección típica y parámetros (todos editables)", padding=8)
        der.pack(side="left", fill="both", padx=(8, 0))
        self.vars_par = {}
        for r, (k, (v, u, d)) in enumerate(PARAMETROS.items()):
            ttk.Label(der, text=k.replace("_", " ").capitalize()).grid(row=r, column=0, sticky="w", pady=2)
            var = tk.StringVar()
            if k == "modo_fachada":
                w = ttk.Combobox(der, textvariable=var, values=["recortar", "avisar"], width=10, state="readonly")
            else:
                w = ttk.Entry(der, textvariable=var, width=12)
            w.grid(row=r, column=1, padx=4)
            ttk.Label(der, text=u).grid(row=r, column=2, sticky="w")
            color = "#b03a2e" if "CONFIRMAR" in d else "#555"
            ttk.Label(der, text=d, foreground=color, wraplength=330).grid(row=r, column=3, sticky="w", padx=4)
            self.vars_par[k] = var
        ttk.Button(der, text="Aplicar parámetros", command=self.aplicar_parametros).grid(
            row=len(PARAMETROS), column=0, columnspan=2, pady=10, sticky="w")
        self.fig_tip = Figure(figsize=(6, 2.6), dpi=90)
        self.can_tip = FigureCanvasTkAgg(self.fig_tip, master=der)
        self.can_tip.get_tk_widget().grid(row=len(PARAMETROS) + 1, column=0, columnspan=4, sticky="nsew")

    def refrescar_capas(self):
        p = self.proy
        capas = p.capas_de("calzada") + p.capas_de("vereda")
        self.tab_capas.cargar([[c.ambito, c.orden, c.nombre, f"{c.espesor_cm:g}"] for c in capas])
        tc = sum(c.espesor_cm for c in p.capas_de("calzada"))
        tv = sum(c.espesor_cm for c in p.capas_de("vereda"))
        self.capas_info.set(f"Paquete de calzada: {tc:g} cm  ·  paquete de vereda: {tv:g} cm")
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
        self.proy.capas.append(Capa(amb, n, f"Nueva capa {amb} {n}", 10.0))
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
            v = v.upper()
            if v not in ("AMBOS", "IZQ", "DER"):
                raise ValueError("use AMBOS, IZQ o DER")
            t.lado = v
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
        try:
            for k, var in self.vars_par.items():
                self.proy.parametros[k] = var.get().strip() if k in TEXTO else numero(var.get())
        except ValueError:
            return messagebox.showerror("Dato no válido", f"Revise el parámetro '{k}'.")
        self.modificado()
        self.dibujar_tipica()

    def dibujar_tipica(self):
        """Sección típica de la calle seleccionada (o la primera), sin terreno."""
        from .geometria import Alineamiento, Perfil
        from .seccion import construir
        self.fig_tip.clear()
        p = self.proy
        c = self.calle_sel() or (p.calles[0] if p.calles else None)
        if c is None or len(c.vertices) < 2 or not c.tramos or not p.capas_de("calzada"):
            self.can_tip.draw_idle()
            return
        try:
            al, pf = Alineamiento(c.vertices, c.prog_inicial), Perfil(c.tramos)
            cun = (p.p("cuneta_ancho") / 100, p.p("cuneta_profundidad") / 100)
            sec = construir(c, al, pf, c.prog_inicial, p.parametros, p.capas_de("calzada"), p.capas_de("vereda"),
                            {"I": True, "D": True}, {"I": c.ancho_vereda, "D": c.ancho_vereda}, {"I": cun, "D": cun})
        except Exception:
            return
        ax = self.fig_tip.add_subplot(111)
        dibujar_seccion(ax, sec, p, etiquetas=False)
        ax.set_title(f"Sección típica {c.eje_id} (ejemplo en {fmt_prog(c.prog_inicial)})", fontsize=9)
        ax.legend().remove()
        self.fig_tip.tight_layout()
        self.can_tip.draw_idle()

    # ---------------------------------------------------------------- 4 modelo 3D
    def _tab_3d(self):
        ctl = ttk.Frame(self.t_3d)
        ctl.pack(fill="x")
        ttk.Label(ctl, text="Calle:").pack(side="left")
        self.v_calle3d = tk.StringVar(value="Todas")
        self.cb_calle3d = ttk.Combobox(ctl, textvariable=self.v_calle3d, width=24, state="readonly")
        self.cb_calle3d.pack(side="left", padx=4)
        self.cb_calle3d.bind("<<ComboboxSelected>>", lambda _: self._llenar_progs())
        ttk.Label(ctl, text="Vista:").pack(side="left", padx=(10, 0))
        self.v_vista = tk.StringVar(value="3D")
        for v in ("3D", "Planta", "Perfil", "Sección"):
            ttk.Radiobutton(ctl, text=v, value=v, variable=self.v_vista, command=self.dibujar_vista).pack(side="left")
        ttk.Label(ctl, text="Progresiva:").pack(side="left", padx=(10, 0))
        self.v_prog = tk.StringVar()
        self.cb_prog = ttk.Combobox(ctl, textvariable=self.v_prog, width=12, state="readonly")
        self.cb_prog.pack(side="left", padx=4)
        self.cb_prog.bind("<<ComboboxSelected>>", lambda _: (self.v_vista.set("Sección"), self.dibujar_vista()))
        ttk.Button(ctl, text="◀", width=3, command=lambda: self._paso_prog(-1)).pack(side="left")
        ttk.Button(ctl, text="▶", width=3, command=lambda: self._paso_prog(1)).pack(side="left")
        ttk.Label(ctl, text="Exageración vertical 3D:").pack(side="left", padx=(10, 0))
        self.v_exag = tk.StringVar(value="5")
        ttk.Spinbox(ctl, from_=1, to=50, textvariable=self.v_exag, width=4, command=self.dibujar_vista).pack(side="left")
        self.v_tn = tk.BooleanVar(value=True)
        self.v_fach = tk.BooleanVar(value=True)
        ttk.Checkbutton(ctl, text="Terreno", variable=self.v_tn, command=self.dibujar_vista).pack(side="left", padx=4)
        ttk.Checkbutton(ctl, text="Fachadas", variable=self.v_fach, command=self.dibujar_vista).pack(side="left")
        self.v_tramo = tk.BooleanVar(value=False)
        ttk.Checkbutton(ctl, text="3D solo tramo ±20 m de la progresiva", variable=self.v_tramo,
                        command=self.dibujar_vista).pack(side="left", padx=4)
        ttk.Button(ctl, text="Redibujar", command=self.dibujar_vista).pack(side="left", padx=8)
        ttk.Label(self.t_3d, text="3D: arrastre con el mouse para girar, botón derecho para acercar. "
                                  "Use la lupa de la barra para zoom en las vistas 2D.", foreground="#555").pack(anchor="w")
        cont = ttk.Frame(self.t_3d)
        cont.pack(fill="both", expand=True)
        self.fig3d = Figure(figsize=(10, 7), dpi=100)
        self.can3d = FigureCanvasTkAgg(self.fig3d, master=cont)
        NavigationToolbar2Tk(self.can3d, cont).update()
        self.can3d.get_tk_widget().pack(fill="both", expand=True)

    def _llenar_progs(self):
        if self.res is None:
            return
        k = self.v_calle3d.get()
        rc = self.res.calles.get(k) or next(iter(self.res.calles.values()))
        vals = [fmt_prog(s.prog) for s in rc.secciones if not s.omitida]
        self.cb_prog["values"] = vals
        if self.v_prog.get() not in vals and vals:
            self.v_prog.set(vals[min(5, len(vals) - 1)])

    def _paso_prog(self, d):
        vals = list(self.cb_prog["values"])
        if not vals:
            return
        i = vals.index(self.v_prog.get()) if self.v_prog.get() in vals else 0
        self.v_prog.set(vals[max(0, min(len(vals) - 1, i + d))])
        self.v_vista.set("Sección")
        self.dibujar_vista()

    def dibujar_vista(self):
        self.fig3d.clear()
        if self.res is None:
            self.can3d.draw_idle()
            return
        k = self.v_calle3d.get()
        rc = self.res.calles.get(k) or next(iter(self.res.calles.values()))
        v = self.v_vista.get()
        try:
            exag = float(self.v_exag.get())
        except ValueError:
            exag = 5.0
        if v == "3D":
            ax = self.fig3d.add_subplot(111, projection="3d")
            tramo = None
            if self.v_tramo.get():
                sec = self._seccion_elegida(rc)
                tramo = (rc.calle.eje_id, sec.prog, 20.0)
            dibujar_3d(ax, self.res, None if k == "Todas" else [k], exag, self.v_tn.get(), self.v_fach.get(), tramo)
            ax.view_init(elev=28, azim=-60 if tramo else -120)
        elif v == "Planta":
            dibujar_planta(self.fig3d.add_subplot(111), self.res, None if k == "Todas" else k)
        elif v == "Perfil":
            dibujar_perfil(self.fig3d.add_subplot(111), rc, self.res)
        else:
            dibujar_seccion(self.fig3d.add_subplot(111), self._seccion_elegida(rc), self.proy)
        self.fig3d.tight_layout()
        self.can3d.draw_idle()

    def _seccion_elegida(self, rc):
        txt = self.v_prog.get()
        sec = next((s for s in rc.secciones if fmt_prog(s.prog) == txt and not s.omitida), None)
        return sec or next(s for s in rc.secciones if not s.omitida)

    # ---------------------------------------------------------------- 5 tierras
    def _tab_tierras(self):
        ctl = ttk.Frame(self.t_tie)
        ctl.pack(fill="x")
        ttk.Label(ctl, text="Ver:").pack(side="left")
        self.v_calle_t = tk.StringVar(value="Resumen total")
        self.cb_calle_t = ttk.Combobox(ctl, textvariable=self.v_calle_t, width=28, state="readonly")
        self.cb_calle_t.pack(side="left", padx=4)
        self.cb_calle_t.bind("<<ComboboxSelected>>", lambda _: self.refrescar_tierras())
        ttk.Button(ctl, text="Exportar a Excel…", command=lambda: self.exportar_rapido("excel")).pack(side="left", padx=6)
        ttk.Button(ctl, text="Exportar a PDF…", command=lambda: self.exportar_rapido("pdf")).pack(side="left")
        self.tot_t = tk.StringVar()
        ttk.Label(self.t_tie, textvariable=self.tot_t, font=("Segoe UI", 11, "bold"), foreground="#1a5276").pack(
            anchor="w", pady=6)
        self.tab_tie = Tabla(self.t_tie, COLS_TIERRAS, alto=16)
        self.tab_tie.pack(fill="both", expand=True)
        ttk.Label(self.t_tie, text="Volumen de material por capa (m³)", font=("Segoe UI", 10, "bold")).pack(
            anchor="w", pady=(8, 2))
        self.tab_mat = Tabla(self.t_tie, ["Material"], alto=8)
        self.tab_mat.pack(fill="x")

    def refrescar_tierras(self):
        if self.res is None:
            return
        k = self.v_calle_t.get()
        r = self.res
        if k in r.calles:
            rc = r.calles[k]
            self.tab_tie.poner_columnas(COLS_TIERRAS)
            self.tab_tie.cargar([[fmt_prog(t["desde"]), fmt_prog(t["hasta"]), f"{t['distancia']:.2f}",
                                  f"{t['ac1']:.3f}", f"{t['ac2']:.3f}", f"{t['ar1']:.3f}", f"{t['ar2']:.3f}",
                                  f"{t['vol_corte']:.2f}", f"{t['vol_relleno']:.2f}", f"{t['acum_corte']:.2f}",
                                  f"{t['acum_relleno']:.2f}"] for t in rc.tramos_volumen])
            self.tot_t.set(f"{k} {rc.calle.nombre}:  corte {rc.vol_corte:.2f} m³   relleno {rc.vol_relleno:.2f} m³   "
                           f"neto {rc.vol_neto:.2f} m³   longitud {rc.alin.longitud:.2f} m")
        else:
            self.tab_tie.poner_columnas(["Eje", "Calle", "Longitud (m)", "Secciones", "Corte (m³)", "Relleno (m³)",
                                         "Neto (m³)"], {1: 220})
            filas = [[kk, rc.calle.nombre, f"{rc.alin.longitud:.2f}",
                      sum(not s.omitida for s in rc.secciones), f"{rc.vol_corte:.2f}", f"{rc.vol_relleno:.2f}",
                      f"{rc.vol_neto:.2f}"] for kk, rc in r.calles.items()]
            c, rr = r.total("vol_corte"), r.total("vol_relleno")
            filas.append(["TOTAL", "", f"{sum(rc.alin.longitud for rc in r.calles.values()):.2f}", "",
                          f"{c:.2f}", f"{rr:.2f}", f"{c - rr:.2f}"])
            self.tab_tie.cargar(filas)
            self.tot_t.set(f"TOTAL ({len(r.calles)} calles):  corte {c:.2f} m³   relleno {rr:.2f} m³   neto {c - rr:.2f} m³")
        # materiales
        cols = ["Material"] + list(r.calles.keys()) + ["TOTAL"]
        self.tab_mat.poner_columnas(cols, {0: 260})
        mt = r.materiales_total()
        nombres = list(mt.keys())
        self.tab_mat.cargar([[n] + [f"{rc.materiales.get(n, 0):.2f}" for rc in r.calles.values()] + [f"{mt[n]:.2f}"]
                             for n in nombres])

    # ---------------------------------------------------------------- 6 exportar
    def _tab_exportar(self):
        f = ttk.LabelFrame(self.t_exp, text="Lectura de mira (nivel): AI = cota del BM + lectura atrás", padding=8)
        f.pack(fill="x")
        ttk.Label(f, text="BM:").grid(row=0, column=0)
        self.v_bm = tk.StringVar()
        self.cb_bm = ttk.Combobox(f, textvariable=self.v_bm, width=12, state="readonly")
        self.cb_bm.grid(row=0, column=1, padx=4)
        ttk.Label(f, text="Lectura atrás (m):").grid(row=0, column=2, padx=(12, 0))
        self.v_la = tk.StringVar(value="1.500")
        ttk.Entry(f, textvariable=self.v_la, width=10).grid(row=0, column=3, padx=4)
        self.v_ai = tk.StringVar()
        ttk.Label(f, textvariable=self.v_ai, foreground="#1a5276").grid(row=0, column=4, padx=12)
        for v in (self.v_bm, self.v_la):
            v.trace_add("write", lambda *_: self._mostrar_ai())
        g = ttk.LabelFrame(self.t_exp, text="Exportar", padding=8)
        g.pack(fill="x", pady=8)
        ttk.Label(g, text="Carpeta de salida:").grid(row=0, column=0, sticky="w")
        self.v_sal = tk.StringVar()
        ttk.Entry(g, textvariable=self.v_sal, width=80).grid(row=0, column=1, padx=4)
        ttk.Button(g, text="…", width=3, command=self._elegir_salida).grid(row=0, column=2)
        self.v_fmt = {}
        textos = {"csv": "CSV (eje, estación total, tablas de campo, PNEZD Civil 3D)",
                  "landxml": "LandXML para Civil 3D (alineamientos, perfiles, superficies)",
                  "dxf": "DXF AutoCAD 2018 (3D, líneas, puntos, hojas de secciones y perfil)",
                  "excel": "Informe Excel", "pdf": "Informe PDF"}
        for i, (k, t) in enumerate(textos.items()):
            v = tk.BooleanVar(value=True)
            ttk.Checkbutton(g, text=t, variable=v).grid(row=1 + i, column=1, sticky="w")
            self.v_fmt[k] = v
        ttk.Button(g, text="EXPORTAR TODO", style="Grande.TButton", command=self.exportar).grid(
            row=7, column=1, sticky="w", pady=8)
        h = ttk.LabelFrame(self.t_exp, text="Avisos de revisión", padding=6)
        h.pack(fill="both", expand=True)
        self.tab_av = Tabla(h, ["Nivel", "Categoría", "Eje", "Progresiva", "Mensaje"],
                            {0: 70, 1: 90, 2: 70, 3: 90, 4: 1000}, alto=14)
        self.tab_av.tree.column("c4", anchor="w")
        self.tab_av.tree.tag_configure("ERROR", foreground="#c0392b")
        self.tab_av.tree.tag_configure("AVISO", foreground="#b9770e")
        self.tab_av.tree.tag_configure("INFO", foreground="#1e8449")
        self.tab_av.pack(fill="both", expand=True)

    def _mostrar_ai(self):
        ai = self._ai()
        self.v_ai.set(f"Altura instrumental AI = {ai:.3f}" if ai is not None else "")

    def _ai(self):
        try:
            return altura_instrumento(self.proy, self.v_bm.get() or None, numero(self.v_la.get()))
        except ValueError:
            return None

    def _elegir_salida(self):
        d = filedialog.askdirectory(title="Carpeta de salida")
        if d:
            self.v_sal.set(d)

    def refrescar_exportar(self):
        self.cb_bm["values"] = [b.id for b in self.proy.bms]
        if self.proy.bms and self.v_bm.get() not in self.cb_bm["values"]:
            self.v_bm.set(self.proy.bms[0].id)
        if not self.v_sal.get() and self.carpeta:
            self.v_sal.set(str(Path(self.carpeta) / "salida"))
        if self.res is not None:
            self.tab_av.cargar([[a.nivel, a.categoria, a.eje_id, fmt_prog(a.prog) if a.prog is not None else "",
                                 a.mensaje] for a in self.res.avisos], [a.nivel for a in self.res.avisos])
        self._mostrar_ai()

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
            messagebox.showerror("No se pudo guardar", f"¿Tiene el archivo abierto en Excel u otro programa?\n{e}")
            return None
        self.estado.set(f"Exportados {len(arch)} archivos en {carpeta}")
        if formatos and len(formatos) > 1:
            messagebox.showinfo("Exportación lista", f"Se generaron {len(arch)} archivos en:\n{carpeta}")
        return arch

    def exportar_rapido(self, fmt):
        arch = self.exportar([fmt])
        if arch and sys.platform.startswith("win"):
            os.startfile(arch[-1])  # noqa: abrir con el programa asociado

    # ---------------------------------------------------------------- acciones generales
    def modificado(self):
        self.res = None
        self.estado.set("Datos modificados: presione CALCULAR.")

    def abrir_dialogo(self):
        d = filedialog.askdirectory(title="Carpeta del proyecto (con calles.csv, ejes.csv, perfil.csv…)")
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
        self.refrescar_todo()
        self.estado.set(f"Proyecto: {carpeta}. Presione CALCULAR.")

    def guardar(self):
        d = self.carpeta or filedialog.askdirectory(title="Guardar proyecto en carpeta")
        if not d:
            return
        if Path(d).resolve() == recurso("datos_ejemplo").resolve():
            d = filedialog.askdirectory(title="El ejemplo no se sobrescribe: elija otra carpeta")
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
        n_err = sum(a.nivel == "ERROR" for a in self.res.avisos)
        n_av = sum(a.nivel == "AVISO" for a in self.res.avisos)
        self.estado.set(f"Calculado: {sum(len(rc.secciones) for rc in self.res.calles.values())} secciones · "
                        f"corte {self.res.total('vol_corte'):.1f} m³ · relleno {self.res.total('vol_relleno'):.1f} m³ · "
                        f"{n_err} errores y {n_av} avisos (ver pestaña 6)")
        self.cb_calle3d["values"] = ["Todas"] + list(self.res.calles.keys())
        self.cb_calle_t["values"] = ["Resumen total"] + list(self.res.calles.keys())
        if self.v_calle3d.get() not in self.cb_calle3d["values"]:
            self.v_calle3d.set("Todas")
        self._llenar_progs()
        self.refrescar_levantamiento()
        self.refrescar_tierras()
        self.refrescar_exportar()
        self.dibujar_vista()
        return True

    def refrescar_todo(self):
        self.refrescar_levantamiento()
        self.refrescar_calles(0)
        self.refrescar_capas()
        self.refrescar_exportar()


class DialogoOrigen(simpledialog.Dialog):
    def __init__(self, master, titulo, origen):
        self.origen = origen
        self.resultado = None
        super().__init__(master, titulo)

    def body(self, m):
        ttk.Label(m, text="Punto de origen del eje (donde empieza la calzada) y su dirección.").grid(
            row=0, column=0, columnspan=2, pady=(0, 6))
        self.vars = []
        for i, (t, v) in enumerate((("Este (m)", f"{self.origen[0]:.3f}"), ("Norte (m)", f"{self.origen[1]:.3f}"),
                                    ("Azimut (grados, 0 = Norte, horario)", "90"), ("Longitud (m)", "100"))):
            ttk.Label(m, text=t).grid(row=i + 1, column=0, sticky="w")
            var = tk.StringVar(value=v)
            ttk.Entry(m, textvariable=var, width=16).grid(row=i + 1, column=1, padx=4, pady=2)
            self.vars.append(var)
        return None

    def validate(self):
        try:
            self.resultado = [numero(v.get()) for v in self.vars]
        except ValueError:
            messagebox.showerror("Dato no válido", "Revise los números.")
            return False
        if self.resultado[3] <= 0:
            messagebox.showerror("Dato no válido", "La longitud debe ser mayor que 0.")
            return False
        return True


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    app = App(argv[0] if argv else None)
    app.mainloop()
