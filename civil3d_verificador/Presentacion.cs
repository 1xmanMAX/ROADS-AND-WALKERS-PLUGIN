// Comandos para trabajar dentro de Civil 3D con un proyecto de Corredor Simple:
//
//   CS_GENERAR   carpeta del proyecto (calles.csv, ejes.csv, terreno.csv...) -> calcula con la app
//                (CorredorSimple.py calcular) y arma en el dibujo actual TODO el modelo:
//                  * alineamientos y perfiles de rasante NATIVOS de Civil 3D
//                  * superficies TIN: terreno (TN), terminado de cada calle y de las esquinas
//                  * modelo 3D del corredor (calzada, cunetas, sardineles, veredas, badenes,
//                    esquinas curvas, martillos, rampas y fachadas) con colores por material
//                  * puntos y líneas de los códigos de campo (postes, tapas, empalmes...)
//                  * vista isométrica realista
//   CS_PRESENTAR igual, pero con una carpeta que ya tiene corredor_civil3d.xml y .dxf (salida de la app)
//
// La carpeta se pide en la línea de comandos (o variable de entorno CS_GEN_DIR / CS_PRES_DIR).
// Python y la app se buscan solos (ver BuscarApp); se pueden fijar con CS_PYTHON y CS_APP_DIR o
// en corredor_simple.json junto al .dll (lo escribe el instalador).
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text.Json.Nodes;
using System.Xml.Linq;
using Autodesk.AutoCAD.ApplicationServices.Core;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
using Autodesk.Civil.ApplicationServices;
using Autodesk.Civil.DatabaseServices;
using Autodesk.Civil.DatabaseServices.Styles;
using CivSurf = Autodesk.Civil.DatabaseServices.Surface;

[assembly: CommandClass(typeof(C3DVerificador.Presentacion))]

namespace C3DVerificador
{
    public class Presentacion
    {
        // capas del DXF que son hojas 2D (secciones, perfiles, textos): se congelan en la vista 3D
        static readonly string[] Capas2D = { "C3D-HOJA", "C3D-PERFIL", "C3D-SECCION", "C3D-TEXTO", "C3D-PUNTOS", "C3D-PT", "C3D-TN", "C3D-EJE-2D", "C3D-EJE-PROGRESIVAS", "C3D-NOMBRE-CALLE", "C3D-BM", "C3D-FACHADA", "C3D-PUERTA", "C3D-UMBRAL", "C3D-ESQUINA-TEXTO" };

        static readonly (string, byte, byte, byte)[] Colores =
        {
            ("C3D-3D-CALZADA", 70, 72, 78), ("C3D-3D-BADEN", 142, 68, 173), ("C3D-3D-ESQUINA-CALZADA", 70, 72, 78),
            ("C3D-3D-ESQUINA-SARDINEL", 235, 235, 230), ("C3D-3D-MARTILLO", 192, 80, 74), ("C3D-3D-RAMPA", 243, 156, 18),
            ("C3D-3D-CUNETA", 90, 150, 200), ("C3D-3D-SARDINEL", 235, 235, 230),
            ("C3D-3D-VEREDA", 222, 196, 150), ("C3D-3D-FACHADA", 192, 57, 43), ("C3D-3D-CAPA_C", 160, 120, 60),
            ("C3D-3D-CAPA_V", 200, 170, 120), ("C3D-LF-EJE", 255, 210, 0), ("C3D-LF-", 120, 120, 120),
            ("C3D-COD-", 255, 0, 255),
        };

        static bool EnConsola => Environment.GetCommandLineArgs()[0].EndsWith("accoreconsole.exe", StringComparison.OrdinalIgnoreCase);
        static string ultimaCarpeta = "";

        static string PedirCarpeta(Editor ed, string variable, string mensaje)
        {
            string dir = Environment.GetEnvironmentVariable(variable);
            if (!string.IsNullOrEmpty(dir) && Directory.Exists(dir)) return dir;
            var op = new PromptStringOptions($"\n{mensaje} <{ultimaCarpeta}>: ") { AllowSpaces = true };
            var r = ed.GetString(op);
            if (r.Status != PromptStatus.OK) return null;
            dir = r.StringResult.Trim().Trim('"');
            if (dir == "") dir = ultimaCarpeta;
            if (!Directory.Exists(dir)) { ed.WriteMessage($"\n[CS] No existe la carpeta '{dir}'."); return null; }
            ultimaCarpeta = dir;
            return dir;
        }

