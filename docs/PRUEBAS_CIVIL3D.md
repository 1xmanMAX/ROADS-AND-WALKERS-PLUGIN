# Pruebas dentro de Civil 3D 2025

La app se probó con 8 levantamientos ficticios, armados para forzar casos que el ejemplo de 4
cuadras no tenía. Cada uno se calculó con la app y después Civil 3D 2025 repitió las cuentas con
su propio motor (complemento `civil3d_verificador`, sin ventana). Ver
[civil3d_verificador/README.md](../civil3d_verificador/README.md).

```bash
python herramientas/generar_escenarios.py                 # crea escenarios/
python herramientas/verificar_civil3d.py --todos escenarios salida_escenarios
```

## Levantamientos

| Escenario | Qué tiene | Qué fuerza |
|---|---|---|
| E01_ladera | 1 calle, 9 % y 6 %, ladera de 12 % transversal; grilla de 4 m | pendiente > máx., corte de un lado y relleno delgado del otro |
| E02_eje_quebrado | eje de 4 tramos (deflexiones 25°, 40°, 15°); levantamiento por cadenas cada 10 m | secciones en quiebres sin curva |
| E03_cruce_oblicuo_T | principal de 10.8 m + oblicua a 60° + T en el eje + T dibujada solo hasta el sardinel | cruces no ortogonales, rasantes que no coinciden, T |
| E04_llano_relleno | terreno bajo y plano, pendiente 0.3 %, perfil 0.56 m más corto que el eje | todo relleno, pendiente < mín., perfil incompleto |
| E05_irregular | puntos al azar con ruido, hueco de 9 m, 14 puntos repetidos, terreno hasta 0+200 de 0+220; CSV de Excel en español con `;` sobrantes; terreno PENZD sin cabecera | lectura de archivos reales, terreno incompleto |
| E06_malla_3x3 | 6 calles giradas 30°, 9 cruces, progresivas desde 1+000, coordenadas locales | muchos cruces, progresiva inicial |
| E07_pasaje_angosto | 4.50 m, sin vereda ni cuneta, 1 sola capa, 12 % | anchos y capas mínimos |
| E08_curva_cerrada | curva de R = 25 m con cuerdas de 1 m; corte mucho mayor al lado exterior | área media en curva |

## Fallas encontradas y corregidas

| # | Dónde salió | Falla | Corrección |
|---|---|---|---|
| 1 | datos_ejemplo | El perfil del LandXML terminaba en 250.000 y el eje medía 250.00005: Civil 3D no daba cota en la última estación. | Los PVI se ajustan exactamente al inicio y fin del eje (`Perfil.pvis`). |
| 2 | datos_ejemplo | Relleno de EJE-02: app 59.53 m³, Civil 3D 51.17 m³ (+16 %). La hondonada es más corta que el intervalo de 10 m. | Secciones intermedias automáticas donde el corte o relleno cambia > 25 % (hasta cada 2.5 m). Ahora 51.52 m³ (+0.7 %). |
| 3 | E05 | La app se cerraba (`AttributeError`) con CSV de Excel que traen `;` de más. | Las columnas sobrantes se pegan a la última columna. |
| 4 | E02 | En un quiebre del eje la sección iba perpendicular al tramo de llegada; del lado interior las secciones vecinas se cruzaban y la superficie TIN se doblaba (22 mm de error en la superficie terminada). | Sección en la bisectriz (inglete) y se omiten las secciones que se cruzarían con ella. Ahora 0.1 mm. |
| 5 | E08 | En curva el área media no considera que el lado exterior es más largo: corte −1.8 %, relleno +5.6 %. | Corrección por excentricidad (Pappus) en tierras y en materiales. Ahora +0.01 % y +0.03 %. |
| 6 | E03 | Una calle cuyo eje empieza en el sardinel de la principal no era cruce: la principal seguía con sardinel y vereda cruzando la boca. | Se detecta la T aunque el eje no toque el de la principal, y se avisa si queda un hueco sin metrar. |
| 7 | E03 | En toda T la principal perdía la vereda de **los dos** lados. | Solo se abre el lado por donde llega la otra calle. |
| 8 | (casos límite) | Terreno con todos los puntos en una línea: la app se cerraba (error de qhull). | Aviso claro, sin corte/relleno. |
| 9 | E05 | Puntos repetidos: la triangulación tomaba cualquiera de los dos. | Se usa el primero y se avisa la diferencia de cota. |
| 10 | E05 | Secciones totalmente fuera del levantamiento se avisaban como "parte de su ancho". | ERROR propio: "quedan FUERA del levantamiento". |
| 11 | E01 | Rellenos delgados no activaban las secciones intermedias (umbral 0.25 m²): +2.1 %. | Umbral 0.10 m². Ahora +0.9 %. |

