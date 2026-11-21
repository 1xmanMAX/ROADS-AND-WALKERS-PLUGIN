// Construye dentro del dibujo de Civil 3D 2025 los objetos del proyecto de Corredor Simple.
using System;
using System.Collections.Generic;
using System.Linq;
using Autodesk.AutoCAD.Colors;
using Autodesk.AutoCAD.Geometry;
using Autodesk.Civil.ApplicationServices;
using AcDb = Autodesk.AutoCAD.DatabaseServices;
using C3D = Autodesk.Civil.DatabaseServices;

namespace CorredorSimpleC3D
{
    public class Opciones
    {
        public bool Puntos = true;          // puntos COGO del levantamiento y BM
        public bool Replanteo = false;      // puntos COGO de replanteo (muchos)
        public bool Superficies = true;     // TN, terminado, subrasante, fondos de capa
        public bool Ejes = true;            // alineamientos, perfiles y vistas de perfil
        public bool Lineas = true;          // líneas características 3D y fachadas
        public bool Caras3D = true;         // modelo 3D de capas (3DFACE)
        public bool Interferencias = true;  // marcas de puertas, cocheras, buzones...
    }

    public class Constructor
    {
        readonly AcDb.Database db;
        readonly CivilDocument civ;
        readonly AcDb.Transaction tr;
        readonly AcDb.BlockTableRecord ms;
        public readonly List<string> Informe = new();
        AcDb.ObjectId tnId = AcDb.ObjectId.Null;

        public Constructor(AcDb.Database db, CivilDocument civ, AcDb.Transaction tr)
        {
            this.db = db;
            this.civ = civ;
            this.tr = tr;
            var bt = (AcDb.BlockTable)tr.GetObject(db.BlockTableId, AcDb.OpenMode.ForRead);
            ms = (AcDb.BlockTableRecord)tr.GetObject(bt[AcDb.BlockTableRecord.ModelSpace], AcDb.OpenMode.ForWrite);
        }

        // ------------------------------------------------------------ utilidades
        public static string Limpio(string s)
        {
            if (string.IsNullOrEmpty(s)) return "SIN-NOMBRE";
            var malos = "<>/\\\":;?*|,='`";
            var r = new string(s.Select(c => malos.Contains(c) ? '-' : c).ToArray());
            return r.Trim();
        }

        public AcDb.ObjectId Capa(string nombre, short color, bool apagada = false)
        {
            nombre = Limpio(nombre);
            var lt = (AcDb.LayerTable)tr.GetObject(db.LayerTableId, AcDb.OpenMode.ForRead);
            if (lt.Has(nombre)) return lt[nombre];
            lt.UpgradeOpen();
            var ltr = new AcDb.LayerTableRecord { Name = nombre, Color = Color.FromColorIndex(ColorMethod.ByAci, color), IsOff = apagada };
            var id = lt.Add(ltr);
            tr.AddNewlyCreatedDBObject(ltr, true);
            return id;
        }

        AcDb.ObjectId Agregar(AcDb.Entity e, string capa, short color = 256)
        {
            e.Layer = Limpio(capa);
            if (color != 256) e.ColorIndex = color;
            var id = ms.AppendEntity(e);
            tr.AddNewlyCreatedDBObject(e, true);
            return id;
        }

        static Point3d P(double[] a) => new Point3d(a[0], a[1], a.Length > 2 ? a[2] : 0.0);

        static AcDb.ObjectId Estilo(C3D.Styles.StyleCollectionBase col, params string[] preferidos)
        {
            foreach (var n in preferidos)
                if (col.Contains(n)) return col[n];
            return col.Count > 0 ? col[0] : AcDb.ObjectId.Null;
        }

        string NombreLibre(IEnumerable<string> existentes, string base_)
        {
            var set = new HashSet<string>(existentes, StringComparer.OrdinalIgnoreCase);
            var n = Limpio(base_);
            if (!set.Contains(n)) return n;
            for (int i = 2; ; i++)
                if (!set.Contains($"{n} ({i})")) return $"{n} ({i})";
        }

        IEnumerable<string> NombresSuperficies() =>
            civ.GetSurfaceIds().Cast<AcDb.ObjectId>().Select(id => ((C3D.Surface)tr.GetObject(id, AcDb.OpenMode.ForRead)).Name);

        IEnumerable<string> NombresAlineamientos() =>
            civ.GetAlignmentIds().Cast<AcDb.ObjectId>().Select(id => ((C3D.Alignment)tr.GetObject(id, AcDb.OpenMode.ForRead)).Name);