        // ------------------------------------------------------------------ comandos
        [CommandMethod("CS_GENERAR", CommandFlags.Session)]
        public void Generar()
        {
            var doc = Application.DocumentManager.MdiActiveDocument;
            var ed = doc.Editor;
            string proy = PedirCarpeta(ed, "CS_GEN_DIR", "Carpeta del proyecto de Corredor Simple (calles.csv, terreno.csv...)");
            if (proy == null) return;
            string salida = proy;
            if (File.Exists(Path.Combine(proy, "calles.csv")))
            {
                salida = Path.Combine(proy, "salida_civil3d");
                if (!Calcular(ed, proy, salida)) return;
            }
            Armar(doc, salida, true);
        }

        [CommandMethod("CS_PRESENTAR", CommandFlags.Session)]
        public void Presentar()
        {
            var doc = Application.DocumentManager.MdiActiveDocument;
            string dir = PedirCarpeta(doc.Editor, "CS_PRES_DIR", "Carpeta con corredor_civil3d.xml y .dxf");
            if (dir != null) Armar(doc, dir, false);
        }

        // ------------------------------------------------------------------ cálculo con la app
        static (string py, string pyArgs, string app) BuscarApp()
        {
            string py = Environment.GetEnvironmentVariable("CS_PYTHON"), app = Environment.GetEnvironmentVariable("CS_APP_DIR");
            string dllDir = Path.GetDirectoryName(typeof(Presentacion).Assembly.Location);
            string cfg = Path.Combine(dllDir, "corredor_simple.json");
            if (File.Exists(cfg))
            {
                try
                {
                    var j = JsonNode.Parse(File.ReadAllText(cfg));
                    py ??= (string)j["python"];
                    app ??= (string)j["app"];
                }
                catch { }
            }
            if (string.IsNullOrEmpty(app))
            {
                // el .dll está dentro del repositorio (civil3d_verificador/bin/...): se sube hasta CorredorSimple.py
                var d = new DirectoryInfo(dllDir);
                while (d != null && !File.Exists(Path.Combine(d.FullName, "CorredorSimple.py"))) d = d.Parent;
                app = d?.FullName;
            }
            string pyArgs = "";
            if (string.IsNullOrEmpty(py))
            {
                string win = Environment.GetFolderPath(Environment.SpecialFolder.Windows);
                if (File.Exists(Path.Combine(win, "py.exe"))) { py = Path.Combine(win, "py.exe"); pyArgs = "-3 "; }
                else py = "python";
            }
            return (py, pyArgs, app);
        }

        static bool Calcular(Editor ed, string proy, string salida)
        {
            var (py, pyArgs, app) = BuscarApp();
            if (app == null || !File.Exists(Path.Combine(app, "CorredorSimple.py")))
            {
                ed.WriteMessage("\n[CS] No encuentro CorredorSimple.py: fije CS_APP_DIR o corredor_simple.json.");
                return false;
            }
            ed.WriteMessage($"\n[CS] Calculando con Corredor Simple ({proy})...");
            var psi = new ProcessStartInfo(py, $"{pyArgs}\"{Path.Combine(app, "CorredorSimple.py")}\" calcular \"{proy}\" \"{salida}\"")
            {
                UseShellExecute = false, RedirectStandardOutput = true, RedirectStandardError = true, CreateNoWindow = true,
                WorkingDirectory = app,
            };
            psi.Environment["PYTHONIOENCODING"] = "utf-8";
            psi.StandardOutputEncoding = System.Text.Encoding.UTF8;
            psi.StandardErrorEncoding = System.Text.Encoding.UTF8;
            using var p = Process.Start(psi);
            string outTxt = p.StandardOutput.ReadToEnd(), errTxt = p.StandardError.ReadToEnd();
            p.WaitForExit(900000);
            try { File.WriteAllText(Path.Combine(proy, "corredor_simple_calculo.log"), outTxt + "\n" + errTxt); } catch { }
            var lineas = outTxt.Split('\n').Select(l => l.TrimEnd()).Where(l => l.Length > 0).ToList();
            foreach (var l in lineas.Where(l => l.StartsWith("[ERROR]") || l.Contains("corte ") && l.Contains("relleno")))
                ed.WriteMessage("\n[CS]   " + l);
            int errores = lineas.Count(l => l.StartsWith("[ERROR]"));
            if (p.ExitCode != 0 || !File.Exists(Path.Combine(salida, "corredor_civil3d.xml")))
            {
                ed.WriteMessage($"\n[CS] La app no terminó (código {p.ExitCode}). Detalle en corredor_simple_calculo.log\n" +
                                string.Join("\n", (errTxt + outTxt).Split('\n').TakeLast(8)));
                return false;
            }
            ed.WriteMessage($"\n[CS] Cálculo listo: {errores} errores, avisos completos en {Path.Combine(salida, "csv", "avisos.txt")}");
            return true;
        }

