# Diseño de la aplicación (Paso 2)

Nombre de trabajo: **Corredor Simple** — un "corridor" de Civil 3D reducido a lo
que una obra de pistas y veredas necesita.

## 1. Idea central

```
EJE EN PLANTA  +  PERFIL DE RASANTE  +  SECCIÓN TÍPICA   ──►  todos los puntos, capas, tablas y metrados
 (dónde va)        (a qué altura)        (qué forma tiene)
```

En cada progresiva la app hace siempre lo mismo:

1. Busca **dónde** está el eje (Este, Norte) y hacia dónde apunta (azimut).
2. Calcula la **cota de rasante** en el eje.
3. "Pega" la sección típica: cada punto de la sección tiene un **desplazamiento**
   (offset, metros a la izquierda/derecha del eje) y un **desnivel** respecto
   a la rasante. Se suman y salen coordenadas y cota de cada punto.
4. Baja las capas restando espesores.
5. Compara con el terreno → corte y relleno.

## 2. Tecnología recomendada

| Necesidad | Elección | Por qué |
|---|---|---|
| Lenguaje | **Python 3.12** | simple de leer y corregir |
| Interfaz | **Tkinter** (viene con Python) | sin instalaciones extra, funciona en Windows |
| Tablas de cálculo | `csv` + `openpyxl` (Excel) | entrada/salida que ya usas en campo |
| Gráficos 2D | `matplotlib` embebido en Tkinter | sección y perfil para revisar |
| Modelo 3D | `matplotlib` 3D embebido (girar con el mouse, rueda para acercar) | sin librerías pesadas; si se queda corto con 30 cuadras, paso a `pyvista` |
| Excel / PDF | `openpyxl` / `matplotlib` (PdfPages) | informe de tierras exportable |
| DXF para Civil 3D | `ezdxf` | eje, secciones y puntos 3D en capas separadas |
| Ejecutable | **PyInstaller** → `CorredorSimple.exe` | un solo archivo para Windows |
| Pruebas | `pytest` con los datos de ejemplo | cada cálculo verificado contra la mano |

Alternativa si prefieres trabajar en Excel: el mismo motor puede leer y escribir
un libro `.xlsx` con una hoja por cada dato de entrada. Recomiendo empezar con
CSV + interfaz y añadir Excel en el Paso 5.

## 3. Estructura del programa (módulos)

```
corredor/
  datos.py        lectura y validación de CSV  (mensajes claros: "fila 7, cota vacía")
  alineamiento.py eje en planta: progresiva ⇄ coordenadas, offset de un punto
  perfil.py       cota de rasante en cualquier progresiva, control de pendientes
  seccion.py      plantilla de la sección: lista de puntos (código, offset, desnivel)
  capas.py        cotas de cada capa hacia abajo
  fachadas.py     ancho de vereda disponible, choques, umbrales de puertas
  terreno.py      superficie TIN del levantamiento (triángulos) y cota en un punto
  movimiento.py   áreas de corte/relleno y volúmenes por área media
  replanteo.py    tablas de campo, lectura de mira, CSV para estación total y Civil 3D
  graficos.py     sección transversal y perfil longitudinal
  modelo3d.py     superficies 3D: calzada, capas, cuneta, vereda, fachadas
  exportar.py     CSV estación total, CSV Civil 3D (PNEZD), DXF, Excel, PDF
  app.py          ventana única con pestañas (ver sección 5)
config/
  normativa.csv   todos los límites normativos, editables, con su fuente
pruebas/
  test_*.py       verificación con los datos de ejemplo
```

## 4. Fórmulas en lenguaje simple (con ejemplo numérico)

Datos del ejemplo: EJE-01 empieza en E = 390100.000, N = 8250300.000 con azimut 80°.
sen 80° = 0.98481, cos 80° = 0.17365.

### 4.1 Coordenadas de un punto de la sección
"Avanzo por el eje la progresiva *p*, y luego me corro *o* metros de costado."

- E = E₀ + p·sen(Az) + o·cos(Az)
- N = N₀ + p·cos(Az) − o·sen(Az)   (o positivo = derecha)

Ejemplo, borde derecho de calzada en 0+050 (o = +3.60):
E = 390100 + 50×0.98481 + 3.60×0.17365 = **390149.866**,
N = 8250300 + 50×0.17365 − 3.60×0.98481 = **8250305.137**.