| 12 | Nuñoa (expediente real) | La cuneta era una V simétrica con el fondo a la mitad. RNE CE.040 art. 14 y la cuneta Tipo I del expediente: triángulo rectángulo con el sardinel como lado vertical. | Fondo (FC) pegado a la cara del sardinel; ya no hay punto PS aparte. |
| 13 | Nuñoa | No había badenes en los cruces (cuneta Tipo II del plano de drenaje). | Badén en V (0.80 m, flecha 0.07, e = 0.22) que cruza la calle secundaria en la línea de cuneta de la principal; solo donde la principal tiene cuneta. Material propio. |
| 14 | Nuñoa | La boca de la secundaria (entre la calzada de la principal y su borde exterior) no la pavimentaba nadie. | La secundaria se omite solo dentro de la CALZADA de la principal. |
| 15 | Nuñoa | Una calle partida en un cruce (cambio de ancho) daba dos T en el mismo punto y la app se quedaba con una. | Las T se distinguen por punto Y por par de calles. |
| 16 | Nuñoa | Secciones de cruce a 5 cm de un vértice del eje (Jr. Tupac Yupanqui 0+086.83): superficie doblada, 107 mm en Civil 3D. | Cerca de un vértice solo queda la sección del vértice. |
| 17 | verificador | Con carpeta de salida relativa accoreconsole no encontraba el script. | Rutas absolutas. |

## Expediente real: Nuñoa (PMB-24)

Los planos CAD del expediente ("Mejoramiento ... jirones del barrio San Pedro II etapa, Nuñoa - Melgar -
Puno") vienen explotados, sin objetos de Civil 3D. Se leen con Civil 3D sin ventana (comando
`CS_EXTRAER`, solo lectura) y se arma el proyecto:

```bash
python herramientas/extraer_dwg.py "<carpeta PLANOS CAD>" json_nunoa
python herramientas/importar_nunoa.py json_nunoa proyectos/nunoa
python herramientas/verificar_civil3d.py proyectos/nunoa salida_nunoa_verif
```

* Ejes: polilíneas C-ROAD del topográfico. Rasante: banda y líneas del plano de perfiles (curvas
  verticales como cuerdas, ±3 mm contra la banda). Terreno: curvas cada 0.20 m + cota de terreno de la
  banda + BMs. Fachadas: bordes de manzana. Pachacutec y Manco Capac se parten donde cambia la calzada.
* Comparado con el expediente (secciones del plano 24.10, mismas progresivas):

| Calle | Corte exp. | Corte app | Dif. | Subrasante en el eje |
|---|---|---|---|---|
| Av. Mariscal Castilla | 777.9 | 739.6 | −4.9 % | ±1 mm |
| Av. Inca Garcilazo | 836.8 | 758.9 | −9.3 % | ±1 mm |
| Jr. Atahualpa | 384.6 | 368.6 | −4.1 % | ±1 mm |
| Jr. Mama Ocllo | 480.3 | 456.0 | −5.1 % | — |
| Jr. Manco Capac | 492.8 | 539.4 | +9.5 % | — |
| Jr. Tupac Yupanqui | 382.3 | 380.9 | −0.4 % | — |
| Jr. Sinchi Roca | 429.5 | 426.6 | −0.7 % | ±2 mm |

  Terreno en el eje: mediana 0 mm. Pavimento rígido: app 11 473.6 m², expediente 11 505.56 m²
  (−0.28 %). Las diferencias de volumen vienen de los costados (veredas y áreas junto al parque),
  no de la calzada.
* Badenes: 22, en las mismas progresivas que las secciones de badén del expediente (±0.4 m).
* Civil 3D (su propio motor) sobre el modelo de Nuñoa: coordenadas y rasante 0.00 mm, superficies OK,
  9 de 11 volúmenes dentro de ±2 %; los otros 2 son rellenos pequeños (diferencia < 0.7 m³).
* Pendiente: esquinas/martillos, sección asimétrica (Manco Capac 3.00/2.70) y el ancho real de los
  badenes en la boca (10.4 m en el expediente, la app usa el ancho de calzada).

## Resultado de los escenarios (Civil 3D 2025, todos OK)

Coordenadas, rasante, TN y cotas de todas las superficies coinciden con Civil 3D en 0.0–0.1 mm, y
la triangulación del terreno de la app es igual a la de Civil 3D. Volúmenes:

