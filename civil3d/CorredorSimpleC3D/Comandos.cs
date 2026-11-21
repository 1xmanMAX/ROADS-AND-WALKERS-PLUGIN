// Comandos de Corredor Simple para Civil 3D 2025.
//   CSIMPORTAR  lee corredor_civil3d.json (exportado por la app) y construye el proyecto en el dibujo.
//   CSRESUMEN   muestra en la línea de comandos el resumen del archivo (volúmenes, interferencias, BM).
//   CSAYUDA     lista los comandos.
using System;
using System.IO;
using System.Linq;
using System.Text.Json;
using Autodesk.AutoCAD.ApplicationServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
using Autodesk.Civil.ApplicationServices;
using AcApp = Autodesk.AutoCAD.ApplicationServices.Core.Application;

[assembly: CommandClass(typeof(CorredorSimpleC3D.Comandos))]
[assembly: ExtensionApplication(typeof(CorredorSimpleC3D.Inicio))]

namespace CorredorSimpleC3D
{
    public class Inicio : IExtensionApplication
    {
        public void Initialize()
        {
            var ed = AcApp.DocumentManager.MdiActiveDocument?.Editor;
            ed?.WriteMessage("\nCorredor Simple para Civil 3D cargado. Comandos: CSIMPORTAR, CSRESUMEN, CSAYUDA.\n");
        }

        public void Terminate() { }
    }

    public class Comandos
    {
        static Paquete Leer(Editor ed, out string ruta)
        {
            ruta = null;
            var op = new PromptOpenFileOptions("\nArchivo de Corredor Simple (corredor_civil3d.json)")
            {
                Filter = "Corredor Simple (*.json)|*.json",
                DialogCaption = "Corredor Simple: seleccione corredor_civil3d.json"
            };
            var r = ed.GetFileNameForOpen(op);
            if (r.Status != PromptStatus.OK) return null;
            ruta = r.StringResult;
            var paq = JsonSerializer.Deserialize<Paquete>(File.ReadAllText(ruta));
            if (paq == null || paq.Formato != "CorredorSimpleC3D")
            {
                ed.WriteMessage("\nEl archivo no es un paquete de Corredor Simple.");
                return null;
            }
            return paq;
        }

        [CommandMethod("CSAYUDA")]
        public void Ayuda()
        {
            var ed = AcApp.DocumentManager.MdiActiveDocument.Editor;
            ed.WriteMessage("\nCorredor Simple para Civil 3D 2025" +
                            "\n  CSIMPORTAR  construye puntos, superficies, ejes, perfiles, líneas 3D, modelo de capas, interferencias y BM" +
                            "\n  CSRESUMEN   muestra volúmenes, interferencias y BM del archivo" +
                            "\nEn la app: pestaña 8 · Exportar, opción 'Civil 3D (paquete para el complemento)'.\n");
        }

        [CommandMethod("CSRESUMEN")]
        public void Resumen()
        {
            var ed = AcApp.DocumentManager.MdiActiveDocument.Editor;
            var p = Leer(ed, out _);
            if (p == null) return;
            ed.WriteMessage($"\nProyecto {p.Proyecto} (generado {p.Generado})");
            foreach (var c in p.Calles)
            {
                c.Balance.TryGetValue("corte", out var co);
                c.Balance.TryGetValue("relleno", out var re);
                ed.WriteMessage($"\n  {c.Id} {c.Nombre}: L = {c.Longitud:F2} m, corte {co:F2} m3, relleno {re:F2} m3");
            }
            ed.WriteMessage($"\n  Interferencias: {p.Elementos.Count(x => x.Nivel == "ERROR")} errores, {p.Elementos.Count(x => x.Nivel == "AVISO")} avisos");
            foreach (var b in p.Bms) ed.WriteMessage($"\n  {b.Id} {b.Z:F3}  {b.Ubicacion}");
            ed.WriteMessage("\n");
        }

        [CommandMethod("CSIMPORTAR", CommandFlags.Modal)]
        public void Importar()
        {
            var doc = AcApp.DocumentManager.MdiActiveDocument;
            var ed = doc.Editor;
            var civ = CivilApplication.ActiveDocument;
            var p = Leer(ed, out var ruta);
            if (p == null) return;

            var o = new Opciones();
            var kw = new PromptKeywordOptions("\n¿Qué importar? [Todo/Basico/Replanteo]", "Todo Basico Replanteo") { AllowNone = true };
            kw.Keywords.Default = "Todo";
            var rk = ed.GetKeywords(kw);
            if (rk.Status == PromptStatus.Cancel) return;
            if (rk.StringResult == "Basico") { o.Caras3D = false; o.Lineas = false; }
            if (rk.StringResult == "Replanteo") o.Replanteo = true;

            // vistas de perfil a la derecha de la obra
            double maxE = p.Calles.SelectMany(c => c.Vertices).Select(v => v[0]).DefaultIfEmpty(0).Max();
            double maxN = p.Calles.SelectMany(c => c.Vertices).Select(v => v[1]).DefaultIfEmpty(0).Max();
            var origenVistas = new Point3d(maxE + 100, maxN, 0);

            Constructor k = null;
            try
            {
                using (doc.LockDocument())
                using (var tr = doc.Database.TransactionManager.StartTransaction())
                {
                    k = new Constructor(doc.Database, civ, tr);
                    if (o.Puntos) k.Puntos(p, o);
                    if (o.Superficies) k.Superficies(p);
                    if (o.Ejes) k.Ejes(p, origenVistas);
                    if (o.Lineas) k.Lineas(p);
                    if (o.Caras3D) k.Caras3D(p);
                    if (o.Interferencias) k.Interferencias(p);
                    tr.Commit();
                }
            }
            catch (System.Exception ex)
            {
                ed.WriteMessage($"\nError al importar: {ex.Message}\n{ex.StackTrace}\n");
                return;
            }
            ed.WriteMessage($"\nCorredor Simple: importado {Path.GetFileName(ruta)}");
            foreach (var l in k.Informe) ed.WriteMessage("\n  " + l);
            ed.WriteMessage("\n  Capas: CS-* · Grupos de puntos: CS * · Superficies: CS * · Use ZOOM Extensión.\n");
            doc.SendStringToExecute("._ZOOM _E ", true, false, false);
        }
    }
}
