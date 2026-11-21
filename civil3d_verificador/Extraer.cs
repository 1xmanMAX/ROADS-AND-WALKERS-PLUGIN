// CS_EXTRAER: lee DWG de un expediente (solo lectura, base de datos lateral) y vuelca a JSON lo que
// sirve para armar un proyecto de Corredor Simple: alineamientos, perfiles, superficies, puntos COGO,
// textos, polilíneas y bloques por capa.
// Entradas: CS_EXT_DWG (rutas separadas por ';') y CS_EXT_OUT (carpeta de salida).
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Nodes;
using Autodesk.AutoCAD.ApplicationServices.Core;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
using Autodesk.Civil.DatabaseServices;

[assembly: CommandClass(typeof(C3DVerificador.Extraer))]

namespace C3DVerificador
{
    public class Extraer
    {
        static JsonArray P(Point3d p) => new JsonArray(Math.Round(p.X, 4), Math.Round(p.Y, 4), Math.Round(p.Z, 4));
        static JsonArray P2(Point2d p) => new JsonArray(Math.Round(p.X, 4), Math.Round(p.Y, 4));

        [CommandMethod("CS_EXTRAER", CommandFlags.Session)]
        public void Ejecutar()
        {
            var ed = Application.DocumentManager.MdiActiveDocument.Editor;
            string lista = Environment.GetEnvironmentVariable("CS_EXT_DWG") ?? "";
            string outDir = Environment.GetEnvironmentVariable("CS_EXT_OUT") ?? ".";
            Directory.CreateDirectory(outDir);
            var op = new JsonSerializerOptions
            {
                WriteIndented = false,
                TypeInfoResolver = new System.Text.Json.Serialization.Metadata.DefaultJsonTypeInfoResolver(),
                NumberHandling = System.Text.Json.Serialization.JsonNumberHandling.AllowNamedFloatingPointLiterals,
            };
            foreach (var ruta in lista.Split(';', StringSplitOptions.RemoveEmptyEntries))
            {
                var res = new JsonObject { ["archivo"] = ruta };
                try { Leer(ruta, res); }
                catch (System.Exception ex) { res["error"] = ex.ToString(); }
                string nom = Path.Combine(outDir, Path.GetFileNameWithoutExtension(ruta) + ".json");
                File.WriteAllText(nom, res.ToJsonString(op));
                ed.WriteMessage($"\n[CS] {ruta} -> {nom}");
            }
        }