Con varios vértices, la app ubica primero en qué tramo recto cae la progresiva
y usa el azimut de ese tramo.

### 4.2 Cota de rasante
"Cota al inicio del tramo + pendiente × distancia recorrida en el tramo."

Cota(p) = Cota_inicio + (pendiente % / 100) × (p − p_inicio)

Ejemplo EJE-01 0+200 (segundo tramo, empieza en 0+120 con 3822.300, −0.8 %):
3822.300 − 0.008 × 80 = **3821.660**.

Control: si |pendiente| > máx. o < mín. configurados → aviso. Si la cota de inicio
de un tramo no coincide con el final del anterior (± 1 mm) → aviso de "escalón".

### 4.3 Puntos de la sección (desde el eje hacia la derecha; la izquierda es simétrica)

| Código | Offset (m) | Cota | Ejemplo en 0+050 (rasante 3821.250) |
|---|---|---|---|
| EJE | 0.00 | rasante | 3821.250 |
| BC (borde calzada) | 3.60 | rasante − 2 % × 3.60 | 3821.250 − 0.072 = 3821.178 |
| FC (fondo cuneta) | 3.80 | BC − 0.10 | 3821.078 |
| PS (pie sardinel) | 4.00 | BC | 3821.178 |
| CS (cabeza sardinel) | 4.00 | BC + 0.15 | 3821.328 |
| BV (borde vereda, tras sardinel) | 4.15 | CS | 3821.328 |
| PF (pie fachada) | 5.65 | BV + 2 % × 1.50 | 3821.358 |

La **cuneta es solo geométrica** (ancho × profundidad, editable por tramo) para que
se vea en el 3D y en las secciones; no hay cálculo hidráulico. El bombeo y los
anchos se leen de la fila de cada calle en `calles.csv`.

### 4.4 Capas hacia abajo
"Cada capa empieza donde termina la de arriba." Mismas formas, paralelas a la rasante.

Ejemplo eje 0+050: losa superior 3821.250 → base superior 3821.250 − 0.16 = **3821.090**
→ subbase superior 3821.090 − 0.15 = **3820.940** → mejoramiento superior 3820.940 − 0.15 =
**3820.790** → fondo (subrasante de corte) 3820.790 − 0.20 = **3820.590**.

### 4.5 Lectura teórica de mira
AI (altura instrumental) = cota BM + lectura atrás. Lectura = AI − cota de diseño.

Ejemplo: BM-01 = 3821.321, lectura atrás 1.425 → AI = **3822.746**.
Eje 0+050 losa: 3822.746 − 3821.250 = **1.496**; base: 3822.746 − 3821.090 = **1.656**.
La app da la tabla; tú solo ingresas la lectura atrás del día.

### 4.6 Terreno existente
Con los puntos del levantamiento se forma una red de triángulos (TIN, como la
superficie de Civil 3D). La cota del terreno en cualquier punto se interpola en
el triángulo que lo contiene (promedio ponderado por distancias de los 3 vértices).

### 4.7 Área de corte y relleno por sección
Se dibujan dos líneas en la sección: terreno y subrasante (fondo de la última
capa). Donde el terreno está **encima** → corte; **debajo** → relleno. El área se
calcula sumando trapecios pequeños: área = ancho × (altura izquierda + altura derecha) / 2.

Ejemplo de un trapecio: ancho 0.50 m, alturas 0.85 y 0.90 → 0.50 × 1.75 / 2 = **0.438 m²**.

### 4.8 Volumen por área media
V = (A₁ + A₂) / 2 × distancia.  Ejemplo: A₁ = 9.80 m², A₂ = 10.40 m², d = 10 m →
(9.80 + 10.40)/2 × 10 = **101.0 m³**. Se suma por calle y total.
Volumen neto = corte − relleno.

### 4.8b Volumen de material por capa
Como los espesores son uniformes: área de la capa en la sección = ancho de la capa × espesor,
y volumen = área media × distancia (igual que 4.8).
Ejemplo losa: 7.20 m × 0.16 m = 1.152 m² por sección → en 10 m: **11.52 m³**.
Base: 7.20 × 0.15 = 1.080 m² → **10.80 m³** en 10 m. (Si la base se extiende bajo la
cuneta o el sardinel, el ancho cambia — ver pregunta 4.)

