# Datos de ejemplo (Paso 1)

Datos **ficticios pero realistas** para probar la app: 4 cuadras de una malla en
el altiplano (cotas ~3820 m), coordenadas UTM WGS84 zona 19S. Se regeneran
siempre iguales con:

```bash
python herramientas/generar_ejemplo.py
```

## Escenario

```
                 N
                 ^        EJE-02 "Jr. Las Flores"  (0+000 al sur, 0+200 al norte)
                 |        pendiente única +1.2 %
        cuadra 3 | cuadra 4
                 |
 EJE-01 ---------+-------------------->  "Jr. Los Andes" (0+000 al oeste, 0+250 al este)
  0+000      0+130 (cruce = EJE-02 0+100)       quiebre de pendiente en 0+120
        cuadra 1 | cuadra 2                     +1.5 % hasta 0+120, luego -0.8 %
                 |
```

| Elemento | Valor de ejemplo |
|---|---|
| EJE-01 | recto, 250 m, azimut 80°, cruce en 0+130 |
| EJE-02 | recto, 200 m, azimut 350° (perpendicular), cruce en 0+100 |
| Rasante EJE-01 | 3820.500 en 0+000, +1.5 % → 3822.300 en 0+120, −0.8 % → 3821.260 en 0+250 |
| Rasante EJE-02 | 3821.020 en 0+000, +1.2 % → 3823.420 en 0+200 (pasa por 3822.220 en el cruce, igual que EJE-01) |
| Calzada | 7.20 m, 2 carriles, bombeo 2 % |
| Cuneta | 0.40 × 0.10 m (en EJE-02 lado DER 0+150–0+200: 0.50 × 0.15 m) |
| Sardinel | 0.15 m de ancho, 0.15 m de desnivel |
| Vereda | 1.50 m, 2 % hacia la calzada |
| Fachada nominal | a 5.65 m del eje (3.60 + 0.40 + 0.15 + 1.50) |

## Casos de prueba incluidos a propósito

| Caso | Dónde | Qué debe detectar la app |
|---|---|---|
| Muro adelantado | EJE-01 IZQ 0+040–0+060, a 5.30 m | vereda disponible 1.15 m (< 1.50) |
| Fachada adelantada | EJE-01 DER 0+200–0+215, a 5.45 m | vereda disponible 1.30 m |
| Escalón invadiendo | EJE-02 DER 0+020–0+032, a 5.05 m | vereda disponible 0.90 m (< mínimo) |
| Puerta enterrada | PU-02 (EJE-01 IZQ 0+085) | umbral 8 cm **debajo** de la vereda |
| Puerta enterrada | PU-04 (EJE-02 DER 0+140) | umbral 3 cm debajo |
| Puertas correctas | PU-01, PU-03 | umbral 6 y 12 cm arriba |
| Cochera | CO-01 (EJE-01 DER 0+170, 3.00 m) | umbral +2 cm; requiere rebaje de sardinel |
| Quiebre de pendiente | EJE-01 0+120 | sección obligatoria en 0+120 |
| Zona de relleno | EJE-02 0+165–0+185 (hondonada) | terreno bajo la subrasante → relleno |
| Resto | — | corte de ~0.8–1.1 m bajo terreno |

## Archivos

| Archivo | Contenido |
|---|---|
| `ejes.csv` | vértices del eje en planta (Este, Norte) y progresiva inicial |
| `perfil.csv` | tramos de rasante: progresiva inicio, cota inicio, pendiente %, progresiva fin |
| `calles.csv` | una fila por calle: nombre, bombeo %, ancho de calzada, ancho de vereda |
| `seccion_tipica.csv` | lo común a todas las calles: cuneta básica, sardinel, pendiente de vereda, intervalo y límites normativos (editables) |
| `capas.csv` | capas de calzada y de vereda, de arriba hacia abajo, espesor en cm |
| `cunetas_por_tramo.csv` | cuneta básica (ancho × profundidad) por defecto y excepciones por tramo |
| `fachadas.csv` | polilíneas de límite de propiedad por eje y lado (FACHADA / MURO) |
| `umbrales.csv` | puertas y cocheras con su cota de umbral levantada |
| `terreno.csv` | 192 puntos del levantamiento (PENZD) cada 15 m, desde 3 m antes hasta 3 m después de cada calle: EJ eje, BC borde camino, PF pie de fachada, TN terreno |
| `bm.csv` | 3 BMs con cota |

**Convención de lados:** IZQ / DER mirando en el sentido de avance de las progresivas.
El signo del desplazamiento (offset) es negativo a la izquierda y positivo a la derecha.

**Suposición usada para generar los umbrales** (ver pregunta 2 en `docs/DISENO.md`):
la vereda terminada junto al sardinel está 0.15 m sobre el borde de calzada, y
sube 2 % hacia la fachada. Ejemplo PU-02 (EJE-01 0+085):

- rasante en eje = 3820.500 + 0.015 × 85 = **3821.775**
- borde de calzada = 3821.775 − 0.02 × 3.60 = **3821.703**
- vereda en sardinel = 3821.703 + 0.15 = **3821.853**
- vereda en fachada = 3821.853 + 0.02 × 1.50 = **3821.883**
- umbral levantado = **3821.803** → queda 0.080 m **debajo** → aviso "puerta enterrada".