        // ------------------------------------------------------------------ armar el dibujo
        static void Armar(Autodesk.AutoCAD.ApplicationServices.Document doc, string dir, bool nativos)
        {
            var ed = doc.Editor;
            var db = doc.Database;
            string xml = Path.Combine(dir, "corredor_civil3d.xml");
            string dxf = Path.Combine(dir, "corredor_civil3d.dxf");
            var civ = CivilApplication.ActiveDocument;
            using (doc.LockDocument())
            {
                if (File.Exists(dxf)) ModeloDxf(db, dxf, ed);
                if (File.Exists(xml))
                {
                    SuperficieTN(db, civ, xml, ed);
                    if (nativos)
                    {
                        EjesYPerfiles(db, civ, xml, ed);
                        SuperficiesDiseno(db, civ, xml, ed);
                    }
                }
            }
            if (!EnConsola)
                // encuadre sobre el modelo 3D (capas C3D-3D-*): con ZOOM E entran los ejes, que están a cota 0,
                // y el modelo (a ~4000 m en la sierra) queda como un punto
                doc.SendStringToExecute("(command \"_.-VIEW\" \"_SWISO\" \"_.VSCURRENT\" \"_R\" \"_.ZOOM\" \"_O\" (ssget \"X\" '((8 . \"C3D-3D-*\"))) \"\") ", true, false, false);
            ed.WriteMessage("\n[CS] Listo. Capas C3D-3D-* = modelo 3D; CS-EJES = alineamientos y perfiles; " +
                            "CS-SUPERFICIES (apagada) = superficies de diseño; C3D-TN-SUPERFICIE (apagada) = terreno.");
        }

        static ObjectId Capa(Transaction tr, Database db, string nombre, byte r, byte g, byte b, bool apagada = false)
        {
            var lt = (LayerTable)tr.GetObject(db.LayerTableId, OpenMode.ForRead);
            if (lt.Has(nombre)) return lt[nombre];
            lt.UpgradeOpen();
            var ly = new LayerTableRecord { Name = nombre, Color = Autodesk.AutoCAD.Colors.Color.FromRgb(r, g, b), IsOff = apagada };
            var id = lt.Add(ly);
            tr.AddNewlyCreatedDBObject(ly, true);
            return id;
        }

        static string Libre(Func<string, bool> existe, string nombre)
        {
            if (!existe(nombre)) return nombre;
            for (int k = 2; ; k++) if (!existe($"{nombre} ({k})")) return $"{nombre} ({k})";
        }

