// Estructura del archivo corredor_civil3d.json que exporta Corredor Simple (Python).
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace CorredorSimpleC3D
{
    public class Paquete
    {
        [JsonPropertyName("formato")] public string Formato { get; set; }
        [JsonPropertyName("version")] public int Version { get; set; }
        [JsonPropertyName("proyecto")] public string Proyecto { get; set; }
        [JsonPropertyName("generado")] public string Generado { get; set; }
        [JsonPropertyName("puntos")] public List<PuntoLev> Puntos { get; set; } = new();
        [JsonPropertyName("tn")] public Malla Tn { get; set; }
        [JsonPropertyName("calles")] public List<CalleC3D> Calles { get; set; } = new();
        [JsonPropertyName("fachadas")] public List<Fachada> Fachadas { get; set; } = new();
        [JsonPropertyName("elementos")] public List<Elemento> Elementos { get; set; } = new();
        [JsonPropertyName("bms")] public List<BmC3D> Bms { get; set; } = new();
    }

    public class PuntoLev
    {
        [JsonPropertyName("num")] public string Num { get; set; }
        [JsonPropertyName("e")] public double E { get; set; }
        [JsonPropertyName("n")] public double N { get; set; }
        [JsonPropertyName("z")] public double Z { get; set; }
        [JsonPropertyName("desc")] public string Desc { get; set; }
        [JsonPropertyName("tipo")] public string Tipo { get; set; }
    }

    public class Malla
    {
        [JsonPropertyName("pts")] public List<double[]> Pts { get; set; } = new();
        [JsonPropertyName("caras")] public List<int[]> Caras { get; set; } = new();
    }

    public class SeccionC3D
    {
        [JsonPropertyName("prog")] public double Prog { get; set; }
        [JsonPropertyName("e")] public double E { get; set; }
        [JsonPropertyName("n")] public double N { get; set; }
        [JsonPropertyName("rasante")] public double Rasante { get; set; }
        [JsonPropertyName("corte")] public double Corte { get; set; }
        [JsonPropertyName("relleno")] public double Relleno { get; set; }
    }

    public class PuntoReplanteo
    {
        [JsonPropertyName("nombre")] public string Nombre { get; set; }
        [JsonPropertyName("e")] public double E { get; set; }
        [JsonPropertyName("n")] public double N { get; set; }
        [JsonPropertyName("z")] public double Z { get; set; }
        [JsonPropertyName("codigo")] public string Codigo { get; set; }
    }

    public class CalleC3D
    {
        [JsonPropertyName("id")] public string Id { get; set; }
        [JsonPropertyName("nombre")] public string Nombre { get; set; }
        [JsonPropertyName("prog0")] public double Prog0 { get; set; }
        [JsonPropertyName("longitud")] public double Longitud { get; set; }
        [JsonPropertyName("vertices")] public List<double[]> Vertices { get; set; } = new();
        [JsonPropertyName("pvis")] public List<double[]> Pvis { get; set; } = new();
        [JsonPropertyName("secciones")] public List<SeccionC3D> Secciones { get; set; } = new();
        // código -> lista de polilíneas 3D -> puntos [e, n, z]
        [JsonPropertyName("lineas")] public Dictionary<string, List<List<double[]>>> Lineas { get; set; } = new();
        [JsonPropertyName("superficies")] public Dictionary<string, Malla> Superficies { get; set; } = new();
        // categoría -> lista de cuadriláteros -> 4 puntos [e, n, z]
        [JsonPropertyName("caras3d")] public Dictionary<string, List<List<double[]>>> Caras3d { get; set; } = new();
        [JsonPropertyName("replanteo")] public List<PuntoReplanteo> Replanteo { get; set; } = new();
        [JsonPropertyName("balance")] public Dictionary<string, double> Balance { get; set; } = new();
    }

    public class Fachada
    {
        [JsonPropertyName("id")] public string Id { get; set; }
        [JsonPropertyName("tipo")] public string Tipo { get; set; }
        [JsonPropertyName("pts")] public List<double[]> Pts { get; set; } = new();
    }

    public class Elemento
    {
        [JsonPropertyName("tipo")] public string Tipo { get; set; }
        [JsonPropertyName("id")] public string Id { get; set; }
        [JsonPropertyName("nombre")] public string Nombre { get; set; }
        [JsonPropertyName("eje")] public string Eje { get; set; }
        [JsonPropertyName("prog")] public double? Prog { get; set; }
        [JsonPropertyName("offset")] public double? Offset { get; set; }
        [JsonPropertyName("lado")] public string Lado { get; set; }
        [JsonPropertyName("zona")] public string Zona { get; set; }
        [JsonPropertyName("cota_campo")] public double? CotaCampo { get; set; }
        [JsonPropertyName("cota_diseno")] public double? CotaDiseno { get; set; }
        [JsonPropertyName("diferencia")] public double? Diferencia { get; set; }
        [JsonPropertyName("estado")] public string Estado { get; set; }
        [JsonPropertyName("nivel")] public string Nivel { get; set; }
        [JsonPropertyName("accion")] public string Accion { get; set; }
        [JsonPropertyName("este")] public double Este { get; set; }
        [JsonPropertyName("norte")] public double Norte { get; set; }
    }

    public class BmC3D
    {
        [JsonPropertyName("id")] public string Id { get; set; }
        [JsonPropertyName("punto")] public string Punto { get; set; }
        [JsonPropertyName("e")] public double E { get; set; }
        [JsonPropertyName("n")] public double N { get; set; }
        [JsonPropertyName("z")] public double Z { get; set; }
        [JsonPropertyName("ubicacion")] public string Ubicacion { get; set; }
        [JsonPropertyName("descripcion")] public string Descripcion { get; set; }
    }
}
