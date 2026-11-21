# Verificación a mano (datos de ejemplo)

Cada cálculo de la app se comprobó a mano con 2 o 3 puntos. Las pruebas automáticas
(`python -m pytest`) repiten estas mismas cuentas cada vez que se cambia el código.
Datos: `datos_ejemplo/`. Resultado: **53 de 53 pruebas correctas** (18 con estas cuentas a mano y 35 con los levantamientos
de `escenarios/` comparados contra Civil 3D 2025, ver `docs/PRUEBAS_CIVIL3D.md`).

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

BM-01 = 3821.321 y lectura atrás = 1.425, así que AI = **3822.746**.
Losa en el eje, 0+050: 3822.746 − 3821.250 = **1.496**.
Base en el eje: 3822.746 − 3821.090 = **1.656**. La app da los mismos valores (hoja *Capas* del Excel).

## 6. Puerta enterrada PU-02 (EJE-01 izquierda, 0+085)

rasante 3821.775 → borde 3821.703 → sardinel 3821.853 → vereda en fachada 3821.853 + 0.02 × 1.50 = **3821.883**.
Umbral 3821.803 − 3821.883 = **−0.080 m**, o sea que queda enterrada. La app también da −0.080.

## 7. Área de corte, EJE-01 0+050 (cuenta gruesa con 7 puntos)

| Tramo (m) | Terreno − subrasante en los extremos | Ancho | Área |
|---|---|---|---|
| −5.30 → −4.15 (vereda) | 3821.649 − 3821.151 = 0.498 ; 3821.649 − 3821.128 = 0.521 | 1.15 | 0.586 |
| −4.15 → −2.00 | 3821.649 − 3820.507 = 1.142 ; 3821.648 − 3820.550 = 1.098 | 2.15 | 2.408 |
| −2.00 → 0.00 | 1.098 ; 3821.623 − 3820.590 = 1.033 | 2.00 | 2.131 |
| 0.00 → 2.00 | 1.033 ; 3821.599 − 3820.550 = 1.049 | 2.00 | 2.082 |
| 2.00 → 4.15 | 1.049 ; 3821.553 − 3820.507 = 1.046 | 2.15 | 2.252 |
| 4.15 → 5.65 (vereda) | 3821.553 − 3821.128 = 0.425 ; 3821.518 − 3821.158 = 0.360 | 1.50 | 0.589 |
| **Total a mano** | | | **10.048 m²** |

La app da **10.053 m²** porque mide el terreno cada 10 cm. La diferencia es de 0.05 %.

**Volumen 0+050 → 0+060** por área media: (10.053 + 9.694) / 2 × 10 = **98.74 m³**. La app da 98.74.

## 8. Material por capa

- **Losa:** 7.20 × 0.16 = 1.152 m² por metro.
  - EJE-01: 250 m × 1.152 = **288.00 m³**. App: 288.00.
  - EJE-02: se descuentan los 8.30 m que quedan dentro de la calzada del EJE-01 (4.15 m a cada lado), así que (200 − 8.30) × 1.152 = **220.84 m³**. App: 220.84.
- **Base (EJE-01):** 8.30 m × 0.15 = 1.245 m² por metro, porque va también bajo la cuneta y el sardinel. Entonces 250 × 1.245 = 311.25. Hay que restar 1.37 m³: dentro del cruce la base solo ocupa la calzada, (8.30 − 7.20) × 0.15 × 8.30 = 1.37. Resultado: **309.88 m³**. App: 309.88.

## 9. Comparación de volúmenes por dos métodos

| Calle | Área media (app) | Entre superficies TN − subrasante, calculado por Civil 3D | Diferencia |
|---|---|---|---|
| EJE-01 | 2306.15 m³ | 2308.19 m³ (Civil 3D 2025) | 0.09 % |
| EJE-02 | 1465.53 m³ | 1465.90 m³ (Civil 3D 2025) | 0.03 % |

En la hondonada de EJE-02 la app agrega secciones intermedias (cada 5 y 2.5 m) porque el relleno
cambia rápido entre secciones. Con secciones solo cada 10 m el relleno salía 59.53 m³, 16 % más que
los 51.17 m³ de Civil 3D; ahora sale 51.52 m³ (+0.7 %).