### 4.9 Vereda contra fachadas
En cada progresiva se traza una línea perpendicular al eje y se busca dónde
corta la polilínea de fachada. Ancho disponible = offset de la fachada − offset del
borde interior de vereda.
Ejemplo EJE-01 IZQ 0+050: fachada a 5.30 → 5.30 − 4.15 = **1.15 m** < 1.50 → aviso / recorte.

Umbral: diferencia = cota umbral − cota de vereda en fachada. Negativa → "enterrada".
(Ejemplo resuelto PU-02 en `datos_ejemplo/README.md`: −0.080 m.)

## 5. Interfaz: una sola ventana, 6 pestañas

| Pestaña | Qué tiene |
|---|---|
| **1. Levantamiento** | cargar `terreno.csv`, `fachadas.csv`, `umbrales.csv`, `bm.csv`; vista en planta de los puntos |
| **2. Calles** | tabla pequeña, una fila por calle: nombre · bombeo % · ancho calzada · ancho vereda. Al seleccionar una calle: sus vértices del eje y sus tramos de perfil |
| **3. Capas** | lista de capas de calzada y de vereda (nombre, espesor cm), botones agregar/quitar; cuneta básica y sardinel |
| **4. Modelo 3D** | vista que se gira y acerca: calzada, capas, cuneta, vereda, fachadas; también perfil longitudinal y sección en una progresiva |
| **5. Movimiento de tierras** | tabla por calle (área corte/relleno por sección, volúmenes de corte, relleno, neto, material por capa) y resumen total |
| **6. Exportar** | botones: tabla del eje, puntos de replanteo, CSV estación total, CSV Civil 3D, DXF, Excel, PDF, reporte de avisos |

Nada más; sin funciones que no hayas pedido.

## 5b. Salidas

1. **Tabla del eje** (una por calle): progresiva, Este, Norte, cota de rasante — cada 10 m
   (configurable) + cambios de pendiente + vértices. Se copia o exporta a CSV
   `progresiva,Este,Norte,cota` lista para la estación total.
2. **Puntos de replanteo**: nombre (con progresiva), progresiva, Este, Norte, cota de rasante y
   la cota de diseño de cada punto de la sección (eje, bordes de calzada, cuneta, sardinel,
   borde de vereda, pie de fachada).
3. **Tablas por capa**: progresiva, punto, Este, Norte, cota de diseño, lectura teórica de mira.
4. **CSV estación total** (PENZD): `nombre, Este, Norte, cota, código`, nombre tipo
   `E1-0+050-BCD` (eje, progresiva, punto, lado). Configurable según tu equipo.
5. **CSV Civil 3D**: PNEZD separado por comas (formato "PNEZD (comma delimited)"),
   numeración correlativa y descripción con la progresiva.
6. **DXF**: eje (polilínea), secciones (líneas 3D por capa), puntos 3D, fachadas; una capa DXF por elemento.
7. **Informe de movimiento de tierras**: en pantalla, Excel y PDF.
8. **Reporte de avisos**: pendientes fuera de rango, veredas recortadas, puertas enterradas, cocheras.
9. **Gráficos**: perfil longitudinal (rasante, terreno en eje, capas) y sección transversal típica.

## 5c. Cómo comparar con Civil 3D (lo detallo con archivos en el Paso 4)

1. Importar `terreno.csv` como puntos → crear superficie **TN**.
2. Importar el DXF → el eje como alineamiento; crear el perfil con los tramos de `perfil.csv`.
3. Armar el ensamblaje con la sección típica y el corredor; superficie **Subrasante**.
4. Comparar en 3 progresivas (p. ej. EJE-01 0+050, 0+120, EJE-02 0+180):
   cotas de eje, bordes, sardinel y fondo de cada capa; coordenadas Este/Norte.
5. Comparar áreas de corte/relleno en esas secciones y el volumen total (Volúmenes de material, área media).
6. **Tolerancias propuestas** (a confirmar contigo): coordenadas y cotas ±0.001–0.002 m
   (redondeo); áreas por sección ±1 %; volúmenes totales ±2 % (la diferencia viene sobre
   todo de cómo cada programa triangula el terreno y de la frecuencia de secciones).

## 6. Normativa (todo como parámetro editable en `config/normativa.csv`)

No fijo ningún valor normativo en el código. Las normas aplicables que identifico son:

