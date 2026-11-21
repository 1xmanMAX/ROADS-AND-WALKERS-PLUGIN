# Codificación de campo (estación total)

Cada punto que se toma lleva un **código** en la descripción. Con ese código la app sabe qué es el
punto y lo usa sola: el terreno, las fachadas, las puertas, los BMs, y revisa postes, tapas y empalmes
contra el diseño. No hace falta llenar `fachadas.csv`, `umbrales.csv` ni `bm.csv` a mano.

La lista para cargar en la libreta de la estación está en [`codigos_campo.csv`](codigos_campo.csv).
El escenario `escenarios/E09_codificado` es un levantamiento completo hecho con estos códigos.

## 1. Cómo se escribe la descripción

```
CODIGO[n]  [parámetros]  [comando]  [/ nota]
```

| Parte | Qué es | Ejemplo |
|---|---|---|
| `CODIGO` | 2 o 3 letras de la tabla | `FAC` |
| `n` | número de **línea**, pegado al código (solo en códigos de línea) | `FAC3` = fachada número 3 |
| parámetros | números en metros (ancho de puerta, diámetro de poste) | `PTA 0.90`, `POS 0.25` |
| comando | `I` inicia una línea nueva con ese número · `C` cierra la línea con su primer punto · `F` la termina | `FAC3 C` |
| `/ nota` | texto libre, la app no lo interpreta (salvo en `BM`, donde es el nombre) | `POS 0.25 / alumbrado`, `BM / BM-01` |

Reglas de las **líneas** (FAC, PEX, CAB, ...):

* Los puntos con el mismo código y número se unen **en el orden en que se toman**.
* Una línea por cuadra y por lado: `FAC1` la fachada izquierda de la cuadra 1, `FAC2` la derecha, etc.
  Si se repite el número después, se empieza con `I` (`FAC1 I`).
* Tomar todos los quiebres (esquinas, ochavos, retiros) y como mucho cada 10 m en tramos rectos.
* En una manzana completa se puede ir alrededor y cerrar con `C`.

## 2. Códigos

### Control
| Código | Qué es | Cómo tomarlo | En la app |
|---|---|---|---|
| `BM` | Banco de nivel | Prisma a plomo sobre la marca del hito. Nombre en la nota: `BM / BM-01` | Va a la tabla de BMs (lectura de mira) |
| `EST` | Estación | Lo registra el equipo | Se ignora |
| `REF` | Referencia / visado | — | Se ignora |
| `PC` | Control GNSS | — | Se ignora |

### Terreno (va al TIN)
| Código | Qué es | Cómo tomarlo |
|---|---|---|
| `TN` | Terreno natural | Prisma apoyado en el suelo. Grilla de 5–10 m y en todo cambio de pendiente. En calles sin pavimentar: secciones cada 10–20 m (eje, bordes, pie de fachada) |
| `TNLn` | Quiebre del terreno (línea) | Lomo, borde de plataforma, cambio brusco |
| `CABn` / `PIEn` | Cabeza / pie de talud (líneas) | Cada 5 m y en los quiebres |
| `ZJn` | Fondo de zanja, acequia o canal | Por el eje del cauce |
| `BORn` | Borde de zanja, canal o río | Cada margen con su número |

### Vía existente: a lo que tiene que llegar el diseño
| Código | Qué es | Cómo tomarlo | En la app |
|---|---|---|---|
| `EMP` | **Punto de empalme** | Donde la obra se une a lo que se queda (pavimento, sardinel o vereda existentes): al menos eje y los dos bordes en cada empalme | Compara con la cota de diseño; aviso si difiere más de 2 cm |
| `PEXn` | Borde de pavimento existente (línea) | Cada 5 m y donde empieza/termina la obra | Igual que `EMP` en cada punto |
| `EJXn` | Eje de vía existente | Cada 10 m | Terreno |
| `SDXn` | Cabeza de sardinel existente | Arista superior | No va al terreno (escalón) |
| `CNXn` | Fondo de cuneta existente | Junto al sardinel | Terreno |
| `VEXn` | Borde de vereda existente | Arista exterior | Terreno |
| `AFIn` | Borde de afirmado / trocha | Borde de la vía sin pavimentar | Terreno |