        static void Leer(string ruta, JsonObject res)
        {
            using var db = new Database(false, true);
            db.ReadDwgFile(ruta, FileOpenMode.OpenForReadAndAllShare, true, "");
            db.CloseInput(true);
            var conteo = new SortedDictionary<string, int>();
            var textos = new JsonArray();
            var polis = new JsonArray();
            var bloques = new JsonArray();
            var alins = new JsonArray();
            var perfiles = new JsonArray();
            var sups = new JsonArray();
            var cogo = new JsonArray();
            var otros = new JsonArray();
            using var tr = db.TransactionManager.StartTransaction();
            var ms = (BlockTableRecord)tr.GetObject(SymbolUtilityServices.GetBlockModelSpaceId(db), OpenMode.ForRead);
            foreach (ObjectId id in ms)
            {
                Autodesk.AutoCAD.DatabaseServices.DBObject o;
                try { o = tr.GetObject(id, OpenMode.ForRead); } catch { continue; }
                if (o is not Autodesk.AutoCAD.DatabaseServices.Entity ent) continue;
                string tipo = o.GetType().Name;
                string k = tipo + " | " + ent.Layer;
                conteo[k] = conteo.TryGetValue(k, out int c) ? c + 1 : 1;
                try
                {
                    switch (o)
                    {
                        case DBText t:
                            textos.Add(new JsonObject { ["t"] = t.TextString, ["c"] = ent.Layer, ["p"] = P(t.Position), ["h"] = Math.Round(t.Height, 3), ["r"] = Math.Round(t.Rotation, 4) });
                            break;
                        case MText m:
                            textos.Add(new JsonObject { ["t"] = m.Text, ["c"] = ent.Layer, ["p"] = P(m.Location), ["h"] = Math.Round(m.TextHeight, 3), ["r"] = Math.Round(m.Rotation, 4) });
                            break;
                        case Polyline pl:
                        {
                            var v = new JsonArray();
                            for (int i = 0; i < pl.NumberOfVertices; i++)
                            {
                                var q = pl.GetPoint2dAt(i);
                                v.Add(new JsonArray(Math.Round(q.X, 4), Math.Round(q.Y, 4), Math.Round(pl.GetBulgeAt(i), 5)));
                            }
                            polis.Add(new JsonObject { ["c"] = ent.Layer, ["z"] = Math.Round(pl.Elevation, 4), ["cerrada"] = pl.Closed, ["v"] = v });
                            break;
                        }
                        case Polyline3d p3:
                        {
                            var v = new JsonArray();
                            foreach (ObjectId vid in p3)
                                v.Add(P(((PolylineVertex3d)tr.GetObject(vid, OpenMode.ForRead)).Position));
                            polis.Add(new JsonObject { ["c"] = ent.Layer, ["3d"] = true, ["v"] = v });
                            break;
                        }
                        case Line ln:
                            polis.Add(new JsonObject { ["c"] = ent.Layer, ["linea"] = true, ["v"] = new JsonArray(P(ln.StartPoint), P(ln.EndPoint)) });
                            break;
                        case BlockReference br:
                        {
                            string nb = br.IsDynamicBlock ? ((BlockTableRecord)tr.GetObject(br.DynamicBlockTableRecord, OpenMode.ForRead)).Name : br.Name;
                            var at = new JsonObject();
                            foreach (ObjectId aid in br.AttributeCollection)
                                if (tr.GetObject(aid, OpenMode.ForRead) is AttributeReference ar) at[ar.Tag] = ar.TextString;
                            bloques.Add(new JsonObject { ["b"] = nb, ["c"] = ent.Layer, ["p"] = P(br.Position), ["r"] = Math.Round(br.Rotation, 4), ["at"] = at });
                            break;
                        }
                        case Alignment al:
                            alins.Add(Alin(al, tr));
                            break;
                        case TinSurface ts:
                        {
                            var pts = new JsonArray();
                            foreach (var v in ts.Vertices) pts.Add(P(v.Location));
                            sups.Add(new JsonObject { ["nombre"] = ts.Name, ["c"] = ent.Layer, ["vertices"] = pts });
                            break;
                        }
                        case CogoPoint cp:
                            cogo.Add(new JsonObject { ["n"] = cp.PointNumber, ["e"] = Math.Round(cp.Easting, 4), ["nn"] = Math.Round(cp.Northing, 4), ["z"] = Math.Round(cp.Elevation, 4), ["d"] = cp.RawDescription, ["c"] = ent.Layer });
                            break;
                        case DBPoint dp:
                            otros.Add(new JsonObject { ["tipo"] = "punto", ["c"] = ent.Layer, ["p"] = P(dp.Position) });
                            break;
                    }
                }
                catch (System.Exception ex) { otros.Add(new JsonObject { ["tipo"] = tipo, ["error"] = ex.Message }); }
            }
            // perfiles: se recorren desde cada alineamiento
            foreach (ObjectId id in ms)
            {
                if (tr.GetObject(id, OpenMode.ForRead) is not Alignment al) continue;
                foreach (ObjectId pid in al.GetProfileIds())
                {
                    try
                    {
                        var pr = (Profile)tr.GetObject(pid, OpenMode.ForRead);
                        var pv = new JsonArray();
                        foreach (ProfilePVI v in pr.PVIs)
                        {
                            double lc = 0;
                            try { if (v.VerticalCurve != null) lc = v.VerticalCurve.Length; } catch { }
                            pv.Add(new JsonArray(Math.Round(v.Station, 4), Math.Round(v.Elevation, 4), Math.Round(lc, 3)));
                        }
                        perfiles.Add(new JsonObject { ["alineamiento"] = al.Name, ["nombre"] = pr.Name, ["tipo"] = pr.ProfileType.ToString(), ["pvis"] = pv,
                            ["ini"] = Math.Round(pr.StartingStation, 4), ["fin"] = Math.Round(pr.EndingStation, 4) });
                    }
                    catch (System.Exception ex) { perfiles.Add(new JsonObject { ["alineamiento"] = al.Name, ["error"] = ex.Message }); }
                }
            }
            tr.Commit();
            var cj = new JsonObject();
            foreach (var kv in conteo) cj[kv.Key] = kv.Value;
            res["conteo"] = cj;
            res["alineamientos"] = alins;
            res["perfiles"] = perfiles;
            res["superficies"] = sups;
            res["cogo"] = cogo;
            res["textos"] = textos;
            res["polilineas"] = polis;
            res["bloques"] = bloques;
            res["otros"] = otros;
        }

        static JsonObject Alin(Alignment al, Transaction tr)
        {
            var ents = new JsonArray();
            for (int i = 0; i < al.Entities.Count; i++)
            {
                var e = al.Entities.GetEntityByOrder(i);
                var j = new JsonObject { ["tipo"] = e.EntityType.ToString() };
                switch (e)
                {
                    case AlignmentLine l:
                        j["ini"] = P2(l.StartPoint); j["fin"] = P2(l.EndPoint); j["L"] = Math.Round(l.Length, 4);
                        break;
                    case AlignmentArc a:
                        j["ini"] = P2(a.StartPoint); j["fin"] = P2(a.EndPoint); j["R"] = Math.Round(a.Radius, 4);
                        j["centro"] = P2(a.CenterPoint); j["horario"] = a.Clockwise; j["L"] = Math.Round(a.Length, 4);
                        break;
                    default:
                        try { j["ini"] = P2(((dynamic)e).StartPoint); j["fin"] = P2(((dynamic)e).EndPoint); } catch { }
                        break;
                }
                ents.Add(j);
            }
            return new JsonObject { ["nombre"] = al.Name, ["c"] = al.Layer, ["ini"] = Math.Round(al.StartingStation, 4), ["fin"] = Math.Round(al.EndingStation, 4),
                ["L"] = Math.Round(al.Length, 4), ["entidades"] = ents };
        }
    }
}
