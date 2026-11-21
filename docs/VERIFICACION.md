# Verificación a mano (datos de ejemplo)

Cada cálculo de la app se comprobó a mano con 2 o 3 puntos. Las pruebas automáticas
(`python -m pytest`) repiten estas mismas cuentas cada vez que se cambia el código.
Datos: `datos_ejemplo/`. Resultado: **23 de 23 pruebas correctas**.

## 1. Coordenadas: borde derecho de calzada, EJE-01 0+050

El eje empieza en E = 390100.000, N = 8250300.000 con azimut 80°.
sen 80° = 0.98481 y cos 80° = 0.17365. Desplazamiento a la derecha: o = +3.60.

| | Fórmula | Resultado | App |
|---|---|---|---|
| Este | 390100 + 50 × 0.98481 + 3.60 × 0.17365 | **390149.866** | 390149.866 |
| Norte | 8250300 + 50 × 0.17365 − 3.60 × 0.98481 | **8250305.137** | 8250305.137 |

## 2. Cota de rasante

| Progresiva | Cuenta | Resultado | App |
|---|---|---|---|
| EJE-01 0+050 | 3820.500 + 0.015 × 50 | **3821.250** | 3821.250 |
| EJE-01 0+200 | 3822.300 − 0.008 × (200 − 120) | **3821.660** | 3821.660 |
| EJE-02 0+100 (cruce) | 3821.020 + 0.012 × 100 | **3822.220** | 3822.220 (igual a EJE-01 0+130 ✔) |

## 3. Puntos de la sección EJE-01 0+050

| Punto | Cuenta | Cota | App |
|---|---|---|---|
| EJE | rasante | 3821.250 | 3821.250 |
| BCD borde de calzada (3.60 m) | 3821.250 − 0.02 × 3.60 | 3821.178 | 3821.178 |
| FCD fondo de cuneta (3.80 m) | 3821.178 − 0.10 | 3821.078 | 3821.078 |
| CSD cabeza de sardinel (4.00 m) | 3821.178 + 0.15 | 3821.328 | 3821.328 |
| BVD borde interior de vereda (4.15 m) | igual a CSD | 3821.328 | 3821.328 |
| PFD pie de fachada (5.65 m) | 3821.328 + 0.02 × 1.50 | 3821.358 | 3821.358 |
| PFI (izquierda, hay un muro a 5.30 m) | vereda 5.30 − 4.15 = 1.15 m → 3821.328 + 0.02 × 1.15 | 3821.351 | 3821.351 |

## 4. Capas hacia abajo (eje, 0+050)

| Superficie | Cuenta | Cota | App |
|---|---|---|---|
| Tope de la losa | rasante | 3821.250 | 3821.250 |
| Tope de la base | 3821.250 − 0.16 | 3821.090 | 3821.090 |
| Tope de la subbase | 3821.090 − 0.15 | 3820.940 | 3820.940 |
| Tope del mejoramiento | 3820.940 − 0.15 | 3820.790 | 3820.790 |
| Subrasante (fondo de excavación) | 3820.790 − 0.20 | 3820.590 | 3820.590 |

## 5. Lectura de mira

BM-01 (punto 1 del levantamiento) = 3821.012 y lectura atrás = 1.425, así que AI = **3822.437**.
Losa en el eje, 0+050: 3822.437 − 3821.250 = **1.187**.
Base en el eje: 3822.437 − 3821.090 = **1.347**. La app da los mismos valores (pestaña *7 · Puntos y BM*).

## 6. Puerta enterrada (EJE-01 izquierda, 0+085, punto PU)

rasante 3821.775 → borde 3821.703 → sardinel 3821.853 → vereda en fachada 3821.853 + 0.02 × 1.50 = **3821.883**.
Umbral 3821.803 − 3821.883 = **−0.080 m**, o sea que queda enterrada. La app también da −0.080 y propone bajar la
vereda frente a la puerta a 3821.783.