### Edificaciones y límites
| Código | Qué es | Cómo tomarlo | En la app |
|---|---|---|---|
| `FACn` | **Pie de fachada** (línea) | Al **pie del muro**, a nivel del suelo o de la vereda actual. En cada esquina, ochavo y quiebre, y cada 10 m | Fachada: límite de la vereda (recorte y avisos de ancho) |
| `MURn` | Muro o cerco | Igual que FAC | Fachada tipo MURO |
| `LPn` | Lindero sin construir | En los hitos o estacas | Fachada tipo LÍMITE |
| `PTA a` | **Puerta** (a = ancho, m) | Al **centro** de la puerta, prisma **sobre el umbral** (grada o piso de la entrada) | Verifica que la vereda nueva no tape la puerta |
| `COC a` | Cochera / portón | Al centro, sobre el piso de la entrada | Igual + aviso de rebaje de sardinel |
| `GRA` | Grada o escalón que sale a la vereda | Arista exterior del escalón | Aviso |

### Servicios y obstáculos
| Código | Qué es | Cómo tomarlo | En la app |
|---|---|---|---|
| `POS d` | **Poste** (d = diámetro, m) | Prisma **pegado al poste, en la cara que mira al eje de la calle, al pie** (nivel del suelo). Así el punto es lo más cercano a la pista y la app pone el centro medio diámetro detrás | ERROR si cae en la calzada, la cuneta o el sardinel; paso libre en la vereda (mínimo 0.90 m) |
| `ARB d` | Árbol (d = tronco) | Igual que el poste | Igual |
| `GRI` | Grifo contra incendio | Al pie, al centro | Igual |
| `BZD` | **Tapa de buzón** de desagüe | Al **centro de la tapa, sobre la tapa** | Cuánto subir o bajar la tapa para la rasante nueva |
| `CAJ` / `VAL` / `MED` | Caja de registro / válvula / medidor | Al centro, sobre la tapa | Igual |
| `SUM` | Sumidero / rejilla | Al centro, sobre la rejilla | Igual |

## 3. Por qué cada punto se toma así

* **Poste en la cara hacia el eje**: es la parte que estorba. Con el diámetro, la app sabe dónde está
  el centro y cuánto paso libre queda entre el poste y la fachada. Si se toma del costado o de atrás,
  el poste "se corre" y la app puede decir que no estorba cuando sí.
* **Puerta sobre el umbral, al centro**: lo que importa es la cota del piso de la entrada contra la de
  la vereda nueva frente a ella. Tomarla en la jamba o en el suelo de afuera da otra cota.
* **Fachada al pie**: es la línea donde termina la vereda. Tomarla en el alero o en la cara de una
  columna corre la vereda.
* **Tapa al centro y encima**: es la cota que hay que dejar a ras con el pavimento nuevo.
* **Empalme**: si el diseño no llega a la cota de lo que se queda, se nota en obra como un escalón.
  Con tres puntos (eje y bordes) la app revisa también el bombeo.

## 4. Códigos propios: `codigos_alias.csv`

Si la brigada ya usa otros códigos, se pone en la carpeta del proyecto un `codigos_alias.csv`:

```
alias,codigo
PF,FAC
PU,PTA
PT,POS
BZ,BZD
TER,TN
```

La app traduce antes de interpretar (también con número: `PF2` -> `FAC2`). Los códigos que no
reconoce los usa como terreno, como siempre, y avisa cuáles son para que se agreguen al alias.

## 5. Qué sale en los resultados

* **Avisos**: OBSTACULO (postes, árboles), TAPA (subir/bajar), EMPALME, PUERTA/COCHERA y CODIGOS.
* **Excel**, hoja *Puntos codificados*: cada poste, tapa y empalme con su eje, progresiva, offset,
  cota de campo, cota de diseño, diferencia y qué hacer.
* **DXF**: capas `C3D-COD-<código>` con las líneas (fachadas, bordes existentes...) y los puntos
  (postes con su diámetro, tapas, puertas).