        static void ModeloDxf(Database db, string dxf, Editor ed)
        {
            using var src = new Database(false, true);
            src.DxfIn(dxf, null);
            var blkId = db.Insert("CS_CORREDOR_" + DateTime.Now.ToString("HHmmss"), src, true);
            using var tr = db.TransactionManager.StartTransaction();
            var ms = (BlockTableRecord)tr.GetObject(SymbolUtilityServices.GetBlockModelSpaceId(db), OpenMode.ForWrite);
            var br = new BlockReference(Point3d.Origin, blkId);
            ms.AppendEntity(br);
            tr.AddNewlyCreatedDBObject(br, true);
            br.ExplodeToOwnerSpace();
            br.Erase();
            var lt = (LayerTable)tr.GetObject(db.LayerTableId, OpenMode.ForRead);
            foreach (ObjectId lid in lt)
            {
                var ly = (LayerTableRecord)tr.GetObject(lid, OpenMode.ForRead);
                if (Capas2D.Any(p => ly.Name.StartsWith(p, StringComparison.OrdinalIgnoreCase)) && lid != db.Clayer)
                {
                    ly.UpgradeOpen();
                    ly.IsFrozen = true;
                }
                foreach (var (pref, r, g, b) in Colores)
                    if (ly.Name.StartsWith(pref, StringComparison.OrdinalIgnoreCase))
                    {
                        ly.UpgradeOpen();
                        ly.Color = Autodesk.AutoCAD.Colors.Color.FromRgb(r, g, b);
                        break;
                    }
            }
            tr.Commit();
            ed.WriteMessage("\n[CS] Modelo 3D insertado desde " + dxf);
        }

        static ObjectId Estilo(Transaction tr, CivilDocument civ, string preferido)
        {
            ObjectId primero = ObjectId.Null;
            foreach (ObjectId sid in civ.Styles.SurfaceStyles)
            {
                var st = (SurfaceStyle)tr.GetObject(sid, OpenMode.ForRead);
                if (st.Name == preferido) return sid;
                if (primero.IsNull) primero = sid;
            }
            return primero;
        }

        static void SuperficieTN(Database db, CivilDocument civ, string xml, Editor ed)
        {
            using var tr = db.TransactionManager.StartTransaction();
            const string nombre = "TN Terreno existente";
            try
            {
                var existentes = new HashSet<string>(civ.GetSurfaceIds().Cast<ObjectId>()
                    .Select(i => ((CivSurf)tr.GetObject(i, OpenMode.ForRead)).Name));
                var id = TinSurface.CreateFromLandXML(db, Libre(existentes.Contains, nombre), xml, nombre);
                var s = (TinSurface)tr.GetObject(id, OpenMode.ForWrite);
                // solo el borde y en su capa apagada: en 3D la superficie se pinta sombreada y, donde la
                // calle va en corte, la tapa. Se enciende con LAYON / cambiando el estilo.
                var est = Estilo(tr, civ, "Border Only");
                if (!est.IsNull) s.StyleId = est;
                s.LayerId = Capa(tr, db, "C3D-TN-SUPERFICIE", 141, 110, 99, apagada: true);
                ed.WriteMessage($"\n[CS] Superficie '{s.Name}'");
            }
            catch (System.Exception ex) { ed.WriteMessage("\n[CS] TN: " + ex.Message); }
            tr.Commit();
        }

        static readonly XNamespace L = "http://www.landxml.org/schema/LandXML-1.2";