        static string Rangos(IEnumerable<uint> numeros)
        {
            var l = numeros.OrderBy(x => x).ToList();
            var partes = new List<string>();
            for (int i = 0; i < l.Count;)
            {
                int j = i;
                while (j + 1 < l.Count && l[j + 1] == l[j] + 1) j++;
                partes.Add(i == j ? $"{l[i]}" : $"{l[i]}-{l[j]}");
                i = j + 1;
            }
            return string.Join(",", partes);
        }

        // ------------------------------------------------------------ puntos COGO
        public void Puntos(Paquete p, Opciones o)
        {
            Capa("CS-PUNTOS-LEVANTAMIENTO", 32);
            var porTipo = new Dictionary<string, List<uint>>();
            int n = 0;
            foreach (var q in p.Puntos)
            {
                var id = civ.CogoPoints.Add(new Point3d(q.E, q.N, q.Z), q.Desc ?? "", true);
                var cp = (C3D.CogoPoint)tr.GetObject(id, AcDb.OpenMode.ForWrite);
                cp.Layer = "CS-PUNTOS-LEVANTAMIENTO";
                try { cp.PointName = "L" + q.Num; } catch { /* nombre repetido: se deja automático */ }
                var grupo = q.Tipo switch
                {
                    "TN" or "EJ" or "BC" or "VE" => "Terreno",
                    "CA" or "MU" or "LP" => "Fachadas y limites",
                    "PU" or "COI" or "COF" => "Puertas y cocheras",
                    "BM" => "BM",
                    "?" => "Codigos desconocidos",
                    _ => "Elementos (buzones, postes...)"
                };
                if (!porTipo.ContainsKey(grupo)) porTipo[grupo] = new List<uint>();
                porTipo[grupo].Add(cp.PointNumber);
                n++;
            }
            foreach (var kv in porTipo) Grupo("CS " + kv.Key, kv.Value);
            Informe.Add($"{n} puntos COGO del levantamiento en {porTipo.Count} grupos de puntos 'CS ...'.");

            if (o.Replanteo)
            {
                Capa("CS-PUNTOS-REPLANTEO", 3);
                foreach (var c in p.Calles)
                {
                    var nums = new List<uint>();
                    foreach (var r in c.Replanteo)
                    {
                        var id = civ.CogoPoints.Add(new Point3d(r.E, r.N, r.Z), r.Codigo ?? "", true);
                        var cp = (C3D.CogoPoint)tr.GetObject(id, AcDb.OpenMode.ForWrite);
                        cp.Layer = "CS-PUNTOS-REPLANTEO";
                        try { cp.PointName = r.Nombre; } catch { }
                        nums.Add(cp.PointNumber);
                    }
                    Grupo($"CS Replanteo {c.Id}", nums);
                    Informe.Add($"{nums.Count} puntos de replanteo de {c.Id}.");
                }
            }
        }

        void Grupo(string nombre, List<uint> numeros)
        {
            if (numeros.Count == 0) return;
            nombre = Limpio(nombre);
            var id = civ.PointGroups.Contains(nombre) ? civ.PointGroups[nombre] : civ.PointGroups.Add(nombre);
            var pg = (C3D.PointGroup)tr.GetObject(id, AcDb.OpenMode.ForWrite);
            var q = new C3D.StandardPointGroupQuery { IncludeNumbers = Rangos(numeros) };
            pg.SetQuery(q);
            pg.Update();
        }

        // ------------------------------------------------------------ superficies
        AcDb.ObjectId Superficie(string nombre, Malla m, string estiloPreferido)
        {
            if (m == null || m.Caras.Count == 0) return AcDb.ObjectId.Null;
            nombre = NombreLibre(NombresSuperficies(), nombre);
            var aux = "CS-AUX-SUPERFICIES";
            Capa(aux, 8, apagada: true);
            var caras = new AcDb.ObjectIdCollection();
            foreach (var f in m.Caras)
            {
                var a = P(m.Pts[f[0]]); var b = P(m.Pts[f[1]]); var c = P(m.Pts[f[2]]);
                caras.Add(Agregar(new AcDb.Face(a, b, c, c, true, true, true, true), aux));
            }
            var sid = C3D.TinSurface.Create(db, nombre);
            var tin = (C3D.TinSurface)tr.GetObject(sid, AcDb.OpenMode.ForWrite);
            tin.StyleId = Estilo(civ.Styles.SurfaceStyles, estiloPreferido, "Contours 1m and 5m (Design)",
                                 "Contours 1m and 5m (Background)", "Standard");
            tin.DrawingObjectsDefinition.AddFrom3DFaces(caras, true, "Corredor Simple");
            tin.Rebuild();
            return sid;
        }

