# C3DVerificador: la app contra Civil 3D 2025

Complemento .NET 8 que repite dentro de Civil 3D (con su propio motor) las cuentas de Corredor
Simple y las compara. Lo usa `herramientas/verificar_civil3d.py`, que abre Civil 3D **sin
ventana** (accoreconsole), así que no interrumpe el Civil 3D que tengas abierto.

## Qué comprueba

| Control | Cómo lo hace Civil 3D | Tolerancia |
|---|---|---|
| LandXML importable | `TinSurface.CreateFromLandXML` de cada superficie (TN, terminado, subrasante, fondos de capa) | todas deben entrar |
| Coordenadas de eje y bordes | alineamiento nativo creado desde los vértices, `PointLocation(est, offset)` | ± 2 mm |
| Rasante | perfil nativo con los PVI, `ElevationAt` | ± 2 mm |
| Cotas de superficies | `FindElevationAtXY` en eje, bordes, cunetas, veredas, subrasante, fondo de losa | ± 2 mm |
| Terreno | superficie TN **propia** de Civil 3D desde los puntos (su triangulación, mismo lado máximo) frente al TIN de la app | ± 5 mm |
| Área de corte/relleno por sección | muestreo TN − subrasante sobre las superficies de Civil 3D | ± 1 % o 0.02 m² |
| Volumen | superficie de volumen TIN (TN de Civil 3D − subrasante), como el *Volumes Dashboard* | ± 2 % o 0.5 m³ |

## Compilar

```bash
dotnet build civil3d_verificador -c Release
```

Necesita el SDK de .NET 8 y Civil 3D 2025 instalado en `C:\Program Files\Autodesk\AutoCAD 2025`
(otra ruta: `dotnet build -p:C3DDir="D:\...\AutoCAD 2025"`).

## Usar

```bash
python herramientas/verificar_civil3d.py datos_ejemplo salida_verificacion
python herramientas/verificar_civil3d.py --todos escenarios salida_escenarios
```

En cada carpeta de salida quedan `verificacion.md` (tabla OK/FALLA), `verificacion_civil3d.json`
(todo lo que midió Civil 3D), `verificacion_civil3d.dwg` (ábrelo para ver alineamientos, perfiles,
superficies y superficies de volumen) y `accoreconsole.log`. Con `--todos` también se escribe
`referencias_civil3d.json`, que se copia a `pruebas/` para que las pruebas automáticas comparen
contra Civil 3D aunque no esté instalado.

Dentro de Civil 3D, con un dibujo abierto: `NETLOAD` → `C3DVerificador.dll` → `CS_VERIFICAR` y
la ruta de `verificacion_trabajo.json`.

## Detalles que costó descubrir

- Hay que referenciar también `ACA\AecBaseMgd.dll` (ahí está la clase base `Entity` de Civil).
- Civil 3D desactiva la serialización JSON por reflexión: hay que dar `TypeInfoResolver`.
- Guardar la base de datos activa desde el propio comando cierra accoreconsole sin aviso; el DWG
  lo guarda el script con `_.SAVEAS 2018`.
- Al muestrear secciones hay que hacerlo por tramos entre quiebres de la subrasante (si no, se
  promedia a través del escalón calzada/vereda) y 1 mm hacia adentro en los bordes de la superficie.

## Presentación 3D (`CS_PRESENTAR`)

Arma en el dibujo actual el modelo 3D del corredor (caras de `corredor_civil3d.dxf` con colores por
material), la superficie TN de Civil 3D (capa `C3D-TN-SUPERFICIE`, apagada para que no tape la calle
en corte) y una vista isométrica realista. `NETLOAD` → `C3DVerificador.dll` → `CS_PRESENTAR` → carpeta
con `corredor_civil3d.xml` y `.dxf`.

## Extraer planos (`CS_EXTRAER`)

Lee DWG en una base de datos lateral (solo lectura) y vuelca a JSON alineamientos, perfiles,
superficies y puntos COGO, o, si el plano está explotado, textos, polilíneas, líneas y bloques por
capa. `python herramientas/extraer_dwg.py <carpeta> <salida_json>`.
