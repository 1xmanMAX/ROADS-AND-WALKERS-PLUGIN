# Proyecto de ejemplo

Son 4 cuadras de una malla en el altiplano (cotas alrededor de 3820 m), en UTM WGS84 19S. Los datos son
ficticios pero realistas. Se regeneran con:

```bash
python herramientas/generar_ejemplo.py
```

| Archivo | Contenido |
|---|---|
| `levantamiento.csv` | **Levantamiento codificado**: 292 puntos con códigos de campo (ver `docs/CODIGOS.md`) |
| `codigos.csv` | Lista de etiquetas: qué significa cada código |
| `calles.csv` | Una fila por calle: nombre, bombeo %, ancho de calzada, ancho de vereda |
| `ejes.csv` | Vértices del eje de cada calle (Este, Norte) y progresiva inicial |
| `perfil.csv` | Tramos de rasante: desde, cota inicial, pendiente %, hasta |
| `capas.csv` | Capas de calzada y vereda (cm) |
| `seccion_tipica.csv` | Parámetros de la sección y de revisión |
| `cunetas_por_tramo.csv` | Excepciones de cuneta: en EJE-02 lado derecho, de 0+150 a 0+200, la cuneta es de 0.50 × 0.15 m |

## Escenario

- **EJE-01 Jr. Los Andes:** 250 m, sube +1.5 % hasta 0+120 y luego baja −0.8 %.
- **EJE-02 Jr. Las Flores:** 200 m, sube +1.2 %. Cruza al EJE-01 en la 0+130 del EJE-01, que es su 0+100.
- **Calles:** calzada de 7.20 m con bombeo de 2 %, cuneta de 0.40 × 0.10 m, sardinel de 0.15 m y vereda de 1.50 m.

## Casos de prueba incluidos a propósito

| Caso | Dónde | Resultado esperado |
|---|---|---|
| Muro adelantado (MU1) | EJE-01 izq. 0+040 a 0+060 | vereda de 1.15 m, ERROR (menor que el mínimo de 1.20 m) |
| Escalón invadiendo (CA) | EJE-02 der. 0+020 a 0+032 | vereda de 0.90 m, ERROR |
| Fachada adelantada | EJE-01 der. 0+200 a 0+215 | vereda de 1.30 m, AVISO |
| Lote vacío (LP1) | EJE-02 izq. 0+150 a 0+190 | límite de propiedad |
| Puertas enterradas (PU) | EJE-01 0+085 y EJE-02 0+140 | −0.080 y −0.030 m |
| Cochera enterrada (COI/COF) | EJE-02 izq. 0+120 a 0+123 | −0.045 m |
| Cochera correcta | EJE-01 der. 0+168.5 a 0+171.5 | +0.025 m, con rebaje de sardinel y rampa de 10.7 % |
| Buzones (BZ) | en el eje de las dos calles | bajar o subir la tapa |
| Poste en la cuneta | EJE-01 0+150 a +3.95 m | ERROR: reubicar |
| Árbol en vereda | EJE-01 0+230 | paso libre de 0.85 m, ERROR |
| Hondonada | EJE-02 0+165 a 0+185 | relleno |
| BM1 a BM3 | junto a fachadas | numerados y ubicados por progresiva |