| Escenario | Calle | Corte app | Corte Civil 3D | Dif. | Relleno app | Relleno Civil 3D | Dif. |
|---|---|---|---|---|---|---|---|
| datos_ejemplo | EJE-01 | 2306.15 | 2308.19 | −0.09 % | 0.00 | 0.00 | — |
| datos_ejemplo | EJE-02 | 1465.53 | 1465.90 | −0.03 % | 51.52 | 51.17 | +0.67 % |
| E01_ladera | EJE-01 | 1713.41 | 1714.64 | −0.07 % | 27.85 | 27.61 | +0.86 % |
| E02_eje_quebrado | EJE-01 | 2915.57 | 2924.99 | −0.32 % | 0.00 | 0.00 | — |
| E03_cruce_oblicuo_T | EJE-01 | 4669.05 | 4677.47 | −0.18 % | 0.00 | 0.00 | — |
| E03_cruce_oblicuo_T | EJE-02 | 1805.98 | 1805.22 | +0.04 % | 0.00 | 0.00 | — |
| E03_cruce_oblicuo_T | EJE-03 | 895.32 | 893.50 | +0.20 % | 0.00 | 0.00 | — |
| E03_cruce_oblicuo_T | EJE-04 | 775.40 | 775.82 | −0.05 % | 0.00 | 0.00 | — |
| E04_llano_relleno | EJE-01 | 0.00 | 0.00 | — | 2454.92 | 2454.92 | 0.00 % |
| E05_irregular | EJE-01 | 2125.17 | 2132.26 | −0.33 % | 0.00 | 0.00 | — |
| E06_malla_3x3 | EJE-01…06 | 1945–2468 | 1950–2464 | −0.22 a +0.16 % | 0.00 | 0.00 | — |
| E07_pasaje_angosto | EJE-01 | 299.82 | 299.70 | +0.04 % | 0.00 | 0.00 | — |
| E08_curva_cerrada | EJE-01 | 2433.17 | 2432.86 | +0.01 % | 48.85 | 48.84 | +0.03 % |

Estos volúmenes de Civil 3D están en `pruebas/referencias_civil3d.json`, y `pruebas/test_escenarios.py`
exige ±1 % (o ±0.5 m³) cada vez que se cambia el código.

## Esquinas curvas (plano 24.14 de veredas, rampas y martillos)

Del expediente: arcos de sardinel R = 3.00 m (capas `C-ROAD-MARK` y `_Martillos`), martillo en
cemento pulido rojo, rampas de 3.00 m (12 % + descanso + 12 %) en cada brazo y el badén de arco a
arco. La app arma cada esquina como una pieza (esquinas.py) y corta el sardinel, la cuneta y la
vereda rectos de cada calle en los puntos de tangencia.

| # | Falla encontrada al armarlas | Corrección |
|---|---|---|
| 18 | Dos tangencias a 0.03 mm caían en la misma sección y una esquina quedaba sin sardinel. | Tangencias al mm; la sección de tangencia tiene prioridad sobre las de transición. |
| 19 | En un cruce oblicuo la zona sin vereda vieja (simétrica) tapaba la tangencia del lado agudo. | La zona va de tangencia a tangencia y reemplaza a la anterior. |
| 20 | Eje con vértice a 3 m del cruce (Nuñoa, Jr. Tupac Yupanqui): el arco no empalmaba y el pavimento de esquina se montaba sobre el sardinel (hasta 32 cm de error en Civil 3D). | El centro se recalcula con la dirección de cada calle en su tangencia. |
| 21 | Astillas de triángulo al recortar el badén dentro de la esquina. | Se quitan puntos repetidos y triángulos de menos de 1 cm². |

Civil 3D (superficie de volumen TN − ESQUINAS SUBRASANTE) frente a la app:

| Proyecto | Esquinas | Corte app | Corte Civil 3D | Relleno app | Relleno Civil 3D |
|---|---|---|---|---|---|
| datos_ejemplo | 4 | 24.06 | 24.06 | 0 | 0 |
| E03 cruce oblicuo | 8 | 104.72 | 104.72 | 0 | 0 |
| E06 malla 3×3 | 36 | 314.40 | 314.40 | 0 | 0 |
| Nuñoa | 46 | 76.28 | 75.73 | 9.38 | 9.39 |

## Lo que sigue pendiente

- En Nuñoa los martillos del expediente miden ~7 m² por esquina (323 m² en total) y los de la app ~4.8 m²:
  el martillo del plano incluye parte de la vereda de los brazos. La app la cuenta como vereda de la calle.
- Curvas horizontales y verticales reales (hoy una curva se dibuja con cuerdas, como en E08).
- Corredor nativo de Civil 3D (ensamblajes y subensamblajes). El complemento actual crea
  alineamientos, perfiles y superficies, pero no el corredor.
