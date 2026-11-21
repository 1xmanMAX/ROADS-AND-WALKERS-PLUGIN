// Verificador de Corredor Simple dentro de Civil 3D 2025.
//
// Lee un "trabajo" (JSON) que escribe herramientas/verificar_civil3d.py y hace, con el motor de
// Civil 3D, las mismas cuentas que la app, para compararlas:
//   1. Importa las superficies del LandXML de la app (prueba que Civil 3D las acepta).
//   2. Crea su propia superficie TN desde los puntos del levantamiento (triangulación de Civil 3D,
//      con el mismo lado máximo de triángulo) para comparar contra el TIN de la app.
//   3. Crea cada alineamiento y su perfil de rasante con la API nativa y mide coordenadas y cotas.
//   4. Lee cotas de las superficies importadas en puntos de control.
//   5. Muestrea TN y subrasante a lo largo de cada sección (área de corte/relleno) y calcula
//      el volumen entre superficies (superficie de volumen TIN, como el Volumes Dashboard).
//   6. Escribe los resultados en JSON y guarda el DWG para abrirlo y revisarlo.
//
// Uso (en Civil 3D o accoreconsole):  NETLOAD C3DVerificador.dll  ->  CS_VERIFICAR
// El trabajo se toma de la variable de entorno CS_VERIF_TRABAJO o se pide en la línea de comandos.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text.Json;
using System.Text.Json.Nodes;
using Autodesk.AutoCAD.ApplicationServices.Core;
using Autodesk.AutoCAD.DatabaseServices;
using Autodesk.AutoCAD.EditorInput;
using Autodesk.AutoCAD.Geometry;
using Autodesk.AutoCAD.Runtime;
using Autodesk.Civil.ApplicationServices;
using Autodesk.Civil.DatabaseServices;
using CivSurface = Autodesk.Civil.DatabaseServices.Surface;

[assembly: CommandClass(typeof(C3DVerificador.Comandos))]

namespace C3DVerificador
{
    public class Comandos
    {
        Editor ed;
        readonly List<string> log = new List<string>();

        string logFile;

        void Log(string m)
        {
            log.Add(m);
            if (logFile != null) try { File.AppendAllText(logFile, DateTime.Now.ToString("HH:mm:ss.fff ") + m + Environment.NewLine); } catch { }
            try { ed?.WriteMessage("\n[CS] " + m); } catch { }
        }

        [CommandMethod("CS_VERIFICAR", CommandFlags.Session)]
        public void Verificar()
        {
            var doc = Application.DocumentManager.MdiActiveDocument;
            ed = doc.Editor;
            string ruta = Environment.GetEnvironmentVariable("CS_VERIF_TRABAJO");
            if (string.IsNullOrEmpty(ruta) || !File.Exists(ruta))
            {
                var r = ed.GetString("\nArchivo de trabajo JSON: ");
                if (r.Status != PromptStatus.OK) return;
                ruta = r.StringResult.Trim('"');
            }
            var trabajo = JsonNode.Parse(File.ReadAllText(ruta));
            string salida = (string)trabajo["salida"];
            logFile = Path.ChangeExtension(salida, ".log");
            try { File.Delete(logFile); } catch { }
            var res = new JsonObject();
            try
            {
                using (doc.LockDocument())
                    Ejecutar(doc.Database, trabajo, res);
                res["ok"] = true;
            }
            catch (System.Exception ex)
            {
                res["ok"] = false;
                res["error"] = ex.ToString();
                Log("ERROR: " + ex.Message);
            }
            var arr = new JsonArray();
            foreach (var m in log) arr.Add(m);
            res["log"] = arr;
            Log("escribiendo JSON");
            try
            {
                // NaN/Infinito se escriben como texto ("NaN") para no perder el resultado completo
                var op = new JsonSerializerOptions
                {
                    WriteIndented = true,
                    // Civil 3D desactiva la serialización por reflexión: se da el resolvedor explícito
                    TypeInfoResolver = new System.Text.Json.Serialization.Metadata.DefaultJsonTypeInfoResolver(),
                    NumberHandling = System.Text.Json.Serialization.JsonNumberHandling.AllowNamedFloatingPointLiterals,
                };
                File.WriteAllText(salida, res.ToJsonString(op));
            }
            catch (System.Exception ex)
            {
                Log("No se pudo escribir el JSON: " + ex);
            }
            Log("Resultado: " + salida);
        }