        public void Superficies(Paquete p)
        {
            tnId = Superficie("CS TN Terreno existente", p.Tn, "Contours 1m and 5m (Background)");
            if (!tnId.IsNull) Informe.Add("Superficie 'CS TN Terreno existente'.");
            foreach (var c in p.Calles)
                foreach (var kv in c.Superficies)
                {
                    var id = Superficie($"CS {c.Id} {kv.Key}", kv.Value,
                                        kv.Key == "TERMINADO" ? "Contours 1m and 5m (Design)" : "Border Only");
                    if (!id.IsNull) Informe.Add($"Superficie 'CS {c.Id} {kv.Key}'.");
                }
        }

        // ------------------------------------------------------------ ejes y perfiles
        public void Ejes(Paquete p, Point3d origenVistas)
        {
            var capaEje = Capa("CS-EJES", 6);
            var capaPerf = Capa("CS-PERFILES", 5);
            var capaPerfTn = Capa("CS-PERFILES-TN", 32);
            double dy = 0;
            foreach (var c in p.Calles)
            {
                if (c.Vertices.Count < 2) continue;
                var nombre = NombreLibre(NombresAlineamientos(), $"{c.Id} {c.Nombre}");
                var alId = C3D.Alignment.Create(civ, nombre, AcDb.ObjectId.Null, capaEje,
                    Estilo(civ.Styles.AlignmentStyles, "Proposed", "Basic", "Standard"),
                    Estilo(civ.Styles.LabelSetStyles.AlignmentLabelSetStyles, "Major and Minor only", "Standard", "Basic"));
                var al = (C3D.Alignment)tr.GetObject(alId, AcDb.OpenMode.ForWrite);
                for (int i = 0; i + 1 < c.Vertices.Count; i++)
                    al.Entities.AddFixedLine(P(c.Vertices[i]), P(c.Vertices[i + 1]));
                al.ReferencePointStation = c.Prog0;

                var pfId = C3D.Profile.CreateByLayout($"{c.Id} Rasante", alId, capaPerf,
                    Estilo(civ.Styles.ProfileStyles, "Design Profile", "Basic", "Standard"),
                    Estilo(civ.Styles.LabelSetStyles.ProfileLabelSetStyles, "Complete Label Set", "Standard", "_No Labels"));
                var pf = (C3D.Profile)tr.GetObject(pfId, AcDb.OpenMode.ForWrite);
                for (int i = 0; i + 1 < c.Pvis.Count; i++)
                    pf.Entities.AddFixedTangent(new Point2d(c.Pvis[i][0], c.Pvis[i][1]), new Point2d(c.Pvis[i + 1][0], c.Pvis[i + 1][1]));

                if (!tnId.IsNull)
                    C3D.Profile.CreateFromSurface($"{c.Id} Terreno", alId, tnId, capaPerfTn,
                        Estilo(civ.Styles.ProfileStyles, "Existing Ground Profile", "Basic", "Standard"),
                        Estilo(civ.Styles.LabelSetStyles.ProfileLabelSetStyles, "_No Labels", "Standard"));
                try
                {
                    C3D.ProfileView.Create(alId, new Point3d(origenVistas.X, origenVistas.Y - dy, 0));
                    dy += 60;
                }
                catch (Exception ex) { Informe.Add($"Vista de perfil de {c.Id} no creada: {ex.Message}"); }
                Informe.Add($"Alineamiento '{nombre}' con perfil de rasante ({c.Pvis.Count} PVI) y vista de perfil.");
            }
        }

