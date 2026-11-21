// CS_TOPOGRAFIA: carga un levantamiento (PENZD: punto,este,norte,cota,descripción) como puntos COGO
// y arma la superficie TIN "TN" con curvas de nivel, listo para diseñar la vía con las herramientas de
// Civil 3D (alineamiento, perfil, ensamblaje, corredor).
// Archivo: variable de entorno CS_TOPO_CSV o se pide en la línea de comandos.
using System;
using System.Globalization;
using System.IO;
using System.Linq;
using Autodesk.AutoCAD.ApplicationServices.Core;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
using Autodesk.Civil.ApplicationServices;
using Autodesk.Civil.DatabaseServices;
using Autodesk.Civil.DatabaseServices.Styles;

[assembly: CommandClass(typeof(C3DVerificador.Topografia))]

namespace C3DVerificador
{
    public class Topografia
    {
        [CommandMethod("CS_TOPOGRAFIA", CommandFlags.Session)]
        public void Cargar()
        {
            var doc = Application.DocumentManager.MdiActiveDocument;
            var ed = doc.Editor;
            var db = doc.Database;
            string csv = Environment.GetEnvironmentVariable("CS_TOPO_CSV");
            if (string.IsNullOrEmpty(csv) || !File.Exists(csv))
            {
                var r = ed.GetString(new PromptStringOptions("\nArchivo de puntos PENZD (punto,este,norte,cota,desc): ") { AllowSpaces = true });
                if (r.Status != PromptStatus.OK) return;
                csv = r.StringResult.Trim().Trim('"');
            }
            var civ = CivilApplication.ActiveDocument;
            var inv = CultureInfo.InvariantCulture;
            var pts = new Point3dCollection();
            int n = 0;
            using (doc.LockDocument())
            using (var tr = db.TransactionManager.StartTransaction())
            {
                foreach (var linea in File.ReadLines(csv))
                {
                    var c = linea.Split(',');
                    if (c.Length < 4 || !double.TryParse(c[1], NumberStyles.Float, inv, out double e)
                        || !double.TryParse(c[2], NumberStyles.Float, inv, out double nn)
                        || !double.TryParse(c[3], NumberStyles.Float, inv, out double z)) continue;
                    string desc = c.Length > 4 ? string.Join(",", c.Skip(4)).Trim() : "";
                    var p = new Point3d(e, nn, z);
                    var id = civ.CogoPoints.Add(p, desc, true);
                    n++;
                    // al TIN solo va el suelo (los BM están sobre un hito): igual que en la app
                    if (!desc.StartsWith("BM", StringComparison.OrdinalIgnoreCase)) pts.Add(p);
                }
                var sid = TinSurface.Create(db, "TN");
                var s = (TinSurface)tr.GetObject(sid, OpenMode.ForWrite);
                s.BuildOptions.UseMaximumTriangleLength = true;
                s.BuildOptions.MaximumTriangleLength = 20.0;
                s.AddVertices(pts);
                foreach (ObjectId st in civ.Styles.SurfaceStyles)
                {
                    var stl = (SurfaceStyle)tr.GetObject(st, OpenMode.ForRead);
                    if (stl.Name == "Contours 1m and 5m (Design)" || stl.Name == "Contours 1m and 5m (Background)")
                    {
                        s.StyleId = st;
                        if (stl.Name.Contains("Design")) break;
                    }
                }
                tr.Commit();
                ed.WriteMessage($"\n[CS] {n} puntos COGO y superficie TN ({pts.Count} puntos, lado máx. 20 m)");
            }
            if (!Environment.GetCommandLineArgs()[0].EndsWith("accoreconsole.exe", StringComparison.OrdinalIgnoreCase))
                doc.SendStringToExecute("_.ZOOM _E ", true, false, false);
        }
    }
}
