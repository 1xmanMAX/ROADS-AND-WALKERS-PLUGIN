# Corredor Simple en Civil 3D 2025

## 1. Instalar el complemento (una sola vez)

1. Copia la carpeta `civil3d` del proyecto a tu computadora.
2. Doble clic en **`civil3d\instalar_en_civil3d.bat`**. Esto copia `CorredorSimple.bundle` a
   `%APPDATA%\Autodesk\ApplicationPlugins` y Civil 3D lo carga solo al iniciar.
3. Abre Civil 3D 2025 y escribe **`CSAYUDA`**. Debe responder con la lista de comandos.

Si no carga, prueba de forma manual: comando `NETLOAD` y elige
`CorredorSimple.bundle\Contents\CorredorSimpleC3D.dll`. Si Windows bloquea el archivo por venir de
internet: clic derecho en el .dll → *Propiedades* → *Desbloquear*.

## 2. Exportar desde la app

Pestaña **8 · Exportar**, con la opción **Civil 3D 2025: paquete para el complemento** marcada.
Se genera `corredor_civil3d.json` en la carpeta de salida.

## 3. Importar en Civil 3D

Abre un dibujo con la plantilla métrica *_Autodesk Civil 3D (Metric) NCS.dwt* y el sistema de
coordenadas de tu obra. Escribe **`CSIMPORTAR`**, elige el `.json` y responde:

- **Todo** (por defecto)
- **Basico**: sin líneas 3D ni modelo de capas
- **Replanteo**: además, los puntos de replanteo como puntos COGO

| Se crea | Nombre en Civil 3D |
|---|---|
| Puntos COGO del levantamiento, con su código como descripción | Grupos de puntos `CS Terreno`, `CS Fachadas y limites`, `CS Puertas y cocheras`, `CS Elementos (buzones, postes...)`, `CS BM` |
| Superficie del terreno | `CS TN Terreno existente` |
| Superficies de diseño por calle | `CS EJE-xx TERMINADO`, `CS EJE-xx SUBRASANTE`, `CS EJE-xx FONDO C1…C4` |
| Alineamientos (con la progresiva inicial) | `EJE-xx Nombre de la calle` |
| Perfil de rasante (PVI de la app) y perfil del terreno | `EJE-xx Rasante`, `EJE-xx Terreno` |
| Vistas de perfil | a la derecha de la obra |
| Líneas características 3D (bordes, cuneta, sardinel, vereda, subrasante) | capas `CS-LF-*` |
| Fachadas, muros y límites | capas `CS-FACHADA-CA/MU/LP` |
| Modelo 3D de calzada, cuneta, sardinel, vereda y cada capa | capas `CS-3D-*` |
| Interferencias con su estado y qué hacer | capas `CS-INTERF-ERROR/AVISO/INFO` |
| BM con cota y ubicación | capa `CS-BM` |

`CSRESUMEN` muestra en la línea de comandos los volúmenes, las interferencias y los BM del archivo.

Desde ahí puedes seguir trabajando como siempre: etiquetas, líneas de muestreo, tablas de volúmenes,
vistas de sección y planos.

## 4. Qué comparar (app frente a Civil 3D)

| # | Qué | En Civil 3D | En la app | Diferencia aceptable |
|---|---|---|---|---|
| 1 | Coordenadas del eje cada 10 m | Informe de estacas del alineamiento | pestaña 7 / CSV del eje | ± 0.002 m |
| 2 | Cota de rasante en los PVI | Vista de perfil | pestaña 2 | ± 0.001 m |
| 3 | Cotas de los puntos de la sección | Etiqueta de cota sobre `CS EJE-xx TERMINADO` | pestaña 4 (ficha) | ± 0.002 m |
| 4 | Volumen de corte | *Volumes Dashboard*: `CS TN` frente a `CS EJE-xx SUBRASANTE` | pestaña 6 | ± 2 % |
| 5 | Volumen de losa | `TERMINADO` frente a `FONDO C1` | pestaña 6 (partidas) | ± 1 % |

La app calcula por **área media**. Civil 3D calcula entre superficies. En el ejemplo la diferencia
es de 0.1 a 0.8 % (ver `docs/VERIFICACION.md`).

## 5. Sin complemento (alternativa)

También puedes exportar **LandXML**: en Civil 3D, *Insertar → LandXML* importa alineamientos, perfiles
y superficies. El **DXF** trae el 3D y las hojas de secciones y perfil.

## 6. Recompilar el complemento

Necesitas el .NET 8 SDK. Haz doble clic en `civil3d\compilar_complemento.bat`. Las referencias
oficiales de Autodesk (AutoCAD.NET 25 y Civil3D.NET 13.7) se descargan de NuGet.

**Estado:** el complemento compila sin errores contra la API de Civil 3D 2025 y lee el paquete de
ejemplo. Falta probarlo dentro de Civil 3D, lo que se hará en tu computadora.