        static double D(JsonNode n) => n.GetValue<double>();

        static double? Elev(CivSurface s, double x, double y)
        {
            try { return s.FindElevationAtXY(x, y); }
            catch { return null; }
        }

        void Ejecutar(Database db, JsonNode t, JsonObject res)
        {
            var civ = CivilApplication.ActiveDocument;
            string xml = (string)t["landxml"];
            var sup = new Dictionary<string, ObjectId>();

            using (var tr = db.TransactionManager.StartTransaction())
            {
                // ---- 1. superficies del LandXML
                var imp = new JsonObject();
                foreach (var n in t["superficies_landxml"].AsArray())
                {
                    string nombre = (string)n;
                    try
                    {
                        var id = TinSurface.CreateFromLandXML(db, nombre, xml, nombre);
                        var s = (TinSurface)tr.GetObject(id, OpenMode.ForRead);
                        var p = s.GetGeneralProperties();
                        var tp = s.GetTinProperties();
                        sup[nombre] = id;
                        imp[nombre] = new JsonObject
                        {
                            ["puntos"] = p.NumberOfPoints,
                            ["triangulos"] = tp.NumberOfTriangles,
                            ["z_min"] = p.MinimumElevation,
                            ["z_max"] = p.MaximumElevation,
                            ["area_2d"] = s.GetTerrainProperties().SurfaceArea2D,
                        };
                        Log($"LandXML '{nombre}': {p.NumberOfPoints} puntos, {tp.NumberOfTriangles} triángulos");
                    }
                    catch (System.Exception ex)
                    {
                        imp[nombre] = new JsonObject { ["error"] = ex.Message };
                        Log($"LandXML '{nombre}' NO se importó: {ex.Message}");
                    }
                }
                res["landxml"] = imp;

                // ---- 2. TN propio de Civil 3D desde los puntos
                var tn = t["terreno"];
                ObjectId tnId = ObjectId.Null;
                if (tn != null && tn["puntos"].AsArray().Count >= 3)
                {
                    tnId = TinSurface.Create(db, "TN Civil3D desde puntos");
                    var s = (TinSurface)tr.GetObject(tnId, OpenMode.ForWrite);
                    s.BuildOptions.UseMaximumTriangleLength = true;
                    s.BuildOptions.MaximumTriangleLength = D(tn["arista_max"]);
                    var pc = new Point3dCollection();
                    foreach (var p in tn["puntos"].AsArray())
                        pc.Add(new Point3d(D(p[0]), D(p[1]), D(p[2])));
                    s.AddVertices(pc);
                    s.Rebuild();
                    var gp = s.GetGeneralProperties();
                    res["tn_civil3d"] = new JsonObject
                    {
                        ["puntos"] = gp.NumberOfPoints,
                        ["triangulos"] = s.GetTinProperties().NumberOfTriangles,
                    };
                    sup["TN Civil3D desde puntos"] = tnId;
                    Log($"TN Civil 3D: {gp.NumberOfPoints} puntos");
                }

                // ---- 3. chequeos de cota sobre superficies
                var chk = new JsonArray();
                foreach (var c in t["chequeos_superficie"].AsArray())
                {
                    string nombre = (string)c["superficie"];
                    double? z = null;
                    if (sup.TryGetValue(nombre, out var id))
                        z = Elev((CivSurface)tr.GetObject(id, OpenMode.ForRead), D(c["x"]), D(c["y"]));
                    chk.Add(new JsonObject
                    {
                        ["superficie"] = nombre, ["etiqueta"] = (string)c["etiqueta"],
                        ["z_app"] = D(c["z"]), ["z_c3d"] = z,
                    });
                }
                res["chequeos_superficie"] = chk;

                // ---- 4. alineamientos y perfiles nativos
                var layer = db.Clayer;
                var alStyle = civ.Styles.AlignmentStyles[0];
                var alLabels = civ.Styles.LabelSetStyles.AlignmentLabelSetStyles[0];
                var prStyle = civ.Styles.ProfileStyles[0];
                var prLabels = civ.Styles.LabelSetStyles.ProfileLabelSetStyles[0];
                var calles = new JsonArray();
                foreach (var c in t["calles"].AsArray())
                {
                    string id = (string)c["id"];
                    var rc = new JsonObject { ["id"] = id };
                    Log($"{id}: creando alineamiento");
                    var alId = Alignment.Create(civ, id, ObjectId.Null, layer, alStyle, alLabels);
                    var al = (Alignment)tr.GetObject(alId, OpenMode.ForWrite);
                    var v = c["vertices"].AsArray();
                    int prev = -1;
                    for (int i = 0; i + 1 < v.Count; i++)
                    {
                        var a = new Point3d(D(v[i][0]), D(v[i][1]), 0);
                        var b = new Point3d(D(v[i + 1][0]), D(v[i + 1][1]), 0);
                        var lin = prev < 0 ? al.Entities.AddFixedLine(a, b) : al.Entities.AddFixedLine(prev, a, b);
                        prev = lin.EntityId;
                    }
                    al.ReferencePoint = new Point2d(D(v[0][0]), D(v[0][1]));
                    al.ReferencePointStation = D(c["prog_inicial"]);
                    rc["est_inicial"] = al.StartingStation;
                    rc["est_final"] = al.EndingStation;

                    var ptsAl = new JsonArray();
                    foreach (var p in c["chequeos_eje"].AsArray())
                    {
                        double e = 0, n = 0;
                        al.PointLocation(D(p["prog"]), D(p["offset"]), ref e, ref n);
                        ptsAl.Add(new JsonObject
                        {
                            ["prog"] = D(p["prog"]), ["offset"] = D(p["offset"]),
                            ["e_app"] = D(p["e"]), ["n_app"] = D(p["n"]), ["e_c3d"] = e, ["n_c3d"] = n,
                        });
                    }
                    rc["chequeos_eje"] = ptsAl;
                    Log($"{id}: eje OK, creando perfil");

                    var prId = Profile.CreateByLayout(id + " Rasante", alId, layer, prStyle, prLabels);
                    var pr = (Profile)tr.GetObject(prId, OpenMode.ForWrite);
                    foreach (var p in c["pvis"].AsArray())
                        pr.PVIs.AddPVI(D(p[0]), D(p[1]));
                    var ptsPr = new JsonArray();
                    foreach (var p in c["chequeos_perfil"].AsArray())
                    {
                        double? z = null;
                        try { z = pr.ElevationAt(D(p["prog"])); } catch { }
                        ptsPr.Add(new JsonObject { ["prog"] = D(p["prog"]), ["z_app"] = D(p["z"]), ["z_c3d"] = z });
                    }
                    rc["chequeos_perfil"] = ptsPr;
                    Log($"{id}: perfil OK, secciones");

                    // ---- 5. áreas por sección y volumen entre superficies
                    string sub = (string)c["sup_subrasante"];
                    if (!tnId.IsNull && sup.TryGetValue(sub, out var subId))
                    {
                        var sTn = (CivSurface)tr.GetObject(tnId, OpenMode.ForRead);
                        var sSub = (CivSurface)tr.GetObject(subId, OpenMode.ForRead);
                        var secs = new JsonArray();
                        foreach (var s in c["secciones"].AsArray())
                        {
                            var (ac, ar, falta) = AreaSeccion(sTn, sSub, s);
                            secs.Add(new JsonObject
                            {
                                ["prog"] = D(s["prog"]), ["corte_app"] = D(s["corte"]), ["relleno_app"] = D(s["relleno"]),
                                ["corte_c3d"] = ac, ["relleno_c3d"] = ar, ["faltante_c3d"] = falta,
                            });
                        }
                        rc["secciones"] = secs;
                        Log($"{id}: secciones OK, volumen");
                        try
                        {
                            var vid = TinVolumeSurface.Create($"VOL {id} TN-SUBRASANTE", tnId, subId);
                            var vs = (TinVolumeSurface)tr.GetObject(vid, OpenMode.ForRead);
                            var vp = vs.GetVolumeProperties();
                            rc["vol_c3d_corte"] = vp.UnadjustedCutVolume;
                            rc["vol_c3d_relleno"] = vp.UnadjustedFillVolume;
                            Log($"{id}: volumen Civil 3D corte {vp.UnadjustedCutVolume:F2} relleno {vp.UnadjustedFillVolume:F2}");
                        }
                        catch (System.Exception ex)
                        {
                            rc["vol_error"] = ex.Message;
                            Log($"{id}: no se pudo crear la superficie de volumen: {ex.Message}");
                        }
                    }
                    calles.Add(rc);
                }
                res["calles"] = calles;

                // ---- 6. volúmenes de otras superficies (esquinas curvas)
                var extra = new JsonArray();
                if (t["volumenes_extra"] is JsonArray vex)
                    foreach (var v in vex)
                    {
                        string vid_ = (string)v["id"], sub = (string)v["sup_subrasante"];
                        var rv = new JsonObject { ["id"] = vid_ };
                        try
                        {
                            if (tnId.IsNull || !sup.TryGetValue(sub, out var subId)) throw new System.Exception("falta superficie " + sub);
                            var vid = TinVolumeSurface.Create($"VOL {vid_} TN-SUBRASANTE", tnId, subId);
                            var vp = ((TinVolumeSurface)tr.GetObject(vid, OpenMode.ForRead)).GetVolumeProperties();
                            rv["vol_c3d_corte"] = vp.UnadjustedCutVolume;
                            rv["vol_c3d_relleno"] = vp.UnadjustedFillVolume;
                            Log($"{vid_}: volumen Civil 3D corte {vp.UnadjustedCutVolume:F2} relleno {vp.UnadjustedFillVolume:F2}");
                        }
                        catch (System.Exception ex) { rv["vol_error"] = ex.Message; Log($"{vid_}: {ex.Message}"); }
                        extra.Add(rv);
                    }
                res["volumenes_extra"] = extra;
                Log("commit");
                tr.Commit();
                Log("commit OK");
            }
            // El DWG lo guarda el script (_.SAVEAS) después del comando: guardar la base de datos
            // activa desde el propio comando cierra accoreconsole sin aviso.
        }

