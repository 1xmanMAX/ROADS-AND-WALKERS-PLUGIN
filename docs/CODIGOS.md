# Códigos de campo (lista de etiquetas)

La app reconoce cada punto del levantamiento por su **código**: la primera palabra del campo
*código* o *descripción* de la estación total. Lo que venga después es una nota libre. Por ejemplo,
`CA1 casa azul` se lee como código `CA1` con la nota "casa azul".

Formato del archivo: `punto, este, norte, cota, codigo`, separado por comas o por punto y coma, con
o sin cabecera. Así es como exporta la mayoría de estaciones (PENZD).

La lista se puede cambiar en la pestaña **1 · Levantamiento**: agregar códigos nuevos, cambiar el
color, el tipo o qué se revisa. Se guarda en `codigos.csv` dentro del proyecto.

## Terreno

| Código | Qué es | Cómo tomarlo |
|---|---|---|
| **TN** | Terreno natural | Puntos sueltos cada 10 a 20 m, también fuera de la calle. |
| **EJ** | Eje del camino actual | Centro del camino existente. |
| **BC** | Borde del camino actual | Bordes del camino existente. |
| **VE** | Vereda existente | Sobre la vereda que ya existe. |

## Líneas (se unen en orden de número de punto)

| Código | Qué es | Cómo tomarlo |
|---|---|---|
| **CA**, CA1, CA2… | Casa o fachada | Al pie del muro, en cada esquina y en cada quiebre de la fachada. Usa un número por manzana (CA1, CA2…). |
| **MU**, MU1… | Muro o cerco | Igual que CA. |
| **LP**, LP1… | Límite de lote sin construir | Esquinas del lote vacío. |

- Los puntos con el **mismo código** (incluido el número) forman una línea, en el orden en que
  los tomaste.
- La línea se corta si dos puntos seguidos están a más de 30 m (parámetro *separación máx. línea*).
- La línea también se corta si cruza el eje de una calle. Aun así, conviene usar CA1, CA2… para
  separar las manzanas.
- Los puntos de línea también sirven como terreno (cota al pie del muro).
- La app mide el **ancho de vereda disponible** desde el sardinel hasta la línea más cercana.

## Puertas y cocheras

| Código | Qué es | Cómo tomarlo |
|---|---|---|
| **PU** | Puerta | **Un punto** al centro del umbral. La cota del punto es la cota del umbral. |
| **COI** | Cochera, inicio del portón | **Primer punto**, en un extremo del portón, a la altura del umbral. |
| **COF** | Cochera, fin del portón | **Segundo punto**, en el otro extremo. Tómalo justo después del COI. |

- Si hay varias cocheras seguidas puedes numerarlas: COI1/COF1, COI2/COF2.
- La app une cada COI con su COF, calcula el ancho del portón y revisa:
  - si el umbral queda **debajo de la vereda** (puerta enterrada);
  - cuánto hay que **rebajar el sardinel**;
  - la **pendiente de la rampa**.

## Elementos

| Código | Qué es | Qué revisa la app |
|---|---|---|
| **BZ** | Buzón (centro de la tapa) | Nivelar: cuánto subir o bajar la tapa hasta la cota del diseño. |
| **CAG** | Caja de agua o medidor | Nivelar. |
| **CDE** | Caja de registro de desagüe | Nivelar. |
| **CLZ** | Caja de luz o telefonía | Nivelar. |
| **PO** | Poste (al pie) | Obstáculo: no puede quedar en calzada, cuneta ni sardinel; en vereda revisa el paso libre. |
| **AR** | Árbol (al pie) | Obstáculo. |
| **GR** | Grifo contra incendio | Obstáculo. |
| **SEN** | Señal o letrero | Obstáculo. |

## BM

| Código | Qué es | Cómo tomarlo |
|---|---|---|
| **BM1**, **BM2**… | Punto de control | Sobre el hito. La cota del punto es la cota del BM. |

- Si escribes solo `BM`, la app le asigna el siguiente número libre.
- Los BM salen numerados (BM-01, BM-02…) con su ubicación respecto a la calle: progresiva, lado y
  distancia al eje. Así es fácil encontrarlos después en obra.

## Códigos que no están en la lista

Se toman como **terreno** y aparecen en rojo en la tabla de puntos, con un aviso. Puedes agregarlos
a la lista con *Agregar código* y pulsar *Reinterpretar códigos*.
