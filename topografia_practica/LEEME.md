# Topografía de práctica (pendientes variadas)

Zona de 420 × 320 m, UTM 19S (E 324000–324420, N 8396000–8396320), cotas 3819.9 a 3854.8 m.
8320 puntos. Ver `topografia_vista.png`.

| Zona | Pendiente | Qué obliga a resolver |
|---|---|---|
| Llanura (oeste) | 0.5 – 1 % | pendiente mínima de drenaje, rasante casi plana |
| Ladera suave (centro) | 3 – 4 % | la zona cómoda |
| Quebrada (x ≈ 205 m, N-S) | cauce de ~3 m | relleno y alcantarilla, o puente |
| Ladera fuerte (este) | 12 – 18 % | pendiente máxima, cortes altos, curvas |
| Talud / terraza (este, N ≈ 8396190) | escalón 1.5 m | corte adicional |
| Lomita (oeste) | 4 m de alto | rodear o cortar |
| Vía existente (sur) | plataforma con bombeo 2 % | **empalme** del diseño (bordes PEX1/PEX2, eje EJX1) |

Códigos (docs/CODIFICACION_CAMPO.md): `TN` terreno · `ZJ1` fondo de quebrada · `BOR1`/`BOR2` bordes ·
`CAB1`/`PIE1` talud · `PEX1`/`PEX2` bordes de asfalto existente · `EJX1` eje existente · `BM`.

## Modelar la vía en Civil 3D (flujo nativo)

1. **Puntos**: `Insert > Points from File` → `topografia_PENZD.csv`, formato **PENZD (comma delimited)**.
   (O abra `topografia.dwg`: ya tiene los puntos COGO y la superficie.)
2. **Superficie**: `Create Surface` → TIN "TN"; Definition → Point Groups (_All Points). Agregue como
   **breaklines** las polilíneas 3D de ZJ1, BOR1, BOR2, CAB1, PIE1 (Description Keys / Linework con
   el mismo código). Estilo de curvas 1 m / 5 m.
3. **Eje**: dibuje una polilínea (por ejemplo desde la vía existente al sur, cruzando la quebrada y
   subiendo la ladera fuerte) → `Alignment > Create Alignment from Objects`, con curvas (radio mínimo).
4. **Perfil**: `Profile > Create Surface Profile` + `Profile View`; luego `Profile Creation Tools` para
   la rasante: empalme a la cota del eje existente, pendiente máx. (8–10 %) en la ladera, mínima 0.5 %
   en la llanura, curvas verticales.
5. **Ensamblaje**: `Assembly` + subensamblajes de la sección típica (`LaneSuperelevationAOR` o
   `BasicLane` 3.60 m × 2, `UrbanCurbGutterGeneral` para cuneta + sardinel, `UrbanSidewalk` para
   vereda, `LinkSlopeToSurface` / `BasicSideSlopeCutDitch` para los taludes en la ladera).
6. **Corredor**: `Corridor` con eje + perfil + ensamblaje, frecuencia 10 m (5 m en curvas); objetivo de
   superficie = TN para los taludes. `Corridor Surface` (Top y Datum).
7. **Volúmenes**: `Sample Lines` cada 10 m → `Compute Materials` (TN vs Datum) → tabla de volúmenes y
   `Section Views`; o `Volumes Dashboard` con superficie TN vs Datum.

Para comparar: el mismo levantamiento se puede abrir en Corredor Simple (`terreno.csv` = este CSV) y
el verificador de la app compara sus volúmenes con los de Civil 3D.