        // Diferencia terreno − subrasante a lo largo de la sección (perpendicular al eje),
        // igual que la app: paso fino, trapecios y corte del tramo donde cambia de signo.
        static (double, double, double) AreaSeccion(CivSurface tn, CivSurface sub, JsonNode s)
        {
            double e0 = D(s["e"]), n0 = D(s["n"]), nx = D(s["nx"]), ny = D(s["ny"]);
            double paso = D(s["paso"]);
            // quiebres de la subrasante (offsets): se muestrea cada tramo por separado, como la app,
            // para no promediar a través de los escalones verticales (calzada / vereda)
            var qb = new List<double>();
            foreach (var q in s["quiebres"].AsArray()) qb.Add(D(q));
            var osL = new List<double>();
            for (int k = 0; k + 1 < qb.Count; k++)
            {
                double qa = qb[k], qz = qb[k + 1];
                if (qz - qa < 1e-9) continue;
                int mk = Math.Max(1, (int)Math.Ceiling((qz - qa) / paso));
                for (int i = (osL.Count == 0 ? 0 : 1); i <= mk; i++) osL.Add(qa + (qz - qa) * i / mk);
            }
            int m = osL.Count - 1;
            var os = osL.ToArray();
            var dif = new double?[m + 1];
            for (int i = 0; i <= m; i++)
            {
                double o = os[i];
                // 1 mm hacia adentro en los extremos para no caer justo en el borde de la superficie
                double oq = i == 0 ? o + 0.001 : (i == m ? o - 0.001 : o);
                double x = e0 + oq * nx, y = n0 + oq * ny;
                var zt = Elev(tn, x, y);
                var zs = Elev(sub, x, y);
                dif[i] = (zt.HasValue && zs.HasValue) ? zt - zs : null;
            }
            double corte = 0, relleno = 0, falta = 0;
            for (int i = 0; i < m; i++)
            {
                double h = os[i + 1] - os[i];
                if (!dif[i].HasValue || !dif[i + 1].HasValue) { falta += h; continue; }
                double d1 = dif[i].Value, d2 = dif[i + 1].Value;
                if (d1 >= 0 && d2 >= 0) corte += h * (d1 + d2) / 2;
                else if (d1 <= 0 && d2 <= 0) relleno += -h * (d1 + d2) / 2;
                else
                {
                    double x = h * d1 / (d1 - d2);
                    if (d1 > 0) { corte += x * d1 / 2; relleno += -(h - x) * d2 / 2; }
                    else { relleno += -x * d1 / 2; corte += (h - x) * d2 / 2; }
                }
            }
            return (corte, relleno, falta);
        }
    }
}