## 7. Área de corte, EJE-01 0+050 (cuenta gruesa con 7 puntos)

| Tramo (m) | Terreno − subrasante en los extremos | Ancho | Área |
|---|---|---|---|
| −5.30 → −4.15 (vereda) | 3821.659 − 3821.151 = 0.508 ; 3821.644 − 3821.128 = 0.516 | 1.15 | 0.589 |
| −4.15 → −2.00 | 3821.644 − 3820.507 = 1.137 ; 3821.617 − 3820.550 = 1.067 | 2.15 | 2.369 |
| −2.00 → 0.00 | 1.067 ; 3821.591 − 3820.590 = 1.001 | 2.00 | 2.068 |
| 0.00 → 2.00 | 1.001 ; 3821.566 − 3820.550 = 1.016 | 2.00 | 2.017 |
| 2.00 → 4.15 | 1.016 ; 3821.538 − 3820.507 = 1.031 | 2.15 | 2.201 |
| 4.15 → 5.65 (vereda) | 3821.538 − 3821.128 = 0.410 ; 3821.519 − 3821.158 = 0.361 | 1.50 | 0.578 |
| **Total a mano** | | | **9.822 m²** |

La app da **9.824 m²** porque mide el terreno cada 10 cm. La diferencia es de 0.02 %.

**Volumen 0+050 → 0+060** por área media: (9.824 + 9.934) / 2 × 10 = **98.79 m³**. La app da 98.79.

## 8. Material por capa

- **Losa:** 7.20 × 0.16 = 1.152 m² por metro.
  - EJE-01: 250 m × 1.152 = **288.00 m³**. App: 288.00.
  - EJE-02: se descuentan los 8.30 m que quedan dentro de la calzada del EJE-01 (4.15 m a cada lado), así que (200 − 8.30) × 1.152 = **220.84 m³**. App: 220.84.
- **Base (EJE-01):** 8.30 m × 0.15 = 1.245 m² por metro, porque va también bajo la cuneta y el sardinel. Entonces 250 × 1.245 = 311.25. Hay que restar 1.37 m³: dentro del cruce la base solo ocupa la calzada, (8.30 − 7.20) × 0.15 × 8.30 = 1.37. Resultado: **309.88 m³**. App: 309.88.

## 9. Comparación de volúmenes por dos métodos

| Calle | Área media (app) | Entre superficies TN − subrasante (como Civil 3D) | Diferencia |
|---|---|---|---|
| EJE-01 | 2267.92 m³ | 2286.55 m³ | 0.8 % |
| EJE-02 | 1475.49 m³ | 1476.36 m³ | 0.06 % |

## 10. Balance de tierras (EJE-02)

- Eliminación = corte × (1 + esponjamiento) = 1475.49 × 1.25 = **1844.36 m³** (app 1844.36).
- Préstamo = relleno × (1 + contracción) = 78.60 × 1.15 = **90.39 m³** (app 90.39).

## 11. Interferencias (ejemplos)

| Elemento | Cuenta | Resultado |
|---|---|---|
| Buzón EJE-01 0+060, en el eje | diseño = rasante 3820.500 + 0.015 × 60 = 3821.400; tapa 3821.762 | bajar la tapa 0.362 m |
| Poste EJE-01 0+150 a +3.95 m | 3.80 < 3.95 ≤ 4.00 → cuneta | ERROR: reubicar |
| Árbol EJE-01 0+230 a +4.80 m | vereda de 4.15 a 5.65: libre = máx(4.80 − 4.15, 5.65 − 4.80) = 0.85 < 0.90 | ERROR: paso libre insuficiente |
| Cochera EJE-01 0+170 | umbral promedio 3822.033 − vereda 3822.008 = +0.025; sardinel rebajado 3821.858; rampa (3822.033 − 3821.858) / 1.63 = 10.7 % | AVISO: rebajar sardinel |
