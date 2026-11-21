# Estado del proyecto y cómo seguir

Corredor Simple calcula calles urbanas (calzada, cuneta, sardinel, vereda, capas, cruces, esquinas,
badenes, rampas) a partir de un levantamiento y entrega todo para Civil 3D 2025. Este documento resume
qué hay, qué está verificado y qué falta, para quien continúe el trabajo.

## Qué hay

| Parte | Dónde | Estado |
|---|---|---|
| Motor de cálculo (Python) | `corredor/` | Secciones, rasante, área media con densificación, corrección por excentricidad en curvas, cruces en X y T |
| Cuneta CE.040 y badén (cuneta Tipo II) | `corredor/seccion.py`, `corredor/motor.py` | Cuneta triangular con fondo junto al sardinel; badén de arco a arco en la línea de cuneta de la principal |
| Esquinas curvas | `corredor/esquinas.py` | Sardinel en arco R = 3.00, pavimento de esquina, martillo, 2 rampas por esquina, materiales y corte/relleno |
| Códigos de campo | `corredor/codigos.py`, [CODIFICACION_CAMPO.md](CODIFICACION_CAMPO.md) | 31 códigos; fachadas, puertas y BM automáticos; controles de postes, tapas y empalmes |
| Interfaz | `corredor/app.py` | Pestañas de levantamiento, calles, capas, 3D, tierras, exportar; botón **Generar en Civil 3D** |
| Salidas | `corredor/exportar.py` | LandXML 1.2 (ejes, perfiles, superficies), DXF 3D, CSV PNEZD, Excel, PDF |
| Complemento Civil 3D (.NET 8) | `civil3d_verificador/` | `CS_GENERAR`, `CS_PRESENTAR`, `CS_TOPOGRAFIA`, `CS_VERIFICAR`, `CS_EXTRAER` |
| Instalador del complemento | `herramientas/instalar_civil3d.py` | Paquete `.bundle` en ApplicationPlugins (carga al iniciar Civil 3D) |
| Verificación contra Civil 3D | `herramientas/verificar_civil3d.py` | Civil 3D recalcula con su motor y compara; ver [PRUEBAS_CIVIL3D.md](PRUEBAS_CIVIL3D.md) |
| Escenarios de prueba | `escenarios/` (`herramientas/generar_escenarios.py`) | E01–E09: ladera, eje quebrado, cruce oblicuo y T, llano, irregular, malla 3×3, pasaje, curva cerrada, levantamiento codificado |
| Expediente real (importador) | `herramientas/extraer_dwg.py`, `herramientas/importar_nunoa.py` | Arma un proyecto desde planos CAD explotados (ejes, perfiles, curvas de nivel, secciones) |
| Topografía de práctica | `topografia_practica/` (`herramientas/generar_topografia.py`) | 420 × 320 m con llanura, ladera suave, quebrada, ladera fuerte, talud, lomita y vía existente; DWG con puntos COGO y TN |
| Pruebas | `pruebas/` | 83 pruebas (`python -m pytest`), con volúmenes de referencia calculados por Civil 3D |

## Verificado con Civil 3D 2025

* Coordenadas, rasante y cotas de superficies: 0.0–0.1 mm (2 mm de tolerancia).
* Volúmenes por calle: dentro de ±1 % en todos los escenarios (referencias en `pruebas/referencias_civil3d.json`).
* Esquinas: corte y relleno de las esquinas = superficie de volumen de Civil 3D (0.00 % a 0.73 %).
* Expediente de Nuñoa: subrasante en el eje ±1 mm frente al plano de secciones; pavimento rígido −0.28 %
  frente al metrado del expediente; badenes en las mismas progresivas (±0.4 m).

## Cómo correr todo

```bash
pip install -r requirements.txt
python CorredorSimple.py                                   # ventana
python CorredorSimple.py calcular datos_ejemplo salida      # sin ventana
python CorredorSimple.py civil3d <proyecto>                 # arma el DWG en Civil 3D y lo abre
python -m pytest                                            # pruebas
dotnet build civil3d_verificador -c Release                 # complemento
python herramientas/instalar_civil3d.py                     # Civil 3D lo carga solo (con Civil 3D cerrado)
python herramientas/verificar_civil3d.py --todos escenarios salida_escenarios
python herramientas/generar_topografia.py                   # topografía de práctica (+ DWG si hay Civil 3D)
```

## Lo que falta (prioridad)

1. **Corredor NATIVO de Civil 3D.** Hoy el complemento crea ejes y perfiles nativos y superficies, pero
   el modelo de la vía va como caras 3D. Lo correcto en Civil 3D es: ensamblaje con subensamblajes
   (carril, cuneta + sardinel, vereda, taludes) → corredor → superficie de corredor → líneas de
   muestreo → materiales. Siguiente paso: que `CS_GENERAR` arme el ensamblaje con los parámetros de
   `seccion_tipica.csv` / `capas.csv` y cree el corredor (API `CorridorCollection.Add`,
   `Assembly`, `SubassemblyTool`), con regiones cortadas en los cruces y esquinas con el asistente de
   intersecciones.
2. Curvas horizontales y verticales reales (hoy son cuerdas).
3. Sección asimétrica (carriles distintos a cada lado) y ancho de calzada variable en un mismo eje.
4. Martillo como lo mide el expediente (incluye parte de la vereda de los brazos).
5. Fusionar la codificación de campo del usuario con la del manual (`codigos_alias.csv`).
6. Relleno pequeño del EJE-05 de Nuñoa (11.1 vs 11.7 m³ en Civil 3D): revisar la densificación.

## Notas para quien siga

* Los datos y salidas del expediente real (`proyectos/`, `salida_nunoa*`) no se suben (`.gitignore`).
* El complemento se compila contra `C:\Program Files\Autodesk\AutoCAD 2025` (`-p:C3DDir=...` para otra ruta).
* En PowerShell/heredocs, cuidado con `\n` dentro de cadenas al parchar código: varias veces se
  convirtió en un salto de línea real.
