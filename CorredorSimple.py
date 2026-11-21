"""Punto de entrada de Corredor Simple.

  python CorredorSimple.py                       -> abre la ventana
  python CorredorSimple.py <carpeta_proyecto>    -> abre la ventana con ese proyecto
  python CorredorSimple.py calcular <carpeta_proyecto> <carpeta_salida> [BM lectura_atras]
                                                 -> calcula y exporta sin ventana
  python CorredorSimple.py civil3d <carpeta_proyecto> [archivo.dwg]
                                                 -> arma el modelo en Civil 3D y lo abre
"""
import sys


def consola(args):
    from corredor.datos import leer_proyecto, validar_proyecto
    from corredor.exportar import altura_instrumento, exportar_todo
    from corredor.motor import calcular

    proy = leer_proyecto(args[0])
    err = validar_proyecto(proy)
    if err:
        print("\n".join(err))
        return 1
    res = calcular(proy)
    ai = altura_instrumento(proy, args[2], float(args[3])) if len(args) >= 4 else None
    for a in res.avisos:
        print(a.texto())
    for k, rc in res.calles.items():
        print(f"{k}: corte {rc.vol_corte:.2f} m3, relleno {rc.vol_relleno:.2f} m3, neto {rc.vol_neto:.2f} m3")
    for f in exportar_todo(res, args[1], ai):
        print("  ->", f)
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "calcular":
        sys.exit(consola(sys.argv[2:]))
    if len(sys.argv) > 2 and sys.argv[1] == "civil3d":
        from corredor.civil3d import generar_y_abrir
        dwg, mensajes, como = generar_y_abrir(sys.argv[2], sys.argv[3] if len(sys.argv) > 3 else None)
        print("\n".join(mensajes))
        print(f"-> {dwg} ({como})")
        sys.exit(0)
    from corredor.app import main
    main()