        static void EjesYPerfiles(Database db, CivilDocument civ, string xml, Editor ed)
        {
            var x = XDocument.Load(xml);
            using var tr = db.TransactionManager.StartTransaction();
            var capa = Capa(tr, db, "CS-EJES", 255, 210, 0);
            var alStyle = civ.Styles.AlignmentStyles[0];
            var alLabels = civ.Styles.LabelSetStyles.AlignmentLabelSetStyles[0];
            var prStyle = civ.Styles.ProfileStyles[0];
            var prLabels = civ.Styles.LabelSetStyles.ProfileLabelSetStyles[0];
            var existentes = new HashSet<string>(civ.GetAlignmentIds().Cast<ObjectId>()
                .Select(i => ((Alignment)tr.GetObject(i, OpenMode.ForRead)).Name));
            int n = 0;
            foreach (var a in x.Descendants(L + "Alignment"))
            {
                string paso = "alineamiento";
                try
                {
                    string nombre = Libre(existentes.Contains, (string)a.Attribute("name"));
                    existentes.Add(nombre);
                    var alId = Alignment.Create(civ, nombre, ObjectId.Null, capa, alStyle, alLabels);
                    var al = (Alignment)tr.GetObject(alId, OpenMode.ForWrite);
                    int prev = -1;
                    Point2d? p0 = null;
                    foreach (var ln in a.Element(L + "CoordGeom").Elements(L + "Line"))
                    {
                        var s = ln.Element(L + "Start").Value.Split(' ', StringSplitOptions.RemoveEmptyEntries).Select(t => double.Parse(t, System.Globalization.CultureInfo.InvariantCulture)).ToArray();
                        var e = ln.Element(L + "End").Value.Split(' ', StringSplitOptions.RemoveEmptyEntries).Select(t => double.Parse(t, System.Globalization.CultureInfo.InvariantCulture)).ToArray();
                        var pa = new Point3d(s[1], s[0], 0);       // LandXML: norte este
                        var pb = new Point3d(e[1], e[0], 0);
                        p0 ??= new Point2d(pa.X, pa.Y);
                        var lin = prev < 0 ? al.Entities.AddFixedLine(pa, pb) : al.Entities.AddFixedLine(prev, pa, pb);
                        prev = lin.EntityId;
                    }
                    al.ReferencePoint = p0.Value;
                    al.ReferencePointStation = double.Parse((string)a.Attribute("staStart"), System.Globalization.CultureInfo.InvariantCulture);
                    paso = "perfil";
                    var pf = a.Descendants(L + "ProfAlign").FirstOrDefault();
                    if (pf != null)
                    {
                        var prId = Profile.CreateByLayout(nombre + " Rasante", alId, capa, prStyle, prLabels);
                        var pr = (Profile)tr.GetObject(prId, OpenMode.ForWrite);
                        foreach (var pvi in pf.Elements(L + "PVI"))
                        {
                            var v = pvi.Value.Split(' ', StringSplitOptions.RemoveEmptyEntries).Select(t => double.Parse(t, System.Globalization.CultureInfo.InvariantCulture)).ToArray();
                            paso = $"PVI {v[0]:F3}";
                            // el LandXML va a 4 decimales: el PVI final puede pasarse unas centésimas de
                            // mm del fin del eje y Civil 3D lo rechaza; se ajusta a los extremos
                            double est = Math.Min(Math.Max(v[0], al.StartingStation), al.EndingStation);
                            pr.PVIs.AddPVI(est, v[1]);
                        }
                    }
                    n++;
                }
                catch (System.Exception ex) { ed.WriteMessage($"\n[CS] Eje {(string)a.Attribute("name")} ({paso}): {ex.Message}"); }
            }
            tr.Commit();
            ed.WriteMessage($"\n[CS] {n} alineamientos con su perfil de rasante (capa CS-EJES)");
        }

        static void SuperficiesDiseno(Database db, CivilDocument civ, string xml, Editor ed)
        {
            var x = XDocument.Load(xml);
            var nombres = x.Descendants(L + "Surface").Select(s => (string)s.Attribute("name"))
                .Where(nm => nm.EndsWith(" TERMINADO") || nm.EndsWith(" SUBRASANTE")).ToList();
            using var tr = db.TransactionManager.StartTransaction();
            var capa = Capa(tr, db, "CS-SUPERFICIES", 150, 150, 150, apagada: true);   // encima del 3D parpadean: LAYON para verlas
            var est = Estilo(tr, civ, "Border Only");
            var existentes = new HashSet<string>(civ.GetSurfaceIds().Cast<ObjectId>()
                .Select(i => ((CivSurf)tr.GetObject(i, OpenMode.ForRead)).Name));
            int n = 0;
            foreach (var nm in nombres)
            {
                try
                {
                    string nombre = Libre(existentes.Contains, nm);
                    existentes.Add(nombre);
                    var id = TinSurface.CreateFromLandXML(db, nombre, xml, nm);
                    var s = (TinSurface)tr.GetObject(id, OpenMode.ForWrite);
                    if (!est.IsNull) s.StyleId = est;
                    s.LayerId = capa;
                    n++;
                }
                catch (System.Exception ex) { ed.WriteMessage($"\n[CS] Superficie {nm}: {ex.Message}"); }
            }
            tr.Commit();
            ed.WriteMessage($"\n[CS] {n} superficies de diseño (terminado y subrasante de cada calle y de las esquinas, capa CS-SUPERFICIES)");
        }
    }
}
