# Cómo llevar los resultados a Civil 3D 2025 y compararlos

En la app, pestaña **6. Exportar**, pulsa **EXPORTAR TODO**. La carpeta de salida queda así:

```
salida/
  corredor_civil3d.xml    LandXML: alineamientos, perfiles de rasante y superficies
  corredor_civil3d.dxf    DXF (AutoCAD 2018): modelo 3D, líneas características, puntos, hojas
  informe.xlsx / informe.pdf
  csv/
    civil3d_puntos_PNEZD.csv      todos los puntos de diseño (terminado + capas)
    civil3d_terreno_PNEZD.csv     puntos del levantamiento
    EJE-xx_eje_progresiva_coordenada.csv
    EJE-xx_estacion_total_terminado.csv / _capas.csv
    EJE-xx_tabla_campo_capas.csv  (con lectura de mira)
    EJE-xx_movimiento_tierras.csv
    avisos.txt
```

## A. Importar en Civil 3D

Usa un dibujo nuevo con la plantilla métrica *_Autodesk Civil 3D (Metric) NCS.dwt*. En
*Configuración del dibujo* pon las unidades en metros y elige el sistema de coordenadas de tu
obra (por ejemplo UTM WGS84 19S).

1. **LandXML**: cinta *Insertar → LandXML* y elige `corredor_civil3d.xml`.
   - Aparecen las superficies `TN Terreno existente`, `EJE-xx TERMINADO`, `EJE-xx SUBRASANTE` y
     `EJE-xx FONDO Cn ...`.
   - Aparecen los alineamientos `EJE-xx ...` y sus perfiles de rasante: haz *Crear vista de perfil*
     sobre cada alineamiento.
   - Si te pide sitio, elige "Ninguno" o uno nuevo.
2. **DXF**: cinta *Insertar → Adjuntar* (o abrir el DXF y copiarlo con *Copiar con punto base 0,0,0*).
   Capas del DXF:
   - `C3D-EJE-2D`: polilínea del eje. Sirve si prefieres *Crear alineamiento desde objetos*.
   - `C3D-LF-*`: polilíneas 3D de bordes, cuneta, sardinel, vereda y subrasante. Sirven como líneas
     de rotura o se pueden convertir en *líneas características*.
   - `C3D-3D-*`: caras 3D del corredor y de cada capa. Revísalas con *Órbita 3D* y estilo visual
     *Realista*.
   - `C3D-PUNTOS*`, `C3D-PUERTAS`, `C3D-FACHADA`, `C3D-BM`, `C3D-TN-PUNTOS`.
   - `C3D-HOJA-*` y `C3D-PERFIL-*`: secciones (1:1) y perfiles (V × 10) ya dibujados, a la derecha de
     la obra, como base de planos.
3. **Puntos**: *Insertar → Puntos desde archivo*, formato **PNEZD (delimitado por comas)**, archivo
   `csv/civil3d_puntos_PNEZD.csv`. Para el terreno, `civil3d_terreno_PNEZD.csv`.

## B. Qué comparar (contra tu diseño en Civil 3D o contra el mismo LandXML)

| # | Qué | Dónde en Civil 3D | Dónde en la app | Diferencia aceptable |
|---|---|---|---|---|
| 1 | Coordenadas del eje cada 10 m | *Alineamiento → Propiedades / Informes → Estacas* | `EJE-xx_eje_progresiva_coordenada.csv` | ± 0.002 m |
| 2 | Cota de rasante en 0+000, 0+120 (quiebre) y 0+250 | Etiquetas de la vista de perfil | Excel, hoja *Eje* | ± 0.001 m |
| 3 | Cotas de BC, FC, CS, BV y PF en 0+050 y 0+200 (EJE-01) y en 0+180 (EJE-02) | Sección, o *Superficie terminada → etiqueta de cota de punto* | Excel, hoja *Secciones* | ± 0.002 m |
| 4 | Fondo de cada capa en el eje | Superficies `FONDO Cn` | Excel, hoja *Capas* | ± 0.002 m |
| 5 | Área de corte y relleno en 0+050, 0+120 (EJE-01) y 0+180 (EJE-02) | *Calcular materiales* (TN vs. SUBRASANTE) con líneas de muestreo cada 10 m | Excel, hoja *Tierras* | ± 1 % |
| 6 | Volumen total por calle | *Volumes Dashboard*: superficie de volumen TN vs. `EJE-xx SUBRASANTE` | Pestaña 5 o *Resumen* | ± 2 % |
| 7 | Volumen de losa | Superficies TERMINADO vs. `FONDO C1` | Resumen, columna losa | ± 1 % |

Valores de referencia del ejemplo (la app calcula por área media; el método entre superficies da
casi lo mismo, ver `docs/VERIFICACION.md`):

| Calle | Corte (m³) | Relleno (m³) | Losa (m³) |
|---|---|---|---|
| EJE-01 | 2306.15 | 0.00 | 288.00 |
| EJE-02 | 1467.37 | 59.53 | 220.84 |

**Por qué puede haber diferencias:**
- Civil 3D triangula el terreno a su manera. Si lo creas desde los puntos, revisa que no se
  formen triángulos largos a través de las manzanas; la app descarta los de más de 25 m.
- El volumen de Civil 3D entre superficies es continuo. El área media depende del intervalo
  entre secciones (10 m).
- En el cruce, la app no mete la calle secundaria dentro de la calzada principal, y las
  esquinas todavía no están resueltas.

Cuando tengas los números de Civil 3D, pásamelos en una tabla con progresiva, punto, cota de
Civil 3D y cota de la app, y revisamos las diferencias.