- **RNE CE.010 Pavimentos Urbanos** — espesores, materiales, pendientes de pavimento.
- **RNE GH.020 Componentes de Diseño Urbano** — secciones de vías, anchos de vereda.
- **RNE A.120 Accesibilidad Universal** — rampas en esquinas y cocheras, pendiente transversal de vereda.
- **OS.060 Drenaje Pluvial Urbano** — cunetas y pendientes mínimas para drenaje.
- **Manual de Carreteras: Diseño Geométrico DG-2018 (MTC)** — referencia solo si no hay valor urbano.

**Honestamente:** no tengo certeza del número de artículo ni del valor exacto vigente
para la pendiente longitudinal máxima/mínima, el bombeo, el ancho mínimo de vereda
ni las pendientes de rampa. Por eso en los datos de ejemplo aparecen como
"PARÁMETRO A CONFIRMAR". Antes del Paso 3 te propongo una tabla con valor, norma
y artículo para que la cotejes con tu copia del RNE vigente (y con las
modificatorias), y solo los que confirmes quedan marcados como "verificado".

## 7. Plan de construcción

| Paso | Entrega | Prueba |
|---|---|---|
| 3a | `datos.py`, `alineamiento.py`, `perfil.py` | coordenadas y cotas del ejemplo 4.1 y 4.2 |
| 3b | `seccion.py`, `capas.py` | tabla 4.3 y 4.4 |
| 3c | `replanteo.py` (tablas y CSV) | lectura 4.5, CSV abre en Civil 3D |
| 3d | `terreno.py`, `movimiento.py` | volumen de EJE-01 y relleno en EJE-02 0+180 |
| 3e | `fachadas.py` | detecta los 3 recortes y las 2 puertas enterradas |
| 3f | `graficos.py`, `modelo3d.py` | perfil, sección y 3D del ejemplo |
| 3g | `exportar.py`, `app.py` | ventana completa; CSV, DXF, Excel, PDF que abren sin error |
| 4 | verificación manual de 2–3 puntos | |
| 5 | validación, mensajes, Excel, `.exe` | |

## 8. Preguntas antes de programar

1. **Cuneta básica**: para dibujarla simple propongo forma **triangular** (fondo en V al centro,
   10 cm bajo el borde). ¿Te sirve, o la prefieres rectangular? ¿Sus 40 cm van **fuera** de los
   7.20 m de calzada (como supuse) o dentro?
2. **Sardinel**: los 15 cm, ¿se miden desde el **borde de calzada** o desde el
   **fondo de cuneta** hasta la vereda terminada? ¿El sardinel es parte de los 1.50 m de
   vereda o adicional (yo supuse adicional, 0.15 m)?
3. **Subrasante para corte/relleno**: ¿la comparación con el terreno se hace contra el
   **fondo del mejoramiento** (−0.66 m) o contra el fondo de la subbase, tratando el
   mejoramiento aparte? ¿Las capas siguen el bombeo (paralelas) o tienen fondo horizontal?
4. **Bajo cuneta y vereda**: ¿qué capas van debajo de la cuneta y del sardinel?
   ¿La excavación se considera hasta qué ancho (fachada a fachada)? Esto cambia el
   volumen por capa.
5. **Recorte de vereda**: cuando la fachada invade, ¿prefieres que la app **solo avise**
   o que **recorte** el ancho (y la pendiente transversal se mantenga en 2 %)?
6. **Puntos de replanteo**: ¿qué puntos marcas realmente en campo (eje, bordes, cuneta,
   sardinel, fachada) y cada cuánto? ¿Qué formato de nombre/código acepta tu estación
   total (marca y modelo) y cuántos caracteres admite el nombre?
7. **Sistema de coordenadas**: ¿trabajas en UTM WGS84 (zona 18S/19S) o en coordenadas locales?
8. **Progresivas**: ¿formato `0+050.00`? ¿Las secciones además deben caer en cada puerta?
9. **Cochera**: ¿qué solución aplicas — rebaje de sardinel con rampa dentro de la vereda?
   ¿Con qué longitud/pendiente?
10. **Intersección (para después)**: ¿qué calle manda en el cruce (la de mayor jerarquía
    conserva su bombeo) y qué radio de esquina/chaflán usa tu expediente?
11. **Entrada**: ¿prefieres cargar los datos como **CSV**, como un **Excel** con hojas,
    o escribiéndolos en tablas dentro de la app?
12. **Tolerancias con Civil 3D**: ¿te parecen bien las de la sección 5c?
13. **Versión de Civil 3D** que usas (para el DXF: guardo en formato R2013 salvo que me digas otro).