        // ------------------------------------------------------------ líneas 3D y fachadas
        public void Lineas(Paquete p)
        {
            int n = 0;
            foreach (var c in p.Calles)
                foreach (var kv in c.Lineas)
                {
                    var cod = kv.Key;
                    var baseCod = cod.StartsWith("SUB-") ? cod : (cod == "EJE" ? cod : cod.Substring(0, cod.Length - 1));
                    var capa = "CS-LF-" + baseCod;
                    Capa(capa, (short)(cod.StartsWith("SUB-") ? 1 : 3));
                    foreach (var pl in kv.Value)
                    {
                        var col = new Point3dCollection();
                        foreach (var q in pl) col.Add(P(q));
                        Agregar(new AcDb.Polyline3d(AcDb.Poly3dType.SimplePoly, col, false), capa);
                        n++;
                    }
                }
            var colores = new Dictionary<string, short> { ["CA"] = 1, ["MU"] = 30, ["LP"] = 50 };
            foreach (var f in p.Fachadas)
            {
                var capa = "CS-FACHADA-" + f.Tipo;
                Capa(capa, colores.TryGetValue(f.Tipo, out var cc) ? cc : (short)1);
                var col = new Point3dCollection();
                foreach (var q in f.Pts) col.Add(P(q));
                Agregar(new AcDb.Polyline3d(AcDb.Poly3dType.SimplePoly, col, false), capa);
                var m = f.Pts[f.Pts.Count / 2];
                Agregar(new AcDb.MText { Contents = f.Id, Location = P(m), TextHeight = 0.6 }, capa);
            }
            Informe.Add($"{n} líneas características 3D y {p.Fachadas.Count} líneas de fachada/muro/límite.");
        }

        // ------------------------------------------------------------ modelo 3D de capas
        public void Caras3D(Paquete p)
        {
            var colores = new Dictionary<string, short> { ["CALZADA"] = 8, ["CUNETA"] = 5, ["SARDINEL"] = 9, ["VEREDA"] = 41 };
            int n = 0;
            short k = 30;
            foreach (var c in p.Calles)
                foreach (var kv in c.Caras3d)
                {
                    var capa = "CS-3D-" + kv.Key.Replace(' ', '_');
                    if (!colores.TryGetValue(kv.Key, out var color)) { color = k; k += 10; colores[kv.Key] = color; }
                    Capa(capa, color);
                    foreach (var q in kv.Value)
                    {
                        Agregar(new AcDb.Face(P(q[0]), P(q[1]), P(q[2]), P(q[3]), true, true, true, true), capa);
                        n++;
                    }
                }
            Informe.Add($"{n} caras 3D del corredor y de las capas (capas CS-3D-*).");
        }

        // ------------------------------------------------------------ interferencias y BM
        public void Interferencias(Paquete p)
        {
            var color = new Dictionary<string, short> { ["ERROR"] = 1, ["AVISO"] = 30, ["INFO"] = 3 };
            foreach (var x in p.Elementos)
            {
                var nivel = x.Nivel ?? "INFO";
                var capa = "CS-INTERF-" + nivel;
                Capa(capa, color.TryGetValue(nivel, out var cc) ? cc : (short)7);
                var z = x.CotaCampo ?? 0.0;
                var c = new Point3d(x.Este, x.Norte, z);
                Agregar(new AcDb.Circle(c, Vector3d.ZAxis, nivel == "INFO" ? 0.35 : 0.7), capa);
                var texto = $"{x.Id} {x.Nombre}\\P{x.Estado}";
                if (!string.IsNullOrEmpty(x.Accion) && x.Accion != "OK") texto += "\\P" + x.Accion;
                Agregar(new AcDb.MText { Contents = texto, Location = new Point3d(x.Este + 0.8, x.Norte + 0.8, z), TextHeight = 0.25, Width = 9 }, capa);
            }
            Capa("CS-BM", 6);
            foreach (var b in p.Bms)
            {
                var c = new Point3d(b.E, b.N, b.Z);
                Agregar(new AcDb.Circle(c, Vector3d.ZAxis, 0.5), "CS-BM");
                Agregar(new AcDb.Line(new Point3d(b.E - 0.8, b.N, b.Z), new Point3d(b.E + 0.8, b.N, b.Z)), "CS-BM");
                Agregar(new AcDb.Line(new Point3d(b.E, b.N - 0.8, b.Z), new Point3d(b.E, b.N + 0.8, b.Z)), "CS-BM");
                Agregar(new AcDb.MText { Contents = $"{b.Id}  cota {b.Z:F3}\\P{b.Ubicacion}", Location = new Point3d(b.E + 0.9, b.N + 0.9, b.Z), TextHeight = 0.35, Width = 12 }, "CS-BM");
            }
            Informe.Add($"{p.Elementos.Count} puertas/cocheras/elementos marcados (capas CS-INTERF-*) y {p.Bms.Count} BM.");
        }
    }
}
